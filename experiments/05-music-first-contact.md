# Music, first contact — the licence dilemma inverts

*Lab notebook, 2026-09-18. audio.cpp `c0b26a5`, CUDA 12.0.140, one RTX 3060 Ti,
**7,840 MiB usable**. Both models 8-bit or lower, `--seed 20260915`.*

**Headline: the model whose output can be sold does not fit. The model that
fits is non-commercial.**

---

## 1 · ACE-Step 1.5 — does not run on the card

MIT licensed, trained on licensed and royalty-free data, the model whose whole
pitch is *"you may use the generated music commercially"*. Turbo variant, 8-bit,
**5.9 GiB of weights**.

```
 10 s requested   FAILED after 16.6 s   peak 7,057 MiB
  5 s requested   FAILED after 16.1 s   peak 7,033 MiB

 alloc_tensor_range: failed to allocate CUDA0 buffer of size 1456983552
 audiocpp_cli failed: ACE-Step timbre encoder backend buffer allocation failed
```

**Identical failure at both durations**, and the peaks differ by 24 MiB. This is
not a length problem — it is a fixed allocation. The model reaches roughly
7,050 MiB and then asks for **1.36 GiB more** for its timbre encoder, against
790 MiB remaining.

Total requirement is about **8.4 GiB on a 7.84 GiB card.** Missing by ~7%.

### There is no escape route, and chapter 05 said so

| Usual fix | Available? |
|---|---|
| A smaller quantization | **no** — 8-bit is the smallest published; the alternative is 16-bit at 9.6 GiB |
| Split across the three cards | **no** — the engine has `--device` to *pick* a card, nothing to divide between them |
| Offload to the 125 GB of system memory | **no** — the sibling project's central technique is not implemented here |

Every model before this one fit one card comfortably, so none of those absences
had cost anything. This is the first that does not fit, and it has none of them.

### It does run on the processor

```
 10 s requested   OK  10.00 s audio  wall 388.9 s   48 kHz stereo
```

**Real-time factor 38.9** — roughly thirty-nine times slower than real time. A
three-minute song would take about two hours. That is usable for a single
deliberate render and not for anything else.

> ⚠️ The memory figure logged for this run is contaminated: the sampler reads
> **whole-card** memory and a YuE2 run was in progress on the same box. A
> processor run does not use the card. The number is discarded, not reported.

## 2 · YuE2-3B — fits, with room to spare

Non-commercial (CC-BY-NC-4.0). 4-bit, **2.5 GiB of weights** plus a 253 MiB decoder.

```
 8 steps, cot=off   48.76 s audio   wall 36.6 s   RTF 0.751
                    peak 3,891 MiB  = 49.6% of usable
                    48,000 Hz, STEREO
```

Faster than real time, on **half a card**, producing the first stereo output
anywhere in this project. Two cards untouched.

## 3 · Two predictions, tested

### Memory: wrong, and usefully so

> `planning/MODELS.md`, 2026-09-15, before anything ran: *"7,755 MiB against a
> 8,192 MiB card... 437 MiB of margin, measured on somebody else's card, is not
> margin."*

Measured peak is **3,891 MiB** — half the published figure, and the margin is
3,949 MiB rather than 437.

The published number was taken on a **225-second** longform generation; ours was
**48.76 seconds**. So the reasonable reading is that YuE2's peak *does* scale
with duration — unlike Kokoro in `experiments/01`, which was flat from 21 s to
171 s. Chapter 04 predicts exactly this asymmetry: a music renderer **sculpts
the whole clip at once**, where a speech model works through text in chunks.

**A duration sweep is running to test that.** Until it returns, "YuE2 fits" is
established only for clips of about a minute.

### Speed: right

> `planning/MODELS.md`: *"If bandwidth-bound, **RTF ≈ 0.8 here** is the estimate
> for this box."*

Measured **0.751**. The published 0.1997 was on an RTX 5090 with roughly four
times this card's memory bandwidth; 0.751 ÷ 0.1997 = **3.76×**.

