# listening/ — the part no sibling had

`selfhostgenai` judged video by watching it and saying so. `selfhostllm` never
had to judge anything subjective: at temperature 0 two engines either produced
identical bytes or they did not.

**Audio has no such anchor**, and the difference matters more than it looks:

> A waveform that differs in every sample can sound identical.
> A waveform that differs in a few samples can sound broken.

So every claim of the form *this one sounds better* is opinion until something
holds it down. This directory is that something.

## The protocol

Non-negotiable, because each rule exists to stop a specific way of fooling
ourselves:

| Rule | The failure it prevents |
|---|---|
| **Blind.** Files renamed to opaque ids before playback; the key held in a separate file, unopened until scoring is finished. | knowing which one is "ours" |
| **Same prompt, same seed, same length.** | comparing a model to a different question |
| **Both sides, always.** | publishing only the take that won |
| **Written before listening:** what is expected, and why. | remembering a prediction more favourably than it was |
| **`n` is stated.** Two people is two people. | a confident average over one opinion |
| **Recorded:** model, quantization, seed, git commit, date. | a result nobody can reproduce |

## One JSON per session

Same discipline as `bench/results/` — the file is the record, the prose comes
later:

```json
{
  "session": "2026-09-20-quant-speech",
  "date": "2026-09-20",
  "question": "At which quantization does VoxCPM2 first become audibly worse?",
  "prediction": "Q4 hurts naturalness before intelligibility. Written 2026-09-19, before any listening.",
  "prompt_id": "s_paragraph",
  "seed": 20260915,
  "commit": "abc1234",
  "blind": true,
  "listeners": 2,
  "takes": [
    {"id": "a", "model": "voxcpm2", "quant": "bf16", "scores": [5.5, 5.0]},
    {"id": "b", "model": "voxcpm2", "quant": "q8_0", "scores": [5.0, 5.5]},
    {"id": "c", "model": "voxcpm2", "quant": "q4_0", "scores": [3.5, 4.0]}
  ],
  "testimony": "Both listeners named the high end on take c. Their words, not a measurement.",
  "conclusion": "...",
  "audio": "box:runs/2026-09-20-quant-speech/"
}
```

**The waveforms are not committed.** They live in `runs/` on the box; this file
points at them. The only audio in this repository is the short cited clips in
`knowledge-base/audio/` — see [`../planning/KB-STYLE.md`](../planning/KB-STYLE.md) §2.

## What this cannot do — written before it is trusted

The same section the PRD writes for Part II, repeated here because this is where
it will be ignored:

- **We are not a listening panel.** Two ears in one room, and we are the people
  who built the thing. That bias does not go away by being acknowledged — but an
  unstated `n` of 2 is worse than a stated one.
- **A blind test detects preference, not quality.** Louder usually wins. If two
  takes differ in loudness, they are matched first or the test measures volume.
- **Scores are ordinal.** "4.1 against 5.6" is a ranking with decimals attached,
  not a measurement of how much better. Do not average across sessions.
- **Nothing here transfers between prompts.** A quantization that survives a
  dense metal mix may not survive a solo guitar — `m_sparse` exists in the
  frozen prompt set for exactly that reason.
