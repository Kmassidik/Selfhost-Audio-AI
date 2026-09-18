# source/ — the experiments, numbered by the chapter they back

**Pulled from the box by `../sync.sh`. Edited there, committed here.**

The box is authoritative for this directory because the code needs the GPU, the
models and the `audio.cpp` build to run at all. This copy exists so it can be
committed — nothing more. `sync.sh --push` overwrites the box and is for
restoring after data loss, not for normal work.

## Naming

`NN_what_it_answers.py`, where `NN` is the chapter number it produces the
numbers for. A file whose chapter does not exist yet keeps the number it will
have. A file that answers a question no chapter asked should not exist.

```
01_probe_kokoro.py        what came out: rate, channels, depth, bytes/second
02_build_check.py         which backend audio.cpp actually compiled
...
```

## Rules

1. **No hardcoded box paths.** Everything reads `$SELFHOSTAUDIO_ROOT`. The first
   sibling wrote `/root/Desktop/selfhosted-minimaxi-h3` into ~25 files and
   flagged it in its own README as the reason nobody else could clone it.
2. **Every run writes `bench/results/<run-id>.json`.** No JSON, no run.
3. **Standard library where possible.** The harness must never fail to run
   because a model's environment installed an incompatible version of something.
   `selfhostllm/bench` holds this line and it has paid off.
4. **Never stream a long job over SSH.** Launch detached, return.
