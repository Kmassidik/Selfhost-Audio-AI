# L0 · Where Kokoro's memory actually goes — three wrong predictions

*Lab notebook, 2026-09-17. Everything measured on the box (3× RTX 3060 Ti, 8 GB,
`sm_86`), audio.cpp at `c0b26a5`, CUDA 12.0.140, all runs `--seed 20260915`.*

**Headline: peak memory does not grow with the length of the speech.**
21 seconds and 171 seconds of the same text both peak at **2,673 MiB**.

---

## The measurements that started it

Frozen prompt set, Kokoro-82M q8_0, one card:

| prompt | audio | peak card 0 |
|---|---:|---:|
| `s_short` | 2.18 s | 819 MiB |
| `s_expressive` | 4.68 s | 1,211 MiB |
| `s_paragraph` | 21.38 s | 2,673 MiB |
| `s_normalize` | 25.48 s | **5,209 MiB** |

A straight line through those says 8,192 MiB — the whole card — arrives at about
**40 seconds of speech.** For a text-to-speech model that would be crippling.

> **Prediction 1, written before testing:** Kokoro runs out of memory at roughly
> 40 seconds of audio.

## Prediction 1: wrong, by at least a factor of five

Repeating one sentence, 2 to 24 times:

```
 17.50 s  peak 2081 MiB      87.50 s  peak 2081 MiB
 35.00 s  peak 2081 MiB     122.50 s  peak 2081 MiB
 52.50 s  peak 2081 MiB     157.50 s  peak 2081 MiB
 70.00 s  peak 2081 MiB     210.00 s  peak 2081 MiB
```

**Flat.** Three and a half minutes of speech on 25.4% of one card, and no
failure. The line through the first table was real and meant nothing.

> **Prediction 2:** memory is set by the longest *sentence*, because the model
> works sentence by sentence and the repeated text has a fixed sentence length.

## Prediction 2: wrong

Same clause count, only the punctuation changed:

| text | chars | audio | peak |
|---|---:|---:|---:|
| 16 short sentences | 1,119 | 72.22 s | 2,971 MiB |
| 1 sentence, 16 clauses | 1,119 | 70.60 s | 2,939 MiB |
| 32 short sentences | 2,239 | 144.55 s | 2,971 MiB |
| 1 sentence, 32 clauses | 2,239 | 141.12 s | 2,939 MiB |
| 1 sentence, 48 clauses | 3,359 | 211.53 s | 2,939 MiB |

Sentence structure moves peak memory by **1%**. Not the cause.

> **Prediction 3:** the first table is contaminated. `nvidia-smi` reports
> whole-card memory, the harness ran processes back to back, and a dying CUDA
> process does not release its allocation instantly — so each run's sampler was
> reading the previous run's memory.

## Prediction 3: wrong, and worth having tested

Same four prompts, back to back, then again waiting for the card to return to
idle first:

```
BACK-TO-BACK                     SETTLED FIRST
 s_short       was 33 ->   821    s_short       was 33 ->   819
 s_paragraph   was 33 ->  2673    s_paragraph   was 33 ->  2673
 s_normalize   was 33 ->  5209    s_normalize   was 33 ->  5209
 s_expressive  was 33 ->  1211    s_expressive  was 33 ->  1211
```

The card was idle at 33 MiB before every single run, and the peaks reproduce
exactly. **The harness was not contaminated; both measurement sets are correct.**
That left only the text itself.

## The decisive test

The same natural paragraph, repeated 1, 2, 4 and 8 times:

| text | chars | audio | peak |
|---|---:|---:|---:|
| ×1 | 357 | 21.38 s | 2,673 MiB |
| ×2 | 715 | 42.77 s | 2,673 MiB |
| ×4 | 1,431 | 85.53 s | 2,673 MiB |
| ×8 | 2,863 | 171.03 s | **2,673 MiB** |

**Eight times the text, byte-identical peak memory.**

## What is established

1. **Peak memory is bounded and does not scale with duration.** The model
   processes text in chunks; the peak is set by the largest chunk, and once the
   text is long enough to fill one, adding more only adds chunks.
2. **Long-form speech is not a memory problem on this hardware.** Three and a
   half minutes fits in about a third of one 8 GB card, with two cards untouched.
3. **A duration sweep that varies the text is not a duration sweep.** The first
   table conflated two variables and produced a confident straight line through
   a relationship that does not exist.

## What is still open

**Why `s_normalize` peaks at 5,209 MiB** — roughly twice `s_paragraph`, from
*fewer* characters. It is the prompt full of dates, decimals, percentages and a
phone number, which text normalisation expands into many more words than it
looks like it contains. That is the likely cause and it is **not measured**.
Recorded as open rather than guessed.

The exact chunking rule — token budget, character count, or something else —
is also not established. It does not need to be for the conclusion above to
hold, and it will matter in Part IV.

## The lesson worth carrying

Four points, a clean straight line, a confident extrapolation, and the
relationship was not there at all. The first table is not wrong — every number
in it reproduces exactly. **It was the interpretation that was invented**, and
the only reason it did not survive is that it was written down as a prediction
specific enough to fail.
