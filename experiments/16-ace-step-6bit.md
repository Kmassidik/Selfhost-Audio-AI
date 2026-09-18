# ACE-Step 1.5 at 6 bits: does it fit the card, and does it still sing

*Lab notebook, 2026-09-18. The prediction half, committed before anything ran.*

Chapter 22: ACE-Step 1.5 turbo at 8 bits (the smallest published package) needs
**8,446 MiB** on a 7,840 MiB card and fails by **606 MiB**. It is the only music model
here whose output could be sold (MIT licence). Chapter 22 estimated a 6-bit package
at ~6,950 MiB, fitting with ~900 MiB spare, by scaling the 8-bit weights. That was
an estimate, and no such package exists.

## Method

- Source: the published 16-bit package `ace-step-1.5-turbo-bf16.gguf`
  (10,090,398,272 bytes, downloaded 2026-09-18). **Not** the 8-bit file: making 6 bits
  from 8 would round the weights twice.
- Tool: the engine's own converter `audiocpp_gguf --type q6_k`, built from the same
  checkout (`c0b26a5`).
- Run: the same command and prompt as chapter 22's failing 8-bit run, one card.

**A warning from the engine's own docs** (`docs/gguf.md`, test matrix): `ace_step`
at 16 bits is "Pass (drift)", and at **8 bits "No (planner sampling can fail)"**. The
maintainers could not make even 8 bits reliable, so 6 bits is further down the
same slope.

## Predictions

> **1 · Size.** The two published files fix how much of the model the converter
> quantizes: 16-bit 10.09 GB, 8-bit 6.19 GB. That implies ~8.29 GB of quantizable
> 16-bit weights and ~1.80 GB kept at full precision. At 6.56 bits per weight
> (q6_k) the file is ≈ **5.2 GB**, about 1.0 GB smaller than 8-bit (derived, not measured).
>
> **2 · It fits.** Peak ≈ 8,446 − ~950 MiB ≈ **7,500 MiB** against 7,840. Moderate-low
> confidence. The margin is thin, and chapter 22 found the failing allocation in the
> **timbre encoder**, which may be among the tensors the converter keeps at full precision.
>
> **3 · It runs and produces a song**, with one or more of the three standard
> prompts failing in the planner as the docs warn. Low confidence either way.
>
> **4 · Speed within ±20% of what 8-bit would do.** 8-bit never ran here, so this is
> compared against the 16-bit processor run in chapter 22 only loosely. Mostly
> recorded, not predicted.

## Results — q6_k (measured 2026-09-19)

Conversion: `audiocpp_gguf --input <bf16.gguf> --family ace_step --type q6_k` accepted a
GGUF as input. It took **7 min 11 s** and 4.4 GB of RAM, and produced
**5,174,422,688 bytes** (prediction 1: ≈ 5.2 GB, **right**).

| Asked | Result | Peak before the failing call | + requested | Needed | Short by |
|---|---|---|---|---|---|
| 10 s | failed after 16.6 s | 6,499 MiB | 1,389.5 MiB | 7,888 | **48 MiB** |
| 30 s | failed after 17.8 s | 6,585 | 1,389.5 | 7,974 | 134 |
| 60 s | failed after 20.4 s | 6,717 | 1,389.5 | 8,106 | 266 |

Same message as 8 bits: *"ACE-Step timbre encoder backend buffer allocation failed"*, the
same 1,456,983,552 bytes.

- **Prediction 2 (fits): wrong, by 48 MiB.** The file shrank 1.01 GB, but the memory
  reached before the failing call fell only **558 MiB** (7,057 → 6,499 at 10 s). About
  half the saving never reaches the card, most likely because not every weight is
  on the card when the timbre encoder asks, or because working buffers are
  sized independently of the weights. Not investigated.
- **Chapter 22 called the allocation "fixed"; it is not entirely.** The memory reached
  first grows with the asked length: +86 MiB from 10 s to 30 s, +218 MiB to 60 s.
  Only the 1,389.5 MiB request itself is fixed.
- Predictions 3 and 4 cannot be scored: nothing ran.

> **Prediction 5 (q5_k).** At 5.5 bits the file is ≈ 4.65 GB (−0.52 GB against q6_k).
> Using the measured transfer rate of 558 MiB per 1.01 GB, the peak falls ≈ 290 MiB:
> 10 s needs ≈ 7,600 and **fits**; 30 s ≈ 7,680 **fits**; 60 s ≈ 7,820 is **on the edge**.
> Moderate confidence for 10 s.

## Results — q5_k (measured 2026-09-19)

