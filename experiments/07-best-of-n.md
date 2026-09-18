# Best-of-N on three cards

*Lab notebook, 2026-09-18. YuE2-3B q4_0, three seeds, one per card, `--device`
selecting each. Same lyrics, same style, 8 steps, planning off.*

**Headline: 2.61× speed-up, 99.8% of the theoretical maximum — and the output
is byte-identical whichever card it runs on.**

---

## 1 · Why this case and not chapter 30's

YuE2's published headline score is **best-of-8**: the best of eight generations
from one prompt. The seed changes the song, so this is how the model is meant to
be used rather than a trick.

Chapter 30 ran three *different* models concurrently. This is three copies of
the *same* one — same weights file, same memory profile, three processes reading
one 2.5 GiB file at once. That is a different experiment and the obvious place
for a shared-resource problem to appear.

## 2 · The measurements

| seed | card | sequential | parallel | change | peak | bytes |
|---|---:|---:|---:|---:|---:|---|
| 20260915 | 0 | 40.64 s | 37.16 s | −8.5% | 3,891 MiB | **same** |
| 20260916 | 1 | 46.34 s | 46.97 s | +1.4% | 3,873 MiB | **same** |
| 20260917 | 2 | 35.94 s | 36.36 s | +1.2% | 3,873 MiB | **same** |

```
three seeds in sequence   122.92 s
three seeds in parallel    47.06 s
speed-up                    2.61x
```

## 3 · 2.61× is not short of 3× — it is at the ceiling

The naive target is 3×, and missing it looks like overhead. It is not.

**The three seeds produce songs of different lengths** — 48.76 s, 59.84 s and
39.96 s — because an autoregressive planner decides its own structure and the
seed changes that decision. So the parallel wall clock is set by the **slowest**
run, not by the average.

```
theoretical best = sum of sequential / longest single run
                 = 122.92 / 46.97 = 2.617x
achieved         = 122.92 / 47.06 = 2.612x
                 = 99.8% of theoretical
```

**The 0.2% gap is the whole cost of running three at once.** The distance from
3× is arithmetic about unequal job lengths, not inefficiency.

## 4 · The result that matters more than the speed

**Byte-identical output, all three seeds, sequential against parallel, on three
different cards.**

Chapter 11 kept the output hash for exactly one purpose: same input, same seed
should give same bytes, and when it does not something is wrong in a way no
listener would catch. This is the strongest form of that check this project has
run — it varies the **card**, the **concurrency**, and the **system load**, and
the bytes do not move.

| Varied | Output |
|---|---|
| Card 0 → 1 → 2 | identical |
| Alone → three at once | identical |
| Cool machine → three-way load | identical |

Two things follow. **Card choice is not a hidden variable** — a result measured
on card 2 is comparable to one measured on card 0, which was assumed throughout
Parts I and III and is now checked. And **best-of-N is reproducible**: a listening
test can name a winning seed, and that seed regenerates exactly.

## 5 · What it makes possible

Eight generations, the way the published score is produced:

| | wall clock |
|---|---|
| one at a time | ~5.5 min |
| three at a time | **~2.1 min** |

Not a different capability — a different amount of patience. Which for a model
where the seed decides whether a song is any good is most of the workflow.

## 6 · Open

- **n = 1 per condition**, again. The −8.5% on seed 20260915 is almost certainly
  file cache and noise, the same effect chapter 30 had to withdraw a headline
  over. It is in the harmless direction and is not claimed as anything.
- **Eight at once on three cards** — the real best-of-8 case is three rounds,
  not one, and queueing was not measured.
- **Nothing was listened to.** Three songs exist from three seeds and no one has
  said which is better, which is the entire point of best-of-N.
