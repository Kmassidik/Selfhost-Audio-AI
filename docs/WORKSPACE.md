# selfhostaudioai — BOX WORKSPACE

**Nothing here exists yet.** This file is the layout the box side *will* have,
written before anything is created so the shape is decided once rather than
drifting into place. It is the contract `sync.sh` and every script read.

This is the **runtime** half: weights, compiled engines, virtualenvs, generated
audio. The **source** half lives on the Mac and is the git repository.

    Mac  ~/Desktop/selfhostaudioai      source of truth, git
    Box  /root/Desktop/selfhostaudioai  models + builds + runs, never in git

Paths come from `$SELFHOSTAUDIO_ROOT` (default: this directory), never from a
literal. `selfhostgenai` hardcoded `/root/Desktop/selfhosted-minimaxi-h3` into
roughly 25 files and flagged it in its own README as the reason nobody else
could clone it. `selfhostllm` fixed that for its Python and then hardcoded the
path again in its two fetch scripts. **The rule only holds if it holds everywhere.**

## Layout

    source/       SYNCED FROM THE MAC — do not edit here, changes are overwritten
    engines/
      audiocpp/   the C++ build. One directory, one backend, rebuilt not reconfigured
    models/
      gguf/       audio.cpp format — what actually runs
      hf/         original safetensors, when a Python reference path is needed
      configs/    architecture only, a few KB — committed to git, cannot run
    bench/
      results/    one JSON per run — the comparison table's only source
    runs/         raw artefacts per run: stdout, nvidia-smi samples, and the audio
    listening/    blind test sessions — the waveforms they reference live in runs/
    scratch/      disposable

## What is here now

    nothing

The first thing to land will be `models/gguf/kokoro-82m-*.gguf` — 0.34 GiB, the
smallest useful thing on the shortlist, chosen because it cannot fail for
interesting reasons.

## Two directories that are not ours

    /root/Desktop/selfhosted-minimaxi-h3/   sibling 1 · 217 GB · DO NOT TOUCH
    /root/Desktop/selfhostllm/              sibling 2 · 131 GB of GGUF
                                            its llama-server currently holds all three cards

## Rules

1. Nothing here is a source of truth except measurements.
2. Every run writes `bench/results/<run-id>.json`. **No JSON, no run.**
3. Never stream a long job over SSH — launch detached, return.
4. `runs/` grows at **11.5 MB per audio-minute**. A single 8-take listening test
   writes ~370 MB. Watch the 431 GB free, and decide a retention policy before
   the first long session, not after the disk fills.
