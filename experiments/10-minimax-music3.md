# MiniMax-Music3 — does the most-liked vocal model fit?

*Lab notebook, 2026-09-18. Written in two halves: the prediction first, then the
measurement. The first half was committed before anything ran.*

---

## 1 · The prediction — written before running

**Context.** MiniMax-Music3 is the third most-liked text-to-audio model on Hugging
Face (♥1,391), sings with vocals, and comes from the same vendor as the video
model in the first sibling project. It turned out to be compiled into the engine
all along, under `src/community_models/` — missed on day one because only
`src/models/` was listed.

**The published figure says it does not fit.** From the packager's card, RTX 5090,
30-second request, 30 steps:

| Mix | Peak VRAM |
|---|---:|
| Default Q4 / Q8 / Q4 | **9.8 GiB** |
| Q8 | 13.4 GiB |
| BF16 | 19.4 GiB |

Against **7.84 GiB usable**, the smallest published mix is 25% over.

**But the last published figure was wrong for this box.** YuE2's card reported
7,755 MiB; this box measured a fit predicting 5,091 MiB at the same duration — a
ratio of **0.66**. A large card has no reason to be frugal with memory.

> **PREDICTION:** applying the same 0.66 ratio, MiniMax-Music3's default mix peaks
> around **6.5 GiB here and fits** — with this box's copy using an even smaller
> 4-bit depth decoder (`q4_k`, 387 MiB) in place of the default 8-bit one.
>
> **Confidence: low.** The 0.66 ratio comes from one model, and there is no reason
> two models' allocators behave alike. If it fails, it fails the way ch.22's
> ACE-Step did: a fixed allocation, and no engine feature to split or offload.

---

## 2 · The measurement

**It does not fit. The prediction was wrong.**

```
CUDA error: out of memory
  current device: 0, in function alloc at ggml-cuda.cu:534
  cuMemCreate(&handle, reserve_size, &prop, 0)
...
prefill_tokens_batched(batch2_prompt_ids(prompt), 2, prompt_steps)   ar_runtime.cpp:377
```

Reached **6,389 MiB (81% of usable)**, then ran out while allocating for the
language model's prompt prefill — at **batch size 2**.

Two setup failures first, both recorded because they cost time: the package needs
**nine small sidecar files** (configs and a tokenizer) beyond the weights, and the
model was compiled into the engine all along under `src/community_models/`, which
the day-one inventory missed by only listing `src/models/`.

### Why the ratio did not transfer

The prediction assumed YuE2's 0.66 ratio between the published figure and this
box would hold for another model. It did not, and the reason is visible: YuE2's
published number came from an allocator with room to be wasteful, while
MiniMax-Music3's weights alone are **~7.7 GiB at 4-bit** (5.6 language model +
1.4 flow transformer + 0.4 + 0.2 + 0.1), against 7.84 usable. There was never
much waste to recover. **The 9.8 GiB figure was honest.** The prediction's own
"confidence: low" was the correct part of it.

### The lever that should exist, and does not

The batch of 2 is classifier-free guidance: the prompt runs once with the
conditioning and once without — exactly the hidden doubling ch.21 describes.
The engine's documentation offers the fix:

> `ar_guidance_scale` — *"Set `0` for the non-CFG AR path."*

The implementation refuses it:

```
audiocpp_cli failed: MiniMax Music 3 guidance scales must be positive
```

And the source shows why it would not help anyway in this build:
`ar_runtime.cpp:377` calls `prefill_tokens_batched(..., 2, ...)` **unconditionally**,
and `pipeline.cpp:157` rejects any scale `<= 0`. **The documented non-guidance
path is not implemented at commit `c0b26a5`.** Documentation ahead of code.

## 3 · What is established

1. **MiniMax-Music3 does not run on this box with this engine build.** Out of
   memory at batch-2 prefill, 81% of the card.
2. **The published peak was accurate.** Not every packager's figure is inflated;
   YuE2's was, this one was not.
3. **The documented escape is not implemented** in this version.

## 4 · The newer engine does not help either — checked by reading, not building

The engine's `main` had moved on to `62c664a` (2026-09-17). Before spending an
hour on a rebuild, its source was read: `pipeline.cpp:157` still rejects scales
`<= 0` and `ar_runtime.cpp:377` still runs the prefill at batch 2 unconditionally.
**Identical.** The rebuild was not done and the clone was removed.

Even with a batch-1 prefill, ~7.7 GiB of weights on a 7.84 GiB card leaves almost
nothing for work. **Expectation, written now: it still does not fit.** This is
the second music model — after ACE-Step — where the missing feature is the same
one: no way to offload part of a model to the 125 GB of system memory.

---

## 5 · The lever that was there all along — prediction, written before running

Asked *"we have three GPUs and huge RAM, why can't it?"*, the claim that the engine
"cannot split" was re-checked against **source** rather than `--help`. Two findings:

- one family (`irodori_tts.codec_backend`) does place a component on a different
  backend, so the engine architecture supports it — MiniMax just does not expose it;
- MiniMax exposes an option absent from its published docs:
  **`mem_saver` — "Load large generation stages only while they are needed to reduce
  peak VRAM."**

The out-of-memory in section 2 fits that exactly: all five components (~7.7 GiB)
resident at once leaves the language model almost nothing to prefill in.

> **PREDICTION:** with `mem_saver=true`, only the 5.6 GiB language model is resident
> during the autoregressive stage, and it **fits**. Moderate confidence — the prefill
> is still batch 2, and 5.6 GiB of weights leaves ~2.2 GiB to work in.

## 6 · mem_saver: the prediction was wrong again

```
mem_saver=true, one-line prompt:  FAILED after 7.8 s, peak 6,389 MiB — identical
CUDA error: out of memory ... cuMemCreate(&handle, reserve_size, &prop, 0)
in prefill_tokens_batched, inside generate_frame_hiddens
```

**Same byte-for-byte peak.** `mem_saver` defers the *later* stages (flow, depth
decoder, vocoder), but the failure is in the *first* stage, so there was nothing
for it to defer. The graph and weight arenas are 32 MiB each — not the problem
either.

**What is actually too big:** the "global" language model on its own. It is an
8-billion-parameter transformer — 36 layers, 4096 wide, 32 attention heads, 8
key/value heads — at 5.6 GiB in 4-bit, plus working memory for a batch-2 prefill.

## 7 · Why three cards and 125 GB of RAM cannot run it

**The hardware can. The engine cannot.**

`global_lm.cpp` contains no scheduler, no offload, no layer split — it runs the
whole model on the one backend it is given. Compare the sibling project's engine,
built on the **same numerical library (ggml)**:

| | audio.cpp, this model | llama.cpp, selfhostllm |
|---|---|---|
| put some layers in system RAM | no | `-ngl N` — measured in selfhostllm ch.11 |
| split layers across cards | no | `-sm layer` — measured in selfhostllm ch.18 |
| per-component device | only `irodori_tts.codec_backend` | n/a |

The shape of this language model is exactly the shape llama.cpp was built for.
Splitting its 36 layers 18 + 18 across two cards would put ~2.8 GiB of weights on
each, leaving over 4 GiB of working room per card. **That is engine work — the
ggml scheduler llama.cpp uses exists underneath audio.cpp already — not a flag.**

Every earlier claim in this project that "the engine cannot split" came from
`--help`. This time the source was read, and the answer is more precise: the
engine *can* place components separately in one family and *can* schedule across
backends at the library level; **this model simply does not use either.**
