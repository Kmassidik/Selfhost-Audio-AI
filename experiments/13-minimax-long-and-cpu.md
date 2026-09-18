# MiniMax-Music3: a song past three minutes, and the processor wall

*Lab notebook, 2026-09-18. The prediction half, committed before anything ran.*

Two open items from experiment 12 / chapter 39, in the order the user asked for,
after a first real full-length song (a 2-minute take through the studio,
recorded at the end of this file).

## 13a · Longer than three minutes

Experiment 12 measured card 0 at 7,071 MiB (30 s of song) and 7,201 MiB (60.7 s),
split 6/15/15, and extrapolated a ceiling near 3.5 minutes. That was two points
and a straight line, and **which stage sets card 0's peak was never separated**:
the language model's key-value cache grows with length, and so could stage 2's
working memory.

> **Prediction 1.** A 4-minute ask with lyrics long enough to fill it, split
> 6/15/15: **fails out of memory on card 0**, somewhere after ~3.5 minutes of
> frames. Low confidence: the growth could equally belong to stage 2, whose
> 8-second windows should NOT grow with length, in which case it simply fits.
>
> **Prediction 2.** If it fails, split 4/16/16 moves ~0.7 GiB off card 0 and the
> same song fits, with cards 1–2 peaking under 7 GB.
>
> **Prediction 3.** RTF stays at 6.8 ± 0.3: the cost is linear in frames.

The run records per-card peaks **per stage** (before and after the swap), so the
question of which stage grows is answered whichever way the song ends.

## 13b · The processor wall

Stage 1 costs 184 ms per frame against a 38 ms weight-reading floor, with one
Python thread at 100% and each card ~8% busy. **Where those 184 ms go has not been
measured.** Candidates: kernel launches for ~36 layers + 7 depth-decoder steps
+ sampling; Python overhead in the pipeline's per-frame loop; the Accelerate
hooks that move tensors at each module; the `.item()` sync every frame.

Step one is a profile, not a fix: `py-spy` on a 10 s song, sampling the
Python stack, plus `torch.profiler` for one frame's kernel count.

> **Prediction 4.** The profile shows **most** stage-1 time in PyTorch op
> dispatch and kernel launch (C++ / CUDA launch frames under the model's
> forward), not in the pipeline's own Python loop or the hooks. Moderate
> confidence.
>
> **Prediction 5.** One frame launches **more than 1,500 kernels**. Estimate
> from structure: ~30 per decoder layer × 36, plus 7 depth steps × 4 layers × 30.

The intervention (graph capture or `torch.compile`) is pre-registered only after
the profile says which one addresses the actual cost.

## First full song — measured 2026-09-18, through the studio (split 6/15/15)

| | |
|---|---|
| Job | `runs/studio/20260918-193706-1a896d.wav` — "Stay With the Rhythm" |
| Lyrics | intro, verse, pre-chorus, chorus, verse, chorus, bridge, chorus, outro |
| Asked | 150 s ceiling, seed 20260918 |
| **Got** | **122.15 s**, stereo 44.1 kHz. The model ended the song itself after the outro |
| Wall | 841.2 s (14.0 min), including load |
| **RTF** | **6.89**: flat against 6.76–6.78 at 30–60 s |
| Card 0, sampled every 10 s | peak **≥ 7,479 MiB** during stage 1; ~5,391 MiB during stage 2 |

**The card-0 growth belongs to stage 1**, the language model's key-value cache,
not stage 2: the stage-2 samples sat near 5.4 GB. Three points now: 7,071 (30 s),
7,201 (61 s), ≥7,479 (122 s), about **4.6 MiB per second of song**. With
7,840 usable, the straight line runs out near **200 s (≈3.3 minutes)**. That
makes prediction 1 above sharper, not different: a 4-minute ask at 6/15/15
should fail in stage 1 on card 0.

## 13a result: 4-minute ask at 6/15/15, out of memory (measured 2026-09-18)

`runs/l12-mm3-split/result-300s-long-oom.json`. Lyrics: 14 sections (`long-lyrics.txt`), 300 s ceiling.

- **Stage 1 completed.** The language model wrote every frame. The failure came
  one line later, at `torch.stack(frame_hiddens)`, where the pipeline joins
  the per-frame hidden states into one tensor on card 0: *"Tried to allocate
  340.00 MiB … 198.19 MiB is free"*.
- 340 MiB at 8 codebooks × 4,096 × 2 bytes = 64 KiB per frame is **≈ 5,440 frames,
  ≈ 218 s of song** (derived, not measured). The model wrote about 3.6 minutes
  before stopping.
- **Peaks: 7,835 / 7,803 / 7,803 MiB. All three cards were full**, not just card 0.
  Cards 1–2 went from 5,999 MiB (20:14) to 7,231 (20:25) to 7,803.

