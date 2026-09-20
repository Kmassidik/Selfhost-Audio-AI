"""The platform's HTTP service.

Public: browse, search, play. Owner-only: anything that spends a graphics card
or changes the box. The split is one dependency, used by every owner route, so
there is a single place to be wrong.

In production Caddy serves the audio files and this process only answers JSON.
For development SERVE_MEDIA=1 makes it serve media too, with byte ranges, so
the whole app runs from one command.
"""
import ipaddress
import os
import secrets

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field

import config
import db
import jobs
import library
import media as media_mod
import registry
import tags as tagger

S = config.settings()
ONLY = registry.music_ids() if S.music_only else ()   # a music platform hides the voices
DIRS = config.media_dirs(S)
DB_PATH = os.path.join(S.data_dir, "app.db")
FRONTEND = os.environ.get(
    "FRONTEND_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend"))

app = FastAPI(title="Music Studio", docs_url=None, redoc_url=None)


def conn():
    return db.shared(DB_PATH)


# ── who may change things ────────────────────────────────────────────
def _private(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def require_owner(request: Request) -> bool:
    """One gate for everything that costs a card or writes to the box.

    With a password set, the caller must send it. With no password set, the
    call must come from the local network — so a fresh deployment is never
    accidentally open to the internet.
    """
    token = (request.headers.get("authorization", "").removeprefix("Bearer ").strip()
             or request.headers.get("x-owner-key", "").strip())
    if S.owner_password:
        if secrets.compare_digest(token, S.owner_password):
            return True
        raise HTTPException(status_code=401, detail="owner password required")
    if _private(request.client.host if request.client else ""):
        return True
    raise HTTPException(status_code=401,
                        detail="no owner password is set, so creating is allowed "
                               "only from the local network")


Owner = Depends(require_owner)


# ── shapes the pages send ────────────────────────────────────────────
class JobIn(BaseModel):
    model: str
    params: dict = Field(default_factory=dict)
    title: str = ""


class PlayIn(BaseModel):
    seconds: float = 0


# ── public: browse and play ──────────────────────────────────────────
@app.get("/healthz")
def healthz():
    return {"ok": True, "songs": library.stats(conn(), ONLY)["songs"]}


@app.get("/api/library")
def get_library(q: str = "", model: str = "", liked: bool = False,
                tag: str = "", ids: str = "", sort: str = "new", seed: int = 0,
                offset: int = 0, limit: int = Query(default=0)):
    """A page of the library. `ids` fetches a browser-kept playlist in one request."""
    return library.page(conn(), q=q, model=model, liked=liked, tag=tag,
                        ids=[i for i in ids.split(",") if i][:500],
                        sort=sort, seed=seed, offset=offset, limit=limit or S.page_size,
                        max_limit=S.max_page_size, only_models=ONLY)


@app.get("/api/categories")
def get_categories():
    """Every category with enough songs to fill a row, biggest first."""
    return {"items": tagger.counts(conn(), ONLY, minimum=2)}


@app.get("/api/home")
def get_home(rows: int = 6, per_row: int = 12, small_library: int = 12):
    """The front page, in one request.

    A library of seven songs cannot fill Spotify's shape: every row would show
    the same songs and the page would look broken. So below `small_library`
    songs the page gets a feature and one clean list; above it, category rows —
    and a row only appears when it brings at least three songs the rows above
    did not already show.
    """
    c = conn()
    total = library.stats(c, ONLY)["songs"]
    out = {"total": total, "recent": library.recently_played(c, limit=6, only_models=ONLY)}

    newest = library.page(c, sort="new", limit=1, only_models=ONLY)["items"]
    out["feature"] = newest[0] if newest else None

    if total < small_library:
        out["mode"] = "small"
        out["rows"] = []
        return out

    out["mode"] = "rows"
    seen = set()
    made = []
    latest = library.page(c, sort="new", limit=per_row, only_models=ONLY)
    made.append({"title": "Latest", "tag": "", "items": latest["items"]})
    seen.update(s["id"] for s in latest["items"])

    for cat in tagger.counts(c, ONLY, minimum=3):
        if len(made) >= rows + 1:
            break
        page = library.page(c, tag=cat["tag"], sort="new", limit=per_row, only_models=ONLY)
        fresh = [s for s in page["items"] if s["id"] not in seen]
        if len(fresh) < 3:                       # a row that only repeats is not a row
            continue
        made.append({"title": cat["tag"], "tag": cat["tag"], "total": page["total"],
                     "items": page["items"]})
        seen.update(s["id"] for s in fresh)
    out["rows"] = made
    return out


@app.get("/api/song/{song_id}")
def get_song(song_id: str):
    song = library.get_song(conn(), song_id)
    if not song:
        raise HTTPException(status_code=404, detail="no such song")
    return song


@app.get("/api/stats")
def get_stats():
    return library.stats(conn(), ONLY)


@app.post("/api/like/{song_id}")
def like(song_id: str):
    return {"liked": library.set_like(conn(), song_id, True)}


@app.delete("/api/like/{song_id}")
def unlike(song_id: str):
    return {"liked": library.set_like(conn(), song_id, False)}


@app.post("/api/play/{song_id}")
def play(song_id: str, body: PlayIn | None = None):
    library.count_play(conn(), song_id, body.seconds if body else 0)
    return {"ok": True}


# Playlists live in the visitor's own browser (localStorage), not here: they are
# personal, they cost the box nothing, and the database stays small — the owner
# asked for exactly that. The page fetches a playlist with /api/library?ids=...

@app.get("/api/models")
def get_models():
    """The outcomes a person picks between, with this box's own speed figures."""
    return {"items": registry.outcomes(conn(), S.music_only)}


@app.post("/api/jobs")
def create_job(body: JobIn, _=Owner):
    spec = registry.get(body.model)
    if not spec:
        raise HTTPException(status_code=400, detail=f"unknown model {body.model}")
    if S.music_only and spec["kind"] != "sing":
        raise HTTPException(status_code=400, detail=f"{spec['name']} does not make music")
    if body.params.get("duration") is not None:
        try:
            body.params["duration"] = registry.as_seconds(body.params["duration"])
        except registry.BadModel as e:
            raise HTTPException(status_code=400, detail=str(e))
    gaps = registry.missing(body.model, body.params)
    if gaps:
        raise HTTPException(status_code=400,
                            detail=f"{spec['name']} needs {', '.join(gaps)} before it can start")
    job_id = jobs.enqueue(conn(), body.model, body.params, body.title)
    return {"id": job_id, **jobs.queue_depth(conn())}


@app.get("/api/jobs")
def list_jobs(status: str = "", limit: int = 50, _=Owner):
    return {"items": jobs.recent(conn(), limit=limit, status=status)}


@app.delete("/api/song/{song_id}")
def delete_song(song_id: str, _=Owner):
    out = library.remove(conn(), song_id)
    if not out["removed"]:
        raise HTTPException(status_code=404, detail="no such song")
    return out


@app.delete("/api/jobs/{job_id}")
def cancel_job(job_id: int, _=Owner):
    if not jobs.cancel(conn(), job_id):
        raise HTTPException(status_code=409, detail="that job has already started")
    return {"cancelled": job_id, **jobs.queue_depth(conn())}


@app.post("/api/video/{song_id}")
def make_video(song_id: str, _=Owner):
    if not S.enable_video:
        raise HTTPException(status_code=404, detail="video export is switched off")
    paths = library.paths(conn(), song_id)
    if not paths:
        raise HTTPException(status_code=404, detail="no such song")
    if paths["video_path"] and os.path.exists(paths["video_path"]):
        return {"ready": True, "url": f"/media/video/{song_id}.mp4"}
    jobs.enqueue(conn(), "video", {"song_id": song_id}, title=f"video {song_id}")
    return {"ready": False, "queued": True}


@app.get("/api/status")
def status(_=Owner):
    import subprocess
    cards = []
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total,utilization.gpu",
                              "--format=csv,noheader,nounits"], capture_output=True,
                             text=True, timeout=5).stdout
        for line in out.strip().splitlines():
            used, total, util = [int(x) for x in line.split(",")]
            cards.append({"used": used, "total": total, "util": util})
    except Exception:
        pass
    return {"cards": cards, **jobs.queue_depth(conn()), **library.stats(conn(), ONLY)}


