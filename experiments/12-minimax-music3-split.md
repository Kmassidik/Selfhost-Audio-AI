# MiniMax-Music3 split across three cards, no streaming

*Lab notebook, 2026-09-18. The prediction half, committed before anything ran.*

## Why this exists

Experiment 11 made it run on one card by streaming the 16 GiB language model
from RAM, **once per audio frame**, at RTF ~52. The box has three cards. Question
asked directly: can it be divided into 3?

## Sizes, measured from the weight files (bf16 in memory)

| Component | Params | GiB | Used in |
|---|---|---|---|
| language_model (Qwen3, 36 layers) | 8.58 B | 15.99 | stage 1, every frame |
| rvq_depth_decoder | 0.65 B | 1.20 | stage 1, every frame |
| transformer (flow matching) | 2.43 B | 4.53 | stage 2 |
| vocoder | 0.05 B | 0.10 | stage 3 |
| condition_encoder | 0.03 B | 0.05 | stage 2 |

Sum 21.9 GiB. The cards together hold 22.97 GiB before three CUDA contexts and
the growing KV cache. **Not everything fits at once, and it does not need to**: the
stages run one after another.

## Layout — `source/43_minimax_music3_split.py`

- **Stage 1 (the language model writes the song, frame by frame):** layers split
  6 / 15 / 15 across cards 0/1/2. Embedding, output head, final norm and depth
  decoder on card 0. The loop calls those directly and mixes their outputs
  with tensors on the pipeline's device, so they must sit together.
  Card 0 ≈ 4.9 GiB, cards 1–2 ≈ 5.4 GiB each, plus cache.
- **Swap:** on the first call of the condition encoder, the language model and
  depth decoder go back to RAM and the transformer moves to card 0.
- **Stage 2–3:** flow transformer and vocoder on card 0.

This is pipeline placement, not tensor parallelism. The cards take turns inside one
frame, so **one card works at a time**. What the split removes is the bus: the
weights are read from card memory at 448 GB/s instead of RAM over PCIe.

## Predictions — written before running

> **1 · It fits.** Peak under 7 GB on every card. Moderate-high confidence. The risk
> is card 0 in stage 2 (4.5 GiB transformer plus activations), not stage 1.
>
> **2 · Stage 1 speeds up by an order of magnitude or more.** Per frame, all 16 GiB
> are read once at 448 GB/s, 38 ms at the limit. At a realistic ~60% of it, plus
> the depth decoder's 7 small steps and the Python loop, that makes **~100 ms per
> frame, so stage 1 at RTF ~2.5**. Range 1–8. Low confidence on the
> overhead term.
>
> **3 · Whole song: RTF ~4, range 1.5–12.** Stage 2 is unmeasured anywhere yet;
> guessed at under 1× real time. Swap ≈ 16 GiB card→RAM, a few seconds.
>
> **4 · Same seed, same card type, same kernels: the 10 s song is bit-identical to
> experiment 11's.** Moderate confidence. The first sibling found a layer split
> bit-identical to one card. A mismatch would most likely come from stage 2 (the
> transformer ran under a different offload hook), not from the split.

## Results — measured 2026-09-18, `source/43_minimax_music3_split.py`

| Asked for | Got | Load | Stage 1 (LM) | Swap | Stage 2+3 | Total | **RTF** | Peak cards 0/1/2 (MiB) | Peak RSS |
|---|---|---|---|---|---|---|---|---|---|
| 10 s (swap = copy to RAM) | 10.0 s | 19.4 s | 46.5 s | 22.1 s | 16.4 s | 85.1 s | **8.51** | 7,033 / 5,847 / 5,847 | 24.2 GB |
| 30 s (swap = drop) | 30.02 s | 25.1 s | 137.7 s | 4.2 s | 61.0 s | 202.9 s | **6.76** | 7,071 / 5,887 / 5,887 | 10.8 GB |
| 180 s (swap = drop) | **60.67 s** | 11.6 s | 275.9 s | 3.9 s | 131.8 s | 411.6 s | **6.78** | 7,201 / 6,047 / 6,047 | 10.8 GB |

The 180 s request came back at 60.7 s. **The model ended the song itself**, because the
lyrics are two sections long. The duration is an upper bound (the pipeline says
so), not a target.

First try failed after stage 1, making noise on "cpu" with a CUDA generator:
without a ComponentsManager the pipeline infers its device from its first
component. Fixed by pinning `_execution_device` to cuda:0
(`result-10s-cpudevice.json`).

### Scored against the predictions

| # | Predicted | Measured | Verdict |
|---|---|---|---|
| 1 | Fits, every card under 7 GB | fits; cards 1–2 at 5.9–6.0 GB, **card 0 at 7,071–7,201 MiB** | fits: **right**. The margin on card 0: **wrong** |
| 2 | Stage 1 RTF ~2.5, range 1–8 | **4.55–4.65** | inside the range, 84% slower than the point |
| 3 | Whole song RTF ~4, range 1.5–12 | **6.76–6.78** (10 s: 8.51 with the slow swap) | inside the range; stage 2 guessed under 1× and measured **~2.1×**: wrong |
| 4 | Bit-identical to experiment 11 | `cmp` identical, **10 s and 30 s** | **right** |

**Headline: 7.6× faster than streaming, byte-for-byte the same song, a quarter of
the RAM.** 30 s of music went from 25.8 minutes to 3.4.

### What the numbers say

- **Stage 1 is CPU-bound, not bandwidth-bound.** 184 ms per 25 Hz frame against the
  38 ms that reading 16 GiB at 448 GB/s would take. While it ran, one Python thread
  sat at 100% and each card at ~8% busy. The old Xeon launching thousands of
  small kernels per frame is now the wall. The obvious next lever is capturing
  the per-frame work as a CUDA graph, which is **untested**.
- **The swap was the cheapest win.** Copying 16 GiB back to pageable RAM took 22.1 s.
  Dropping it, since a one-song process never needs it again, took 3.9–4.2 s.
- **RTF is flat from 10 s to 60 s** (6.76 → 6.78), so the cost is linear in frames, as
  in experiment 11.
- **Card 0 grows with length**: 7,071 MiB at 30 s, 7,201 MiB at 60.7 s, about 130
  MiB per 30 s. Against 7,840 usable, that extrapolates to about **3.5 minutes of
  song before card 0 runs out. This is an estimate, not tested.** The fix, if needed,
  is moving layers off card 0 (split 4/16/16).

Outputs on the box: `runs/l12-mm3-split/song-{10,30,180}s.wav`, `result-*.json`.