File 4,620,968,512 bytes. **Memory now fits**: the peaks are 5,673 / 5,987 / 6,119 MiB at 10 / 30 / 60 s,
and the run got past the timbre encoder. **Every run then failed in the planner:**
*"ACE-Step planner phase-2 sampling found no finite logits"*. That is exactly the
engine docs' warning for this family ("planner sampling can fail"). The planner is
ACE-Step's 1.7B language model, and at 5 bits its output scores became NaN or infinite.

Prediction 5: fits **right** (and with more room than predicted); but nothing ran.

### Where the bytes are, per group (read from the GGUF headers)

| Group | bf16 | q8_0 | q5_k |
|---|---:|---:|---:|
| DiT decoder (the renderer) | 3,005 MiB | 1,655 | 1,115 |
| **planner layers** (`lm_weights/layers`) | 2,688 | **1,428** | **924** |
| engine-side extras (`_audiocpp`) | 1,352 | 722 | 470 |
| planner embedding table | 849 | 849 | 849 |
| text encoder layers + table | 1,136 | 743 | 585 |
| VAE, detokenizer, rest | 533 | 443 | 404 |

Embedding tables and norms stay 16-bit at every level. The converter already keeps them.

> **Prediction 6 (mixed).** q5_k everywhere **except the planner layers at q8_0**
> (`--keep-type "lm_weights/*=q8_0"`): +504 MiB, so peaks ≈ 6,180 / 6,490 / 6,620,
> which **fit**. The planner produces finite scores and a song comes out.
> Moderate-low confidence: the docs list even pure q8_0 as "planner sampling can
> fail". If it fails, the next step is the planner at bf16 (+1,260 MiB more, ≈ 7,440
> at 10 s, which still fits on paper).

## Results — q5_k + planner q8_0 (measured 2026-09-19)

The first attempt with `--keep-type "lm_weights/*=q8_0"` was refused: *"cannot quantize
tensor: lm_weights/layers.0.input_layernorm.weight"*. The prefix also caught the
1-D norms. The fix is one `--keep-type <name>*=q8_0` per planner matrix: 196 rules,
generated from the q5_k file's own tensor list.

File 5,149,450,816 bytes; planner layers 1,428 MiB (q8_0), DiT decoder 1,115 (q5_k).
**Out of memory again, at the timbre encoder:** 6,527 / 6,571 / 6,703 MiB reached,
plus the same 1,389.5 MiB request, is **76 / 120 / 252 MiB short**.
Prediction 6 **wrong**. The planner is on the card when the timbre encoder asks, so
its +504 MiB lands directly in the gap.

> **Prediction 7 (q4_k base + planner q8_0).** The q5_k groups other than the planner
> (renderer 1,115, extras 470, text-encoder layers 289, detokenizer 74 = 1,948 MiB)
> fall by ~1/5.5 to 4.5 bits, ≈ −354 MiB in the file. At the measured transfer
> of ~0.55 that is ≈ −195 MiB reached: **10 s and 30 s fit** (by ~120 and ~75 MiB),
> **60 s still fails** (by ~57). If it runs, the question becomes quality: a
> diffusion renderer at 4 bits, **judged by listening, not by this notebook**.

## Results — q4_k base + planner q8_0 (measured 2026-09-19)

File 4,804,713,536 bytes (DiT decoder 935 MiB q4_k, extras 386, planner 1,428 q8_0).

| Asked | Result | Where it failed |
|---|---|---|
| 10 s | **past the timbre encoder**, peak 7,765, then out of memory | the diffusion cross-attention cache wanted **78 MiB** more |
| 30 s | out of memory, peak 6,255 | timbre encoder (1,389.5 MiB) |
| 60 s | out of memory, peak 6,387 | timbre encoder |

Prediction 7 **wrong for 30 s**: 6,255 + 1,389.5 = 7,645 should have fit 7,840. The
sampler reads every 0.2 s and misses short spikes, so the memory actually held when
the request came was higher than the recorded peak. **Recorded peaks near a failure are
lower bounds, not the true figure.**

## `ace_step.mem_saver` (found in `docs/models/ace_step.md`)

*"Release staged graph/cache state after request phases to reduce resident VRAM."*
The obvious lever, missed until now. Chapter 37 found the same flag for MiniMax,
where it did nothing.

