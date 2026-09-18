# Self-Hosted Audio AI — PRD

*From "the box is silent" to "the box has a voice, and it can sing." On three
consumer GPUs, one long night at a time.*

*Third sibling to [`selfhostgenai`](../selfhostgenai/) (MiniMax-H3 33B video on
8 GB) and [`selfhostllm`](../selfhostllm/) (the serving ladder, L0 → L4).
Same box, same rule: **every number measured, nothing invented.***

Status: **DRAFT v0.1** · 2026-09-15 · scaffolded, nothing run

---

## 1 · The mission

```
selfhostgenai :  run a 33B model nobody thought would fit        (done)
selfhostllm   :  understand serving deeply enough to build the
                 engine, the agent, and eventually the model     (done to L4)
selfhostaudioai: make the box speak and sing — and prove it      (this)
```

Two products, both of which people currently rent by the month:

- **Speech** — the ElevenLabs shape. Type a sentence, get a voice. Then get a
  *specific* voice: designed from a description, or cloned from a clip.
- **Music** — the Suno shape. Type a style and some lyrics, get a finished song
  with vocals and accompaniment.

Both are now within reach of this hardware, and the survey in
[`planning/MODELS.md`](planning/MODELS.md) says why with dated evidence rather
than recall.

### The founding honesty

The first version of this plan chose a model from the assistant's training data.
**Five of the models that matter were published after that cutoff**, and the
leading one was six days old. That mistake is recorded here on purpose, because
it is the same class of mistake as quoting a vendor spec sheet as a measurement:
*confident, cheap, and wrong.*

Currently in the fog, and to be explainable out loud by the end:
*neural audio codec, residual vector quantization, mel-spectrogram, vocoder,
flow matching for audio, RTF, AR vs NAR, semantic vs acoustic tokens, speaker
embedding, WER/CER, MUSHRA, zero-shot cloning.*

### What is genuinely new here

Neither sibling had to solve this, and it is the reason Part II exists:

> **`selfhostllm` Part I ended with a byte-identical output hash.** Two engines
> either computed the same thing or they did not. **Audio has no such anchor.**
> A waveform differing in every sample can sound identical; one differing in a
> few samples can sound broken.

Everything downstream — "is Q4 good enough", "is our engine correct", "is the
model we fine-tuned better" — is opinion until that is solved. So it gets solved
before any music is generated, not after.

---

## 2 · The arc

```
PART I    THE SOUND   get audio out, one card, our engine    L0 -> L2   the foundation
PART II   THE EAR     how audio gets scored                  L3         the instrument
PART III  THE SONG    music, the Suno shape                  L4 -> L5   the headline
PART IV   THE WALL    8 GB, quantized, long-form, 3 cards    L6         where the box fights
PART V    OURS        our own voice, our own model           L7         the long nights
```

**Part I is single-card, enforced.** One variable at a time — the same
constraint `selfhostllm` put on its Part I, and for the same reason. Every model
on the shortlist fits one card once quantized, so this costs nothing.

**Part II is second, not last.** See §1. It is the load-bearing decision in this
document.

**Part IV is separate because 8 GB is the whole point.** Third-party numbers say
YuE2 at Q4_0 peaks at 7,755 MiB against an 8,192 MiB card. That is a 437 MiB
margin measured on somebody else's hardware. Part IV is where that either holds
or becomes the project's defining problem.

---

## 3 · The box

Full detail, and what is audio-specific about it:
[`planning/HARDWARE.md`](planning/HARDWARE.md).

```
Host    : root@dalang-Z9PE-D8-WS   via Tailscale 100.122.45.32
GPU     : 3x RTX 3060 Ti · 8 GB each · 24 GB total
          Ampere sm_86 · 448 GB/s each · no NVLink · bf16 YES · FP8 NO
CPU/RAM : 2x Xeon E5-2665, 32 threads · 125 GB RAM
Disk    : 879 GB, 431 GB free        <- measured 2026-09-15; was 585 GB on 09-11
Present : git, Python 3.12, torch 2.11.0+cu128 (in the H3 venv)
Absent  : nvcc, uv, tmux, docker     <- nvcc is now BLOCKING, see §8 Q2
Busy    : all three cards hold a llama-server from selfhostllm
```

**Three cards, and audio may not want them split.** Unlike the siblings, nothing
here needs splitting — everything fits one card. That turns three cards into
three *slots*: three models compared simultaneously, or three seeds of the same
prompt in parallel. The second is not a luxury: **best-of-8 is how YuE2's
headline score was produced**, so parallel seeds are a quality lever, not a
throughput one.

