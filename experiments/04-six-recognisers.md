# Six recognisers on real human speech — and one that breaks the model

*Lab notebook, 2026-09-18. LibriSpeech test-clean, first 30 utterances sorted,
242 seconds of audio, **identical for every recogniser**. audio.cpp `c0b26a5`,
CUDA, one card, 8-bit weights throughout.*

---

## The table

| Recogniser | Weights | WER | RTF | Peak |
|---|---:|---:|---:|---:|
| **Qwen3-ASR 1.7B** | 2,358 MiB | **0.0047** | 0.5557 | 3,393 MiB |
| **Canary 180M Flash** | 238 MiB | **0.0062** | **0.1790** | **583 MiB** |
| Parakeet-TDT 0.6B | 873 MiB | 0.0078 | 0.4911 | 2,053 MiB |
| Qwen3-ASR 0.6B | 1,098 MiB | 0.0078 | 0.3213 | 2,133 MiB |
| Nemotron-3.5 0.6B | 888 MiB | 0.0109 | 0.2862 | 1,283 MiB |
| Moonshine tiny | **58 MiB** | 0.0186 | **0.1561** | 311 MiB |

## 1 · The floor under chapter 14 is now a number

Every word error rate in Part I was produced by **Qwen3-ASR 1.7B**, and its own
error rate on read English is **0.47%** — about one word in 213.

That is the floor, and it is low enough that the 0.000 scores in chapter 14 are
safe: three voices scoring zero against a recogniser that itself errs once in
213 words is a real result, not an artefact of a blunt instrument.

**It is also only read English.** Nothing here measures the recogniser on
accented speech, noise, or the technical vocabulary it mangled in chapter 14
("431 GB" → "431 goby", "TFLOPS" → "TF all plus"). LibriSpeech is audiobooks.

## 2 · The one that should not win

**Canary 180M Flash is 10× smaller than the most accurate model, 3.1× faster,
and costs 1.5 extra errors per thousand words.**

| | Qwen3-ASR 1.7B | Canary 180M | Canary's price |
|---|---:|---:|---|
| Weights | 2,358 MiB | 238 MiB | **10× smaller** |
| Peak memory | 3,393 MiB | 583 MiB | **5.8× less** |
| RTF | 0.5557 | 0.1790 | **3.1× faster** |
| WER | 0.0047 | 0.0062 | +0.0015 |

On 2,000 words that is three extra errors. For every use in this project —
scoring generated speech — Canary is the better instrument, and it is not close.

## 3 · Model size predicts speed, except once

Fitting real-time factor against weight size across five of the six:

```
RTF = 0.000175 x MiB + 0.1374
```

| Recogniser | Predicted | Measured | Error |
|---|---:|---:|---:|
| Canary 180M | 0.1790 | 0.1790 | **−0.0%** |
| Qwen3-ASR 1.7B | 0.5497 | 0.5557 | +1.1% |
| Nemotron-3.5 | 0.2927 | 0.2862 | −2.2% |
| Qwen3-ASR 0.6B | 0.3294 | 0.3213 | −2.5% |
| Moonshine tiny | 0.1475 | 0.1561 | +5.8% |
| **Parakeet-TDT** | **0.2900** | **0.4911** | **+69.3%** |

Five models across a **40× size range** land within 6% of a straight line. This
confirms chapter 09's hypothesis, which was formed from two voices that happened
to be the same size and could not have tested it: **generation cost is
substantially set by how fast the card reads the weights.**

### And the exception is the interesting part

**Parakeet is the only transducer in the set.** Chapter 16 describes three ways
to turn frames into letters, and a transducer is the one that runs a *joint
network at every step* combining the audio encoder with a text predictor — work
that is not weight-reading and therefore invisible to a size-based model.

Every other model here is CTC or an attention encoder-decoder. The one
architectural outlier is the one timing outlier, and the direction is the one
the mechanism predicts.

> **This is a hypothesis fitted after the fact, not a prediction.** It is
> consistent and mechanistically plausible; confirming it needs a second
> transducer, and none is on the box.

## 4 · The caveat on every RTF above

These numbers come from **30 separate process launches** over 242 seconds of
audio, so per-invocation startup is inside them — the same contamination
chapter 06 found, where a one-shot tool's fixed cost swamped the generation cost.

The 0.1374 intercept is largely that startup. So:

- The figures are honest for **batch transcription of separate files**, which is
  how this harness uses them.
- They are **not** the pure generation cost, and a resident server would be
  faster for all six.
- The *slope* is unaffected by startup, which is why the size finding survives.

## 5 · Open

- **A second transducer**, to test the section-3 explanation rather than assume it.
- **The startup split**, via the two-length fit chapter 06 uses.
- **Harder audio**: accents, noise, overlapping speech, technical vocabulary —
  where these six will separate far more than 0.0047 to 0.0186.
- **Whisper**, the model almost every published word error rate is quoted
  against, has no package in this engine and is therefore absent from the table.
