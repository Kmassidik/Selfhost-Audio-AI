# MiniMax-Music3, streamed from RAM — the route the engine could not take

*Lab notebook, 2026-09-18. The prediction half, committed before anything ran.*

## Why this exists

`experiments/10`: MiniMax-Music3 does not fit through audio.cpp — its 8B language
model alone fills the card, and the engine has no layer split or offload. The
model's own Python pipeline has one: `apply_group_offloading(..., "leaf_level",
use_stream=True)` keeps the language model in system RAM and moves one layer at a
time onto the card. **The first sibling project already used that exact call on
this box**, on MiniMax-H3's 32B text encoder — so the technique is proven here,
on a model five times this one's size.

This runs outside audio.cpp, in its own environment mirroring the sibling's
proven package set (torch 2.11 + cu128, diffusers dev). **Its numbers are not
comparable with the audio.cpp measurements in the guide** — a different stack is
a different measurement. They answer a different question: can it run at all.

## Predictions — written before running

> **1 · It fits.** The authors say so and the sibling proved the mechanism.
> Moderate confidence. The risk is not the language model but the *other* large
> components: the flow transformer and its VAE are several GB each in bf16, and
> `enable_auto_cpu_offload` moves whole components onto the card when used. If it
> fails, expect it there, and the fix is the same one-line offload applied to them.
>
> **2 · Peak card memory stays well under 8 GB during the language-model stage**
> — one layer resident at a time — and the peak is set by a later stage.
>
> **3 · It is slow, and the speed is set by the bus, not the card.** The language
> model is ~16 GB in bf16, and every generated frame streams all of it across the
> PCIe bus once. At the sibling-measured 23.4 GB/s of host RAM and a PCIe 3.0 link
> of roughly 12 GB/s (**estimate**, not measured here), that is ~1.3 s per frame.
> At 25 frames a second, 30 s of music is ~750 frames: **~17 minutes, a real-time
> factor around 35 — range 15 to 60.** Low confidence; this is the number most
> likely to be wrong, and the most informative if it is.

## Results — measured 2026-09-18, card 0, `source/41_minimax_music3_run.py`

| Run | Audio | Load | Generate | RTF | Peak card | Peak RAM (RSS) |
|---|---|---|---|---|---|---|
| 10 s, first try | — | 60.7 s | 526.3 s | — | 5,297 MiB | 39,336 MiB |
| 10 s | 10.0 s stereo 44.1 kHz | 74.3 s | 522.8 s | **52.3** | 5,297 MiB | 42,746 MiB |
| 30 s | 30.02 s stereo 44.1 kHz | 29.8 s | 1,545.6 s | **51.5** | 5,325 MiB | 42,891 MiB |

The first try generated a song, then lost it: the save line assumed a torch tensor
and the pipeline returned a numpy array (`result-10s-lostsave.json`). The fix
accepts both. **Save paths get tested on a one-second run before a ten-minute one.**

**Prediction 1, it fits: right.** 5.3 GB of 7.8 on the card, where audio.cpp died at
6.4 GB (experiment 10).

**Prediction 2, well under 8 GB: right**, but the stage that sets the peak was not
separated. That split is measured in experiment 12.

**Prediction 3, RTF about 35 (range 15–60): inside the range, 47% slower than the
point estimate.** The cost is ~2.06 s per 25 Hz audio frame against the predicted
1.3 s. Two runs of different length agree within 2%, so **the cost is per frame and
linear**: a 3-minute song would take about 2.6 hours this way.

Where the machine went: RAM held ~43 GB (the whole pipeline in bf16 plus
working copies). The card mostly waited on the bus. Two cards sat idle, and
that is the next experiment.

Outputs: `runs/l12-mm3-py/song-10s.wav`, `song-30s.wav` (on the box).
