#!/usr/bin/env python3
"""One MiniMax-Music3 generation, for the studio. Same layout as 43 (experiment
12, 13): the language model split 4/16/16 across all three cards, then swapped out
for the flow transformer on card 0. Parameters come from the command line; the
only output is the WAV.

  python 42_minimax_music3_job.py --prompt ... --lyrics ... --seconds 30 --seed 1 --out x.wav
Run with HF_HUB_OFFLINE=1 and all three cards visible. The studio gives it the
cards exclusively. The fallback (--stream) is 41's one-card recipe: RAM
streaming at RTF ~52.
"""
import argparse, os
import numpy as np, soundfile as sf, torch
from diffusers import ModularPipeline

ap = argparse.ArgumentParser()
ap.add_argument("--prompt", required=True); ap.add_argument("--lyrics", required=True)
ap.add_argument("--seconds", type=float, default=30); ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--out", required=True)
ap.add_argument("--stream", action="store_true", help="one card, language model streamed from RAM")
a = ap.parse_args()
W = os.path.join(os.environ["SELFHOSTAUDIO_ROOT"], "models", "hf", "MiniMax-Music3")

if a.stream:
    from diffusers import ComponentsManager
    from diffusers.hooks import apply_group_offloading
    manager = ComponentsManager(); manager.enable_auto_cpu_offload(device="cuda:0")
    pipe = ModularPipeline.from_pretrained(W, components_manager=manager)
    pipe.load_components(dtype=torch.bfloat16)
    apply_group_offloading(pipe.language_model, onload_device=torch.device("cuda:0"),
                           offload_type="leaf_level", use_stream=True)
else:
    from accelerate import dispatch_model
    from accelerate.hooks import remove_hook_from_module
    pipe = ModularPipeline.from_pretrained(W)
    pipe.load_components(dtype=torch.bfloat16)
    lm, rvq = pipe.language_model, pipe.rvq_depth_decoder
    dm = {"model.embed_tokens": 0, "model.rotary_emb": 0, "model.norm": 0, "lm_head": 0}
    # 4/16/16, not 6/15/15: card 0 also holds the per-frame states the pipeline joins at the
    # end, and a 3.6-minute song ran it out of memory at 6/15/15 (experiment 13a)
    dm.update({f"model.layers.{i}": 0 if i < 4 else 1 if i < 20 else 2 for i in range(36)})
    dispatch_model(lm, device_map=dm, main_device="cuda:0")
    rvq.to("cuda:0"); pipe.condition_encoder.to("cuda:0"); pipe.vocoder.to("cuda:0")
    done = []
    def swap(module, args):
        if done:
            return
        done.append(1)
        remove_hook_from_module(lm, recurse=True)
        lm.to("meta"); rvq.to("meta")   # drop, not copy back: 16 GiB card->RAM cost 22 s (exp. 12)
        for i in range(3):
            with torch.cuda.device(i):
                torch.cuda.empty_cache()
        pipe.transformer.to("cuda:0")
    pipe.condition_encoder.register_forward_pre_hook(swap)
    type(pipe)._execution_device = property(lambda self: torch.device("cuda:0"))

audio = pipe(prompt=a.prompt, lyrics=a.lyrics, audio_duration=a.seconds,
             generator=torch.Generator("cuda:0").manual_seed(a.seed), output="audios")[0]
x = audio.float().cpu().numpy() if hasattr(audio, "cpu") else np.asarray(audio)
if x.ndim == 2 and x.shape[0] < x.shape[1]:
    x = x.T
sf.write(a.out, x, pipe.sampling_rate)
