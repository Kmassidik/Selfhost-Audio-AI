#!/usr/bin/env python3
"""The studio — pick a template, tweak, generate. Standard library only.

    python3 serve/studio.py                 # serves http://0.0.0.0:8095
    STUDIO_PORT=8099 python3 serve/studio.py

One page (studio.html) in front of ONE resident model at a time, with every
default this project MEASURED rather than guessed:

  - a seed is always passed and recorded       ch.06: without it, same input != same bytes
  - VoxCPM2 long text is chunked at 400 chars  ch.08: the default fails past ~60 s
  - VoxCPM2 reference clips trimmed to 14.5 s  ch.08: 15.0 s is refused
  - YuE2 plans with melody by default          ch.27: 27% FASTER than planning off
  - Stable Audio capped at 120 s               ch.24: a hard cap, silently enforced
  - one model loaded, jobs one by one          the LLM sibling's arena rule: never two
                                                models resident; switching = unload, wait
                                                until the driver has the memory back, load
  - compare loudness-matches before playing    ch.13: louder always wins otherwise

Jobs and audio live in runs/studio/ on the box. Blind comparisons are written to
listening/, one JSON per session, the format chapter 13 specifies.
"""
import base64, json, os, queue, signal, random, re, shutil, struct, subprocess, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("SELFHOSTAUDIO_ROOT", os.path.dirname(HERE))
CLI = os.path.join(ROOT, "engines", "audiocpp", "build",
                   os.environ.get("AUDIOCPP_BUILD", "linux-cuda-full"), "bin", "audiocpp_cli")
G = os.path.join(ROOT, "models", "gguf")
OUT = os.path.join(ROOT, "runs", "studio")
UPL = os.path.join(OUT, "uploads")
LISTEN = os.path.join(ROOT, "listening")
for d in (OUT, UPL, LISTEN):
    os.makedirs(d, exist_ok=True)

CARDS = [int(c) for c in os.environ.get("STUDIO_CARDS", "0,1,2").split(",")]
REF_MAX_S = 14.5
SA_MAX_S = 120

MODELS = {
    "yue2":         {"kind": "sing",  "label": "YuE2 — full songs with vocals", "path": os.path.join(G, "Yue2-3B-GGUF")},
    "stable-audio": {"kind": "sing",  "label": "Stable Audio — instrumental, up to 2 min",
                     "path": os.path.join(G, "Stable-Audio-3-Small-Music-GGUF", "stable-audio-3-small-music-q8_0.gguf")},
    "minimax":      {"kind": "sing",  "label": "MiniMax-Music3 — best vocals, all three cards, RTF ~7",
                     "path": os.path.join(ROOT, "models", "hf", "MiniMax-Music3")},
    "kokoro":       {"kind": "speak", "label": "Kokoro — fast, 49 voices",
                     "path": os.path.join(G, "Kokoro-82M-GGUF", "kokoro-82m-q8_0.gguf")},
    "qwen3":        {"kind": "speak", "label": "Qwen3 — 9 speakers, takes direction",
                     "path": os.path.join(G, "Qwen3-TTS-12Hz-1.7B-CustomVoice-GGUF",
                                          "qwen3-tts-12hz-1.7b-customvoice-q8_0.gguf")},
    "voxcpm2":      {"kind": "speak", "label": "VoxCPM2 — 48 kHz, 30 languages, clones a voice",
                     "path": os.path.join(G, "VoxCPM2-GGUF", "voxcpm2-q8_0.gguf")},
    "canary":       {"kind": "listen", "label": "Canary — speech to text",
                     "path": os.path.join(G, "Canary-180M-Flash-GGUF", "canary-180m-flash-q8_0.gguf")},
}

KOKORO_VOICES = ("af_alloy af_aoede af_bella af_heart af_jessica af_kore af_nicole af_nova af_river "
                 "af_sarah af_sky am_adam am_echo am_eric am_fenrir am_liam am_michael am_onyx am_puck "
                 "am_santa bf_alice bf_emma bf_isabella bf_lily bm_daniel bm_fable bm_george bm_lewis "
                 "ef_dora em_alex em_santa ff_siwis hf_alpha hf_beta hm_omega hm_psi if_sara im_nicola "
                 "jf_alpha jf_gongitsune jf_nezumi jf_tebukuro jm_kumo pf_dora pm_alex pm_santa "
                 "zf_xiaobei zf_xiaoni zf_xiaoxiao zf_xiaoyi zm_yunjian zm_yunxi zm_yunxia zm_yunyang").split()
