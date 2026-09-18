# 🏠 Self-Hosted Audio AI — Vault Home

> **Master map.** Open this folder as an Obsidian vault and start here.
> Third sibling to [`../selfhostgenai/`](../selfhostgenai/) (MiniMax-H3 33B video on 8 GB)
> and [`../selfhostllm/`](../selfhostllm/) (the serving ladder, L0 → L4).
> Same box, same rule: **every number measured, nothing invented.**

---

## The one-line mission

`selfhostgenai` proved we could **run** a model that did not fit.
`selfhostllm` proved we could **build the engine** that runs it.
This project makes the box **speak and sing** — and then works out how to prove
it is any good, which is the part that has no precedent in either sibling.

## The arc

| Part | What | Levels | Why here |
|---|---|---|---|
| **I · The Sound** | get audio out at all, on one card | L0 → L2 | the foundation |
| **II · The Ear** | how audio gets scored | L3 | ⭐ built before it is needed |
| **III · The Song** | music generation, the Suno shape | L4 → L5 | the headline |
| **IV · The Wall** | 8 GB, quantized, long-form, three cards | L6 | where the box fights back |
| **V · Ours** | our own voice, our own model | L7 | the long nights |

**[→ Read the PRD](PRD.md)** — the plan, the math, the open questions.

### Why the ear comes second, not last

`selfhostllm` learned this the expensive way and wrote it down:
*training without an eval is burning electricity with extra steps.* Its agent
harness existed **before** the model it was meant to judge.

Audio makes that worse, not better. Part I of `selfhostllm` could end with a
**byte-identical output hash** — two engines either computed the same thing or
they did not. **There is no output hash for audio.** A waveform that differs in
every sample can sound identical, and one that differs in few can sound broken.
Part II exists because that problem has to be solved before any music gets
generated, or the whole project is opinion.

---

## 🗺️ Where everything lives

Two machines, on purpose — the split `selfhostllm` arrived at after
`selfhostgenai` hardcoded a box path into ~25 files:

```
Mac  ~/Desktop/selfhostaudioai    SOURCE OF TRUTH — git
     PRD · planning · knowledge-base · bench/ · source/ · listening/

     ./sync.sh   ──pull──▶        the box is authoritative for CODE,
                                  this side is authoritative for WRITING

Box  /root/Desktop/selfhostaudioai   RUNTIME — not in git
     models/ · engines/ · runs/ · outputs/ · venvs
```

No box path is ever written as a literal. Everything reads `$SELFHOSTAUDIO_ROOT`.

### The writing split

| | Lives on | Reader | Contains |
|---|---|---|---|
| **`knowledge-base/`** | **Mac** | us | source of truth — measured numbers, pros/cons, **failures included** |
| **`docs/`** | **Box** | the public | distilled, self-contained, GitHub-bound — must stand alone |

Nothing reaches `docs/` that is not already in the knowledge base.

---

## 📂 This repo

| Path | What |
|---|---|
| [`PRD.md`](PRD.md) | the plan — mission, the ladder, the math, open questions |
| [`planning/MODELS.md`](planning/MODELS.md) | **the survey** — what is actually on Hugging Face, dated and sourced |
| [`planning/QUEUE.md`](planning/QUEUE.md) | living task list — active, blocked, backlog |
| [`planning/HARDWARE.md`](planning/HARDWARE.md) | the box, and what is audio-specific about it |
| [`planning/KB-STYLE.md`](planning/KB-STYLE.md) | house style — inherited, plus the rules audio needs |
| `knowledge-base/` | the teaching — open `index.html` |
| `bench/` | the measuring instrument — frozen prompts, one JSON per run |
| `listening/` | **the part no sibling had** — scored listening tests |
| `source/NN_*.py` | experiments, numbered by the chapter they back — pulled from the box |
| `serve/` | the studio — a place to actually use it (the Arena analogue) |
| `experiments/` | lab notebook — raw findings before they become chapters |

## 🔌 The box

```
ssh root@100.122.45.32              control path (Tailscale, works anywhere)
http://10.0.0.20:<port>             serving path (LAN, 2.9 ms from this Mac)
```

3× RTX 3060 Ti · 8 GB each · 24 GB total · no NVLink · 125 GB RAM.
**444 GB free** as of 2026-09-18. Every model in this project fits one card except one.
Full detail, and what is audio-specific: [`planning/HARDWARE.md`](planning/HARDWARE.md).

**Golden rules** (inherited, learned the expensive way):
- Servers bind to **`0.0.0.0` / `10.0.0.20`**, never `127.0.0.1`.
- **Never stream a long job over SSH** — launch detached, return.
- Never rapid-retry SSH. Never move files a running job depends on.
- **A number not measured on this box is an estimate, or it does not appear.**

## 🧠 How to use this vault

- **Want the plan?** → [PRD](PRD.md)
- **Which model, and why?** → [MODELS](planning/MODELS.md)
- **Want to start work?** → [QUEUE](planning/QUEUE.md)
- **Want the story so far?** → the first sibling's [Journey](../selfhostgenai/history/JOURNEY.html)

🐢🔥🔊
