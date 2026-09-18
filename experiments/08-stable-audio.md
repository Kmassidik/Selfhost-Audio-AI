# Stable Audio 3 Small Music — the third model, and a hard cap

*Lab notebook, 2026-09-18. 8-bit, 1,606 MiB of weights, one card, seed 20260915.*

**Headline: the fastest and smallest music model here by a wide margin — and it
stops at exactly two minutes and cannot sing.**

---

## 1 · The measurements

| request | produced | wall | RTF | peak | % card |
|---|---:|---:|---:|---:|---:|
| 30 s | 30.00 s | 7.48 s | 0.249 | 1,457 MiB | 18.6% |
| 45 s (sparse) | 45.00 s | 7.75 s | 0.172 | 1,473 MiB | 18.8% |
| 45 s (dense) | 45.00 s | 8.29 s | 0.184 | 1,473 MiB | 18.8% |
| 60 s | 60.00 s | 7.77 s | 0.129 | 1,485 MiB | 18.9% |
| **240 s** | **120.00 s** | 8.78 s | 0.073 | 1,517 MiB | 19.3% |

44,100 samples a second, **stereo**, and the requested duration is honoured
exactly — 30 s means 30.00 s — which neither other music model does.

## 2 · Cost is almost independent of length

**7.48 seconds for 30 seconds of music. 8.78 seconds for 120.** Four times the
output for **17% more time.**

This is chapter 04's prediction in its purest form. A diffusion renderer does a
**fixed number of passes over the whole clip**, so a longer clip makes each pass
larger but does not make more of them. Compare the two mechanisms as measured on
this box:

| | mechanism | wall clock against output length |
|---|---|---|
| Stable Audio | pure diffusion | **7.48 s → 8.78 s** for 4× the audio |
| YuE2 | planner + renderer | 37.5 s → 89.5 s for 3× the audio |

YuE2's autoregressive planner has to *write* more song before anything is
rendered, and that part is strictly sequential. Stable Audio has no planner to
be slow.

The real-time factor therefore **improves with length** all the way to the cap:
0.249 at 30 seconds, **0.073 at 120** — 13.7× faster than real time.

## 3 · The cap is hard, and it is the price

Asked for **240 seconds**, it produced **120.00 seconds**. Not an error, not a
truncated file — a clean two-minute output with no warning.

**It cannot make a four-minute song.** Every other length request was honoured
to the hundredth of a second, so this is a designed limit rather than a failure.

And a second limit, visible in the engine's own interface rather than in a
measurement: **there is no `--lyrics` flag for this family.** Text-to-music,
init-audio and inpainting. It is an instrumental model.

## 4 · Where it sits

| | YuE2-3B | ACE-Step turbo | **Stable Audio 3 Small** |
|---|---|---|---|
| Weights, as run | 2,542 MiB (4-bit) | 5,899 MiB (8-bit) | **1,606 MiB (8-bit)** |
| Runs on the card | yes | **no** | **yes** |
| Peak | 3,891 MiB — 50% | ~8,446 wanted | **1,517 MiB — 19%** |
| RTF | 0.751 | 38.9 (processor) | **0.073** |
| Output | 48 kHz stereo | 48 kHz stereo | 44.1 kHz stereo |
| Max length | 10.5 min (memory) | — | **2 min (hard cap)** |
| Duration control | model chooses | requested | **exact** |
| **Lyrics and vocals** | **yes** | **yes** | **no** |
| Licence | CC-BY-NC | **MIT** | Stability community |

Three models, three different things:

- **YuE2** makes complete songs with sung lyrics and is the quality claim. Cannot be sold from.
- **ACE-Step** could be sold from and does not run here.
- **Stable Audio** is ten times faster on a fifth of the memory, and makes
  instrumental beds up to two minutes.

**None of them is the same product**, which is worth saying before any of them
is declared better than another.

## 5 · Open

- **Nothing listened to.** As everywhere else, this is memory and clock.
- **Whether the two-minute cap can be lifted.** It looks designed; whether a
  session option moves it has not been checked.
- **Init-audio and inpainting**, the two capabilities unique to this model in
  this set, are untested — and inpainting is the only tool here for *editing*
  existing audio rather than generating from nothing.
- **The medium variant**, 3,417 MiB at 8-bit, is downloading. It would fit
  comfortably and may lift the cap.
