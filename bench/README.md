# bench/ — the measuring instrument

Every model in the ladder is measured by the same harness, with the same
prompts, the same seed and the same metrics. Nothing is measured by hand.

```
source/NN_*.py  ->  bench/results/<run-id>.json  ->  bench/table.py  ->  a chapter
```

**Nothing is built yet.** This file is the contract it will be built against,
written first so the shape is decided before the first measurement rather than
after the fifth.

## Why it is shaped this way

Inherited wholesale from [`../../selfhostllm/bench/`](../../selfhostllm/bench/),
which earned each of these the hard way:

**One JSON per run, and the table is generated.** A hand-maintained comparison
drifts from the measurements within a week. `table.py` reads `results/*.json`
and nothing else, so **a number that was never measured cannot appear.**

**`prompts.json` is frozen.** Changing a prompt invalidates every measurement
taken before the change. To add one, add a new id and keep the old. Not even
typos get fixed — a typo present during a measurement is part of it.

**One seed, everywhere.** Without it two runs cannot be compared, because any
difference might be chance. `seed = 20260915`.

**Standard library only.** The harness must never fail to run because a model's
environment installed an incompatible version of something.

## The metrics

| Metric | Unit | Why |
|---|---|---|
| **RTF** | ratio | wall time ÷ audio duration. The one number a user feels. `< 1` is faster than real time |
| **Time to first audio** | ms | the analogue of TTFT — how long before anything is heard |
| **Peak VRAM**, per card | MiB | did the memory model predict this? All three cards sampled, so a run that quietly spread is visible |
| **Max duration** before failure | s | the real capacity limit |
| **Output SHA-256** | hex | **not** a quality check — see below |
| **WER / CER** | % | speech only. Did it say the words? |
| **Speaker similarity** | cosine | cloning only. Is it the same voice? |

Plus, every run: **predicted vs measured**, and a written explanation of any gap.

## ⚠️ The hash column means something different here

In `selfhostllm`, a matching output hash at temperature 0 meant two engines
computed the same thing, and it was the strongest result in Part I.

**Here it means almost nothing.** Two waveforms that differ in every sample can
be indistinguishable to a listener, and two that differ in a handful of samples
can be obviously broken. The hash is recorded because **determinism is worth
knowing about** — a model that produces a different hash from the same seed has
a reproducibility problem, and that is a real finding — but it is never evidence
about quality.

Quality lives in [`../listening/`](../listening/) and in the objective scorers
above. **This is the gap that Part II of the PRD exists to fill.**

## The honest caveats — written before the first run

Stated now so they cannot be quietly dropped later:

- **Peak VRAM is sampled, not traced.** Polling `nvidia-smi` at 5 Hz misses a
  spike shorter than 200 ms. The sibling recorded this; it applies unchanged.
- **RTF depends on what else is on the card.** The box's three cards currently
  hold a sibling's engine. A run sharing a card is labelled as sharing.
- **Audio duration is read from the file, not from the request.** A model asked
  for 240 seconds that produces 180 has not been fast; it has been short, and
  dividing by the requested length would hide exactly that.
- **WER cannot hear tone.** A monotone that pronounces every word scores
  perfectly. It measures intelligibility, and nothing else.

## Layout

```
prompts.json    FROZEN — the experimental control
prompts/        longer prompt bodies, when they outgrow the JSON
results/        one JSON per run — the table's only source
raw/            stdout, nvidia-smi samples, anything not yet distilled
```