| Prediction | Verdict |
|---|---|
| 1 · fails out of memory on card 0 after ~3.5 min of frames | **right on card and length**. Wrong on mechanism: it failed at the final join after stage 1, not during it |
| 2 · 4/16/16 would fix it | **now expected wrong**: cards 1–2 were full too, so moving layers there cannot help |
| 3 · RTF 6.8 | not measurable, since the run failed |

**Why cards 1–2 filled.** Their key-value cache is 15 layers × 2 × 8 heads × 128 ×
2 bytes × batch 2 = 120 KiB per frame, ≈ 650 MiB for 5,440 frames. That explains
~0.7 GB of the ~1.9 GB growth. The rest is most likely **fragmentation**: the
cache grows by concatenation every frame, so each step allocates a slightly
larger block and leaves the old one as a gap the allocator cannot reuse for the
next, larger request. This is an inference, not a measurement.

> **Prediction 4 (13a-2), before the rerun.** The same song with
> `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`, which lets the allocator
> grow a block in place instead of leaving gaps, **completes**, with peaks at
> least 500 MiB lower on cards 1–2. Moderate confidence. If it still fails at the
> final join on card 0, the next fix is moving `frame_hiddens` off card 0.

## 13a-2 result: same song with `expandable_segments` (measured)

`result-300s-long-expseg-oom.json`. Same 6/15/15 split, same failure point: the final
`torch.stack` on card 0, *"Tried to allocate 340.00 MiB … 246.19 MiB is free"*.

| Peak, MiB | card 0 | card 1 | card 2 |
|---|---|---|---|
| default allocator | 7,835 | 7,803 | 7,803 |
| `expandable_segments:True` | 7,619 | **6,475** | **6,475** |
| difference | −216 | **−1,328** | **−1,328** |

**Prediction 4 was half right.** The fragmentation diagnosis holds: on cards 1–2 the
same work needed 1.3 GB less, which is far more than the 500 MiB predicted. But
the song still did not complete, because **card 0 is genuinely full, not
fragmented**: 7.18 GiB actually allocated by PyTorch, and only 30 MiB reserved
but unused.

This revives prediction 2. Cards 1–2 now have ~1.2 GB spare each.

> **Prediction 5 (13a-3).** `expandable_segments` plus split **4/16/16** moves two
> layers (≈ 0.72 GiB of weights plus their share of the key-value cache) off card 0.
> The song completes. Card 0 peaks ≈ 6.9 GB; cards 1–2 ≈ 6.9 GB. Moderate-high confidence.

## 13a-3 result: `expandable_segments` + 4/16/16, completes (measured)

`result-300s-long-4-16-16.json`, `song-300s-long-4-16-16.wav`.

| | |
|---|---|
| Got | **217.25 s** (3 min 37 s), stereo 44.1 kHz. The model ended the song itself |
| Total | 1,482.2 s (24.7 min): stage 1 991.7 s, swap 4.5 s, stages 2+3 485.9 s |
| **RTF** | **6.82**; stage 1 4.56 |
| Peak, stage 1 | 6,799 / 6,895 / 6,895 MiB |
| Peak, stage 2 | 6,521 / 6,895 / 6,895 MiB (cards 1–2 carry their stage-1 peak) |

**The derived length was right.** The failed 6/15/15 run's 340 MiB join implied
≈ 218 s of song; this run produced 217.25 s from the same lyrics and seed.

| Prediction | Verdict |
|---|---|
| 1 · fails on card 0 after ~3.5 min (6/15/15) | **right** on card and length; failed at the final join, not during stage 1 |
| 2 · 4/16/16 fixes it | **right**, but only together with `expandable_segments` (13a-2 showed why) |
| 3 · RTF 6.8 ± 0.3 | **right: 6.82** |
| 4 · `expandable_segments` completes it | **wrong** on its own; right that it frees ≥ 500 MiB (1,328 on cards 1–2) |
| 5 · both together complete it; peaks ≈ 6.9 GB | **right**: 6,799 / 6,895 / 6,895 |

**How far this layout should go (estimate, untested).** About 1 GB is left per card.
Cards 1–2 grow at about 3.2 MiB per second of song (key-value cache, 16 layers),
and card 0 at about 2.4 MiB/s plus the final join, which needs a second copy of
~1.6 MiB per second of song. On those rates the layout reaches roughly **5–6
minutes**, near the model's 6-minute cap. **Unmeasured**, so the studio caps asks at
300 s. Only 217 s has actually been run.

**Applied to the studio:** `source/42` now uses 4/16/16, studio jobs run with
`expandable_segments:True`, and the length slider goes to 300 s.

