# Setup — the plan, before it is run

> ✅ **§0–§6 RUN AND VERIFIED 2026-09-17.** §7–§8 not yet.
>
> Originally this file opened *"NOTHING IN THIS FILE HAS BEEN RUN YET"*. The
> build, the download and the first generation have since been executed on the
> box, and the corrections are in place. Two things the plan got wrong:
> **`nvcc` was already present** (the prerequisite that was called blocking),
> and **the cards were already free** — the sibling's engine had been stopped.
> Both were inherited from a stale document rather than measured.
>
> The sibling's `SETUP.md` opens *"every command, as actually run"* and earns
> that line — it records the failures next to the fixes. This file cannot claim
> that yet. Every command below is **intended**, not verified, and this banner
> stays until each section has been executed and corrected in place.
>
> Predictions that turn out wrong are kept and quoted, not deleted.

Target: **Ubuntu 24.04**, NVIDIA driver 595.84 already installed, 3× RTX 3060 Ti
(`sm_86`). Full hardware detail: [`../planning/HARDWARE.md`](../planning/HARDWARE.md).

---

## 0 · Before anything — two things that are not ours to decide

**The cards are occupied.** All three hold a `llama-server` from `selfhostllm`
(5.5–6.1 GB each, measured 2026-09-15). Sharing an 8 GB card with that leaves
2.6 GB, which is not enough for anything on the shortlist.

```bash
nvidia-smi --query-compute-apps=pid,used_memory,name --format=csv
```

**Stopping a sibling's engine is a decision, not a step.** Ask first.

**`nvcc` is absent.** The driver alone does not provide a CUDA compiler, and
`audio.cpp` compiles its own kernels. This is the blocking prerequisite.

---

## 1 · Where things will live

```
/root/Desktop/selfhostaudioai/
  source/        code — NN_<name>.py, numbered by knowledge-base chapter
  engines/
    audiocpp/    the C++ build
  models/
    gguf/        audio.cpp format — what runs
    hf/          safetensors, for Python reference paths
    configs/     architecture only, a few KB — committed
  bench/results/ one JSON per run
  runs/          stdout, GPU samples, and the generated audio
```

Set once, in `~/.bashrc`, so no script needs a literal:

```bash
export SELFHOSTAUDIO_ROOT=/root/Desktop/selfhostaudioai
```

---

## 2 · Python, with uv — never pip

Only the reference paths and the scorers need Python. **`audio.cpp` itself needs
none**, which is most of why it was chosen.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc

cd $SELFHOSTAUDIO_ROOT
uv venv --python 3.12
uv pip install -e .                  # reads pyproject.toml
```

> **Why uv rather than pip.** The environment is declared in `pyproject.toml`,
> not remembered. A dependency that exists only in somebody's shell history is a
> dependency that breaks the next clone.

---

## 3 · The CUDA toolkit — the blocking step

`selfhostllm` hit this at L1 and recorded exactly what `apt` gives:

```bash
apt-get install -y cmake ccache nvidia-cuda-toolkit    # ~3 GB, several minutes
nvcc --version                                          # expect: release 12.0
```

⚠️ **`apt` provides CUDA 12.0.** In the sibling that was new enough for
llama.cpp and *not* new enough for two other engines, which needed 12.8 and
failed in different places. **Whether `audio.cpp` compiles against 12.0 is
unknown and is the first thing this setup will discover.** If it does not, the
choice is a manual toolkit install or the Vulkan backend — and Vulkan makes
every speed number incomparable with the published CUDA figures.

*Prediction, written before running: 12.0 will be enough, because `audio.cpp`
is ggml-based and llama.cpp built fine against it.*

> ✅ **CONFIRMED 2026-09-17.** `nvcc` was already installed at 12.0.140, and
> `audio.cpp` built clean against it: 463 targets, `rc=0`, **zero errors**, with
> `CUDA architectures: 86`. The runtime confirms it reaches the cards:
> `ggml_cuda_init: found 3 CUDA devices ... compute capability 8.6`.

---

## 4 · audio.cpp, built with CUDA

```bash
cd $SELFHOSTAUDIO_ROOT/engines
git clone --depth 1 https://github.com/0xShug0/audio.cpp audiocpp
cd audiocpp
export PATH=/usr/local/cuda/bin:$PATH

scripts/build_linux.sh --backend cuda --cuda-arch 86 \
  --target audiocpp_cli --target audiocpp_server
