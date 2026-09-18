# Three cards, three models, at once

*Lab notebook, 2026-09-18. YuE2 on card 0, VoxCPM2 on card 1, Kokoro on card 2.
Same prompts, same seeds, `--device` selecting each card.*

**Headline: 1.55× throughput, and no interference that can be distinguished
from run-to-run noise.**

---

## 1 · The measurements, all three conditions

| | solo, cold cache | **concurrent** | solo, warm cache |
|---|---:|---:|---:|
| YuE2 (card 0) | 40.04 s | **40.05 s** | 40.46 s |
| VoxCPM2 (card 1) | 13.28 s | **11.64 s** | 12.98 s |
| Kokoro (card 2) | 8.95 s | **7.87 s** | 8.27 s |

```
wall for all three concurrently   40.05 s
sum of the three solo runs        62.27 s
                                  -> 1.55x throughput
```

Peak memory during the concurrent run: **card 0 3,891 MiB · card 1 6,603 MiB ·
card 2 2,655 MiB.** All three within their own cards, nothing shared.

## 2 · The result that was wrong, and the control that caught it

The first run showed two of three models **12% faster** when run concurrently
than alone. That cannot be a concurrency benefit — three processes competing
for host memory bandwidth do not make each other quicker.

The suspect was **order**: solo ran first, warming the operating system's file
cache, so the concurrent runs loaded their weights from memory rather than disk.

So solo was re-run with the cache already warm. It landed **between** the two:

| | cold → concurrent | cold → warm | warm → concurrent |
|---|---:|---:|---:|
| YuE2 | +0.0% | +1.0% | −1.0% |
| VoxCPM2 | −12.3% | −2.3% | −10.3% |
| Kokoro | −12.1% | −7.6% | −4.8% |

**Caching explains part of it and not all of it.** Against the properly warm
baseline, concurrent is still 10.3% and 4.8% faster for the two small models.

## 3 · What can honestly be claimed

With one run per condition, the run-to-run spread on identical work is already
**1.0% to 7.6%** (the cold-versus-warm column, which should mostly be cache but
also carries ordinary noise). Kokoro alone varies 8% between two identical solo
runs.

So:

| Claim | Supported? |
|---|---|
| **Three models run on three cards simultaneously** | **yes** — all completed, all within their own card |
| **1.55× throughput over running them in sequence** | **yes** — 40.05 s against 62.27 s |
| **Interference is small** | **yes** — the largest adverse change measured is +1.0% |
| "Concurrency makes models faster" | **no** — physically implausible, and inside the noise |
| Interference is *exactly* zero | **no** — n = 1 per condition cannot establish that |

**The honest version: concurrency costs at most a few percent, and this
experiment cannot resolve smaller than its own noise floor.** Settling it needs
several repetitions per condition, which is cheap and has not been done.

## 4 · Why interference is small, mechanically

Nothing is being *split*. Chapter 29 declined sequence parallelism precisely
because every model fits one card — which means there is **no card-to-card
traffic at all.** Three independent processes each own a card and touch each
other only through:

- the host memory bus, during weight loading
- the PCIe links, during the same
- the processor, for orchestration — 32 threads across three jobs

None of those is the bottleneck once generation starts, because generation is
the card reading its own memory. That is the same bandwidth finding as chapters
9, 19 and 23, arriving as an absence: **a workload limited by each card's own
memory bandwidth does not contend with a workload on another card.**

Card 0 sits on a different bus branch from cards 1 and 2, and the topology that
would have mattered for a split model **does not appear in these numbers.**

## 5 · What this makes available

| Use | Now possible |
|---|---|
| Three different models compared live, side by side | ✅ |
| **Three seeds of one prompt in parallel** | ✅ — best-of-N in wall-clock 1/3 |
| Generate on one card, transcribe on another | ✅ — and it was already possible on one |

The second is the one that matters for Part IV. YuE2's published headline score
is **best-of-8**, and best-of-N is the standard way these models are used. Three
cards turn that from a patience problem into a throughput one.

## 6 · Open

- **Repetitions.** n = 1 per condition. Five would put an error bar on section 3.
- **Three copies of the *same* model**, which is the best-of-N case and was not
  what was tested here — three *different* models have different load profiles.
- **Whether card 0's separate bus branch matters under heavier load.** It did
  not appear here, on a workload that barely uses the links.
