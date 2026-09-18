# serve/ — the studio

**Nothing here yet. There is nothing to serve.**

The analogue of `selfhostllm/serve/` (Arena): one place to actually *use* what
the ladder builds, rather than reading about it. Arena's lesson, worth inheriting
before a line is written:

> Everything below was found by using the thing, not by reading it.

That README lists eight app bugs and three benchmark bugs, every one of which
was invisible until someone sat down and used it. **The studio is not a demo;
it is how the bugs get found.**

## What it will need, when there is something to serve

- Pick a model, pick a card, load. Live per-card memory visible, not described.
- **Playback with provenance attached** — model, quantization, seed, date, on
  the player. A clip with no provenance is decoration.
- **A/B two takes blind**, with the key held back. This is the `listening/`
  harness with a user interface, and it is the feature that makes it a studio
  rather than a player.
- Generations that persist, on the box, named from the prompt.
- **Truncation and failure stated, not hidden.** Arena's first version silently
  cut replies at 512 tokens, which looks exactly like a model that finished. The
  audio version of that mistake is a song that stops early and looks complete.

## Not before

Part I has to produce audio, and Part II has to be able to score it. A studio
built before the ear is a player, and a player is not worth building.