| File | Asked | Result | Peak | Failed at |
|---|---|---|---|---|
| published q8_0 | 10 s | out of memory | 7,437 | timbre encoder |
| published q8_0 | 30 s | out of memory | 7,523 | lyric encoder (161 MiB) |
| published q8_0 | 60 s | out of memory | 7,655 | detokenizer (830 MiB) |
| **q4_k + planner q8_0** | **10 s** | **a song: 10.0 s, 48 kHz stereo, made in 20.0 s (RTF 2.00)** | **6,591** | — |
| q4_k + planner q8_0 | 30 s | out of memory | 6,255 | timbre encoder |
| q4_k + planner q8_0 | 60 s | out of memory | 6,387 | timbre encoder |

**The first ACE-Step song on this box**: `runs/l16-ace-q6k/FIRST-ace-q4k-lmq8-memsaver-10s.wav`,
seed 20260915, prompt `m_song_short`. With 8-bit weights, `mem_saver` moves the failure
around, from timbre encoder to lyric encoder to detokenizer, but does not remove it.
**Only mixed precision and `mem_saver` together make a song, and only a 10-second one.**

**Where this leaves ACE-Step.** It runs, at 10 s. 30 s and longer still fail on the
1,389.5 MiB timbre-encoder request. The remaining levers, in order of cost:
planner at q6_k (≈ −330 MiB, NaN risk: q5_k produced NaN); renderer at q3_k; the
engine's per-component weight-type options (`dit_weight_type`,
`planner_weight_type`) at load time. **Quality at 4 bits is untested; it needs a
listener.**

## Next: 30 seconds (pre-registered 2026-09-19)

> **Prediction 8 (q4_k base + planner q6_k + `mem_saver`).** The planner's 196 matrices
> go from q8_0 (1,428 MiB) to q6_k (≈ 1,102 MiB), −326 MiB in the file, ≈ −180 MiB on the
> card at the measured transfer. The 30 s run is 1,389.5 MiB into a card at ≥ 6,255
> (a lower bound), so the true gap is unknown and this may not be enough.
> **30 s fits: coin-flip. 10 s still works: likely.** The planner at q6_k returns finite
> scores: moderate (q5_k returned NaN, q8_0 did not; 6 bits is between them).

## Results — q4_k base + planner q6_k + `mem_saver` (measured 2026-09-19): 30 s works

File: planner layers 1,102.7 MiB (q6_k, 196 matrices), everything else as the q4_k build.

| Asked | Result | Made in | Real-time factor | Peak |
|---|---|---|---|---|
| 10 s | **10.0 s, 48 kHz stereo** | 19.5 s | 1.95 | 6,269 MiB |
| **30 s** | **30.0 s, 48 kHz stereo** | **20.6 s** | **0.69** | 5,931 MiB |
| 60 s | out of memory, timbre encoder | — | — | 6,737 |
| 120 s | out of memory, timbre encoder | — | — | 6,329 |
| 240 s | out of memory, timbre encoder | — | — | 7,185 |

- **Prediction 8: right on every count.** 30 s fits, 10 s still works, and the planner returns
  finite scores at 6 bits. The planner's threshold is between 5 bits (NaN) and 6 (fine).
- **Speed is nearly flat in length.** 10 s took 19.5 s and 30 s took 20.6 s. Most of the time is
  loading and fixed stages, so the real-time factor falls as the song gets longer.
- **The ceiling is 30–60 s on this card.** Before the 1,389.5 MiB timbre-encoder request, the
  memory held grows with the asked length. By 60 s there is no room, even with
  `mem_saver`, and the recorded peaks are lower bounds (see q4_k above).

**The whole trail, eight builds:**

| # | Build | Result |
|---|---|---|
| 1 | published q8_0 | out of memory, 606 MiB short (chapter 22) |
| 2 | q6_k | out of memory, 48 MiB short |
| 3 | q5_k | fits, **planner NaN** |
| 4 | q5_k, planner q8_0 | out of memory, 76 MiB short |
| 5 | q4_k, planner q8_0 | out of memory, 78 MiB short (10 s got further) |
| 6 | published q8_0 + `mem_saver` | out of memory at three different stages |
| 7 | q4_k, planner q8_0 + `mem_saver` | **10 s works** |
| 8 | **q4_k, planner q6_k + `mem_saver`** | **10 s and 30 s work; 60 s+ does not** |

**Where ACE-Step stands for a personal music platform:** a working 30-second
generator, faster than real time. For full-length songs the box already has YuE2
(tested to ~2.6 min here, memory fit to 10.5 min) and MiniMax-Music3 (tested to 3 min 37 s).
Getting ACE-Step past 60 s on this engine would need the timbre encoder's buffer
shrunk or moved, which is engine work in C++. The alternative is ACE-Step's own
Python release, which advertises running in under 4 GB. Neither has been tried.
