# Tasks — one line per proven step

*Fine-grained tracker. A line moves to ✅ only when there is a measurement, a
file, or a committed page behind it. "It worked when I tried it" is not a proof.*

*The coarse view lives in [QUEUE.md](QUEUE.md). This file is the audit trail.*

---

## Legend

| | |
|---|---|
| ✅ | done, with evidence committed |
| 🔨 | in progress |
| ⏸ | blocked — the blocker is named |
| 📋 | queued |

---

## Part 0 · Scaffold

| | Task | Evidence |
|---|---|---|
| ✅ | Survey Hugging Face live, not from recall | `planning/MODELS.md`, dated 2026-09-15 |
| ✅ | Read both siblings, record what transfers | `PRD.md` §1, `planning/HARDWARE.md` |
| ✅ | Confirm the box is reachable and record its state | `planning/HARDWARE.md` — measured 2026-09-15 09:28 |
| ✅ | Folder structure + house style + frozen prompts | this repo |
| ✅ | Box-side setup files, honestly marked as not-yet-run | `docs/SETUP.md` banner |
| ✅ | ch.01 · the mechanism, before any run | `knowledge-base/01-what-a-sound-is.html` |
| ✅ | ch.05–07 · **Part II written in full** | 3 chapters, `check.py` clean |
| ✅ | ch.08 · how a prompt becomes a song | every knob costed |
| ✅ | Every citation fetched and verified before committing | 8 sources, titles + authors matched |

## Part I · The Sound

| | Task | Blocker / evidence |
|---|---|---|
| ⏸ | L0 · Kokoro-82M makes one `.wav` | blocked: cards occupied (QUEUE #2) |
| ⏸ | L0 · `ffprobe` the output, record format from the file | after the above |
| ⏸ | L1 · CUDA toolkit installed on the box | blocked: QUEUE #1 |
| ⏸ | L1 · `audio.cpp` built `--backend cuda --cuda-arch 86` | after the above |
| ⏸ | L1 · Kokoro through `audio.cpp`, compared to L0 | — |
| 📋 | L2 · VoxCPM2 voice design from a description | — |
| 📋 | L2 · VoxCPM2 clone from a reference clip | — |
| 📋 | L2 · quantization sweep bf16 / Q8 / Q4 at fixed seed | — |
| 📋 | L2 · **prediction written down before listening** | — |

## Part II · The Ear

| | Task | Note |
|---|---|---|
| 📋 | `bench/run.py` — RTF, peak VRAM, time to first audio | one JSON per run |
| 📋 | WER / CER scorer | objective, and blind to tone |
| 📋 | Speaker-similarity scorer | embedding cosine |
| 📋 | Null test (A−B) | detects difference, **never audibility** |
| 📋 | `listening/` — blind, seeded, recorded, honest `n` | no precedent in either sibling |
| 📋 | WildSongBench wired up | 192 prompts, Suno v5/v6 already scored |
| 📋 | **Write down what the ear cannot see** | same day it is built, not later |

## Part III · The Song

| | Task | Note |
|---|---|---|
| 📋 | L4 · ACE-Step 1.5 — a full song | MIT, commercial-safe |
| 📋 | L4 · predict RTF and VRAM for a 3060 Ti **before** running | card claims 3090 <10 s, <4 GB |
| 📋 | L4 · planner sweep 0.6B / 1.7B / 4B | same prompt |
| 📋 | L5 · YuE2-3B at bf16 / Q8_0 / Q4_0 | the exam |
| 📋 | L5 · **does 7,755 MiB fit 8,192 MiB?** | 437 MiB margin, on someone else's card |
| 📋 | L5 · explain the gap vs the RTX 5090 figures | PRD §4.2 |

## Part IV · The Wall

| | Task |
|---|---|
| 📋 | Where does Q4 stop being acceptable — speech vs music, separately |
| 📋 | Four-minute attention: chunk-and-chain, or port the ring |
| 📋 | Three cards as three slots — parallel seeds for best-of-N |
| 📋 | Profile where peak VRAM actually goes (PRD §4.1 predicts ⅔ is not weights) |

## Part V · Ours

| | Task |
|---|---|
| 📋 | T1 · a voice fine-tuned on our own recordings |
| 📋 | T2 · a style |
| 📋 | T3 · the pipeline — the three siblings joined |
| 📋 | T4 · a model from scratch (aspiration, not plan) |