# ── media, in development only ───────────────────────────────────────
def _ranged(path: str, request: Request, media_type: str) -> Response:
    """Serve a file with byte ranges, which is how browsers seek in audio."""
    size = os.path.getsize(path)
    rng = request.headers.get("range", "")
    versioned = bool(request.query_params.get("v"))
    headers = {"accept-ranges": "bytes",
               "cache-control": "public, max-age=31536000, immutable" if versioned
               else "no-cache"}
    if not rng.startswith("bytes="):
        return FileResponse(path, media_type=media_type, headers=headers)
    first, _, last = rng.removeprefix("bytes=").partition("-")
    start = int(first) if first else max(0, size - int(last or 0))
    end = int(last) if last and first else size - 1
    end = min(end, size - 1)
    if start > end:
        return Response(status_code=416, headers={"content-range": f"bytes */{size}"})

    def chunks():
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                block = f.read(min(1 << 20, left))
                if not block:
                    break
                left -= len(block)
                yield block

    from starlette.responses import StreamingResponse
    headers |= {"content-range": f"bytes {start}-{end}/{size}",
                "content-length": str(end - start + 1)}
    return StreamingResponse(chunks(), status_code=206, media_type=media_type, headers=headers)


MEDIA_TYPES = {"mp3": "audio/mpeg", "audio": "audio/wav",
               "covers": "image/png", "video": "video/mp4"}
