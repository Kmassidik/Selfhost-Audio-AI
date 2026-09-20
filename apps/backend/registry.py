"""The model catalogue: one JSON file per model, no code per model.

Adding a model that runs on an engine already here — audio.cpp, or a Python
script — is a file in catalog/ and nothing else. A model that needs a new
engine gets one adapter below, then the same file. Turning one off is a flag.

The pages never learn model names: they ask for outcomes ("a finished song",
"a quick draft") and the catalogue decides which model serves each one.
"""
import glob
import json
import os
import re
import statistics

CATALOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog")

REQUIRED = ("id", "name", "kind", "engine", "run", "fields")
_cache = {"mtime": 0.0, "models": {}}


class BadModel(ValueError):
    """A catalogue file that cannot be trusted. Better loud than half-loaded."""


def _validate(d: dict, path: str) -> dict:
    missing = [k for k in REQUIRED if k not in d]
    if missing:
        raise BadModel(f"{os.path.basename(path)} is missing {', '.join(missing)}")
    if d["engine"] == "audiocpp" and not (d["run"].get("gguf") or d["run"].get("model_path")):
        raise BadModel(f"{d['id']}: an audio.cpp model needs gguf or model_path")
    if d["engine"] not in ENGINES:
        raise BadModel(f"{d['id']}: no engine called {d['engine']}")
    d.setdefault("enabled", True)
    d.setdefault("cards", 1)
    d.setdefault("limits", {})
    d.setdefault("rate", 1.0)
    d.setdefault("notes", [])
    d.setdefault("outcome", {"title": d["name"], "blurb": "", "icon": "", "order": 99})
    # Which fields the engine cannot be handed empty. An empty style reached
    # audio.cpp once as "--request-option style=" and the job died there
    # rather than here, where a person could still have fixed it.
    d.setdefault("required", ["style"] if "style" in d["fields"] else [])
    return d


def _newest() -> float:
    return max((os.path.getmtime(p) for p in glob.glob(os.path.join(CATALOG, "*.json"))),
               default=0.0)


def models(include_disabled: bool = False) -> dict:
    """Every model, reloaded when a file on disk changes."""
    newest = _newest()
    if newest != _cache["mtime"]:
        found = {}
        for path in sorted(glob.glob(os.path.join(CATALOG, "*.json"))):
            with open(path, encoding="utf-8") as f:
                spec = _validate(json.load(f), path)
            found[spec["id"]] = spec
        _cache.update(mtime=newest, models=found)
    return {k: v for k, v in _cache["models"].items() if include_disabled or v["enabled"]}


def get(model_id: str) -> dict | None:
    return models().get(model_id)


def music_ids() -> tuple:
    return tuple(m["id"] for m in models().values() if m["kind"] == "sing")


# ── engines: how a declaration becomes a command ─────────────────────
def _fill(args, values: dict) -> list:
    """Substitute {style}, {lyrics}, {duration}, {seed}, {out} into the arguments."""
    out = []
    for a in args:
        for key, val in values.items():
            a = a.replace("{" + key + "}", str(val))
        out.append(a)
    return out


def _audiocpp(spec: dict, values: dict, root: str, device: int) -> tuple:
    build = os.environ.get("AUDIOCPP_BUILD", "linux-cuda-full")
    cli = os.path.join(root, "engines", "audiocpp", "build", build, "bin", "audiocpp_cli")
    run = spec["run"]
    # Most families load one file from models/gguf/. Some — MiniMax-Music3 — are
    # a package of components in a directory of their own, so a file is declared
    # with "gguf" and a directory with "model_path", relative to the root.
    model = (os.path.join(root, run["model_path"]) if run.get("model_path")
             else os.path.join(root, "models", "gguf", run["gguf"]))
    argv = [cli, "--task", run.get("task", "gen"), "--family", run["family"],
            "--model", model,
            "--backend", "cuda", "--device", str(device)]
    if run.get("seed", True):
        argv += ["--seed", str(values["seed"])]
    argv += _fill(run.get("args", []), values)
    argv += ["--out", values["out"]]
    return argv, dict(os.environ, **{k: str(v) for k, v in run.get("env", {}).items()})


def _python(spec: dict, values: dict, root: str, device: int) -> tuple:
    run = spec["run"]
    argv = [os.path.join(root, run["python"]), os.path.join(root, run["script"])]
    argv += _fill(run.get("args", []), values)
    env = dict(os.environ, SELFHOSTAUDIO_ROOT=root,
               **{k: str(v) for k, v in run.get("env", {}).items()})
    if run.get("all_cards"):
        env.pop("CUDA_VISIBLE_DEVICES", None)
    else:
        env["CUDA_VISIBLE_DEVICES"] = str(device)
    return argv, env


ENGINES = {"audiocpp": _audiocpp, "python": _python}


