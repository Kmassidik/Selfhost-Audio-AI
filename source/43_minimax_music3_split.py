#!/usr/bin/env python3
"""MiniMax-Music3 split across all three 8 GB cards: no streaming from RAM.

41 kept the 16 GiB language model in system RAM and pulled every layer across
the PCIe bus once per audio frame (RTF ~52). Here the language model lives on
the cards: 36 layers split 6 / 15 / 15, with embedding, output head, final norm
and the RVQ depth decoder on card 0 (the loop calls those directly and mixes
their outputs with tensors on the pipeline's device, so they must share it).

The pipeline runs its two big stages one after the other, and both do not fit
at once (16 + 1.2 + 4.5 GiB against 23 GiB with three CUDA contexts). So when
the flow stage starts (first call of the condition encoder) the language model
and depth decoder leave the cards and the flow transformer takes card 0.

    engines/minimax-py/.venv/bin/python source/43_minimax_music3_split.py
    MM3_SECONDS=30 MM3_SPLIT=6,15,15 ...
    MM3_LYRICS_FILE=x.txt MM3_PROMPT="..." MM3_TAG=long   (experiment 13)
"""
import json, os, threading, time, subprocess, traceback
import numpy as np
import torch, soundfile as sf
from accelerate import dispatch_model
from accelerate.hooks import remove_hook_from_module
from diffusers import ModularPipeline

R = os.environ["SELFHOSTAUDIO_ROOT"]
W = f"{R}/models/hf/MiniMax-Music3"
OUT = f"{R}/runs/l12-mm3-split"; os.makedirs(OUT, exist_ok=True)
TAG = os.environ.get("MM3_TAG", "")
PROFILE = os.environ.get("MM3_PROFILE") == "1"      # experiment 13b: profile stage 1 only
COMPILE = os.environ.get("MM3_COMPILE") == "1"      # experiment 13b-2: fuse elementwise chains
prof = None
SECS = float(os.environ.get("MM3_SECONDS", "10"))
SPLIT = [int(x) for x in os.environ.get("MM3_SPLIT", "6,15,15").split(",")]
assert sum(SPLIT) == 36 and len(SPLIT) == 3, SPLIT

peak = {"gpu": [0, 0, 0], "rss": 0}; stop = [False]
def sample():
    while not stop[0]:
        try:
            g = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=5).stdout.split()
            for i in range(3):
                peak["gpu"][i] = max(peak["gpu"][i], int(g[i]))
            rss = int(open(f"/proc/{os.getpid()}/status").read().split("VmRSS:")[1].split()[0]) // 1024
            peak["rss"] = max(peak["rss"], rss)
        except Exception:
            pass
        time.sleep(0.25)
threading.Thread(target=sample, daemon=True).start()

def lm_device_map(split):
    dm = {"model.embed_tokens": 0, "model.rotary_emb": 0, "model.norm": 0, "lm_head": 0}
    layer = 0
    for card, n in enumerate(split):
        for _ in range(n):
            dm[f"model.layers.{layer}"] = card; layer += 1
    return dm