---

## 4 · The math — what fits, and what it costs

Predictable on paper before anything is installed. When measurement disagrees
with the paper, *that gap is the finding* and gets written up.

### 4.1 The memory budget

```
VRAM = weights + activations + working buffers + ~1 GB CUDA context
```

- **weights** — the model file, sized by quantization. Q4_0 is roughly a quarter
  of bf16; Q8_0 roughly a half.
- **activations** — the intermediate numbers produced while generating. For a
  diffusion or flow-matching model this scales with **how long the audio is**,
  because the whole clip is denoised as one sequence.
- **working buffers** — temporaries inside matrix multiplication kernels.
- **CUDA context** — fixed overhead, roughly 1 GB, and unavoidable.

**The prediction this project starts with**, from the third-party table in
[MODELS.md](planning/MODELS.md):

```
YuE2-3B Q4_0    weights 2.48 GiB + VAE 0.25 GiB  =  2.73 GiB
                measured peak (RTX 5090)         =  7.57 GiB
                therefore not-weights            =  4.84 GiB   <- 64% of the total
```

> **Weights are the minority of the footprint.** Roughly two-thirds of peak VRAM
> is activations, buffers and context — *not* the model.

If that holds here, it is the same shape as `selfhostgenai`'s founding finding:
the 8 GB wall was a **2.24 GB `fast_int8_mm` temporary**, not the weights, not
attention, not the feed-forward network. **Found by profiling, not guessing** —
and the lever, if one is needed in Part IV, is likely to be in the same place.

*Estimate until measured on this box.*

### 4.2 Speed — real-time factor

```
RTF = wall_clock_seconds / audio_duration_seconds
```

`RTF < 1` means faster than real time: a four-minute song in under four minutes.
It is the one number a user feels, and it replaces `tok/s` from the sibling.

Third-party: YuE2 Q4_0 at **RTF 0.1997 on an RTX 5090**. That card's memory
bandwidth is roughly 4× the 3060 Ti's 448 GB/s.

```
if bandwidth-bound   ->  RTF ~ 0.8 here      still faster than real time
if compute-bound     ->  different, and the gap is a chapter
```

**Which one it is, is the first real measurement of Part III.** The sibling's
formula `tokens_per_sec ≈ bandwidth / bytes_read_per_token` is the tool for
deciding — the audio analogue reads the model once per denoising step.

### 4.3 Why audio is cheap, and where it stops being cheap

Raw audio is a torrent of numbers. Nothing generates it directly.

```
48 kHz stereo                    =  96,000 samples per second
a 25 Hz latent, 32 channels      =     800 numbers per second
compression                      =     120x
```

*Derived from the latent frame rates stated on the model cards — MiniMax-Music3
says 25 frames/s, ACE-Step's language model is 5 Hz, Qwen3-TTS is 12 Hz.*

That 120× is why a four-minute song is tractable on an 8 GB card at all, and it
is the same trick as the video VAE in `selfhostgenai`: **the transformer never
touches a sample.**

Where it stops being cheap is **length**. Attention over the whole clip means
cost grows faster than duration — the identical wall `selfhostgenai` hit with
15-second video and solved with chunk-and-chain and a ring. A song is four
minutes. **That is Part IV.**

### 4.4 Disk

```
48 kHz stereo 16-bit  =  192,000 bytes/s  =  11.5 MB per minute of audio
```

A single listening test — 8 takes × 4 minutes — writes **~370 MB** before
anything is kept. The shortlist of models is ~30 GB. Against 431 GB free and two
siblings consuming it, **generated audio needs a retention policy from day one**,
not after the disk fills. *Derived; see [HARDWARE.md](planning/HARDWARE.md).*

---

# PART I · THE SOUND — get audio out, on one card

**The method, inherited and unchanged:**

```
CONTROL the task.  VARY the model.
```

One fixed prompt set, one fixed seed, one card. Then every difference is
attributable to the model or the quantization, not the workload.

### L0 · Kokoro-82M — "make it talk" *(~1 hour)*

0.34 GiB, Apache-2.0, 11.5M downloads. Deliberately the least interesting model
on the shortlist.

- **Build:** get a `.wav` out of the box and onto the Mac. Play it.
- **Teaches:** the shape of the path — text in, samples out, sample rate,
  channels, bit depth, and where the file actually goes.
- **Checkpoint:** what sample rate, how many channels, what format, how many
  megabytes per minute — **read off the file, not off the card.**
