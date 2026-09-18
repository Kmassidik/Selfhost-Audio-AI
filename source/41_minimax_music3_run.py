#!/usr/bin/env python3
"""MiniMax-Music3 on one 8 GB card, the language model streamed from system RAM.

The exact recipe from the model card's "Low VRAM" section, which is the same
apply_group_offloading call the first sibling project used on this box for
MiniMax-H3's 32B text encoder. Card 0 only, so the memory figure is clean.

    CUDA_VISIBLE_DEVICES=0 engines/minimax-py/.venv/bin/python source/41_minimax_music3_run.py
"""
import json, os, sys, threading, time, subprocess, traceback
import torch, soundfile as sf
from diffusers import ComponentsManager, ModularPipeline
from diffusers.hooks import apply_group_offloading

R = os.environ["SELFHOSTAUDIO_ROOT"]
W = f"{R}/models/hf/MiniMax-Music3"
OUT = f"{R}/runs/l12-mm3-py"; os.makedirs(OUT, exist_ok=True)
SECS = float(os.environ.get("MM3_SECONDS", "30"))

peak = {"gpu": 0, "rss": 0}; stop = [False]
def sample():
    while not stop[0]:
        try:
            g = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits",
                                "-i", "0"], capture_output=True, text=True, timeout=5).stdout.strip()
            peak["gpu"] = max(peak["gpu"], int(g))
            rss = int(open(f"/proc/{os.getpid()}/status").read().split("VmRSS:")[1].split()[0]) // 1024
            peak["rss"] = max(peak["rss"], rss)
        except Exception:
            pass
        time.sleep(0.25)
threading.Thread(target=sample, daemon=True).start()

T = {}; stage = "load"
try:
    t0 = time.time()
    manager = ComponentsManager()
    manager.enable_auto_cpu_offload(device="cuda")
    pipe = ModularPipeline.from_pretrained(W, components_manager=manager)
    pipe.load_components(dtype=torch.bfloat16)
    apply_group_offloading(pipe.language_model, onload_device=torch.device("cuda"),
                           offload_type="leaf_level", use_stream=True)
    T["load_s"] = round(time.time() - t0, 1)
    print(f"loaded in {T['load_s']} s · peak card {peak['gpu']} MiB · rss {peak['rss']} MiB", flush=True)

    stage = "generate"
    lyrics = ("[verse]\nSoft morning light is touching the window\nI hear the city waking below\n"
              "[chorus]\nStay with the rhythm, let it carry us home\nSing with the sunrise, we are never alone")
    prompt = ("Genre: indie pop. BPM: 104. Key: G major. Bright and warm. Vocals: warm lead vocal. "
              "Arrangement: bright acoustic guitar, soft drums, polished demo mix.")
    t0 = time.time()
    audio = pipe(prompt=prompt, lyrics=lyrics, audio_duration=SECS,
                 generator=torch.Generator("cuda").manual_seed(20260915), output="audios")[0]
    T["generate_s"] = round(time.time() - t0, 1)
    wav = f"{OUT}/song-{int(SECS)}s.wav"
    # the pipeline may hand back a torch tensor or a numpy array; accept both.
    # (First run lost a finished 526 s generation to assuming a tensor.)
    import numpy as np
    a = audio.float().cpu().numpy() if hasattr(audio, "cpu") else np.asarray(audio)
    if a.ndim == 2 and a.shape[0] < a.shape[1]:
        a = a.T                               # (channels, samples) -> (samples, channels)
    sf.write(wav, a, pipe.sampling_rate)
    dur = a.shape[0] / pipe.sampling_rate
    res = {"ok": True, "audio_s": round(dur, 2), "sample_rate": pipe.sampling_rate,
           "channels": int(a.shape[1]) if a.ndim == 2 else 1,
           "rtf": round(T["generate_s"] / dur, 2), **T,
           "peak_card_mib": peak["gpu"], "peak_rss_mib": peak["rss"], "file": wav}
except Exception as e:
    res = {"ok": False, "stage": stage, "error": f"{type(e).__name__}: {str(e)[:300]}",
           "trace": traceback.format_exc().splitlines()[-6:], **T,
           "peak_card_mib": peak["gpu"], "peak_rss_mib": peak["rss"]}
stop[0] = True
json.dump(res, open(f"{OUT}/result-{int(SECS)}s.json", "w"), indent=2)
print(json.dumps(res, indent=2), flush=True)
