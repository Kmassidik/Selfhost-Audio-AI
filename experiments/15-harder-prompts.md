# The three voices on harder prompts

*Lab notebook, 2026-09-18. The prediction half, committed before anything ran.*

Experiment 03 found word error rate **0.000 for every voice on every prose
prompt**: an instrument that cannot rank. It asked for harder material as **new
ids**, and `bench/prompts.json` v2 adds five speech prompts (`s2_*`). Runner:
`source/46_harder_speech.py`, which runs Kokoro, VoxCPM2 and Qwen3-TTS (all q8_0,
seed 20260915), one at a time on card 0. The ear is Qwen3-ASR 1.7B, the most
accurate recogniser in experiment 04.

| Prompt | Scored by | Why |
|---|---|---|
| `s2_tongue` | word error rate | near-identical repeated sounds: where readers skip or loop |
| `s2_long_list` | word error rate | 20 counted items: a dropped or repeated item is unambiguous |
| `s2_codeswitch_id` | word error rate | Indonesian with English mid-sentence. Kokoro skipped (no Indonesian voice) |
| `s2_numbers_hard` | transcript only | digits in the reference, words in the audio: WER would be meaningless |
| `s2_homographs` | transcript only | *read/read, lead/lead*: the ear writes the spelling whichever way it is said |

## Predictions

> **1 · The ceiling breaks.** At least one voice scores above zero on `s2_tongue`
> or `s2_long_list`. Moderate-high confidence.
>
> **2 · Kokoro makes the fewest errors on the tongue twister and the list.** It
> reads from phonemes with no autoregressive loop to skip or repeat; VoxCPM2 and
> Qwen3 generate token by token and can lose their place. Moderate confidence.
>
> **3 · Code-switching: VoxCPM2 under 20% WER, Qwen3-TTS higher.** VoxCPM2 claims 30
> languages; Qwen3-TTS's language list is shorter. Low confidence: the ear's own
> Indonesian is untested.
>
> **4 · Every voice misreads at least two of**: XIV/XIII (Roman numerals), €1.250,00
> (European decimal comma), 10½, 2:07:53, 2.10.3. Moderate confidence.
>
> **5 · Homographs are invisible to the ear.** Every transcript spells them
> correctly whatever was said. That is the instrument's limit, not a result about
> the voices, and a listener is needed to score it. High confidence.

## Results — measured 2026-09-18

Raw: `experiments/15-harder-v2-results.json` (every transcript). Ear: Qwen3-ASR 1.7B.

### The word error rates, and why two of them are the scorer's fault

| Voice | `s2_tongue` | `s2_long_list` | `s2_codeswitch_id` |
|---|---|---|---|
| Kokoro | 13.8% raw → **0 real errors** | **0%** | skipped (no Indonesian voice) |
| VoxCPM2 | 13.8% raw → **0 real errors** | **0%** | 8.7% raw → **0 real errors** |
| Qwen3-TTS | 13.8% raw → **0 real errors** | **0%** | 26.1% raw → **4 real errors** of 23 words (~17%) |

**Scorer artefacts.** `score_wer.words()` splits on spaces and hyphens. The prompt says
*sea shells* and *sea shore*, which the ear writes *seashells* and *seashore*, so each
is scored as one substitution plus one deletion. That is exactly the S = 2, D = 2 that
all three voices "made". Likewise *deadline-nya* against *deadlinenya* on the
code-switch prompt. **The identical 13.8% for three different voices was the clue**:
three independent readers do not make the same four mistakes. The scorer is
deliberately crude and symmetric (its own docstring says so) and is **not being
changed**, because every earlier score used it. The artefacts are reported here instead.

**Qwen3-TTS's real code-switch errors, as heard:** *Besok pagi* → "Bisakah" (2 words), *Jumat* →
"Jumaat", *oke* → "Okey". The last two are Malay spellings. Whether the voice
spoke with a Malay accent or the ear leaned that way cannot be separated with one
ear. That needs a listener.

### Hard numbers: every voice fails, differently (by transcript)

| Written | Kokoro said | VoxCPM2 said | Qwen3-TTS said |
|---|---|---|---|
| Chapter XIV | "Roman fourteen" ✗ | "Spectre theme" ✗✗ | "Chapter 14" ✓ |
| $1,299.99 | "dollar one two hundred ninety nine, ninety nine" ✗ | "one thousand two hundred ninety-nine dollars ninety-nine cents" ✓ | "205.99 euros" ✗✗ |
| €1.250,00 (European comma) | "euros one two hundred fifty zero zero" ✗ | "two hundred fifty thousand euros" ✗ | "21 to 150.50 percent" ✗✗ |
| 2:07:53 | "two zero seven fifty three" ✗ | "two one seven fifty-three" ✗ | "two hours 7:53" ✓ |
| 1/3 | "one slash three" ✗ | "one thirtieths" ✗ | "one third" ✓ |
| 10½ | "ten a half" ~ | "ten and a half" ✓ | "10 and a half" ✓ |
| Leo XIII | "Roman thirteen" ✗ | "the Thirteenth" ✓ | "XIII" (ear wrote a numeral) ? |
| 1891 | "one thousand eight hundred ninety one" ~ | "eighteen ninety-one" ✓ | "1891" ? |
| 2.10.3 | "two, ten three" ✗ | "two point one zero point three" ✓ | "2.10.3" ? |

✗✗ = changes the meaning. ? = the ear wrote digits back, so how it was said is unknown.
**Kokoro** reads symbols literally ("Roman", "slash", "dollar" first): it has no number
normaliser. **VoxCPM2** normalises well but badly misreads the European decimal comma
and one Roman numeral. **Qwen3-TTS** sounds the most natural where it can be judged,
and **changes two amounts**: $1,299.99 became "205.99 euros". For a voice reading
invoices, that is the worst failure on this page.

### Homographs

All three transcripts are word-for-word identical: *read … read … lead … lead … wind …
wind … close*. As predicted, **the ear cannot tell** which pronunciation was used. The
one shared deviation, *"we **closed** the window"* in all three, is most likely the
ear's own grammar correcting the sentence, since three voices would not add the same
"-d". A listener has to score this prompt.

### Scored

| Prediction | Verdict |
|---|---|
| 1 · the ceiling breaks on the twister or the list | **wrong**: 0 real errors from every voice. The raw 13.8% was the scorer |
| 2 · Kokoro fewest errors on twister and list | **not supported**: all tied at zero |
| 3 · code-switch: VoxCPM2 < 20%, Qwen3 higher | **right**: VoxCPM2 0 real errors, Qwen3 4 of 23 |
| 4 · every voice misreads ≥ 2 hard numbers | **right**: Kokoro 7, VoxCPM2 5, Qwen3 ≥ 2 (both meaning-changing) |
| 5 · homographs invisible to the ear | **right**: identical transcripts |

**What the harder prompts bought.** Intelligibility is still at the ceiling for all
three voices: tongue twisters and a 20-item list gave no errors. The voices
separate on **normalisation**, turning written symbols into words, and on
**language**. Those are the axes the next voice comparisons should use.