```

`--cuda-arch 86` is this card's compute capability, and it is the value
`audio.cpp`'s own documentation uses as its worked example. Without it the build
compiles for a dozen architectures and takes far longer for no benefit.

Output lands in `build/linux-cuda-release/`.

| Flag | Why |
|---|---|
| `--backend cuda` | the prebuilt Linux packages are **CPU and Vulkan only** |
| `--cuda-arch 86` | `sm_86` — Ampere, this card |
| `--model-set` | optional: build only named families, for a faster compile |

A narrower build, once the ladder is known:

```bash
scripts/build_linux.sh --backend cuda --cuda-arch 86 \
  --model-set custom --models kokoro,voxcpm2,ace_step,yue2 \
  --target audiocpp_cli --target audiocpp_server
```

Confirm the backend is really CUDA and not a silent fallback — **this is the
check that matters**, because a CPU fallback produces correct audio slowly and
looks like success:

```bash
build/linux-cuda-release/bin/audiocpp_cli --version
nvidia-smi          # during a run: the card should be busy, not idle
```

---

## 5 · Getting a model

```bash
planning/fetch-model.sh <owner>/<repo> <path/inside/repo.gguf>
```

`--http1.1` is not decoration: HTTP/2 gets throttled on large downloads and
stalls. `-C -` resumes rather than restarting. `setsid` means a closed SSH
session does not take the download with it.

The first one, deliberately the smallest:

```bash
planning/fetch-model.sh audio-cpp/audio.cpp-gguf Kokoro-82M-GGUF/kokoro-82m-f16.gguf
```

Check it finished — a truncated GGUF is a valid-looking file of the right name
and the wrong length:

```bash
curl -sI -L "https://huggingface.co/audio-cpp/audio.cpp-gguf/resolve/main/<path>" \
  | grep -i x-linked-size
stat -c %s models/gguf/<file>
head -c 4 models/gguf/<file> | xxd        # must read GGUF
```

---

## 6 · L0 · make a sound

```bash
build/linux-cuda-release/bin/audiocpp_cli \
  --task tts --family kokoro \
  --model $SELFHOSTAUDIO_ROOT/models/gguf \
  --backend cuda --threads 8 \
  --text "The box is finally speaking." \
  --out $SELFHOSTAUDIO_ROOT/runs/l0-first/s_short.wav --log
```

**Then read the file, not the model card:**

```bash
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,bits_per_raw_sample,duration \
        -of default=nw=1 runs/l0-first/s_short.wav
```

That output is the L0 checkpoint. Sample rate, channels, bit depth and duration
**come from the file**, because the card is a claim and the file is a
measurement. `selfhostllm` caught itself quoting "40 TFLOPS" from a spec sheet
in a chapter that claimed every number was measured; the measured figure was
36.59.

---

## 7 · Serving it

```bash
build/linux-cuda-release/bin/audiocpp_server \
  --ui --backend cuda --host 0.0.0.0 --port 8095
```

⚠️ **`--host 0.0.0.0`, never localhost.** The single most common
"works on the server, not from my laptop" problem, and it is one flag. The Mac
reaches the box at `http://10.0.0.20:8095`.

**Port choice:** `8086`, `8090` and `11434` are taken by the siblings. Check
before binding:

```bash
ss -ltnp | grep -v 127.0.0.1
```

---

## 8 · Measuring

Every model is measured by the same script with the same frozen prompts:

```bash
python3 bench/run.py --family kokoro --level L0 --quant F16 \
        --label "L0 · Kokoro-82M · F16"
python3 bench/table.py            # rebuild the comparison from results/
```

Results land in `bench/results/<run-id>.json`, one per run, and the table reads
those files and nothing else — so **a number that was never measured cannot
appear in it.**

---

## Rules worth keeping

1. **Never stream a long job over SSH.** Launch detached, return, poll. A
   four-minute song at RTF 0.8 is a three-minute foreground job; a 24-take
   listening test is not.
2. **Bind servers to `0.0.0.0`**, never localhost.
3. **Check every card's memory after a run**, not just the one you meant to use.
4. **Confirm the backend is CUDA.** A CPU fallback is correct and slow, and
   looks exactly like success.
5. **Use uv, not pip.** Declare dependencies in `pyproject.toml`.
6. **A number not measured on this machine is an estimate**, and must say so.
7. **Check `nvidia-smi` before believing a memory error.** In the sibling, a
   "model too large" error was a different engine still holding 6.8 GB.
