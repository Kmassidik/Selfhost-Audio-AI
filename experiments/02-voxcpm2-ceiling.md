# L1 · VoxCPM2 — the ceiling was a default

*Lab notebook, 2026-09-18. Box: 3× RTX 3060 Ti 8 GB, `sm_86`. audio.cpp `c0b26a5`,
CUDA 12.0.140. VoxCPM2 q8_0 (2.8 GiB), all runs `--seed 20260915`, one card.*

**Headline: out of the box VoxCPM2 fails somewhere between 40 and 63 seconds of
speech. One flag takes it to 4.7 minutes with memory flat.**

---

## 1 · What VoxCPM2 costs, against Kokoro

Same four frozen prompts, same card, same seed:

| | Kokoro-82M q8_0 | VoxCPM2 q8_0 |
|---|---:|---:|
| Model file | 181 MiB | **2.8 GiB** |
| Sample rate | 24 kHz | **48 kHz** |
| Channels | mono | mono |
| Fixed overhead | 5.64 s | **9.09 s** |
| Generation factor | 0.0575 (17.4× real time) | **0.2798 (3.6× real time)** |
| Peak, `s_paragraph` | 2,673 MiB | **6,621 MiB — 80.8% of the card** |

**4.9× slower, 2.5× the memory, and twice the bandwidth out.** Whether the 48 kHz
is worth it is a listening question and is not answered here.

A second finding fell out of the same table and is not about speed at all:

| prompt | Kokoro | VoxCPM2 |
|---|---:|---:|
| `s_normalize` | 25.48 s | **13.60 s** |
| `s_short` | 2.18 s | 1.76 s |

**Kokoro takes almost twice as long to say the same sentence.** `s_normalize` is
the prompt packed with dates, decimals and a phone number, so the two models are
expanding those very differently — and that is a *content* difference, not a
speaking-rate one. Untested, and the likely explanation for the open question
left at the end of `experiments/01`.

## 2 · The failure

Repeating `s_paragraph` to lengthen the text:

```
 ×1    357 chars   21.76 s audio   peak 6621 MiB (80.8%)
 ×2    715 chars   40.00 s audio   peak 6639 MiB (81.0%)
 ×3   1073 chars   FAILED          peak 4251 MiB
 ×4   1431 chars   FAILED          peak 4269 MiB
```

The error names the culprit precisely, which is the whole reason it was worth
reading rather than summarising:

```
800.00 MiB on device 0: cudaMalloc failed: out of memory
ggml_gallocr_reserve_n_impl: failed to allocate CUDA0 buffer of size 5033165824
audiocpp_cli failed: failed to allocate VoxCPM2 AudioVAE graph
```

**4.7 GiB, for the AudioVAE graph.** Not the language model, not attention — the
**decoder**, the part that turns the finished compressed form into a 48 kHz
waveform. VoxCPM2 chunks its generation and then decodes the whole thing in one
allocation, so the decoder is what hits the wall first.

That is the same shape as `selfhostgenai`'s founding result — the 8 GB wall
there was a single 2.24 GB quantized-matmul temporary — and it was found the
same way: **by reading the error, not by guessing.**

> **Prediction, written before testing:** the ceiling is a *default*, not a
> hardware limit. `audio.cpp` documents `--text-chunk-size`, default **8192
> characters** — larger than any realistic prompt, so nothing ever chunks.
> Capping it will make the same text succeed.

## 3 · The prediction held

```
 ×4   1431 chars  chunk=400    84.00 s audio  wall  40.24 s  peak 6671 MiB (81.4%)
 ×8   2863 chars  chunk=400   156.80 s audio  wall  69.68 s  peak 6671 MiB (81.4%)
 ×16  5727 chars  chunk=400   282.08 s audio  wall 123.72 s  peak 6709 MiB (81.9%)
```

**Four minutes and forty-two seconds of 48 kHz speech**, and peak memory moves by
**38 MiB — 0.5% — between 84 seconds and 282 seconds.** Flat, exactly as Kokoro
is flat, once the chunk is bounded.

## 4 · What is established

1. **VoxCPM2's usable ceiling on this card is set by one flag.** Default: fails
   under about a minute. `--text-chunk-size 400`: at least 4.7 minutes, and
   nothing suggests that is a limit either.
2. **The decoder is the wall, not the generator.** The allocation that fails is
   the AudioVAE graph. Any future attempt to push length further should start there.
3. **81% of one card, flat.** Two cards remain completely untouched, which makes
   the three-slot idea in Part V available rather than theoretical.

## 5 · The pattern, now twice

| Model | Looked like | Actually was |
|---|---|---|
| Kokoro | non-deterministic engine | a default random seed — `--seed` |
| VoxCPM2 | 8 GB is too small for long speech | a default chunk size — `--text-chunk-size` |

Both were found by writing down a specific claim and testing it, and in both
cases the honest first reading of the evidence was **wrong in the direction of
blaming the hardware.** Worth remembering in Part V, where the hardware really
will be the limit and it will be tempting to reach that conclusion early.

## 6 · Open

- **The seam.** Chunked output has boundaries in it. Whether they are audible is
  a listening question and has not been asked. `--text-chunk-mode` offers
  `default | tag_aware | japanese | endline`, none of which has been compared.
- **Where the true ceiling is** with chunking on. 282 seconds was the longest
  tried, not the longest possible.
- **400 characters is arbitrary.** It was chosen to be safely under the failure,
  not tuned. The largest chunk that still fits is unmeasured, and it is the
  setting that would minimise the number of seams.
