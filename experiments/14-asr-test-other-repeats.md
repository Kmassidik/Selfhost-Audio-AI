# Six recognisers on the hard half, three times over

*Lab notebook, 2026-09-18. The prediction half, committed before anything ran.*

Experiment 04 ranked six recognisers on LibriSpeech **test-clean**, first 30
utterances sorted, one run each. Two gaps from the approved backlog:

1. **test-clean is the easy half.** LibriSpeech splits its test speakers by how
   hard a reference recogniser found them; **test-other** is the harder half.
   Published results are quoted on both, so this also puts our numbers beside theirs.
2. **One run has no error bars.** Every number in 04 is a single measurement.

Runner: `source/45_asr_test_other.sh`, which runs the same N = 30 sorted and the
same 8-bit weights, one model at a time on card 0, and three repeats of
everything on both halves.

## Predictions

> **1 · Every recogniser's word error rate rises on test-other, by 2× to 4×.**
> That is the usual ratio in published results for strong models. Moderate confidence.
>
> **2 · The ranking mostly holds.** Qwen3-ASR 1.7B stays first; Moonshine tiny
> stays last and degrades the most (the smallest model has the least to fall
> back on). **Canary's gap to Qwen3 1.7B widens**: 10× fewer parameters matter
> more on hard speech. Low confidence on the Canary claim, which is the
> interesting one: it decides whether the studio's choice of Canary survives.
>
> **3 · Repeats: word error rate is identical across all three runs** for every
> model. The decoding is greedy (no sampling), so the same audio should give the
> same words. Real-time factor varies by **under 5%** run to run (coefficient of
> variation), so experiment 04's single-run speed ranking stands.

## Results — measured 2026-09-18, 36 runs (6 recognisers × 2 halves × 3 repeats)

`bench/results-asr/*-test-{clean,other}-r{1,2,3}-*.json` on the box. N = 30 utterances each:
test-clean 644 words / 242 s, test-other **463 words / 188 s**.

| Recogniser | WER clean | WER other | ×  | errors other (S/D/I) | RTF clean (mean ± sd) | RTF other | peak MiB |
|---|---:|---:|---:|---|---:|---:|---:|
| Qwen3-ASR 1.7B | 0.47% | **1.73%** | 3.7 | 8 / 0 / 0 | 0.514 ± 0.002 | 0.661 ± 0.027 | 3,393 |
| Canary 180M Flash | 0.62% | **1.30%** | 2.1 | 6 / 0 / 0 | 0.148 ± 0.000 | 0.188 ± 0.003 | 583 |
| Parakeet-TDT 0.6B | 0.78% | **1.30%** | 1.7 | 6 / 0 / 0 | 0.452 ± 0.001 | 0.582 ± 0.001 | 2,041 |
| Qwen3-ASR 0.6B | 0.78% | **1.30%** | 1.7 | 6 / 0 / 0 | 0.279 ± 0.001 | 0.357 ± 0.015 | 2,133 |
| Nemotron-3.5 0.6B | 1.09% | **3.67%** | 3.4 | 16 / 0 / 1 | 0.247 ± 0.001 | 0.320 ± 0.011 | 1,283 |
| Moonshine tiny | 1.86% | **7.34%** | 3.9 | 26 / 4 / 4 | 0.122 ± 0.000 | 0.157 ± 0.001 | 311 |

**Read the error counts before the percentages.** On test-other, 1.30% is 6 wrong
words and 1.73% is 8, out of 463. **A two-word difference is not a ranking.** The
first four recognisers are statistically tied on this sample; only Nemotron (17 errors)
and Moonshine (34) are clearly worse. A real separation needs far more than 30
utterances. The full halves have ~2,900 each.

| Prediction | Verdict |
|---|---|
| 1 · WER rises 2–4× on test-other | **4 of 6 right** (2.1–3.9×); Parakeet and Qwen3 0.6B rose only 1.7× |
| 2 · ranking holds, Qwen3 1.7B first, Moonshine last and degrades most, Canary's gap widens | **Moonshine: right** (3.9×, 34 errors). **Qwen3 1.7B first: wrong**, with 8 errors to Canary's 6, within noise. **Canary's gap widens: wrong**, since Canary did not fall behind |
| 3 · WER identical across repeats; RTF varies < 5% | **right**: WER identical in all 36; worst RTF coefficient of variation 4.2% |

**What it settles for the studio.** Canary stays. On the hard half it is tied with
recognisers 3–10× its size and 2–4× slower, at 565 MiB.

**Two side findings.**
- **RTF is ~25% higher on test-other for every model.** The utterances are shorter
  (188 s against 242 s for the same 30), and each command-line run pays a fixed load
  cost, so less audio carries the same overhead. It is the tool, not the speech.
- **This run's test-clean speeds are 4–17% faster than experiment 04's** (Canary
  0.148 against 0.179), with identical WER. Nothing else was running this time.
  The single runs in 04 had no error bars, which is what this experiment was for.
  The ranking by speed is unchanged.