- **Deliberate ignorance:** we do not study Kokoro's internals. It is the
  control, not the subject. This is exactly the role Ollama played at L0 in
  `selfhostllm`.

### L1 · audio.cpp — "make it ours to run" *(the engine)*

The rung everything else stands on.

- **Build:** install the CUDA toolkit, compile with
  `--backend cuda --cuda-arch 86`, run Kokoro through it, confirm it matches L0.
- **Teaches:** GGUF for audio, quantization levels, what `audio.cpp` calls a
  *family*, *session* and *route*, and the CPU/Vulkan/CUDA backend split.
- **Checkpoint:** the same prompt and seed through the Python reference path and
  through `audio.cpp` — and an honest written answer to *do these sound the
  same, and how do we know?* **This is where Part II gets its motivation**, and
  it is deliberately placed before Part II so the need is felt, not asserted.
- **Blocking:** `nvcc` is absent. See §8 Q2.

### L2 · VoxCPM2 — "make it anyone's voice"

4.62 GiB, Apache-2.0, 30 languages, 48 kHz out, voice design **and** cloning.

- **Build:** design a voice from a text description. Then clone one from a clip.
  Then sweep quantization: bf16 → Q8 → Q4, same text, same seed.
- **Teaches:** speaker embeddings, zero-shot cloning, what a reference clip
  actually has to contain, and where quantization first becomes audible.
- **Checkpoint:** predict which quantization level breaks first, **write the
  prediction down before listening**, then run the L3 harness against it.
- **The finding to chase:** does Q4 hurt *intelligibility* (measurable) or
  *naturalness* (not)? They are different failures and the distinction is the
  whole of Part II.

### The Part I chain

```
L0 Kokoro     it makes a sound     -> a reference, and a format
L1 audio.cpp  we run it ourselves  -> GGUF, CUDA, quantization
L2 VoxCPM2    it is a voice        -> cloning, design, the first quality question
```

---

# PART II · THE EAR — the measuring instrument

**Not a detour, and not last.** This part produces the thing every later claim
depends on. `selfhostllm` wrote the rule; audio is where it gets expensive to
ignore.

### L3a · What can be scored objectively

| Instrument | Answers | Blind to |
|---|---|---|
| **WER / CER** | did it say the words? | tone, naturalness, whether it sounds human |
| **Speaker similarity** | is it the same voice? | whether that voice sounds *good* |
| **RTF, peak VRAM** | did it fit, was it fast? | everything about quality |
| **Null test** *(A−B)* | are two outputs bit-identical? | whether a difference is audible |

The null test is the closest audio gets to the sibling's output hash, and its
limits must be written down the day it is built: **it detects difference, never
audibility.**

### L3b · The listening test — `listening/`

The part with no precedent in either sibling. Non-negotiable properties:

- **Blind.** Files renamed before playback, key held separately.
- **Seeded and recorded.** Prompt, seed, model, quantization, git commit.
- **Written down.** One JSON per session, same discipline as `bench/results/`.
- **Honest about n.** Two people listening is two people, and the file says so.

### L3c · WildSongBench

192 prompts, 9 metrics, published 2026-09-09, **with Suno v5 and v6 already
scored in the table.** The nearest thing music generation has to an anchor.

- **Checkpoint:** run it against whatever Part III produces and put our number
  next to theirs, with the protocol difference (best-of-8 vs single-shot) stated
  in the same sentence.

### ⚠️ Written before Part III leans on it — what the ear CANNOT see

Deliberately written now, the way `selfhostllm` wrote the limits of its agent
harness before Part V used it:

- **WER cannot hear tone.** A monotone that pronounces every word scores 100%.
- **Speaker similarity cannot hear quality.** Recognisably the right person, and
  still a phone call.
- **WildSongBench is the YuE2 authors' own benchmark**, and its top score is theirs.
- **Best-of-8 is not one click.** Every headline in [MODELS.md](planning/MODELS.md)
  marked Bo8 measures something a user does not get.
- **We are not a listening panel.** Two ears in one room, and we like our own output.

---

# PART III · THE SONG — the Suno shape

### L4 · ACE-Step 1.5 — "make it a song" *(MIT)*

9.40 GiB across four files, each of which fits a card alone.

- **Build:** a full song from a style prompt and lyrics. Then cover, repaint,
  and vocal-to-BGM. Then the three language-model planner sizes — 0.6B, 1.7B,
  4B — against the same prompt.
