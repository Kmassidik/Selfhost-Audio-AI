#!/usr/bin/env python3
"""The worker — one song at a time, on the cards, for the Dalang Music Box app.

The web app only writes a job row. This process claims it, drives the engine,
and turns the result into a song: master WAV, MP3 for listeners, a cover, and
the row the library reads.

Two things it does that the old one could not:

  * **weights stay warm.** The audio.cpp engine runs as a resident server
    (`audiocpp_server`) with one model loaded, so a song does not pay the
    12-25 s reload every time. Switching models unloads first and waits for
    the driver to report the memory back, because a killed model is not a
    freed card.
  * **it follows the queue's model.** Given a choice it takes the next job
    that matches what is already loaded, so a batch of YuE2 songs costs one
    load instead of one per song.

MiniMax is the exception: its own Python pipeline, all three cards, never
served by the engine process. It is run per job, because its reload is noise
next to its 6.9 RTF.

    SELFHOSTAUDIO_ROOT=/root/Desktop/selfhostaudioai python3 -u box-worker.py
"""
import base64
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.environ.get("SELFHOSTAUDIO_ROOT", "/root/Desktop/selfhostaudioai")
HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(os.path.dirname(HERE), "catalog")
ENV_FILE = os.path.join(os.path.dirname(HERE), "deploy", ".env")
ENGINE_CONFIG = os.path.join(HERE, "engine-models.json")
ENGINE_BIN = os.path.join(ROOT, "engines", "audiocpp", "build", "linux-cuda-full", "bin", "audiocpp_server")
MINIMAX_PY = os.path.join(ROOT, "engines", "minimax-py", ".venv", "bin", "python")

MEDIA = os.path.join(ROOT, "data", "studio")
AUDIO_DIR = os.path.join(MEDIA, "audio")
MP3_DIR = os.path.join(MEDIA, "mp3")
COVER_DIR = os.path.join(MEDIA, "covers")
LOG_DIR = os.path.join(ROOT, "runs", "worker")
ENGINE_PORT = int(os.environ.get("WORKER_ENGINE_PORT", "8077"))
ENGINE_URL = "http://127.0.0.1:%d" % ENGINE_PORT

for d in (AUDIO_DIR, MP3_DIR, COVER_DIR, LOG_DIR):
    os.makedirs(d, exist_ok=True)

# ── settings ─────────────────────────────────────────────────────────
def setting(key, default=""):
    """The box's own .env is the source of truth for the database URL."""
    if key in os.environ:
        return os.environ[key]
    try:
        for line in open(ENV_FILE):
            if line.startswith(key + "="):
                return line.split("=", 1)[1].strip()
    except OSError:
        pass
    return default


DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgres://music:%s@127.0.0.1:54329/musicbox" % setting("POSTGRES_PASSWORD", "musicbox-db"),
)

DEFAULT_SEED = 20260915          # the seed every measured run on this box used
RUNNING = True
ENGINE = {"proc": None, "loaded": None}


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def new_song_id():
    """The id convention the media route already understands."""
    return time.strftime("%Y%m%d-%H%M%S-") + os.urandom(3).hex()


# ── the engine server, kept warm ─────────────────────────────────────
def engine_alive():
    proc = ENGINE["proc"]
    return proc is not None and proc.poll() is None


def engine_health(timeout=3):
    try:
        with urllib.request.urlopen(ENGINE_URL + "/health", timeout=timeout) as r:
            return json.loads(r.read())
    except Exception:
        return None


def start_engine():
    """Start the engine from our config — and only from our config.

    A running engine is reused only if it reports the same number of models we
    have configured: an engine left over from an older config would silently
    keep serving a model the app has dropped (ACE-Step stayed resident after
    being removed from the catalogue, which is what prompted this).
    """
    health = engine_health() if engine_alive() else None
    if health:
        configured = len(json.load(open(ENGINE_CONFIG))["models"])
        if health.get("models") == configured:
            return
        log("engine is running an older config (%s models vs %s) — restarting it"
            % (health.get("models"), configured))
        stop_engine()

    if engine_alive():
        stop_engine()
    logfile = open(os.path.join(LOG_DIR, "engine.log"), "a")
    ENGINE["proc"] = subprocess.Popen(
        [ENGINE_BIN, "--config", ENGINE_CONFIG, "--no-ui", "--max-loaded-models", "1", "--busy-timeout-ms", "0"],
        stdout=logfile, stderr=subprocess.STDOUT, start_new_session=True,
    )
    for _ in range(120):
        time.sleep(0.5)
        if not engine_alive():
            raise RuntimeError("the engine exited on start — see runs/worker/engine.log")
        if engine_health():
            log("engine up")
            return
    raise RuntimeError("the engine did not come up in 60 s")