# Japanese voices (j*) are left out: the packaged GGUF lacks the UniDic dictionary
# they need — "Kokoro UniDic resources are not bundled in this GGUF". Found by the
# studio's own smoke test, 2026-09-18. Re-exporting with multilingual resources
# would bring them back.
KOKORO_VOICES = [v for v in KOKORO_VOICES if not v.startswith("j")]
# The first letter of a Kokoro voice is its language.
KOKORO_LANG = {"a": "en-us", "b": "en-gb", "e": "es", "f": "fr-fr", "h": "hi",
               "i": "it", "j": "ja", "p": "pt-br", "z": "zh"}
QWEN3_SPEAKERS = ["Vivian", "Serena", "Ryan", "Aiden", "Dylan", "Eric",
                  "Uncle_Fu", "Ono_Anna", "Sohee"]

# ── state ────────────────────────────────────────────────────────────
JOBS = {}
LOCK = threading.Lock()
Q = queue.Queue()


# ── the one resident model ───────────────────────────────────────────
# Same rule as the LLM sibling's arena (selfhostllm/serve/arena.py): one model
# on the cards at a time, and a switch is unload -> wait until the DRIVER reports
# the memory back -> load. The audio.cpp models live in the engine's own server
# with --max-loaded-models 1; MiniMax-Music3 is a separate process that needs all
# three cards, so switching to it stops the engine outright (a process exit is
# the one unload that always gives the memory back).
ENGINE_BIN = os.path.join(os.path.dirname(CLI), "audiocpp_server")
ENGINE_PORT = int(os.environ.get("STUDIO_ENGINE_PORT", "8097"))
ENGINE_CARD = CARDS[0]
ENGINE_ID = {"kokoro": "kokoro", "qwen3": "qwen3-tts", "voxcpm2": "voxcpm2",
             "canary": "canary", "yue2": "yue2", "stable-audio": "stable-audio"}
engine = {"proc": None, "loaded": None, "switching": None, "busy": None, "note": ""}


def vram():
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
                              "--format=csv,noheader,nounits"], capture_output=True, text=True,
                             timeout=5).stdout
        return [dict(zip(("used", "total", "util"), map(int, l.split(","))))
                for l in out.strip().splitlines()]
    except Exception:
        return []


def wait_free(floor=600, timeout=90):
    """A killed or unloaded model is not a freed card (arena, lesson one)."""
    end = time.time() + timeout
    while time.time() < end:
        rows = vram()
        if rows and max(r["used"] for r in rows) <= floor:
            return True
        time.sleep(0.5)
    return False


