# The box — what audio has to live inside

*The full hardware survey lives in the sibling and is not repeated here:*
**[`../../selfhostllm/planning/HARDWARE.md`](../../selfhostllm/planning/HARDWARE.md)**
*— measured 2026-09-11, and still current.*

*This file records only what is **audio-specific**, and what changed. Anything
below marked `measured` was read off the machine on the stated date.*

---

## The short version

```
Host    : dalang-Z9PE-D8-WS          root@100.122.45.32  (Tailscale)
                                     10.0.0.20           (LAN, 2.9 ms from the Mac)
GPU     : 3x RTX 3060 Ti · 8 GB each · 24 GB total
          Ampere sm_86 · 448 GB/s each · no NVLink · FP8 NO · bf16 YES
CPU/RAM : 2x Xeon E5-2665, 32 threads · 125 GB RAM
OS      : Ubuntu 24.04.3 LTS · driver 595.84
```

**It is `root`, not `dalang`.** That user rejects the key. The first sibling's
docs are wrong about this throughout.

---

## What is occupying it right now

`measured 2026-09-15, 09:28`

```
GPU0  5,577 / 8,192 MiB      all three held by one process:
GPU1  5,429 / 8,192 MiB      /root/Desktop/selfhostllm/engines/llamacpp/build/bin/llama-server
GPU2  6,119 / 8,192 MiB      (DeepSeek-V4-Flash IQ2_M, split across three cards)

:11434   ollama
:8086    llama-server
:8090    selfhostllm arena (10.0.0.20)
```

**The cards are not free.** Any audio work either waits for that server to be
stopped, or shares. Sharing an 8 GB card with a resident 5.5 GB engine leaves
2.6 GB, which is not enough for anything in [MODELS.md](MODELS.md). **Stopping a
sibling's engine is a decision, not a step** — check before killing it.

---

## Disk — the number that constrains the model list

`measured 2026-09-15`

```
879 GB total · 404 GB used · 431 GB free   (49%)

  217 GB   /root/Desktop/selfhosted-minimaxi-h3      sibling 1 runtime
  131 GB   /root/Desktop/selfhostllm/models/gguf     sibling 2 weights
    ~1 GB  /root/Desktop/selfhostllm/models/hf
```

`selfhostllm`'s own HARDWARE.md recorded **585 GB free on 2026-09-11**. Four days
later it is 431 GB. **The siblings are consuming roughly 38 GB a day** while
active, and neither has a retention policy.

Audio is cheaper than video but not free. The models in [MODELS.md](MODELS.md)
come to roughly **30 GB** for the shortlist, and **generated audio accumulates**:
48 kHz stereo 16-bit is ~11.5 MB per minute, and a listening test that generates
eight takes of a four-minute song writes ~370 MB before anything is kept.

**Open:** whether to reclaim from the siblings, or work inside 431 GB. See [QUEUE](QUEUE.md).

---

## What is audio-specific about this hardware

### 1 · `sm_86` is `audio.cpp`'s own worked example

Its Linux build script documents `--cuda-arch "86;89"`. `86` is this card. That
is a good sign about how well-trodden the path is — **and it is not a
measurement.** It means the code compiles for this architecture, not that it is
fast on it.

### 2 · `nvcc` — the claim that was wrong

> ⚠️ **CORRECTED 2026-09-17.** This section said *"`nvcc` is absent — and this is
> now blocking"*, inherited from the sibling's `HARDWARE.md`, which was stale.
> Measured directly on the box: **`nvcc` release 12.0, V12.0.140 is present**,
> along with gcc 13.3.0, cmake 3.28.3 and ninja. The CUDA toolkit was installed
> for `selfhostllm`'s L1 and never written back into its hardware notes.
>
> **The lesson is the one this project already claims to hold:** a fact copied
> from a document is not a measurement. It was never checked with
> `nvcc --version` until it blocked something.
>
> `audio.cpp` then built clean against 12.0 — `rc=0`, zero errors, 463 targets —
> confirming the prediction recorded in `docs/SETUP.md` §3.