def engine_api(path, payload=None, timeout=1800):
    data = json.dumps(payload).encode() if payload is not None else b"{}"
    req = urllib.request.Request(ENGINE_URL + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def stop_engine():
    """Ask the engine to let go of its models, then stop the process."""
    proc = ENGINE["proc"]
    if proc is not None and proc.poll() is None:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            proc.wait(timeout=60)
        except Exception:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
    ENGINE["proc"] = None
    ENGINE["loaded"] = None


def unload_models():
    if not engine_alive():
        return
    try:
        engine_api("/v1/tasks/unload_all_models", {}, timeout=180)
    except Exception as e:
        log("unload said:", str(e)[:120])
    ENGINE["loaded"] = None


def cards():
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5).stdout
        return [{"index": int(a), "used": int(b), "total": int(c)}
                for a, b, c in (line.split(",") for line in out.strip().splitlines())]
    except Exception:
        return []


def free_cards(seconds=90):
    """A killed or unloaded model is not a freed card: wait for the driver."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if all(c["used"] < 1200 for c in cards()):
            return True
        time.sleep(2)
    return False


# ── the catalogue decides how each model is driven ───────────────────
def model_spec(model_id):
    with open(os.path.join(CATALOG, model_id + ".json")) as f:
        return json.load(f)


def fill(text, params, extra=None):
    """{style} {lyrics} {duration} {seed} {out} — the placeholders the catalogue uses."""
    out = {"style": params.get("style", ""), "lyrics": params.get("lyrics", ""),
           "duration": int(params.get("duration") or 0), "seed": params.get("seed") or 20260915}
    if extra:
        out.update(extra)
    for key, value in list(out.items()):
        text = str(text).replace("{%s}" % key, str(value))
    return text


def engine_request(spec, params):
    """The catalogue's CLI args, translated into the server's request fields.

    The catalogue stays the authority on how a model is run — this only renames
    the flags the engine server already takes as JSON.
    """
    request = {"seed": params.get("seed") or DEFAULT_SEED}
    options, args = {}, list(spec["run"].get("args", []))
    i = 0
    while i < len(args):
        a = args[i]
        value = ""
        if a.startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
            value = fill(args[i + 1], params)
            i += 1
        i += 1
        if not a.startswith("--"):
            continue
        if a == "--text":
            request["text"] = value
        elif a == "--lyrics":
            request["lyrics"] = value
        elif a == "--duration-seconds":
            request["duration_seconds"] = float(value or 0)
        elif a == "--task-route":
            request["task_route"] = value
        elif a == "--request-option":
            key, _, val = value.partition("=")
            options[key] = val
        elif a == "--session-option":
            continue                      # session options live in the engine config
        elif a in ("--threads",):
            continue
    # advanced fields the create page may send
    for key in ("guidance_scale", "num_inference_steps", "cot", "vocal_language", "bpm", "keyscale", "shift"):
        if params.get(key) not in (None, ""):
            options[key] = params[key]
    if options:
        request["options"] = options
    return request


def minimax_command(spec, params, song_id):
    out = os.path.join(AUDIO_DIR, song_id + ".wav")
    run = spec["run"]
    env = dict(os.environ,
               HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1",
               SELFHOSTAUDIO_ROOT=ROOT,
               **{k: str(v) for k, v in (run.get("env") or {}).items()},
               # the growing key-value cache fragments the default allocator:
               # 1.3 GB lost per card on a 3.6-minute song (experiment 13a-2)
               PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
    env.pop("CUDA_VISIBLE_DEVICES", None)          # all three cards (experiment 12)
    args = [fill(a, params, {"out": out}) for a in run["args"]]
    return [MINIMAX_PY, os.path.join(ROOT, run["script"])] + args, env, out


def audiocpp_audio(spec, params, song_id):
    """One task on the engine server; its audio comes back base64."""
    request = engine_request(spec, params)
    res = engine_api("/v1/tasks/run", {"model": spec["id"], "request": request})
    audio = res.get("audio") or next(iter(res.get("named_audio_outputs") or []), {}).get("audio")
    if not audio:
        raise RuntimeError("the engine returned no audio")
    out = os.path.join(AUDIO_DIR, song_id + ".wav")
    with open(out, "wb") as f:
        f.write(base64.b64decode(audio))
    return out


# ── turning a take into a song ───────────────────────────────────────
def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=sample_rate,channels:format=duration", "-of", "default=nw=1:nk=1", path],
                       capture_output=True, text=True, timeout=60)
    vals = [v for v in r.stdout.split() if v]
    return (float(vals[2]) if len(vals) > 2 else 0.0,
            int(vals[0]) if vals else 0,
            int(vals[1]) if len(vals) > 1 else 0)


def to_mp3(wav, song_id, bitrate="128k"):
    out = os.path.join(MP3_DIR, song_id + ".mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "libmp3lame",
                    "-b:a", bitrate, "-id3v2_version", "3", out],
                   capture_output=True, text=True, timeout=1800, check=True)
    return out


# the cover takes its colour from what the song IS, not from the model that
# made it: a morning song is amber, a night song indigo (the studio's own rule)
TAG_HUE = {"Morning": 32, "Night": 250, "Rainy": 205, "Chill": 175, "Upbeat": 335, "Sad": 222,
           "Focus": 190, "Lo-fi": 30, "Hip hop": 300, "Jazz": 42, "Electronic": 265, "Ambient": 195,
           "Cinematic": 14, "Indie pop": 340, "Rock": 6, "Folk": 62, "Neo soul": 285, "Ballad": 315,
           "Funk": 46, "Japanese": 350, "Instrumental": 168}
DEFAULT_HUE = 28


def hsv_hex(h, s, v):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
    return "%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
CJK_FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def _font_for(text):
    if re.search(r"[\u3040-\u30ff\u4e00-\u9faf\uac00-\ud7af]", text or ""):
        for path in (CJK_FONT,):
            if os.path.exists(path):
                return path
    return FONT if os.path.exists(FONT) else CJK_FONT


def wrap_title(title, per_line=16, lines=2):
    words, out, current = (title or "Untitled").split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > per_line and current:
            out.append(current)
            current = word
        else:
            current = (current + " " + word).strip()
        if len(out) == lines:
            break
    if current and len(out) < lines:
        out.append(current)
    return out or ["Untitled"]


def fetch_photo(seed, out, timeout=25):
    """One photograph per song, the same one forever (Picsum serves Unsplash).

    Deterministic by the song's own id, so a song keeps its sleeve. If the box
    cannot reach the service the drawn gradient takes over — a song always has
    art (the old studio's rule, kept).
    """
    # a title with spaces is not a URL: quote it, or the request dies with
    # "URL can't contain control characters" and the sleeve falls back to a
    # gradient (measured on the first MusicGen take)
    from urllib.parse import quote
    url = "https://picsum.photos/seed/%s/1080/1080" % quote(str(seed), safe="")
    raw = out + ".src.jpg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "dalang-music-box/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if not r.headers.get("content-type", "").startswith("image/"):
                return None
            data = r.read()
        if len(data) < 5000:
            return None
        with open(raw, "wb") as f:
            f.write(data)
        return raw
    except Exception as e:
        log("photo for", seed, "failed:", str(e)[:80])
        return None


def draw_gradient(song_id, deep, glow, out, text_chain):
    chain = (f"gradients=s=1080x1080:c0=0x{deep}:c1=0x{glow}:x0=0:y0=1080:x1=1080:y1=0,"
             "format=rgb24,drawbox=x=0:y=780:w=1080:h=300:color=black@0.34:t=fill" + text_chain)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", chain,
                    "-frames:v", "1", out], capture_output=True, text=True, timeout=120)
    return out


def asset_path(name):
    """A chosen background from the asset library, if it is really there."""
    if not name:
        return None
    safe = os.path.basename(str(name))
    path = os.path.join(MEDIA, "assets", safe)
    return path if os.path.exists(path) else None


def cover(song_id, tags, title, label="", asset=None):
    """A sleeve: a photograph, graded to the song's colour, with the title on it.

    Square (1080x1080) because the library shows covers square — a 16:9 sleeve
    had its left edge, and the title, cropped off. No film grain: a full-frame
    noise filter on a still is not grain, it is television static (measured:
    5.6 MB of static against 66 KB of gradient).
    """
    hue = None
    for t in tags or []:
        if t in TAG_HUE:
            hue = TAG_HUE[t]
            break
    if hue is None:
        hue = DEFAULT_HUE
    deep = hsv_hex(hue / 360.0, 0.62, 0.14)
    glow = hsv_hex(((hue + 40) % 360) / 360.0, 0.55, 0.92)
    out = os.path.join(COVER_DIR, song_id + ".png")

    text_files, text_chain = [], ""
    try:
        font = _font_for(title)
        if font and os.path.exists(font):
            lines = wrap_title(title)
            size = 78
            y = 1080 - 90 - (len(lines) - 1) * int(size * 1.15) - size
            if label:
                lf = out + ".label.txt"
                with open(lf, "w") as f:
                    f.write(label.upper()[:24])
                text_files.append(lf)
                text_chain += (f",drawtext=textfile='{lf}':fontfile='{font}':fontcolor=white@0.85:"
                               f"fontsize=30:x=70:y={y - 56}")
            for i, line in enumerate(lines):
                tf = out + ".line%d.txt" % i
                with open(tf, "w") as f:
                    f.write(line)
                text_files.append(tf)
                text_chain += (f",drawtext=textfile='{tf}':fontfile='{font}':fontcolor=white:"
                               f"fontsize={size}:x=70:y={y + i * int(size * 1.15)}:"
                               "shadowcolor=black@0.55:shadowx=0:shadowy=3")

        photo = asset_path(asset)
        if not photo:
            # no choice made: a photograph chosen by the title, so a song keeps
            # the same sleeve for as long as it keeps its name
            photo = fetch_photo(title or song_id, out)
        if not photo:
            return draw_gradient(song_id, deep, glow, out, text_chain)

        # a duotone in the song's own colour, the bottom darkened for the words
        chain = ",".join([
            "scale=1080:1080:force_original_aspect_ratio=increase",
            "crop=1080:1080",
            "format=gray",
            "format=yuv444p",
            f"colorize=hue={hue}:saturation=0.72:lightness=0.04",
            "curves=preset=increase_contrast",
            "eq=brightness=-0.02:contrast=1.12:saturation=1.5",
            "format=rgb24",
            "drawbox=x=0:y=780:w=1080:h=300:color=black@0.38:t=fill",
        ]) + text_chain
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", photo, "-vf", chain, out],
                       capture_output=True, text=True, timeout=180)
        return out
    except Exception as e:
        log("cover failed, drawing one:", str(e)[:100])
        return draw_gradient(song_id, deep, glow, out, text_chain)
    finally:
        for f in text_files + [out + ".src.jpg"]:
            if os.path.exists(f):
                os.remove(f)


def clean_title(title, model_name):
    title = re.sub(r"\s*\((?:YuE2|MiniMax[^)]*|Stable Audio|ACE-Step[^)]*)\)\s*$", "", title or "").strip()
    return title or model_name


def sweep_orphans(conn, older_than_s=600):
    """Delete media whose song is gone.

    The web app cannot: its view of the data tree is read-only on purpose. The
    worker owns the bytes, so it cleans up after a deletion — and after any
    future orphan. A file younger than `older_than_s` is left alone, in case a
    song is being written right now.
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM songs")
        known = {r[0] for r in cur.fetchall()}
    removed = 0
    now = time.time()
    for kind, ext in (("audio", ".wav"), ("mp3", ".mp3"), ("covers", ".png"), ("video", ".mp4")):
        folder = os.path.join(MEDIA, kind)
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if not name.endswith(ext):
                continue
            song_id = name[: -len(ext)]
            path = os.path.join(folder, name)
            if song_id in known or now - os.path.getmtime(path) < older_than_s:
                continue
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    if removed:
        log("swept", removed, "orphaned file(s)")
    return removed


# ── the queue ────────────────────────────────────────────────────────
def connect():
    import psycopg2
    return psycopg2.connect(DATABASE_URL)


def claim(conn, prefer):
    """The oldest waiting job — preferring the model the engine already holds."""
    with conn, conn.cursor() as cur:
        if prefer:
            cur.execute("""SELECT id, model, title, params, creator_id FROM jobs
                           WHERE status='queued' AND model=%s ORDER BY id LIMIT 1""", (prefer,))
            row = cur.fetchone()
        else:
            row = None
        if row is None:
            cur.execute("""SELECT id, model, title, params, creator_id FROM jobs
                           WHERE status='queued' ORDER BY id LIMIT 1""")
            row = cur.fetchone()
        if row is None:
            return None
        cur.execute("""UPDATE jobs SET status='running', started_at=%s,
                       progress='{"stage":"loading"}'::jsonb WHERE id=%s""", (now(), row[0]))
    return {"id": row[0], "model": row[1], "title": row[2], "params": row[3] or {}, "creator_id": row[4] or ""}


def progress(conn, job_id, **fields):
    with conn, conn.cursor() as cur:
        cur.execute("UPDATE jobs SET progress=%s::jsonb WHERE id=%s", (json.dumps(fields), job_id))


def finish(conn, job_id, song_id=None, error="", wall=None):
    with conn, conn.cursor() as cur:
        cur.execute("""UPDATE jobs SET status=%s, song_id=%s, error=%s, finished_at=%s, wall_s=%s,
                       progress='{}'::jsonb WHERE id=%s""",
                    ("failed" if error else "done", song_id, error[-300:], now(), wall, job_id))


def add_song(conn, song_id, spec, job, took, media):
    seconds, rate, channels = took
    params = job["params"]
    tags = [t for t in (params.get("tags") or []) if t][:8]
    title = clean_title(job.get("title") or "", spec["name"])
    style = params.get("style", "")
    lyrics = params.get("lyrics", "")
    with conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO songs (id,title,model,seed,style,lyrics,seconds,sample_rate,channels,
                       created_at,source,creator_id,visible,has_mp3,has_video,cover_v,formats)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'generated',%s,TRUE,TRUE,FALSE,%s,%s)
                       ON CONFLICT (id) DO NOTHING""",
                    (song_id, title, spec["id"], str(params.get("seed") or DEFAULT_SEED), style, lyrics,
                     seconds, rate, channels, now(), job["creator_id"], media["cover_v"],
                     ["wav", "mp3"]))
        for tag in tags:
            cur.execute("INSERT INTO tags (song_id, tag) VALUES (%s, %s) ON CONFLICT DO NOTHING", (song_id, tag))
    return title


def run_one(conn, job):
    spec = model_spec(job["model"])
    song_id = new_song_id()
    params = dict(job["params"])
    started = time.time()
    engine_kind = spec.get("engine", "audiocpp")

    if engine_kind != "python" and ENGINE["loaded"] != spec["id"]:
        log("switching to", spec["id"])
        progress(conn, job["id"], stage="switching", to=spec["id"])
        unload_models()
        if not free_cards():
            log("cards did not fully free in 90 s — carrying on")
        if engine_kind != "python":
            start_engine()
        ENGINE["loaded"] = spec["id"]

    progress(conn, job["id"], stage="generating", model=spec["id"], cards=cards())

    if engine_kind == "python":
        cmd, env, out = minimax_command(spec, params, song_id)
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        while proc.poll() is None:
            time.sleep(5)
            progress(conn, job["id"], stage="generating", model=spec["id"],
                     elapsed_s=round(time.time() - started), cards=cards())
        output = proc.stdout.read() if proc.stdout else ""
        if proc.returncode != 0 or not os.path.exists(out):
            raise RuntimeError((output.strip().splitlines() or ["minimax failed"])[-1][:280])
    else:
        start_engine()
        out = audiocpp_audio(spec, params, song_id)

    took = probe(out)
    progress(conn, job["id"], stage="encoding", seconds=took[0])

    title_for_cover = clean_title(job.get("title") or "", spec["name"])
    mp3 = to_mp3(out, song_id)
    png = cover(song_id, params.get("tags") or [], title_for_cover,
                (params.get("tags") or [""])[0], params.get("cover_asset"))
    media = {"cover_v": os.path.getmtime(png) if os.path.exists(png) else 0}
    title = add_song(conn, song_id, spec, job, took, media)
    wall = round(time.time() - started, 1)
    finish(conn, job["id"], song_id=song_id, wall=wall)
    log("done", song_id, title[:40], "%ss audio in %ss" % (round(took[0], 1), wall),
        "rtf", round(wall / took[0], 2) if took[0] else "-", "mp3", os.path.basename(mp3))
    return True


def stop(signum, frame):
    global RUNNING
    RUNNING = False
    log("signal", signum, "— finishing the song in hand, then stopping")


# ── the loop ─────────────────────────────────────────────────────────
def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log("worker up · root", ROOT, "· engine", ENGINE_URL)
    conn = connect()
    try:
        start_engine()
    except Exception as e:
        log("engine start failed:", e)
    while RUNNING:
        try:
            job = claim(conn, ENGINE["loaded"])
        except Exception as e:
            log("database said:", str(e)[:160])
            time.sleep(5)
            continue
        if not job:
            time.sleep(3)
            try:
                sweep_orphans(conn)
            except Exception as e:
                log("sweep said:", str(e)[:120])
            continue
        log("job", job["id"], job["model"], repr(job.get("title"))[:40])
        try:
            run_one(conn, job)
        except Exception as e:
            log("job", job["id"], "failed:", str(e)[:200])
            try:
                finish(conn, job["id"], error=str(e))
            except Exception:
                pass
    log("worker stopping with the queue as it stands")
    try:
        conn.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