def as_seconds(value) -> int:
    """A length, whatever the page sent. Anything that is not one is refused.

    The page filters what can be typed, but the page is not the only caller:
    curl, a script and a mistake all reach the same route, and int("🎵")
    raises inside the worker where nobody is looking.
    """
    if isinstance(value, bool) or value is None:
        raise BadModel("length must be a number of seconds")
    if isinstance(value, (int, float)):
        seconds = int(value)
    else:
        text = str(value).strip()
        if ":" in text:                       # "2:45" is a length people write
            parts = text.split(":")
            if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
                raise BadModel(f"{value!r} is not a length")
            seconds = int(parts[0]) * 60 + int(parts[1])
        elif text.isdigit():
            seconds = int(text)
        else:
            raise BadModel(f"{value!r} is not a length")
    if seconds < 0:
        raise BadModel("length cannot be negative")
    return seconds


def missing(model_id: str, params: dict) -> list:
    """The fields this model needs that the request did not fill in."""
    spec = get(model_id)
    if not spec:
        raise BadModel(f"unknown model {model_id}")
    return [f for f in spec["required"] if not str(params.get(f, "")).strip()]


def command(model_id: str, params: dict, out_path: str, root: str, device: int = 0) -> tuple:
    """(argv, env) for one generation, with the declared limits applied."""
    spec = get(model_id)
    if not spec:
        raise BadModel(f"unknown model {model_id}")
    gaps = missing(model_id, params)
    if gaps:
        raise BadModel(f"{spec['name']} needs {', '.join(gaps)}")
    lim = spec["limits"]
    duration = params.get("duration")
    if duration is not None:
        duration = max(int(lim.get("min_duration", 1)),
                       min(int(lim.get("max_duration", 600)), as_seconds(duration)))
    values = {
        "style": params.get("style") or params.get("prompt", ""),
        "lyrics": params.get("lyrics") or params.get("text", ""),
        "duration": duration if duration is not None else "",
        "seed": params.get("seed") or 20260915,
        "out": out_path,
    }
    return ENGINES[spec["engine"]](spec, values, root, device)


# ── what the pages see ───────────────────────────────────────────────
def measured_rate(conn, model_id: str, declared: float, minimum_runs: int = 3) -> tuple:
    """Seconds of work per second of music, from this box's own finished jobs.

    A declared rate is a starting guess; after three real runs the box knows
    better than the catalogue does, and the estimate on the page improves by
    itself. Returns (rate, "measured" | "estimated").
    """
    rows = conn.execute("""
        SELECT j.wall_s, s.seconds FROM jobs j JOIN songs s ON s.id = j.song_id
        WHERE j.model = ? AND j.status = 'done' AND j.wall_s > 0 AND s.seconds > 0
        ORDER BY j.id DESC LIMIT 8""", (model_id,)).fetchall()
    rates = [r["wall_s"] / r["seconds"] for r in rows]
    if len(rates) >= minimum_runs:
        return round(statistics.median(rates), 2), "measured"
    return declared, "estimated"


def seconds_per_word(conn, model_id: str, minimum_runs: int = 3) -> float:
    """How long this model sings one word, measured on this box.

    Neither singing model takes a length as an instruction: they sing the
    lyrics and stop, and MiniMax's duration is a ceiling it need not reach.
    The honest prediction of how long a song will be is therefore made from
    the words, not from the slider — and the box has the evidence to make it.
    """
    rows = conn.execute("""
        SELECT seconds, lyrics FROM songs
        WHERE model = ? AND seconds > 0 AND lyrics <> '' ORDER BY rowid DESC LIMIT 12""",
                        (model_id,)).fetchall()
    rates = []
    for r in rows:
        words = len(re.sub(r"\[[^\]]*\]", " ", r["lyrics"]).split())
        if words >= 20:                      # a handful of words tells nothing
            rates.append(r["seconds"] / words)
    return round(statistics.median(rates), 2) if len(rates) >= minimum_runs else 0.0


def outcomes(conn=None, music_only: bool = True) -> list:
    """The choices a person picks between, newest speed figures included."""
    out = []
    for spec in models().values():
        if music_only and spec["kind"] != "sing":
            continue
        rate, source = (measured_rate(conn, spec["id"], spec["rate"]) if conn
                        else (spec["rate"], "estimated"))
        out.append({
            "id": spec["id"],
            "name": spec["name"],
            "traits": spec.get("traits", {}),
            "title": spec["outcome"].get("title", spec["name"]),
            "blurb": spec["outcome"].get("blurb", ""),
            "icon": spec["outcome"].get("icon", ""),
            "order": spec["outcome"].get("order", 99),
            "fields": spec["fields"],
            "cards": spec["cards"],
            "limits": spec["limits"],
            "rate": rate,
            "rate_source": source,
            "seconds_per_word": seconds_per_word(conn, spec["id"]) if conn else 0.0,
        })
    return sorted(out, key=lambda o: o["order"])
