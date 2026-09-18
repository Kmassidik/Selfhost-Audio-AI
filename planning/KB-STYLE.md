# Knowledge-base house style

**Inherited in full from
[`../../selfhostllm/planning/KB-STYLE.md`](../../selfhostllm/planning/KB-STYLE.md)**,
which is itself inherited from `selfhostgenai/planning/KB-REWRITE-SPEC.md`.
**Read that file first.** This one records only what audio changes.

The rule both siblings rest on carries over unchanged: **every number was
measured.** If a number is not measured on the box, it is labelled an estimate —
in that word — or it does not appear.

---

## Carried over without change

- **Page skeleton** — `<script type="text/markdown" id="md">`, then
  marked → mermaid → katex → app.js, **in that order**.
- **Never a blank line inside a raw HTML block.** `marked` terminates the block
  there and renders the rest as garbage, silently. Run `check.py` after every edit.
- **Every formula gets a symbol decoder** — every symbol, including the obvious
  ones, with a typical-value column and a worked instantiation, closing by naming
  **which term is the lever**.
- **Every acronym spelled out** at or near first use. No exceptions.
- **At most three sources per page**, each verified before committing.
- **Answer the title in the first sentence.** End with "The vocabulary you now
  own" and a one-line pointer to the next chapter.
- **No second person about the machine.** "The box", not "your box".
- **Be honest about failures.** Keep the disproved prediction, quote it, show
  what happened instead.
- **Say where a number came from** — measured / derived / estimate.

---

## 1 · The rule this project adds: a chapter about sound must be audible

A page that claims one file sounds better than another, and does not let the
reader hear both, is an opinion with styling. **The claim and the evidence go on
the same page.**

```html
<div class="listen"><span class="t">Q8_0 against Q4_0 — same prompt, same seed</span>
<figure><figcaption>Q8_0 · 3.97 GiB</figcaption>
<audio controls preload="none" src="audio/NN-q8.wav"></audio></figure>
<figure><figcaption>Q4_0 · 2.48 GiB</figcaption>
<audio controls preload="none" src="audio/NN-q4.wav"></audio></figure>
</div>
```

- `preload="none"` — always. A chapter with six players must not fetch six files
  on load.
- Every clip carries **what produced it**: model, quantization, seed, and the
  date. A clip with no provenance is decoration.
- **Both sides of a comparison, or neither.** Publishing only the good take is
  the audio version of rounding a number to look better.

## 2 · `knowledge-base/audio/` is the one place audio is committed

`.gitignore` excludes `*.wav` and `*.mp3` everywhere, because a repository is not
an audio host and generated takes live on the box. **This directory is the
deliberate exception**, and it is narrow:

| Rule | Why |
|---|---|
| **≤ 15 seconds** per clip | enough to hear a difference, not enough to be a song |
| **≤ 1 MB** per file — encode to MP3 or Opus, not WAV | a clone of this repo should not be a gigabyte |
| **Only clips a chapter actually references** | orphans accumulate and nobody deletes them |
| The full-length take stays in `runs/` **on the box** | the clip is the citation, not the artefact |

`check.py` enforces size and orphan rules. A chapter needing a four-minute
example links to the box; it does not commit it.

## 3 · Figures — waveforms and spectrograms

The sibling's chart rules hold: **inline SVG, no library**, one axis, direct
labels sparingly, and **the table is the accessible view**. Audio adds three:

- **A spectrogram is a chart, not a screenshot.** It needs axes with units —
  time in seconds, frequency in kilohertz — and a stated colour scale. A
  rectangle of colour with no axes proves nothing.
- **Say the sample rate next to any frequency axis.** A spectrum that stops at
  16 kHz because the model outputs 32 kHz looks identical to one that stops
  because the model is broken.
- **Amplitude is not loudness.** If a page compares "how loud" two takes are,
  it uses a measured loudness figure (LUFS), not the height of a waveform.

Palette, validated against the chapter surface `#0d1017`, unchanged from the
sibling: `#3987e5` · `#d95926` · `#199e70` · `#c98500`.

## 4 · Never describe a sound as if the description were the measurement

The failure mode specific to this project, and the easiest one to fall into:

> ❌ "Q4 sounds noticeably muddier in the high end."
>
> ✅ "Q4 scored 4.1 against Q8's 5.6 in a blind test, n = 2
> (`listening/2026-09-20-quant.json`). Both clips are below. The difference the
> listeners named was the high end; that is their words, not a measurement."

Adjectives about sound are **testimony**. They are allowed, they are often the
most useful thing on the page, and they are labelled as testimony with the `n`
attached. Testimony presented as measurement is the audio equivalent of quoting
a spec sheet — the exact violation the sibling caught itself committing with
"40 TFLOPS".

## 5 · The vocabulary of this project, for `check.py`

Audio terms a stranger cannot look up mid-sentence, to be added to the acronym
list as chapters introduce them:

```
RTF        real-time factor          WER   word error rate
CER        character error rate      VAE   variational autoencoder
GGUF       GPT-Generated Unified Format
RVQ        residual vector quantization
kHz        kilohertz — thousands of samples per second
LUFS       loudness units relative to full scale
AR / NAR   autoregressive / non-autoregressive
CFG        classifier-free guidance
codec      the compressor between a waveform and the numbers a model works on
latent     the compressed form; the model never touches a sample
vocoder    turns a compressed representation back into a waveform
timbre     what makes two instruments playing one note sound different
prosody    the rhythm and melody of speech, as opposed to its words
```

## 6 · Callouts

Unchanged from the sibling — `callout spec` · `truth` · `warn` · `danger` —
plus one:

| Class | Use for |
|---|---|
| `listen` | a comparison the reader is meant to hear, with both sides present |