def engine_api(path, body=None, timeout=4 * 3600):
    req = urllib.request.Request(f"http://127.0.0.1:{ENGINE_PORT}{path}",
                                 json.dumps(body).encode() if body is not None else None,
                                 {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")
        try:
            msg = json.loads(msg).get("error", msg)
        except Exception:
            pass
        raise RuntimeError(f"engine {e.code}: {msg if isinstance(msg, str) else json.dumps(msg)}"[:400])


def reap_orphans():
    """An engine left behind by an earlier studio holds a card while the page says nothing is loaded."""
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            cmd = open(f"/proc/{d}/cmdline", "rb").read().split(b"\0")
        except Exception:
            continue
        if cmd and cmd[0].decode("utf-8", "replace") == ENGINE_BIN:
            try:
                os.killpg(os.getpgid(int(d)), signal.SIGKILL)
            except Exception:
                pass


def engine_alive():
    p = engine["proc"]
    return p is not None and p.poll() is None


def start_engine():
    cfg = json.load(open(os.path.join(HERE, "server.json")))
    cfg.pop("_comment", None)
    cfg.update(host="127.0.0.1", port=ENGINE_PORT, device=ENGINE_CARD, lazy_load=True)
    for m in cfg["models"]:                    # server.json paths are relative to serve/
        m["path"] = os.path.normpath(os.path.join(HERE, m["path"]))
    path = os.path.join(ROOT, "runs", "studio-engine.json")   # NOT in OUT: every .json there is a job
    json.dump(cfg, open(path, "w"), indent=2)
    log = open(os.path.join(ROOT, "runs", "studio-engine.log"), "a")
    engine["proc"] = subprocess.Popen(
        [ENGINE_BIN, "--config", path, "--no-ui", "--max-loaded-models", "1", "--busy-timeout-ms", "0"],
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(120):
        time.sleep(0.5)
        if not engine_alive():
            raise RuntimeError("engine exited on start — see runs/studio-engine.log")
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{ENGINE_PORT}/health", timeout=2)
            return
        except Exception:
            pass
    raise RuntimeError("engine did not come up in 60 s")


def stop_engine():
    p = engine["proc"]
    if p is not None and p.poll() is None:
        try:
            os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            p.wait(timeout=15)
        except Exception:
            pass
    engine["proc"] = None


def switch_to(m):
    """Make `m` the one model on the cards. Returns True if this was a switch."""
    if engine["loaded"] == m and (m == "minimax" or engine_alive()):
        return False
    engine["switching"] = m
    try:
        if m == "minimax" or not engine_alive():
            stop_engine()
        else:
            engine_api("/v1/tasks/unload_all_models", {}, timeout=120)
        engine["loaded"] = None
        engine["note"] = "" if wait_free() else "cards did not fully free in 90 s — something else is using them"
        if m != "minimax":
            start_engine() if not engine_alive() else None
        engine["loaded"] = m               # audio.cpp loads it on the first request (lazy)
        return True
    finally:
        engine["switching"] = None


def unload():
    stop_engine()
    engine["loaded"] = None
    wait_free()


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def save(job):
    with open(os.path.join(OUT, job["id"] + ".json"), "w") as f:
        json.dump(job, f, indent=2)


def load_history():
    for f in os.listdir(OUT):
        if f.endswith(".json"):
            try:
                j = json.load(open(os.path.join(OUT, f)))
            except Exception:
                continue
            if not isinstance(j, dict) or "id" not in j:
                continue
            if j.get("status") in ("queued", "running"):
                j["status"], j["error"] = "failed", "interrupted — the studio was restarted"
            JOBS[j["id"]] = j


def wav_seconds(path):
    try:
        b = open(path, "rb").read(4096)
        i = b.find(b"fmt ")
        ch, sr = struct.unpack("<HI", b[i + 10:i + 16])
        bits = struct.unpack("<H", b[i + 22:i + 24])[0]
        d = b.find(b"data")
        n = struct.unpack("<I", b[d + 4:d + 8])[0]
        return round(n / (sr * ch * bits // 8), 2), sr, ch
    except Exception:
        return None, None, None


def ffmpeg(*args):
    return subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args],
                          capture_output=True, text=True).returncode == 0


# ── building each request, one place per model ──────────────────────
def minimax_command(job, out):
    p = job["params"]
    py = os.path.join(ROOT, "engines", "minimax-py", ".venv", "bin", "python")
    job_py = os.path.join(ROOT, "source", "42_minimax_music3_job.py")
    secs = max(5, min(300, int(p.get("duration", 30))))   # 217 s measured to fit (exp. 13a-3)
    env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", SELFHOSTAUDIO_ROOT=ROOT,
               # the growing key-value cache fragments the default allocator: 1.3 GB lost
               # per card on a 3.6-minute song (experiment 13a-2)
               PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True")
    env.pop("CUDA_VISIBLE_DEVICES", None)          # all three cards (experiment 12)
    return [py, job_py, "--prompt", p.get("style", ""), "--lyrics", p["lyrics"],
            "--seconds", str(secs), "--seed", str(p["seed"]), "--out", out], env


def engine_request(job):
    """The engine server takes the same fields as the CLI's request-sequence JSON."""
    p, m = job["params"], job["model"]
    r = {} if m == "canary" else {"seed": int(p["seed"])}   # Canary refuses a seed option outright
    if m == "yue2":
        r.update(lyrics=p["lyrics"], options={"style": p.get("style", ""),
                                              "cot": p.get("planning", "melody"),
                                              "num_inference_steps": str(int(p.get("steps", 8)))})
    elif m == "stable-audio":
        r.update(text=p["prompt"], duration_seconds=max(1, min(SA_MAX_S, int(p.get("duration", 30)))))
    elif m == "kokoro":
        v = p.get("voice", "af_heart")
        r.update(text=p["text"], language=KOKORO_LANG.get(v[0], "en-us"), voice_id=v)
    elif m == "qwen3":
        r.update(text=p["text"], speaker=p.get("speaker", "Vivian"))
        if p.get("instruct"):
            r["instruct"] = p["instruct"]
    elif m == "voxcpm2":
        r.update(text=p["text"], text_chunk_size=400)
        if p.get("ref"):
            r["voice_ref"] = os.path.join(UPL, os.path.basename(p["ref"]))
            if p.get("ref_text"):
                r["reference_text"] = p["ref_text"]
    elif m == "canary":
        r.update(audio=os.path.join(UPL, os.path.basename(p["audio"])))
    else:
        raise ValueError(f"unknown model {m}")
    return {"model": ENGINE_ID[m], "request": r}


def worker():
    """One job at a time, on the one loaded model."""
    while True:
        jid = Q.get()
        with LOCK:
            job = JOBS.get(jid)
            if not job:
                continue
        m, is_text = job["model"], job["model"] == "canary"
        out = os.path.join(OUT, jid + (".txt" if is_text else ".wav"))
        try:
            if engine["loaded"] != m:
                with LOCK:
                    job["note"] = f"switching model: {engine['loaded'] or 'none'} → {m}"; save(job)
            t0 = time.time()
            switched = switch_to(m)
            with LOCK:
                job.pop("note", None)
                job.update(status="running", started=now(),
                           device="0+1+2" if m == "minimax" else ENGINE_CARD)
                if switched:
                    job["switch_s"] = round(time.time() - t0, 2)
                save(job)
            engine["busy"] = jid
            t0 = time.time()
            if m == "minimax":
                cmd, env = minimax_command(job, out)
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=4 * 3600, env=env)
                ok = r.returncode == 0 and os.path.exists(out)
                err = "" if ok else ((r.stderr or r.stdout).strip().splitlines() or ["failed"])[-1]
            else:
                res = engine_api("/v1/tasks/run", engine_request(job))
                if is_text:
                    open(out, "w").write(res.get("text", ""))
                else:
                    audio = res.get("audio") or next(iter(res.get("named_audio_outputs") or []), {}).get("audio")
                    if not audio:
                        raise RuntimeError("engine returned no audio")
                    open(out, "wb").write(base64.b64decode(audio))
                ok, err = True, ""
        except Exception as e:
            ok, err = False, str(e)
        finally:
            engine["busy"] = None
        wall = round(time.time() - t0, 2)
        with LOCK:
            job.update(finished=now(), wall_s=wall, cold=bool(job.get("switch_s") is not None))
            if ok and is_text:
                job.update(status="done", text=open(out).read().strip())
            elif ok:
                dur, sr, ch = wav_seconds(out)
                job.update(status="done", file=jid + ".wav", duration_s=dur,
                           sample_rate=sr, channels=ch,
                           rtf=round(wall / dur, 3) if dur else None)
            else:
                job.update(status="failed", error=err[-300:])
            save(job)


def submit(body):
    m = body.get("model")
    if m not in MODELS:
        raise ValueError("choose a model")
    p = dict(body.get("params") or {})
    n = max(1, min(8, int(body.get("variations", 1))))
    base_seed = int(p["seed"]) if str(p.get("seed", "")).strip().lstrip("-").isdigit() \
        else random.randint(1, 2**31 - 1)
    group = uuid.uuid4().hex[:8]
    ids = []
    for k in range(n):
        q = dict(p, seed=base_seed + k)
        jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        job = {"id": jid, "group": group, "model": m, "kind": MODELS[m]["kind"],
               "title": body.get("title") or MODELS[m]["label"].split(" —")[0],
               "template": body.get("template"), "params": q, "status": "queued",
               "created": now()}
        with LOCK:
            JOBS[jid] = job
            save(job)
        Q.put(jid)
        ids.append(jid)
    return ids


def take_upload(raw, filename, purpose):
    ext = os.path.splitext(filename or "")[1].lower() or ".bin"
    uid = uuid.uuid4().hex[:10]
    src = os.path.join(UPL, uid + "-src" + re.sub(r"[^.a-z0-9]", "", ext))
    open(src, "wb").write(raw)
    dst = os.path.join(UPL, uid + ".wav")
    note = ""
    if purpose == "ref":
        # VoxCPM2 refuses 15.0 s and accepts 14.5 s (ch.08). Trim rather than refuse.
        ok = ffmpeg("-i", src, "-ac", "1", "-ar", "24000", "-t", str(REF_MAX_S), dst)
        full = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                               "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip()
        try:
            if float(full) > REF_MAX_S:
                note = f"trimmed from {float(full):.1f} s to {REF_MAX_S} s — VoxCPM2 refuses longer clips"
        except ValueError:
            pass
    else:
        ok = ffmpeg("-i", src, "-ac", "1", "-ar", "16000", dst)
    os.remove(src)
    if not ok:
        raise ValueError("could not read that audio file")
    dur, _, _ = wav_seconds(dst)
    return {"id": uid + ".wav", "seconds": dur, "note": note}


# ── blind comparison (ch.13) ─────────────────────────────────────────
SESSIONS = {}


def start_compare(a, b, question):
    ja, jb = JOBS.get(a), JOBS.get(b)
    if not (ja and jb and ja.get("file") and jb.get("file")):
        raise ValueError("pick two finished audio takes")
    sid = uuid.uuid4().hex[:8]
    pair = [ja, jb]
    random.shuffle(pair)                      # the key stays on the server
    for slot, j in zip("AB", pair):
        # match loudness first — louder is judged better regardless of quality
        ffmpeg("-i", os.path.join(OUT, j["file"]), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
               "-ar", "48000", os.path.join(OUT, f"cmp-{sid}-{slot}.wav"))
    SESSIONS[sid] = {"key": {"A": pair[0]["id"], "B": pair[1]["id"]},
                     "question": question, "started": now()}
    return {"session": sid, "A": f"cmp-{sid}-A.wav", "B": f"cmp-{sid}-B.wav"}


def vote(sid, choice, why, listener):
    s = SESSIONS.pop(sid, None)
    if not s:
        raise ValueError("unknown or finished session")
    takes = []
    for slot in "AB":
        j = JOBS.get(s["key"][slot], {})
        takes.append({"slot": slot, "id": j.get("id"), "model": j.get("model"),
                      "seed": j.get("params", {}).get("seed"), "params": j.get("params"),
                      "chosen": slot == choice})
    rec = {"session": sid, "date": now(), "question": s["question"], "blind": True,
           "loudness_matched": "ffmpeg loudnorm, single pass, -16 LUFS",
           "listeners": 1, "listener": listener or None, "choice": choice,
           "testimony": why or None, "takes": takes,
           "note": "One listener, one judgement. Ordinal, not a measurement. See ch.13."}
    path = os.path.join(LISTEN, time.strftime("%Y-%m-%d-") + sid + ".json")
    json.dump(rec, open(path, "w"), indent=2)
    for slot in "AB":
        try:
            os.remove(os.path.join(OUT, f"cmp-{sid}-{slot}.wav"))
        except OSError:
            pass
    return {"revealed": {t["slot"]: {"model": t["model"], "seed": t["seed"], "id": t["id"]}
                         for t in takes}, "saved": os.path.relpath(path, ROOT)}


# ── HTTP ─────────────────────────────────────────────────────────────
class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, obj=None, body=None, ctype="application/json"):
        data = body if body is not None else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n) if n else b""

    def do_GET(self):
        u = urlparse(self.path)
        if u.path in ("/", "/index.html"):
            return self.send(200, body=open(os.path.join(HERE, "studio.html"), "rb").read(),
                             ctype="text/html; charset=utf-8")
        if u.path == "/api/config":
            tpl = json.load(open(os.path.join(HERE, "templates.json")))
            return self.send(200, {
                "templates": tpl,
                "models": {k: {"kind": v["kind"], "label": v["label"],
                               "installed": os.path.exists(v["path"])} for k, v in MODELS.items()},
                "kokoro_voices": KOKORO_VOICES, "qwen3_speakers": QWEN3_SPEAKERS,
                "limits": {"ref_max_s": REF_MAX_S, "stable_audio_max_s": SA_MAX_S},
                "cards": CARDS})
        if u.path == "/api/status":
            return self.send(200, {"loaded": engine["loaded"], "switching": engine["switching"],
                                   "busy": engine["busy"], "note": engine["note"],
                                   "engine_alive": engine_alive(), "queued": Q.qsize(),
                                   "vram": vram()})
        if u.path == "/api/jobs":
            with LOCK:
                jobs = sorted(JOBS.values(), key=lambda j: j["created"], reverse=True)[:300]
            return self.send(200, {"jobs": jobs, "queued": Q.qsize()})
        if u.path.startswith("/files/"):
            name = os.path.basename(u.path)
            path = os.path.join(OUT, name)
            if not re.fullmatch(r"[\w.-]+\.wav", name) or not os.path.exists(path):
                return self.send(404, {"error": "not found"})
            # Byte ranges: browsers stream and seek long takes with Range requests, and
            # Safari will not play audio from a server that ignores them.
            size = os.path.getsize(path)
            start, end, code = 0, size - 1, 200
            rng = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "").strip())
            if rng and (rng.group(1) or rng.group(2)):
                if rng.group(1):
                    start = int(rng.group(1)); end = int(rng.group(2)) if rng.group(2) else size - 1
                else:
                    start = max(0, size - int(rng.group(2)))
                end = min(end, size - 1)
                if start > end:
                    self.send_response(416); self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers(); return
                code = 206
            self.send_response(code)
            self.send_header("Content-Type", "audio/wav")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if code == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            if parse_qs(u.query).get("dl"):
                self.send_header("Content-Disposition", f'attachment; filename="{name}"')
            self.end_headers()
            try:
                with open(path, "rb") as f:
                    f.seek(start); left = end - start + 1
                    while left > 0:
                        chunk = f.read(min(1 << 20, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk); left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError):
                pass          # the browser cancelled a range it no longer needs
            return
        self.send(404, {"error": "not found"})

    def do_POST(self):
        u = urlparse(self.path)
        try:
            if u.path == "/api/jobs":
                return self.send(200, {"ids": submit(json.loads(self.body()))})
            if u.path == "/api/upload":
                q = parse_qs(u.query)
                return self.send(200, take_upload(self.body(), q.get("name", [""])[0],
                                                  q.get("purpose", ["audio"])[0]))
            if u.path == "/api/compare":
                b = json.loads(self.body())
                return self.send(200, start_compare(b.get("a"), b.get("b"), b.get("question", "")))
            if u.path == "/api/vote":
                b = json.loads(self.body())
                return self.send(200, vote(b.get("session"), b.get("choice"),
                                           b.get("why", ""), b.get("listener", "")))
            if u.path == "/api/unload":
                if engine["busy"] or engine["switching"] or Q.qsize():
                    return self.send(409, {"error": "a job is running or queued — unload when idle"})
                unload()
                return self.send(200, {"ok": True})
            m = re.fullmatch(r"/api/jobs/([\w-]+)/delete", u.path)
            if m:
                with LOCK:
                    j = JOBS.pop(m.group(1), None)
                if j:
                    for ext in (".json", ".wav", ".txt"):
                        try:
                            os.remove(os.path.join(OUT, j["id"] + ext))
                        except OSError:
                            pass
                return self.send(200, {"ok": True})
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            return self.send(400, {"error": str(e)})
        self.send(404, {"error": "not found"})


def main():
    if not os.path.exists(CLI):
        sys.exit(f"engine not found at {CLI}")
    load_history()
    reap_orphans()
    threading.Thread(target=worker, daemon=True).start()
    host = os.environ.get("STUDIO_HOST", "0.0.0.0")      # golden rule 1: never 127.0.0.1
    port = int(os.environ.get("STUDIO_PORT", "8095"))
    print(f"studio on http://{host}:{port}  ·  one model at a time  ·  {len(JOBS)} jobs in history",
          flush=True)
    ThreadingHTTPServer((host, port), H).serve_forever()


if __name__ == "__main__":
    main()
