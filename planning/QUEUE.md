# 🗂️ Build Queue — living task list

> What we are building and in what order. Update status as we go.
> Last updated: **2026-09-18** · Status: **✅ COMPLETE — 35 of 35 chapters, glossary of 259 terms, 9 experiments, every number measured**

---

## ✅ RESOLVED — the two original blockers, and how

Both cleared themselves before any work started, and **both were inherited from
a stale document rather than measured.** `nvcc` was already present at 12.0.140;
the sibling's engine had already been stopped. The lesson is recorded in
[HARDWARE.md](HARDWARE.md) §2: *a fact copied from a document is not a
measurement.*

<details><summary>The original blocked section, kept</summary>

## 🔴 BLOCKED — needs a decision before any code runs

These are not tasks. They are questions only you can answer, and the ladder
cannot start without the first two. Full context in [PRD §8](../PRD.md).

| # | Question | Blocks | Leaning |
|---|---|---|---|
| **1** | **Install the CUDA toolkit (`nvcc`) on the box?** `audio.cpp` ships no Linux CUDA binary, so without it we are on Vulkan or CPU and every speed number is meaningless. It is a change to a machine two other projects depend on. | **L1, and everything after** | yes, but it is asked not assumed |
| **2** | **May the sibling's `llama-server` be stopped?** It holds all three cards (5.5–6.1 GB each). Nothing here can run beside it. | **L0** | ask before killing |
| **3** | **Does CC-BY-NC-4.0 disqualify YuE2-3B?** If output must be sellable, YuE2 becomes a benchmark ceiling and ACE-Step 1.5 (MIT) becomes the product. | **L5 only** | decide before Part III |
| 4 | **Reclaim disk from the siblings, or live inside 431 GB?** | Part IV | live inside it, with a retention policy |

</details>

---

## ⏭️ NEXT UP

### ✅ All 35 chapters written

Foundations · I The Voice · II The Ear · III The Listener · IV The Song ·
V The Wall · VI Ours — all complete, `check.py` clean, glossary generated.

**The studio is running** at `http://10.0.0.20:8095` as a transient unit — it
does not survive a reboot. To stop: `systemctl stop studio`. To make it
permanent it needs a real service file; not done.

### 🔴 Blocked on a person, not on work

| # | What | Why it cannot be done here |
|---|---|---|
| **1** | **The blind listening test** | ch.13 requires a real `n`. **Nothing in this project has been listened to** — every number is memory and clock. Parts I, III and IV each end on this. |
| **2** | **Quantize ACE-Step to 6-bit?** | ~900 MiB would come free and the only sellable music model would run. Hours of work against the engine's conversion tools, and worth doing only if selling output matters. |

### 📌 Settled by measurement, not by plan

- **The licence question answered itself.** The model that can be sold from
  does not fit (short by 606 MiB); the model that fits cannot be sold from.
- **Three of Part V's four expected walls do not exist**, and all three were
  inherited from siblings measuring a different workload.
- **The instrument changed.** Canary 180M replaces Qwen3-ASR for scoring —
  10× smaller, 3.1× faster, 1.5 extra errors per thousand words. Part I is
  **not** rescored; results name their recogniser.

## 🔒 Golden rules

1. **Servers bind to `0.0.0.0` / `10.0.0.20`** — never `127.0.0.1`. The Mac must reach them.
2. **Never stream a long job over SSH** — launch detached, return.
3. **Every run writes `bench/results/<run-id>.json`.** No JSON, no run.
4. **A number not measured on this box is an estimate, or it does not appear.**
5. Never rapid-retry SSH. Never move files a running job depends on.
6. Nothing reaches `docs/` that is not already in the knowledge base.
7. **Do not touch `/root/Desktop/selfhosted-minimaxi-h3/`.** Sibling 1's runtime.
8. **Recall is not research.** Model choices come from a dated survey, never from
   memory — see [MODELS.md](MODELS.md) for why this rule exists.
9. **Launch long jobs as a systemd unit, never as a polling shell.**
   `systemd-run --unit=<name> --collect --quiet /usr/bin/python3 -u <script>`,
   then read it with `journalctl -u <name>`. Learned 2026-09-18: three
   `until ! pgrep -f <job>; do sleep; done` waiters each matched *the other
   waiters' own command lines*, concluded the job was still running, and
   deadlocked forever — silently gating a benchmark that never launched. The
   cards read idle while something claimed to be running, which is the only
   reason it was caught. **A `pgrep -f` pattern matches the watcher as readily
   as the watched.** It recurred on 2026-09-18 with `pkill -f`: the pattern
   matched the very shell running the command, and killed it partway.
10. **A secret never goes on a command line.** Command-line arguments are visible
    to every process listing, and a listing printed during debugging put the
    Hugging Face token into a conversation log on 2026-09-18. Pass secrets
    through a file with mode 600 (`curl -H @file`). **If one leaks anyway,
    rotate it** at huggingface.co/settings/tokens — the sibling's own rule.