- **Teaches:** how a language model *plans* a song and a diffusion transformer
  *renders* it; why an 8-step turbo model exists; what a "structured caption" is.
- **Checkpoint:** the card claims *under 10 seconds on an RTX 3090* and *under
  4 GB of VRAM*. **Predict both for a 3060 Ti before running, then measure.**

### L5 · YuE2-3B — "make it a good song" *(non-commercial)*

The quality ceiling, and the model that claims to beat Suno.

- **Build:** bf16, Q8_0, Q4_0 — same lyrics, same style, same seed, same VAE
  precision held constant, then varied. Long-form: the four-minute run.
- **Teaches:** AR–NAR mixture-of-transformers, symbolic planning
  (`cot=off|full|melody`), flow matching to acoustic latents, editable scores.
- **Checkpoint (the exam):** reproduce the published table on our hardware —
  **RTF and peak VRAM for all three quantizations** — and explain the gap
  against the RTX 5090 figures in terms of §4.2. *A gap that gets explained is a
  chapter. A gap that gets ignored is a lie.*
- **The finding to chase:** **does 7,755 MiB actually fit 8,192 MiB here?**
  437 MiB of margin on somebody else's card is not margin.

### Measurement protocol (non-negotiable)

Every model reports the same numbers on the same prompts, or the comparison is
meaningless. Fixed across the ladder: the prompt set, the seed, the sampling
settings, the output format.

| Metric | Why |
|---|---|
| **RTF** | the number a user feels |
| **Peak VRAM**, per card | did the memory model predict this? |
| **Time to first audio** | the audio analogue of TTFT |
| **Max duration** before failure | the real capacity limit |
| **WER / speaker similarity** | objective quality, where it applies |
| **Listening score** | the part only ears can answer — and its `n` |

Plus, every level: **predicted vs measured**, with a written explanation of any gap.

**House rule, inherited:** a number not measured on this box is labelled an
estimate, or it does not appear.

---

# PART IV · THE WALL — 8 GB, and four minutes

Where the box fights back. Each of these is a real question, not a chore:

- **The quantization cliff.** Where does Q4 stop being acceptable — and is the
  answer different for *speech* than for *music*? (Words versus timbre.)
- **Length.** Attention over a four-minute clip. `selfhostgenai` solved exactly
  this shape for video with chunk-and-chain and a ring across three cards. **It
  is attention, not video — the ring should port.**
- **Three cards as three slots.** Parallel seeds for best-of-N, or three models
  live at once. Measure whether the PCIe topology (`SYS` vs `PHB`) matters when
  nothing is being split.
- **Where the memory actually goes.** §4.1 predicts two-thirds is not weights.
  Profile it. If the lever is a single temporary buffer, that is the first
  sibling's finding happening twice, and it is worth a chapter either way.

---

# PART V · OURS — the long nights

Deliberately not specified in detail. `selfhostllm` reached Part V with a real
eval and a real engine, and the shape of Part V was better for having waited.

The ladder within the ladder, cheapest first:

```
T1  a voice        fine-tune a speaker on our own recordings         hours
T2  a style        fine-tune a music model on a chosen genre         days
T3  a pipeline     text -> lyrics -> song -> master, end to end      weeks
T4  a model        our own, from scratch                             long nights
```

T3 is the one that is actually a *product*, and it is the one the siblings'
combined work makes possible: `selfhostllm`'s agent writes the lyrics, this
project sings them, `selfhostgenai` makes the video.

---

## 5 · Scope

### In scope
Speech and music generated locally · one engine (`audio.cpp`) built and
understood · an honest scoring method for a medium with no output hash · a
measured comparison across models and quantizations · a studio worth using ·
and something of our own at the end.

### Explicitly NOT in scope
- **Training a music model from scratch.** §4 will say why with arithmetic, once
  measured. T4 is aspiration, not plan.
- **Voice cloning of real people without consent.** A clone of a stranger's voice
  is not a demo. Our own voices, licensed datasets, or synthetic.
- **Real-time / streaming latency as a goal.** Inherited principle,
  `selfhostgenai` 2026-09-06: *"we not charge the speed... its not our style."*
  Speed is a **measurement**, never a target.
- **A music catalogue.** We are building the instrument, not the discography.

---

## 6 · Success criteria

1. **The box speaks.** A voice, designed or cloned, that survives a blind test.
2. **The box sings.** A complete song — lyrics, vocals, accompaniment — generated
   end to end on 8 GB.
3. **The ear exists.** A scoring method whose limits are written down, and which
   ranks models defensibly rather than agreeably.
