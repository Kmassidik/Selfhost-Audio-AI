# WildSongBench — the generation half, and why the other half is out of reach

*Lab notebook, 2026-09-18. YuE2-3B q4_0, three cards, 6 prompts from the
benchmark's own `prompts.jsonl`, seed 20260915.*

**Headline: the full generation campaign is 3.7 hours on this box. The scoring
campaign needs a stack this project deliberately does not have.**

---

## 1 · What the benchmark actually is

192 prompts, **17 systems**, nine metrics, published 2026-09-12. Not a demo reel:
eight public systems, seven proprietary, and YuE2 in two settings.

The model card's claim — *"highest SongBench average among all evaluated open and
proprietary models"* — is true and is a thinner claim than it sounds. From the
benchmark's own `results.md`:

| Setting | SongBench Avg ↑ | SongEval Avg ↑ | PER ↓ |
|---|---:|---:|---:|
| **YuE2 (best-of-8)** | **6.9632** | 4.2960 | 9.79% |
| Mureka 9 | 6.9377 | **4.4111** | 11.69% |
| Suno v5 | 6.8721 | 4.3579 | 8.10% |
| **YuE2** | 6.7316 | 4.2625 | 8.44% |
| Suno v6 | 6.5562 | 4.3086 | 7.58% |
| **ACE-Step 1.5** | **6.0118** | 3.8465 | 7.46% |

Their own text says it plainly: *"Suno v6 has higher SongEval scores than both
YuE2 settings, and both v6 variants have lower PER"*, and *"the small gaps are
descriptive, not claims of statistical significance."*

**ACE-Step scores 6.0118** — last but two of the seventeen, and below every Suno
version. So the model this project cannot run is also the weaker one, which
softens chapter 22's disappointment considerably.

## 2 · The protocol, which is not what the model card implies

Four details from `results.md` that change what the number means:

| Detail | Consequence |
|---|---|
| Both YuE2 rows use **melody-and-chord planning** | our first runs used planning **off** |
| Evaluation uses the **YuE2-Vae-legacy** decoder | not the default one we have |
| "Standard" YuE2 is **already best-of-2**, selected by phoneme error rate | there is no unselected number in the table at all |
| Best-of-8 selects on **musicality, then prompt control, then error rate** | selection uses a scored dimension, which the authors flag themselves |

That third row is the sharp one. **Neither published YuE2 figure is what one
click gives.**

## 3 · Generation, measured

Six benchmark prompts, three cards, both planning modes:

| Planning | audio | card time | wall, 3 cards | mean RTF | 384 runs |
|---|---:|---:|---:|---:|---:|
| `cot=off` | 1,132 s | 705 s | 258 s | 0.623 | **276 min** |
| `cot=melody` | **1,306 s** | **592 s** | **208 s** | **0.453** | **222 min** |

These are **full-length songs** — 189 s average, against the 48 s of the earlier
tests — because the benchmark's prompts are complete lyric sheets.

**The full standard protocol, 192 prompts × 2 candidates, is 3.7 hours on this
box.** That is an afternoon, not an obstacle.

### Symbolic planning is faster, not slower

The surprise. Adding melody-and-chord planning produced **more audio** (1,306 s
against 1,132) in **less card time** (592 s against 705) — a real-time factor of
**0.453 against 0.623, a 27% improvement.**

Planning was expected to cost: chapter 04 describes an autoregressive planner as
the slow, strictly sequential half. Instead the planner appears to make the
renderer's job cheaper per second of output — plausibly because a written score
gives it less to resolve, but **that is a guess and was not measured.** What is
measured is that the benchmark's own protocol is the faster one.

## 4 · Why the scoring half is out of reach

Nine metrics, and each is a model or a toolchain of its own: SongBench and
SongEval are learned quality evaluators, AudioBox PQ is a production-quality
predictor, MuLan and AllMusicCaps are text–audio alignment models, Q3O is a
prompt-control scorer, and PER needs four recogniser passes per candidate.

<br>

**None of them has a package in this engine.** Reproducing the score means
standing up a Python stack with several multi-gigabyte models — which is exactly
the thing chapter 05 chose this engine to avoid, and for a reason that applies
here: measurements taken through a different stack compare the stack.

| Option | Verdict |
|---|---|
| Run the full scoring stack | possible, and it is a second project |
| Score with what we have | **no** — none of the nine is available |
| Report generation cost and stop | **this** |

So this project can say **what the benchmark costs to run here** and cannot say
**what we would score.** Stating the second without the first would have been
easy and wrong.

## 5 · What was actually established

1. **The benchmark's generation half is affordable** — 3.7 hours, three cards.
2. **The benchmark's own protocol is the faster one**, by 27%.
3. **ACE-Step, the model that does not fit, scores 6.0118** — below every Suno
   version and 0.72 below YuE2. Chapter 22's wall costs less than it appeared.
4. **Neither published YuE2 number is a single generation**, and the authors say
   so in their own results file rather than in the model card.

## 6 · Open

- **The full campaign**, if the scoring stack is ever stood up. Generation is the
  cheap half.
- **Why planning is faster.** Measured once, on six prompts, unexplained.
- **The legacy decoder**, which the benchmark uses for evaluation and we do not have.
- **Listening**, still. Six full-length songs now exist on the box and nobody has
  heard one.