# Audio never changes once written, so it keeps the long cache. Covers get
# redrawn, so they revalidate unless the page asked for a specific version.


@app.get("/media/{kind}/{name}")
def media(kind: str, name: str, request: Request, v: str = ""):
    if not S.serve_media:
        raise HTTPException(status_code=404, detail="media is served by the front proxy")
    if kind not in MEDIA_TYPES or "/" in name or ".." in name:
        raise HTTPException(status_code=404, detail="not found")
    if kind == "audio":                      # the master WAV is the owner's, not the public's
        require_owner(request)
    path = os.path.join(DIRS[kind], name)
    if not os.path.exists(path):
        # A song whose photo never arrived would otherwise leave a hole in the
        # grid. Draw one from the song's own id instead: the same song always
        # gets the same colours, and the page never shows a broken image.
        if kind == "covers" and name.endswith(".png"):
            media_mod.cover(os.path.splitext(name)[0], path)
            return _ranged(path, request, MEDIA_TYPES[kind])
        raise HTTPException(status_code=404, detail="not found")
    return _ranged(path, request, MEDIA_TYPES[kind])


# ── the two pages ────────────────────────────────────────────────────
def _page(name: str) -> Response:
    """Serve a page with its stylesheet's version stamped into the link.

    Without this, a visitor who loaded the site once keeps the old stylesheet
    and sees a broken layout after every change — which is exactly what
    happened on 2026-09-20.
    """
    html = open(os.path.join(FRONTEND, name), encoding="utf-8").read()
    css = os.path.join(FRONTEND, "vendor", "tailwind.min.css")
    stamp = int(os.path.getmtime(css)) if os.path.exists(css) else 0
    html = html.replace("/vendor/tailwind.min.css", f"/vendor/tailwind.min.css?v={stamp}")
    return Response(html, media_type="text/html; charset=utf-8",
                    headers={"cache-control": "no-cache"})


@app.get("/")
def music_page():
    return _page("music.html")


@app.get("/create")
def create_page():
    return _page("create.html")


@app.get("/vendor/{name}")
def vendor(name: str):
    if "/" in name or ".." in name:
        raise HTTPException(status_code=404, detail="not found")
    path = os.path.join(FRONTEND, "vendor", name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="not found")
    kind = "text/css" if name.endswith(".css") else "application/javascript"
    # Revalidate rather than cache hard: this file is 13 KB and it changes
    # whenever the pages do. A week-long cache left visitors on an old design.
    return FileResponse(path, media_type=kind,
                        headers={"cache-control": "no-cache"})


@app.exception_handler(404)
def not_found(request, exc):
    return JSONResponse({"error": "not found"}, status_code=404)


def main():
    import uvicorn
    db.init(db.connect(DB_PATH))
    uvicorn.run(app, host=S.host, port=S.port, log_level=os.environ.get("LOG_LEVEL", "info"))


if __name__ == "__main__":
    main()
