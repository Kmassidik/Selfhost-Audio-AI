# The survey — what is actually on Hugging Face

*Pulled live from the Hugging Face API on **2026-09-15**. Every figure here is
either **from the model card** or **from the API**, and is labelled as such.
**Nothing in this file was measured by us.** The moment anything is run on the
box, the measured number replaces the claim and the claim is kept beside it.*

> **Why this file exists.** The first attempt at choosing a model was made from
> the assistant's training data, which ends in May 2026. Five of the models that
> matter here were published **after** that date, and the leader was six days old
> on the day of the survey. Recall is not research. This file is the correction,
> and it carries a date because it will rot.

---

## 1 · The engine — `audio.cpp`

This is the finding that shapes everything else.

```
github.com/0xShug0/audio.cpp     2,720 stars · 308 forks · C++ · pushed 2026-09-15
"An all-in-one, pure C++ inference engine for audio models, powered by ggml.
 Supports TTS, STT, VAD, voice conversion, music generation, and more.
 No Python dependency."
```

It is llama.cpp for audio: **GGUF weights, quantization, a CUDA backend, a
server mode with an embedded WebUI**, and 74 model families already converted in
[`audio-cpp/audio.cpp-gguf`](https://huggingface.co/audio-cpp/audio.cpp-gguf)
(590 GiB of GGUF, **3.48M downloads**).

**Why it matters to this box specifically:** every lesson from `selfhostllm`
Part I — GGUF, quantization levels, layer offload, `-ngl` sweeps, the memory
model — transfers to audio without translation. And its own build documentation
uses **`--cuda-arch "86;89"`** as the worked example. `86` is `sm_86`. That is
the RTX 3060 Ti.

**Two obstacles, both real:**

| | |
|---|---|
| Prebuilt Linux binaries are **CPU and Vulkan only** | CUDA needs a source build |
| **`nvcc` is absent on the box** | the CUDA toolkit is a prerequisite, not a detail |

Without CUDA we are on Vulkan or CPU and every speed number becomes
uninterpretable. This is the first blocking decision — see [QUEUE](QUEUE.md).

---

## 2 · Music — the Suno shape

Sorted by what the decision actually turns on: **licence, then quality, then fit.**

### The two real candidates

| | `m-a-p/YuE2-3B` | `ACE-Step/Ace-Step1.5` |
|---|---|---|
| Published | **2026-09-09** (6 days before this survey) | 2026-01-23 |
| API traction | ♥477 · trending #1 in `text-to-audio` | ♥855 · 56,082 downloads |
| Repo size | 6.79 GiB | 9.40 GiB |
| **Licence** | ⚠️ **CC-BY-NC-4.0 — non-commercial** | ✅ **MIT** |
| Training data | not stated on the card | licensed + royalty-free + synthetic, **stated** |
| Output | **48 kHz stereo**, songs up to ~5 min in the demos | full songs, card claims up to 10 min |
| Architecture | AR–NAR Mixture-of-Transformers → flow matching → VAE | Qwen3 LM planner + DiT (turbo: 8 steps) |
| Editing | editable ABC score, melody+chords, cover, agentic editing | cover, repaint, extract, vocal-to-BGM, "lego" |
| GGUF | ✅ `audio-cpp/Yue2-3B-GGUF` | ✅ `audio.cpp-gguf/ACE-Step1.5-GGUF` |

**The quality claim, quoted rather than paraphrased.** From the YuE2-3B card:

> YuE2 (best-of-8) achieves the highest SongBench average among all evaluated
> open and proprietary models: **6.9632**, compared with **6.8721** for Suno v5,
> **6.5562** for Suno v6, and **6.4195** for Suno v6 Wild.

Dated 2026-09-12 on `m-a-p/WildSongBench`, 192 prompts, nine metrics. It is the
model author's own benchmark and it is best-of-8 rather than single-shot — both
facts belong next to the number. **It is a claim, not a measurement of ours.**

**ACE-Step's claim is a different one**, and aimed at a different buyer:

> Extreme Speed: Generates a full song in under 2 seconds on an A100 and under
> 10 seconds on an RTX 3090. Consumer Hardware Friendly: Runs locally with less
> than 4GB of VRAM. Commercial-Ready: You can strictly use the generated music
> for commercial purposes.

ACE-Step 1.5 splits into four files, and **each one fits a card on its own**:
DiT turbo 4.46 GiB · LM 3.45 GiB · Qwen3-Embedding-0.6B 1.11 GiB · VAE 0.31 GiB.

### Third-party measurement — YuE2 under `audio.cpp`

From the `audio-cpp/Yue2-3B-GGUF` card. **Measured on an RTX 5090, not by us:**

| Combo | Audio | Wall | RTF | Peak VRAM |
|---|---:|---:|---:|---:|
| BF16 main + F32 VAE | 224.96 s | 60.46 s | 0.2688 | 12,535 MiB |
| Q8_0 main + F16 VAE | 194.84 s | 38.81 s | 0.1992 | 8,867 MiB |
| **Q4_0 main + F16 VAE** | **221.12 s** | 44.15 s | 0.1997 | **7,755 MiB** |

**7,755 MiB against a 8,192 MiB card.** Nearly four minutes of music from one
second-hand 8 GB GPU — *if* that peak reproduces here.

**It may not, and the reason is bandwidth, not memory.** A 5090's memory
bandwidth is roughly four times a 3060 Ti's 448 GB/s. If generation is
bandwidth-bound — as decode is for a language model — then **RTF ≈ 0.8 is the
estimate for this box**, still about real time. If it is compute-bound the gap
is different again. Which one it is, is the first thing Part III measures.

GGUF sizes: `yue2-3b-bf16` 6.76 GiB · `q8_0` 3.97 GiB · `q4_0` **2.48 GiB** ·
`yue2-vae-f32` 0.49 GiB · `vae-f16` 0.25 GiB.

### Also surveyed, not chosen

| Model | Size | Licence | Why not first |
|---|---|---|---|
| `MiniMaxAI/MiniMax-Music3` | **53.41 GiB** | not stated on the card | See below — interesting for a different reason |
| `stabilityai/stable-audio-3-medium` | 9.73 GiB | `other` (Stability community) | Licence gate; 97k downloads makes it a strong control |
| `google/magenta-realtime-2` | 14.52 GiB | CC-BY-4.0 | Real-time framing, not song-shaped |
| `facebook/musicgen-*` | — | — | 2023. The old baseline. Useful only as a floor |

**MiniMax-Music3 deserves its own line.** Same vendor as the MiniMax-H3 already
running on this box: an 8B global LLM + a 0.6B local LLM + flow-matching
synthesis, 32 kHz stereo. Its card says:

> With automatic CPU offloading, generation takes in ~22 GB; additionally
> streaming the language model layer by layer makes it fit even 8 GB video cards.

That is **Memory-First Execution** — the technique `selfhostgenai` invented for
H3 on this exact hardware — now shipped as vendor guidance. It is not the first
model to run, but it is the most interesting thing in this table.

---

## 3 · Speech — the ElevenLabs shape

| Model | Size | Licence | What it does | Traction |
|---|---|---|---|---|
| **`openbmb/VoxCPM2`** | 4.62 GiB | ✅ **Apache-2.0** | 2B, **30 languages, 48 kHz out**, voice *design* from text **and** cloning from a clip | ♥1612 · 384k dl |
| **`tencent/AuK`** | 6.30 GiB | ✅ **MIT** | one instruction interface: TTS, cloning, editing, enhancement, **source separation** | ♥220 · trending #1 |
| `Qwen/Qwen3-TTS-12Hz-1.7B` | 4.21 GiB | ✅ Apache-2.0 | streaming + non-streaming, 10 languages, 3-second clone on `-Base` | ♥1967 · **2.6M dl** |
| **`hexgrad/Kokoro-82M`** | **0.34 GiB** | ✅ Apache-2.0 | small, fast, plain | ♥6917 · **11.5M dl** |
| `BreezeBlue/Breeze-TTS-2` | — | Non-commercial | card claims #1 open-weight on Artificial Analysis | ♥552 |
| `bosonai/higgs-tts-3-4b` | 8.68 GiB | `other` | expressive / controllable | ♥763 |
| `k2-fsa/OmniVoice` | — | — | **600+ languages**, card claims RTF 0.025 | ♥1384 · 1.2M dl |

**Kokoro is the L0.** 0.34 GiB and eleven and a half million downloads. It is
not the best model here and it is not meant to be — it is the *reference*, the
same role Ollama played in `selfhostllm`: prove the path end to end with
something that cannot fail for interesting reasons.

**VoxCPM2 is the L2 candidate.** Apache-2.0 with no commercial gate, 48 kHz out
(via the AudioVAE's built-in super-resolution — no external upsampler), and it
does both halves of the ElevenLabs product: *design a voice from a description*
and *clone a voice from a clip*. Its card claims RTF ~0.3 on a 4090 — again, a
faster card than ours, so treat it as an upper bound.

**AuK is the one to watch.** MIT, and a single natural-language instruction
interface across generation, editing, enhancement and separation is a genuinely
different product shape. It is also four weeks old with 1,928 downloads. New is
not the same as good.

---

## 4 · The eval — and why this section is the important one

`selfhostllm` could end Part I with an **output hash**: at temperature 0, two
engines either produced the same bytes or they did not. **Audio has no such
anchor**, and every listening judgement is a person's opinion unless something
holds it down.

What exists to hold it down:

| Instrument | For | What it gives |
|---|---|---|
| **`m-a-p/WildSongBench`** | music | 192 prompts · 9 metrics · published 2026-09-09 · **Suno v5/v6 scores already in the table** |
| **WER / CER** | speech | did the model say the words? Scriptable, objective, and blind to whether it sounds human |
| **Speaker similarity** | cloning | is it the same voice? An embedding cosine, not an opinion |
| **Our own listening test** | everything | `listening/` — blind, seeded, recorded. The part no sibling had |

WildSongBench matters out of proportion to its size: it is a **192-prompt
benchmark with proprietary competitors already scored on it.** That is the
closest thing audio has to the byte-identical anchor, and it arrived six days
before this survey.

**What none of these can see** — written now, before Part III leans on them,
because `selfhostllm` learned to write this section early:

- WER cannot hear tone. A monotone robot that pronounces every word scores perfectly.
- Speaker similarity cannot hear *quality* — a clone can be recognisably the
  right person and still sound like a phone call.
- WildSongBench is the YuE2 authors' own benchmark. Its top score is theirs.
- **Best-of-8 is not single-shot.** Every headline number above that says Bo8
  measures a different thing from what a user gets on one click.

---

## 5 · Where this leaves the choice

Nothing is decided here — the decisions live in [PRD §8](../PRD.md) and
[QUEUE](QUEUE.md). What the survey establishes:

1. **The engine is `audio.cpp`**, and it needs the CUDA toolkit on the box.
2. **Music is a two-model comparison, not a pick.** YuE2-3B sets the quality
   ceiling; ACE-Step 1.5 is the one whose output can be sold. Running both is
   the siblings' own method — *control the task, vary the model* — and it costs
   2.48 GiB + 9.40 GiB, which this box can afford.
3. **Speech is VoxCPM2, with Kokoro-82M as the reference below it.**
4. **The licence question is a product question, not a technical one**, and it
   decides which of the two music models is the subject and which is the control.

---

## Sources

1. [Hugging Face Hub API](https://huggingface.co/docs/hub/api) — model listings, download
   and like counts, file sizes. Queried 2026-09-15; these figures move daily.
2. [audio.cpp](https://github.com/0xShug0/audio.cpp) — *0xShug0* — the engine, its
   build flags, and the GGUF conversion guide.
3. [WildSongBench](https://huggingface.co/datasets/m-a-p/WildSongBench) — *m-a-p, 2026* —
   the benchmark, its protocol, and the full nine-metric results table.