T = {}; stage = "load"; marks = {}
try:
    t0 = time.time()
    pipe = ModularPipeline.from_pretrained(W)
    pipe.load_components(dtype=torch.bfloat16)            # everything to system RAM first
    lm, rvq = pipe.language_model, pipe.rvq_depth_decoder
    dispatch_model(lm, device_map=lm_device_map(SPLIT), main_device="cuda:0")
    rvq.to("cuda:0")
    if COMPILE:
        # Compile the parts INSIDE each hooked layer, not the layer itself: accelerate
        # replaces layer.forward with its device-moving wrapper, and the parts below it
        # are plain modules on one card. dynamic=True: the cache grows every frame.
        t_c = time.time()
        import torch._dynamo as dyn
        # First try fell back to eager for most parts: the same code runs on three cards
        # with a growing cache, which needs more variants than the default limit of 8.
        for k in ("recompile_limit", "cache_size_limit"):
            if hasattr(dyn.config, k):
                setattr(dyn.config, k, 128)
        if hasattr(dyn.config, "accumulated_recompile_limit"):
            dyn.config.accumulated_recompile_limit = 4096
        for layer in lm.model.layers:
            for part in (layer.self_attn, layer.mlp, layer.input_layernorm, layer.post_attention_layernorm):
                part.compile(dynamic=True)
        for layer in rvq.layers:
            layer.compile(dynamic=True)
        rvq.norm.compile(dynamic=True)
        T["compile_wrap_s"] = round(time.time() - t_c, 1)
    pipe.condition_encoder.to("cuda:0"); pipe.vocoder.to("cuda:0")   # small; anchor the pipeline on card 0

    def swap(module, args):                                # AR stage is over: hand card 0 to the flow stage
        if "ar_end" in marks:
            return
        marks["ar_end"] = time.time()
        if prof is not None:
            torch.cuda.synchronize(); prof.stop()
        marks["peak_stage1"] = list(peak["gpu"])          # per-stage peaks (experiment 13)
        peak["gpu"] = [0, 0, 0]
        remove_hook_from_module(lm, recurse=True)
        lm.to("meta"); rvq.to("meta")   # drop, not copy back: 16 GiB card->RAM cost 22 s (exp. 12)
        for i in range(3):
            with torch.cuda.device(i):
                torch.cuda.empty_cache()
        pipe.transformer.to("cuda:0")
        marks["swap_end"] = time.time()
    pipe.condition_encoder.register_forward_pre_hook(swap)
    # Steady-state speed: the final norm runs once per frame, so the gaps between its calls
    # are frame times, free of load and compile time. The first 20 frames are warm-up.
    frame_t = []
    lm.model.norm.register_forward_pre_hook(lambda m, a: frame_t.append(time.time()))
    # Without a ComponentsManager the pipeline infers its device from the first component,
    # which lands on "cpu" once the language model's hooks are gone -> first try failed making
    # the flow stage's noise on the CPU with a CUDA generator. Pin it.
    type(pipe)._execution_device = property(lambda self: torch.device("cuda:0"))

    T["load_s"] = round(time.time() - t0, 1)
    print(f"loaded in {T['load_s']} s · cards {peak['gpu']} MiB · rss {peak['rss']} MiB", flush=True)

    stage = "generate"
    # identical to 41: same prompt, lyrics and seed, so the outputs can be compared byte for byte
    lyrics = open(os.environ["MM3_LYRICS_FILE"]).read() if os.environ.get("MM3_LYRICS_FILE") else ("[verse]\nSoft morning light is touching the window\nI hear the city waking below\n"
              "[chorus]\nStay with the rhythm, let it carry us home\nSing with the sunrise, we are never alone")
    prompt = os.environ.get("MM3_PROMPT") or ("Genre: indie pop. BPM: 104. Key: G major. Bright and warm. Vocals: warm lead vocal. "
              "Arrangement: bright acoustic guitar, soft drums, polished demo mix.")
    if PROFILE:
        from torch.profiler import profile, ProfilerActivity
        prof = profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA])
        prof.start()
    t0 = time.time()
    audio = pipe(prompt=prompt, lyrics=lyrics, audio_duration=SECS,
                 generator=torch.Generator("cuda:0").manual_seed(20260915), output="audios")[0]
    t1 = time.time()
    T["generate_s"] = round(t1 - t0, 1)
    T["ar_s"] = round(marks["ar_end"] - t0, 1)
    T["swap_s"] = round(marks["swap_end"] - marks["ar_end"], 1)
    T["flow_and_vocode_s"] = round(t1 - marks["swap_end"], 1)
    gaps = sorted(b - a for a, b in zip(frame_t[20:], frame_t[21:]))
    if gaps:
        T["frame_ms_median"] = round(1000 * gaps[len(gaps) // 2], 1)
        T["stage1_rtf_steady"] = round(gaps[len(gaps) // 2] * 25, 2)
    if prof is not None:
        ev = prof.key_averages()
        kernels = sum(e.count for e in ev if getattr(e, "device_type", None) is not None
                      and str(e.device_type).endswith("CUDA"))
        launches = sum(e.count for e in ev if e.key in ("cudaLaunchKernel", "cuLaunchKernel", "cudaLaunchKernelExC"))
        T["profile"] = {"frames": int(SECS * 25) + 1, "cuda_kernels": kernels, "launch_calls": launches,
                        "kernels_per_frame": round(kernels / (int(SECS * 25) + 1), 1),
                        "launches_per_frame": round(launches / (int(SECS * 25) + 1), 1)}
        open(f"{OUT}/profile-{int(SECS)}s{TAG}.txt", "w").write(
            ev.table(sort_by="self_cpu_time_total", row_limit=40))
    wav = f"{OUT}/song-{int(SECS)}s{TAG}.wav"
    a = audio.float().cpu().numpy() if hasattr(audio, "cpu") else np.asarray(audio)
    if a.ndim == 2 and a.shape[0] < a.shape[1]:
        a = a.T
    sf.write(wav, a, pipe.sampling_rate)
    dur = a.shape[0] / pipe.sampling_rate
    res = {"ok": True, "split": SPLIT, "audio_s": round(dur, 2), "sample_rate": pipe.sampling_rate,
           "channels": int(a.shape[1]) if a.ndim == 2 else 1,
           "rtf": round(T["generate_s"] / dur, 2), "ar_rtf": round(T["ar_s"] / dur, 2), **T,
           "peak_card_mib": peak["gpu"], "peak_stage1_mib": marks.get("peak_stage1"),
           "peak_stage2_mib": peak["gpu"], "peak_rss_mib": peak["rss"], "file": wav}
except Exception as e:
    if "ar_end" in marks and "generate_s" not in T:
        T["ar_s"] = round(marks["ar_end"] - t0, 1)
    res = {"ok": False, "stage": stage, "split": SPLIT, "error": f"{type(e).__name__}: {str(e)[:300]}",
           "trace": traceback.format_exc().splitlines()[-8:], **T,
           "peak_card_mib": peak["gpu"], "peak_stage1_mib": marks.get("peak_stage1"),
           "peak_rss_mib": peak["rss"]}
stop[0] = True
json.dump(res, open(f"{OUT}/result-{int(SECS)}s{TAG}.json", "w"), indent=2)
print(json.dumps(res, indent=2), flush=True)
