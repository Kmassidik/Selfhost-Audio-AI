# The ear, first results — and the instrument's own ceiling

*Lab notebook, 2026-09-18. Recogniser: Qwen3-ASR-1.7B q8_0 through audio.cpp,
CUDA, one card. Reference: the frozen prompt set.*

**Two results, and the second is more useful than the first.**

---

## 1 · Word error rate is zero. Everywhere.

| prompt | Kokoro bf16 | Kokoro q8_0 | VoxCPM2 q8_0 | Qwen3-TTS q8_0 |
|---|---:|---:|---:|---:|
| `s_short` (5 words) | 0.000 | 0.000 | 0.000 | 0.000 |
| `s_expressive` (12 words) | 0.000 | 0.000 | 0.000 | 0.000 |
| `s_paragraph` (66 words) | 0.000 | 0.000 | 0.000 | 0.000 |

Zero substitutions, zero deletions, zero insertions, every model, every prose
prompt, both quantizations. 66 reference words matched by 66 hypothesis words.

**This is a real result and a useless one at the same time.** Real: all three
models are fully intelligible on ordinary prose, and 8-bit quantization costs
nothing measurable in intelligibility. Useless: an instrument that returns the
same number for every subject cannot rank them.

> **The frozen prose prompts are too easy.** They were written to exercise
> prosody and length, not to break a recogniser. Discriminating between these
> models on intelligibility needs harder material — overlapping speech, rare
> proper nouns, dense technical vocabulary, non-native phonemes — and the
> prompt set is frozen, so that means **new ids, not edited ones.**

This is exactly the ceiling effect the sibling project hit from the other side:
its ten-task evaluation could not distinguish 8-bit from 4-bit, and it published
**"NOT defensible, p = 1.00"** rather than a tidier answer.

## 2 · The 1.87× disagreement, settled — and it is expansion

`s_normalize` is the prompt built from dates, decimals, percentages, an
abbreviation and a telephone number. Its reference text contains **digits**;
speech contains **words**; the recogniser writes words. Scoring one against the
other would mark every model catastrophically wrong and mean nothing, so this
prompt is reported **by transcript**.

**Kokoro — 25.48 s**
> On two thousand twenty-six **dash** zero nine **dash** fifteen, the box had four
> hundred thirty-one GB free... Call plus forty for twenty-seven thousand nine
> hundred forty-six zero nine five eight before five, thirty p.m.

**Qwen3-TTS — 22.16 s**
> On **26 June 2020**, the box had 431 goby free... Dr Chen's estimate was 36.59
> tiflops... Call +44 279460958 before 5:30 p.m.

**VoxCPM2 — 13.60 s**
> On 2026-09-15, the box had 431 gigabytes free, down from 585 gigabytes 4 days
> earlier. Dr. Chen's estimate was 36.59 **TF all plus**...

**The 1.87× is expansion, not omission.** Kokoro pronounces the separators —
it literally says "dash" — and reads the phone number digit by digit. That is
the most words any model could produce from this text, and it explains both the
25-second duration and the 5,209 MiB peak that `experiments/01` left open.

Nothing was skipped. The shorter file was not a model cutting corners.

## 3 · But the recogniser is in the loop, and it is not clean

Three things in those transcripts are wrong, and **it cannot be established from
here which component produced them.**

| In the transcript | Plausibly the speech model | Plausibly the recogniser |
|---|---|---|
| "431 **goby**" (for GB) | — | ✅ almost certainly |
| "36.59 **TF all plus**" | — | ✅ likely, mishearing TFLOPS |
| "**26 June 2020**" for 2026-09-15 | ✅ a real date error | ✅ a mishearing |

"Goby" settles the principle: **this recogniser demonstrably makes errors on
this material.** So the date discrepancy is a discrepancy in the *pipeline*,
and attributing it to Qwen3-TTS would be exactly the mistake
`experiments/01` was written about — a confident attribution to the variable
being looked for.

**It matters, because a date read as the wrong date is a correctness failure
that word error rate on prose would never surface**, and the only instrument
that settles it is a person listening to twenty-two seconds of audio. That is
the blind test from ch.13, and it is the first job it has.

## 4 · What this establishes about the ear itself

1. **Word error rate works, and has a ceiling.** It confirms intelligibility and
   confirms quantization is free. It cannot rank models that all score zero.
2. **The normalisation problem is structural, not a bug.** Any reference text
   containing digits is uncomparable to a transcript. Reporting those by
   transcript rather than by score is the honest handling, and it turned out to
   be where the actual finding was.
3. **The recogniser's own error rate is the floor.** Every score here is
   `Qwen3-ASR-1.7B q8_0`'s opinion, recorded in every result for that reason.
   Part III measures the recogniser itself, and until it does, these numbers
   have an unmeasured floor under them.
4. **The most informative output was not a number.** Four transcripts side by
   side answered a question three chapters had deferred. The score answered
   nothing.

## 5 · Open

- **Harder prompts**, as new frozen ids, so word error rate can discriminate.
- **Is "26 June 2020" the speech model or the recogniser?** Needs listening.
- **Measure the recogniser** against known-good human recordings, so the floor
  under every score above is a number rather than an assumption.
- **Speaker similarity** is still unbuilt, so nothing here says whether
  VoxCPM2's clone sounds like its reference.