## 13b result: the profile (measured, `torch.profiler`, 4 s song = 101 frames, 4/16/16)

Full table: `experiments/13-profile-4s.txt`. Stage 1 ran at 293 ms/frame under the
profiler (184 unprofiled), so read times as shares and counts, not as speeds.

| Per frame | Value |
|---|---|
| CUDA kernels | **3,620** |
| `cudaLaunchKernel` calls | 3,392, **17.1 µs of processor time each**, ≈ 58 ms/frame |
| matrix multiplies (`aten::mm`) | 464 calls: 36 layers × 7 + 7 depth steps × 4 layers × 7 + heads |
| card time in matrix multiplies | 67.6 ms (**89%** of all card time) |
| all card time | ≈ 76 ms |
| elementwise ops: `mul` · `add` · `copy_` · `mean` · `pow` · `rsqrt` · `cat` · `neg` · `silu` | 636 · 442 · 561 · 208 · 208 · 208 · 163 · 72 · 64 calls, each **1.5–4.7 µs on the card** and **~40–50 µs of processor time** |
| card-to-card copies | 99 (the seams carry several tensors each); 1.4% of processor time |

| Prediction | Verdict |
|---|---|
| 4 · most stage-1 time is op dispatch and kernel launch, not the pipeline's loop or the hooks | **right**: launch plus aten dispatch dominate; copies at the seams 1.4% |
| 5 · more than 1,500 kernels per frame | **right**: 3,620, 2.4× the structural estimate |

**What this says.** The cards need about 76 ms per frame and get 184. The difference is
the processor issuing 3,400 launches at 17 µs each, plus dispatch. Most of those
launches are **elementwise** operations: normalisation (`pow`, `mean`, `rsqrt`, `mul`),
rotary position (`neg`, `cat`, `mul`, `add`), and gating (`silu`, `mul`). Each one
costs 10–30× more to launch than to run.

> **Prediction 6 (13b-2): `torch.compile` on each decoder layer's parts**
> (attention, MLP, the two norms) and the depth decoder's layers, with
> `dynamic=True` so the growing cache does not force a recompile every frame.
> **Fusion** turns each chain of elementwise ops into one kernel.
> - kernels per frame fall by **≥ 40%** (3,620 → ≤ 2,200)
> - stage-1 real-time factor falls **from 4.56 to 3.0–3.8**; the whole song from 6.8 to ~5.5
> - the output is **not** bit-identical, because fused kernels add in a different order
> - one-time compile cost under 3 minutes
>
> Low-moderate confidence: the accelerate hooks may break the compiled graphs.
> The bigger lever, capturing a whole frame as a CUDA graph (card time ≈ 76 ms,
> which would make stage 1 ≈ 1.9× real time), needs a fixed-size cache and is the
> step after this one.

## 13b-2 result: `torch.compile` fusion (measured, both runs under the profiler, 4 s song, 4/16/16)

| | eager | compiled, default limit | compiled, recompile limit 128 |
|---|---|---|---|
| kernels per frame | 3,620 | 3,221 (−11%) | **2,062 (−43%)** |
| launches per frame | 3,392 | 2,989 | 1,832 |
| stage-1 frame time, steady (median of frames 21+) | 293 ms* | not recorded | **372 ms** |
| stage 1 total, including compiling | 29.6 s | 90.4 s | **864.8 s** |

\* The eager figure is stage 1's mean over all frames. The steady-state timer was added
for the third run.

- **First compiled run:** most parts fell back to uncompiled execution after hitting
  dynamo's recompile limit of 8. The same code runs on three cards with a growing
  cache, and each combination is a separate variant.
- **With the limit raised:** fusion worked as designed, and **kernels fell 43%, as
  prediction 6 said.** But each frame got **slower**, 372 ms against 293, and
  compiling all the variants took ~14 minutes of the 4-second song.
  The profile shows 152,779 dynamo cache lookups: the guard checks that decide
  which compiled variant to run cost more processor time than the fused launches
  saved. On a slow 2012 processor, that trade goes the wrong way.

| Prediction 6 | Verdict |
|---|---|
| kernels per frame fall ≥ 40% | **right** (−43%) |
| stage-1 real-time factor 3.0–3.8 | **wrong direction** under the profiler; an unprofiled comparison is still owed |
| not bit-identical | not checked |
| compile under 3 minutes | **wrong**: ~14 minutes |

**Where this leaves the processor wall.** Fusing kernels while keeping a dynamic,
growing cache does not pay here. The remaining lever is the one named before: a
**fixed-size cache plus a captured CUDA graph per frame**, which removes both the
launches and the guard checks. That means patching the pipeline's loop, not
flipping a setting, and it is the next piece of work on this item. Not started.