That is the third independent confirmation that generation cost on this hardware
is substantially set by how fast the card reads weights — after chapter 09's two
voices and chapter 19's forty-fold recogniser range.

## 4 · What this does to the project

The licence question in `PRD §8` assumed a choice between quality and
commercial usability. **The hardware has made that choice**, in the direction
nobody planned:

| | ACE-Step 1.5 | YuE2-3B |
|---|---|---|
| Licence | **MIT — sellable** | CC-BY-NC — not sellable |
| Runs on the card | **no** | **yes, on half of it** |
| Runs at all | processor only, RTF 38.9 | RTF 0.751 |
| Quality claim | commercial-grade | beats Suno v5 and v6 on the authors' benchmark |

The A-versus-B-versus-C comparison this part was commissioned to produce is
still possible, but **B cannot be measured under the same conditions as A** —
and comparing a card run against a processor run measures the backend, which is
the exact mistake the single-engine rule exists to prevent.

## 5 · Open

- **The YuE2 duration sweep**, running. Decides whether "it fits" survives to
  song length.
- **A smaller ACE-Step.** 6-bit or 4-bit would bring 5.9 GiB to roughly 4.4 or
  3.0 and the whole model inside the card. None is published; converting one is
  possible and is the obvious next move for this track.
- **The third model.** Stable Audio 3 Small has a 1.57 GiB package and would fit
  easily — a genuine third point, and the C in A-versus-B-versus-C.
- **Nothing has been listened to yet.** Every number here is memory and clock.

---

## 6 · The duration sweep — YuE2 fits, with four minutes to spare

*Added 2026-09-18, after the sweep completed.*

| lyrics | audio | wall | RTF | peak | % usable |
|---|---:|---:|---:|---:|---:|
| ×1 | 48.76 s | 37.5 s | 0.769 | 3,891 MiB | 49.6% |
| ×2 | 51.32 s | 38.6 s | 0.752 | 3,901 MiB | 49.8% |
| ×4 | 144.92 s | 90.5 s | 0.624 | 4,519 MiB | 57.6% |
| ×6 | 147.68 s | 89.5 s | 0.606 | 4,587 MiB | 58.5% |

**Memory does scale with duration — and very gently.**

```
peak_MiB = 6.832 x seconds + 3,554
-> 7,840 MiB reached at 627 s = 10.5 minutes of music
```

A four-minute song needs about **5,193 MiB — 66% of one card**, with two cards
untouched. **Song length is not a constraint for this model on this hardware.**

Three things fall out of that table.

### The hypothesis was right, and the conclusion was still wrong

Section 3 predicted memory would scale with duration because a music renderer
sculpts the whole clip at once (ch.04), unlike Kokoro which chunks. **It does
scale** — 6.8 MiB per second of audio. But the slope is so shallow that the
practical answer is the same as if it had been flat.

*Being right about the mechanism and wrong about whether it matters is the
failure mode `experiments/01` is about, arriving from the other direction.*

### Real-time factor improves with length

0.769 at 49 seconds, **0.606 at 148 seconds.** The opposite of the memory
direction, and for the reason ch.06 established: a fixed startup cost divided
across more output. Longer generations are *more* efficient here.

### We use 2,664 MiB less than the published figure

Our fit predicts **5,091 MiB** at 225 seconds. The packagers reported **7,755
MiB** for a 225-second run on an RTX 5090.

Not a contradiction to wave away — it is a 52% difference on the same model and
quantization. Candidate causes, none tested:

| Candidate | Note |
|---|---|
| `cot=off` here, planning mode there | their example used the full symbolic-planning path |
| Step count | ours is 8; theirs unstated in the table |
| Allocator behaviour | a 32 GB card has no reason to be frugal; ggml reserves differently under pressure |

**The safe reading is that 7,755 MiB was never a floor**, and the prediction it
generated — "437 MiB of margin is not margin" — was answering a question that
did not apply. The margin on this box is **3,253 MiB at song length.**
