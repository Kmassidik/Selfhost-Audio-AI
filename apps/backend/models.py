"""Every model this box can run, with the defaults this project MEASURED.

Nothing here is a guess. Each default carries the chapter or experiment that
earned it, so nobody "tidies" one away later:

  seed always passed                ch. 06  without it, same input != same bytes
  VoxCPM2 chunked at 400 characters ch. 08  the default fails past ~60 s
  reference clips trimmed to 14.5 s ch. 08  15.0 s is refused
  YuE2 plans with melody            ch. 27  27% FASTER than planning off
  Stable Audio capped at 120 s      ch. 24  a hard cap, silently enforced
  Canary gets no seed               ch. 40  the server refuses the option
  MiniMax split 4/16/16             exp. 13 card 0 also holds the frame states
  MiniMax expandable_segments       exp. 13 1.3 GB per card lost to fragmentation
  MiniMax capped at 300 s           exp. 13 3 min 37 s is the longest tested
"""
import os
from dataclasses import dataclass, field

SA_MAX_S = 120          # ch. 24
MM_MAX_S = 300          # exp. 13a-3
REF_MAX_S = 14.5        # ch. 08


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    kind: str                     # sing | speak | listen
    gguf: str = ""                # relative to models/gguf
    family: str = ""              # audio.cpp family
    cards: int = 1                # how many cards it takes while running
    note: str = ""
    fields: tuple = field(default_factory=tuple)   # what the creator page shows


MODELS = {
    "minimax": ModelSpec(
        id="minimax", label="MiniMax-Music3", kind="sing", cards=3,
        note="Best vocals. All three cards, about 7 seconds of work per second of song.",
        fields=("style", "lyrics", "duration")),
    "yue2": ModelSpec(
        id="yue2", label="YuE2", kind="sing", family="yue2",
        gguf="Yue2-3B-GGUF/yue2-3b-q4_0.gguf",
        note="Fast sketching: a 2.5-minute song in about a minute, on one card.",
        fields=("style", "lyrics")),
    "stable-audio": ModelSpec(
        id="stable-audio", label="Stable Audio", kind="sing", family="stable_audio",
        gguf="Stable-Audio-3-Small-Music-GGUF/stable-audio-3-small-music-q8_0.gguf",
        note="Instrumental only, up to two minutes.",
        fields=("prompt", "duration")),
    "kokoro": ModelSpec(
        id="kokoro", label="Kokoro", kind="speak", family="kokoro_tts",
        gguf="Kokoro-82M-GGUF/kokoro-82m-q8_0.gguf",
        note="49 voices, eight languages, very fast.", fields=("text", "voice")),
    "qwen3": ModelSpec(
        id="qwen3", label="Qwen3-TTS", kind="speak", family="qwen3_tts",
        gguf="Qwen3-TTS-12Hz-1.7B-CustomVoice-GGUF/qwen3-tts-12hz-1.7b-customvoice-q8_0.gguf",
        note="Nine speakers, takes direction.", fields=("text", "speaker", "instruct")),
    "voxcpm2": ModelSpec(
        id="voxcpm2", label="VoxCPM2", kind="speak", family="voxcpm2",
        gguf="VoxCPM2-GGUF/voxcpm2-q8_0.gguf",
        note="48 kHz, 30 languages, clones a voice from a short clip.",
        fields=("text", "ref")),
}

KOKORO_LANG = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi",
               "i": "it", "p": "pt-br", "z": "cmn"}


def cli_path(root: str) -> str:
    build = os.environ.get("AUDIOCPP_BUILD", "linux-cuda-full")
    return os.path.join(root, "engines", "audiocpp", "build", build, "bin", "audiocpp_cli")


def command(spec: ModelSpec, params: dict, out_path: str, root: str, device: int = 0):
    """Build (argv, env) for one generation. The env is never inherited blindly."""
    p = params
    seed = str(p.get("seed") or 20260915)
    env = dict(os.environ)

    if spec.id == "minimax":
        py = os.path.join(root, "engines", "minimax-py", ".venv", "bin", "python")
        job = os.path.join(root, "source", "42_minimax_music3_job.py")
        secs = max(5, min(MM_MAX_S, int(p.get("duration") or 120)))
        env.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", SELFHOSTAUDIO_ROOT=root,
                   PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
        env.pop("CUDA_VISIBLE_DEVICES", None)          # it wants all three cards
        return ([py, job, "--prompt", p.get("style", ""), "--lyrics", p.get("lyrics", ""),
                 "--seconds", str(secs), "--seed", seed, "--out", out_path], env)

    cli = cli_path(root)
    model = os.path.join(root, "models", "gguf", spec.gguf)
    base = [cli, "--backend", "cuda", "--device", str(device)]
    if spec.id != "canary":
        base += ["--seed", seed]

    if spec.id == "yue2":
        return (base + ["--task", "gen", "--family", "yue2", "--model", model,
                        "--threads", os.environ.get("AUDIOCPP_THREADS", "8"),
                        "--lyrics", p.get("lyrics", ""),
                        "--request-option", f"style={p.get('style', '')}",
                        "--request-option", f"cot={p.get('planning', 'melody')}",
                        "--request-option", f"num_inference_steps={int(p.get('steps') or 8)}",
                        "--session-option", "yue2.model_gguf=yue2-3b-q4_0.gguf",
                        "--session-option", "yue2.vae_gguf=yue2-vae-f16.gguf",
                        "--out", out_path], env)

    if spec.id == "stable-audio":
        secs = max(1, min(SA_MAX_S, int(p.get("duration") or 30)))
        return (base + ["--task", "gen", "--family", "stable_audio", "--model", model,
                        "--text", p.get("prompt", ""), "--duration-seconds", str(secs),
                        "--out", out_path], env)

    if spec.id == "kokoro":
        voice = p.get("voice", "af_heart")
        return (base + ["--task", "tts", "--family", "kokoro_tts", "--model", model,
                        "--language", KOKORO_LANG.get(voice[0], "en-us"),
                        "--voice-id", voice, "--text", p.get("text", ""),
                        "--out", out_path], env)

    if spec.id == "qwen3":
        argv = base + ["--task", "tts", "--family", "qwen3_tts", "--model", model,
                       "--speaker", p.get("speaker", "Vivian"), "--text", p.get("text", ""),
                       "--out", out_path]
        if p.get("instruct"):
            argv += ["--instruct", p["instruct"]]
        return (argv, env)

    if spec.id == "voxcpm2":
        argv = base + ["--task", "tts", "--family", "voxcpm2", "--model", model,
                       "--text", p.get("text", ""), "--text-chunk-size", "400",
                       "--out", out_path]
        if p.get("ref"):
            argv += ["--voice-ref", p["ref"]]
            if p.get("ref_text"):
                argv += ["--reference-text", p["ref_text"]]
        return (argv, env)

    raise ValueError(f"unknown model {spec.id}")


MUSIC = tuple(m.id for m in MODELS.values() if m.kind == "sing")


def public(music_only: bool = True) -> list:
    """What the creator page needs to draw its picker.

    The speech models stay in this file — the lab still measures them — but the
    platform is a music platform, so by default it only offers the ones that sing.
    """
    return [{"id": m.id, "label": m.label, "kind": m.kind, "cards": m.cards,
             "note": m.note, "fields": list(m.fields)}
            for m in MODELS.values() if not music_only or m.kind == "sing"]
