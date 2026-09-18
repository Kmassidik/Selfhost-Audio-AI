# YuE2 against MiniMax-Music3: the same song, measured side by side

*Lab notebook, 2026-09-19. No prediction was pre-registered: this is a measurement of two
takes that already existed, made at the user's request. It is recorded as such.*

Same lyrics (9 sections, 182 sung words), close style prompts, one take each, through the studio.

| | MiniMax-Music3 | YuE2 |
|---|---|---|
| job | `runs/studio/20260918-193706-1a896d` | `runs/studio/20260919-033544-31a206` |
| seed | 20260918 | 20260918 |
| length | 122.15 s | 157.56 s |
| time to make | 841.2 s (14.0 min) | **75.1 s** |
| real-time factor | 6.89 | **0.48** (14.5× faster) |
| cards used | **3** (peak card 0 ≥ 7,479 MiB, sampled) | 1 (≈ 4,630 MiB, *derived* from chapter 23's fit 6.832 × s + 3,554) |
| output | 44.1 kHz stereo | 48 kHz stereo |
| integrated loudness | −14.0 LUFS | −13.7 LUFS |
| loudness range | 10.4 LU | 5.3 LU |
| lyric WER (ear: Qwen3-ASR 1.7B, section tags removed from reference) | 1.65%: **0 wrong, 0 missing, 3 extra** | **0.00%** |
| licence | community licence: **commercial use allowed**, "MiniMax-Music3" shown in the product UI; written permission above $20M/yr revenue | CC-BY-NC-4.0: **non-commercial** |

- **MiniMax's 3 "errors" are insertions**: an echoed ad-lib (*"…everybody knows. Nobody
  knows."*) and a repeated "the". **Both models sang every word of the lyrics.** WER cannot rank them.
- **Loudness range** (how much the level moves between quiet and loud passages) is twice as
  wide for MiniMax: 10.4 LU against 5.3. That is a measured difference in dynamics. Whether
  it sounds better is a listening question.
- **Not measured: which one sounds better.** That is the blind test in the studio's Compare
  tab, loudness-matched, and its result goes here with the listener count.
- The two lengths differ because each model paced the same lyrics differently. Neither was
  asked for a fixed length (YuE2 follows the lyrics; MiniMax had a 150 s ceiling).

Raw transcripts: `experiments/17-yue2-vs-minimax-lyrics.json`.

## Addendum 2026-09-19: a bilingual lo-fi song (user request), YuE2

`runs/studio/20260919-035318-5d2b90.wav`, "Midnight Tokyo Rain". Lyrics written for this:
Japanese verses, choruses mixing English and Japanese, a おやすみ/goodnight outro. Style:
lo-fi hip hop, 78 bpm, dusty drums, vinyl crackle, rhodes, breathy female vocal. Seed 20260919.

**152.5 s of 48 kHz stereo in 47.6 s (RTF 0.31).**

Ear (Qwen3-ASR 1.7B, no language tag), by transcript: **every English line came back
correctly**. Of the Japanese, the second chorus's 君の声が聞こえる気がする and the outro's
おやすみ came back exactly. The **Japanese verse lines** came back as English-sounding
words ("I'm in the hotel. Window tapping. Quiet room.") or not at all. That is either
soft Japanese singing or the ear's own difficulty with switching languages mid-song.
One ear cannot separate the two; a Japanese-speaking listener can.

## Addendum 2026-09-19: "Good Morning Tokyo / 朝のホーム", and the first listener verdict

Same lyrics and style on both models (Japanese chill rap, neo soul, lo-fi, 94 bpm, F major,
bilingual lyrics). Seed 20260919.

| | YuE2 | MiniMax-Music3 |
|---|---|---|
| job | `20260919-040148-99b475` | `20260919-040148-e527e0` |
| length | 134.0 s | 111.5 s |
| made in | 54.1 s (RTF 0.40) | 767.3 s (RTF 6.88) |

**Testimony, n = 1, not blind.** The user, after listening: *"its really game changer you
know the minimaxi, its like i never know that song haha"*. This is recorded as testimony,
not measurement: one listener, who knew which take was which. **Acted on:** the studio's Sing tab
now defaults to MiniMax-Music3. A blind, loudness-matched comparison (Compare tab) is
still owed if this is to become a measured result.

An earlier 82 bpm "One Umbrella Left" MiniMax take was stopped halfway at the user's
direction ("too slow"), after its YuE2 take (149.2 s in 59.3 s) was heard.
