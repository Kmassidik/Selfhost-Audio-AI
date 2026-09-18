# selfhostaudioai

Text to audio on three second-hand 8 GB GPUs — speech that sounds like a person,
and songs that stand next to Suno.

Third in a series on one machine. `selfhostgenai` ran somebody else's 33B video
model on hardware six times too small for it. `selfhostllm` climbed the serving
ladder until the engine could be written from an empty file. This one is about
**sound** — and about the one thing neither sibling had to solve: **how do you
measure a thing you can only hear?**

```
PART I    THE SOUND   get audio out, one card, our engine   L0 -> L2
PART II   THE EAR     how audio gets scored                 L3        <- built early, on purpose
PART III  THE SONG    music, the Suno shape                 L4 -> L5
PART IV   THE WALL    8 GB, quantized, long-form, 3 cards   L6
PART V    OURS        our own voice, our own model          L7
```

**Start here:** [HOME.md](HOME.md) · the plan: [PRD.md](PRD.md) · the models:
[planning/MODELS.md](planning/MODELS.md) · the work: [planning/QUEUE.md](planning/QUEUE.md)

Siblings: [`../selfhostgenai/`](../selfhostgenai/) · [`../selfhostllm/`](../selfhostllm/)
Same box, same rule: **every number measured, nothing invented.**

Status: **35-chapter guide complete, plus Part VII (R&D) — 38 chapters, 10 experiments.** 2026-09-18.

| | |
|---|---|
| **Speaks** | Kokoro, VoxCPM2, Qwen3-TTS — 17.4× to 3.6× real time, one card |
| **Listens** | six recognisers, 40× size range; Canary 180M chosen, 1 word in 161 |
| **Sings** | YuE2 — up to 10.5 min of stereo song on half a card, faster than real time |
| **Studio** | `http://10.0.0.20:8095` — web page plus an API-compatible speech endpoint |
| **Joined** | sibling 2's Llama writes lyrics → this sings → recogniser checks: 27.7 s |

**Not done, and cannot be from here:** nothing has been listened to by a person.
See [chapter 35](knowledge-base/35-the-scorecard.html).
# Selfhost-Audio-AI