### 2b · The original concern, kept for the record

`selfhostllm` recorded the CUDA toolkit as absent and did not need it, because
PyTorch ships its own runtime. **`audio.cpp` compiles CUDA kernels itself.**
Prebuilt Linux packages ship **CPU and Vulkan only**.

```
no nvcc  ->  no CUDA build  ->  Vulkan or CPU  ->  every speed number is uninterpretable
```

This is the first blocking item in the [QUEUE](QUEUE.md).

### 3 · Bandwidth is the number that predicts generation speed

448 GB/s per card. Every third-party timing in [MODELS.md](MODELS.md) was taken
on an RTX 5090, which has roughly **four times** that. When a measured number
here comes in four times slower than the card claims, **that is the expected
result, not a problem** — and if it does not, the workload is compute-bound and
that is a finding worth a chapter.

### 4 · No FP8, and it matters less here than it did

FP8 needs Ada or Hopper. This card is Ampere. For audio the practical path is
**GGUF Q4_0 / Q8_0 through `audio.cpp`**, which is integer quantization and runs
fine on `sm_86`. The sibling's FP8 exclusion carries over but costs less.

### 5 · Three cards, and audio may not want them

`selfhostllm` measured card-to-card at **4.9–5.8 GB/s** over PCIe, with GPU0 on a
separate root complex (`SYS`) from GPU1 and GPU2 (`PHB`).

**Every model on the shortlist fits one card once quantized.** So unlike the
siblings, Part I here does not *need* three cards — which makes three cards an
opportunity rather than a constraint:

| Use | Worth measuring |
|---|---|
| **Three models at once** | YuE2 on c0, ACE-Step on c1, VoxCPM2 on c2 — the whole comparison live simultaneously |
| **Three takes at once** | best-of-N is how YuE2's headline score was produced. Three cards = three seeds in parallel |
| Splitting one model | probably pointless when it already fits. Measure before assuming |

The third row is the honest one: **do not split a model that fits.** The
siblings split because they had to.

---

## Access and the rules that came from breaking them

```
ssh root@100.122.45.32            control  — Tailscale, works anywhere
http://10.0.0.20:<port>           serving  — LAN, 2.9 ms
163.128.54.74                     public   — do not use
```

1. Servers bind **`0.0.0.0` / `10.0.0.20`**, never `127.0.0.1`.
2. **Never stream a long job over SSH** — launch detached, return. A four-minute
   song at RTF 0.8 is a three-minute foreground job; a listening test of 24 takes
   is not.
3. Never rapid-retry SSH. Never move files a running job depends on.
4. **Do not touch `/root/Desktop/selfhosted-minimaxi-h3/`** — sibling 1's runtime,
   its venv, and its `dalang_ref` golden reference tensors.
5. `/root/Desktop/selfhostllm/` is sibling 2's, and **its engine is currently
   running**.

---

## The neighbours

| Path | What | Rule |
|---|---|---|
| `/root/Desktop/selfhosted-minimaxi-h3/` | MiniMax-H3 33B video **+ audio**, 217 GB | Do not touch. **But read it** — it already contains a working 32 kHz stereo audio VAE |
| `/root/Desktop/selfhostllm/` | the serving ladder, engines, 131 GB of GGUF | Engine currently resident on all three cards |

**H3 is the closest prior art in the building.** Its DiT carries 24 video
channels and 32 audio channels through the same 50 blocks, flow-matched, and its
Audio VAE maps that 32-channel latent to **32 kHz stereo** — `~/Desktop/outputs/`
on the Mac holds the proof (`g4final.wav`, `ballad/`, `measured`: 32 kHz, stereo,
`pcm_s16le`). Latent flow-matching over an audio codec latent is not new ground
in this building. It is just never been done on its own before.