4. **The math predicts.** Peak VRAM and RTF for an untried configuration,
   predicted within 20% *before* running it.
5. **The vocabulary is owned.** Every term in §7 explainable out loud, with a
   number from our own box attached.
6. **The published claims are checked.** The third-party table in
   [MODELS.md](planning/MODELS.md) reproduced on this hardware — confirmed or
   destroyed, and either is a result.
7. **⭐ Something is ours.** A voice, a style, or a pipeline that did not exist
   before, running on our own box, scored by our own ear.

The real test, stated the way the siblings state it:

> **Can a stranger hand us a paragraph and a genre and walk away with a finished
> song — generated on three second-hand 8 GB cards, with a number attached to
> why it is good?**

---

## 7 · The vocabulary to own

From fog to fluent. Each term ends with a plain-words definition **and a number
from our box.**

**Representation:** sample rate · bit depth · channels · mel-spectrogram ·
neural audio codec · residual vector quantization · latent frame rate ·
semantic vs acoustic tokens

**Generation:** autoregressive vs non-autoregressive · flow matching · diffusion
step · classifier-free guidance · vocoder · VAE decode

**Speech:** zero-shot cloning · speaker embedding · voice design · prosody ·
WER / CER · streaming vs non-streaming

**Music:** symbolic planning · score conditioning · stem / repaint / cover ·
structured caption · best-of-N

**Serving:** RTF · time to first audio · peak VRAM · GGUF · Q4_0 / Q8_0 ·
`sm_86` · session and route

**Judgement:** null test · blind test · MUSHRA · the difference between
*measurable* and *audible*

---

## 8 · Open questions — decide before building

1. **Does the non-commercial licence disqualify YuE2-3B?** CC-BY-NC-4.0. If the
   output is meant to be sold, YuE2 becomes a benchmark-only ceiling and
   ACE-Step 1.5 (MIT, clean training data) becomes the product. This changes
   which model is the *subject* and which is the *control*, so it changes Part
   III. **Blocking for L5, not for L0–L4.**

2. **Install the CUDA toolkit on the box?** `nvcc` is absent; `audio.cpp` ships
   no Linux CUDA binary. Without it: Vulkan or CPU, and every speed number is
   uninterpretable. **Blocking for L1. Leaning: yes, obviously — but it is a
   change to a machine two other projects depend on, so it is asked, not
   assumed.**

3. **Reclaim disk, or live inside 431 GB?** The siblings hold 348 GB and are
   still growing. Audio adds ~30 GB of models plus generated output at 11.5 MB
   per audio-minute. *Leaning: live inside it, with a retention policy from day
   one.*

4. **Is stopping the sibling's `llama-server` allowed?** It currently holds all
   three cards. Nothing here can run beside it. *Needs an answer before L0.*

5. **Speech first or music first?** The ladder above does speech first, because
   Kokoro is the cheapest possible proof of path and WER is the cheapest possible
   eval. But music is the headline. *Leaning: speech first, and it is a short
   Part I.*

6. **What is the listening test's `n`?** Two people is two people. Does this
   project recruit listeners, or state its `n` honestly and move on?
   *Leaning: state it honestly. A dishonest 1.0 is worse than a small n.*

7. **Where does Part V point?** T1 a voice, T2 a style, T3 the pipeline, T4 a
   model. It does not need answering yet, but it shapes what data gets collected
   along the way — and **T3 is the one that joins all three siblings together.**

---

## 9 · The shape of the whole thing

```
PART I    L0 Kokoro     it makes a sound        hours
          L1 audio.cpp  we run it ourselves     days      <- blocked on nvcc
          L2 VoxCPM2    it is a voice           days
PART II   L3 the ear    the instrument          weeks     <- the load-bearing part
PART III  L4 ACE-Step   it is a song            weeks
          L5 YuE2       it is a good song       weeks
PART IV   L6 the wall   8 GB, four minutes      weeks
PART V    L7 ours       T1 voice   / T2 style
                        T3 pipeline / T4 model  long nights
```

Each part is usable on its own. Nothing here is scaffolding that gets thrown
away — the engine from Part I runs everything after it, the ear from Part II
scores everything after it, and the pipeline in Part V is the three siblings
finally joined: **the agent writes the words, this project sings them, and the
first sibling makes the picture.**

---

*Siblings: [`../selfhostgenai/`](../selfhostgenai/) · [`../selfhostllm/`](../selfhostllm/)
Same box, same rule: every number measured.*

🐢🔥🔊
