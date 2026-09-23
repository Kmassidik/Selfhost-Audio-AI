#!/usr/bin/env python3
"""MusicGen, one job, for the Dalang Music Box worker.

MusicGen is not a family the audio.cpp engine carries, so it runs here the way
MiniMax does: a Python process, this time in the box's own transformers venv.
It is instrumental — the model has no lyrics input at all.

    musicgen_job.py --prompt "..." --seconds 120 --seed 1 --out song.wav
"""
import argparse
import os
import wave

import numpy as np
import torch
from transformers import AutoProcessor, MusicgenForConditionalGeneration

FRAMES_PER_SECOND = 50          # MusicGen's token rate; duration is a token budget


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--seconds", type=float, default=30)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    ap.add_argument("--guidance_scale", type=float, default=3.0)
    ap.add_argument("--temperature", type=float, default=1.0)
    ap.add_argument("--top_k", type=int, default=250)
    ap.add_argument("--model", default=os.environ.get("MUSICGEN_MODEL",
                   "/root/Desktop/selfhostaudioai/models/hf/musicgen-medium"))
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    model = MusicgenForConditionalGeneration.from_pretrained(
        args.model, torch_dtype=torch.float16).to("cuda")
    processor = AutoProcessor.from_pretrained(args.model)

    inputs = processor(text=[args.prompt], padding=True, return_tensors="pt").to("cuda")
    tokens = max(64, int(args.seconds * FRAMES_PER_SECOND))
    with torch.no_grad():
        audio = model.generate(
            **inputs,
            do_sample=True,
            guidance_scale=args.guidance_scale,
            temperature=args.temperature,
            top_k=args.top_k if args.top_k > 0 else None,
            max_new_tokens=tokens,
        )

    sample_rate = model.config.audio_encoder.sampling_rate
    samples = audio[0, 0].to(torch.float32).cpu().numpy()
    peak = float(np.max(np.abs(samples))) or 1.0
    pcm = (samples / peak * 0.97 * 32767).astype("<i2")

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with wave.open(args.out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    print("wrote %s · %.1f s at %d Hz" % (args.out, len(pcm) / sample_rate, sample_rate))


if __name__ == "__main__":
    main()
