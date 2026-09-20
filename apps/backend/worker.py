"""The graphics-card side. Runs on the box, natively, under systemd.

It claims one job at a time and never shares the cards: MiniMax-Music3 needs
all three (ch. 39), so a second job would fail rather than queue politely.
After each song it writes the MP3 and the cover, because listeners are served
MP3 (see media.py for the bandwidth arithmetic).
"""
import os
import signal
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import db
import jobs
import library
import media
import tags
import registry

S = config.settings()
DIRS = config.media_dirs(S)
DB_PATH = os.path.join(S.data_dir, "app.db")
FREE_MIB = int(os.environ.get("CARD_FREE_MIB", "600"))


def cards_free(timeout=90) -> bool:
    """Wait until the driver says the cards are back.

    An unloaded model is not a freed card: the next load races the teardown and
    dies with 'unable to allocate'. The lab console learned this (ch. 40).
    """
    end = time.time() + timeout
    while time.time() < end:
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                                  "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5).stdout
            used = [int(x) for x in out.split()]
            if used and max(used) <= FREE_MIB:
                return True
        except Exception:
            return True                      # no driver here: nothing to wait for
        time.sleep(0.5)
    return False


def _md5(path: str) -> str:
    import hashlib
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def _cover_hashes(conn, exclude_id: str) -> set:
    """What the other songs' covers look like, so this one can be different."""
    out = set()
    for r in conn.execute("SELECT cover_path FROM songs WHERE cover_path != '' AND id != ?",
                          (exclude_id,)):
        try:
            out.add(_md5(r["cover_path"]))
        except OSError:
            pass
    return out


def _keywords(conn, song_id: str) -> str:
    """The song's own style words, so a fetched cover can match its mood."""
    r = conn.execute("SELECT style FROM songs WHERE id=?", (song_id,)).fetchone()
    return (r["style"] if r else "") or ""


def _finish_media(conn, song_id: str, wav: str, seed: str, given_tags=()) -> dict:
    """WAV in, MP3 + cover out, sizes recorded."""
    facts = media.probe(wav)
    mp3 = media.to_mp3(wav, os.path.join(DIRS["mp3"], f"{song_id}.mp3"), S.mp3_bitrate)
    # keyed by the song, not the seed: two takes of one seed must not share art.
    # Picsum's pool repeats, so ask again if this photo is already on another song.
    cover_path = os.path.join(DIRS["covers"], f"{song_id}.png")
    keywords = _keywords(conn, song_id)
    taken = _cover_hashes(conn, song_id)
    r = conn.execute("SELECT lyrics, model, seconds FROM songs WHERE id=?", (song_id,)).fetchone()
    song_tags = tags.for_song(keywords, r["lyrics"] if r else "", r["model"] if r else "",
                              r["seconds"] if r else 0)
    title = (conn.execute("SELECT title FROM songs WHERE id=?", (song_id,)).fetchone() or [""])[0]
    for attempt in range(4):
        cover = media.art_cover(song_id, cover_path, title=title, style=keywords,
                                label=" · ".join(song_tags[:2]), size=S.cover_size,
                                source=S.cover_source, attempt=attempt,
                                tags_in_order=song_tags)
        if _md5(cover) not in taken:
            break
    library.set_paths(conn, song_id, mp3_path=mp3, cover_path=cover, wav_path=wav, **facts)
    tags.tag_song(conn, song_id, given_tags)
    return facts


def handle_video(conn, job) -> None:
    song_id = job["params"].get("song_id", "")
    paths = library.paths(conn, song_id)
    if not paths or not paths["mp3_path"]:
        jobs.finish(conn, job["id"], error="no audio for that song")
        return
    cover = paths["cover_path"] or media.fetch_cover(
        song_id, os.path.join(DIRS["covers"], f"{song_id}.png"),
        size=S.cover_size, source=S.cover_source)
    out = media.to_mp4(paths["mp3_path"], cover, os.path.join(DIRS["video"], f"{song_id}.mp4"))
    library.set_paths(conn, song_id, video_path=out)
    jobs.finish(conn, job["id"], song_id=song_id)


def tick(conn, run=subprocess.run) -> bool:
    """Handle one job if there is one. Returns True if something was done."""
    job = jobs.claim(conn)
    if not job:
        return False
    t0 = time.time()
    try:
        if job["model"] == "video":
            handle_video(conn, job)
            return True

        spec = registry.get(job["model"])
        if not spec:
            jobs.finish(conn, job["id"], error=f"unknown model {job['model']}")
            return True

        song_id = library.new_id()
        wav = os.path.join(DIRS["audio"], f"{song_id}.wav")
        argv, env = registry.command(job["model"], job["params"], wav, S.root)
        cards_free()
        r = run(argv, capture_output=True, text=True, env=env, timeout=4 * 3600)
        if r.returncode != 0 or not os.path.exists(wav):
            last = ((r.stderr or r.stdout or "").strip().splitlines() or ["failed"])[-1]
            jobs.finish(conn, job["id"], error=last, wall_s=round(time.time() - t0, 2))
            return True

        # A file can exist and still hold no music. Two such rows reached the
        # library on 2026-09-20 and showed up as blank cards with no cover and
        # nothing to play. A song enters the library only if it has audio in it.
        seconds = media.probe(wav).get("seconds", 0)
        if seconds < 1:
            jobs.finish(conn, job["id"],
                        error=f"the model wrote {seconds:.1f} s of audio — nothing to keep",
                        wall_s=round(time.time() - t0, 2))
            return True

        p = job["params"]
        library.add_song(conn, id=song_id,
                         title=job["title"] or f"{spec['outcome'].get('title', spec['name'])}",
                         model=spec["id"], seed=str(p.get("seed", "")),
                         style=p.get("style") or p.get("prompt", ""),
                         lyrics=p.get("lyrics") or p.get("text", ""),
                         wav_path=wav)
        _finish_media(conn, song_id, wav, str(p.get("seed", "")), p.get("tags", []))
        jobs.finish(conn, job["id"], song_id=song_id, wall_s=round(time.time() - t0, 2))
    except Exception as e:                    # a crash must never wedge the queue
        jobs.finish(conn, job["id"], error=f"{type(e).__name__}: {e}",
                    wall_s=round(time.time() - t0, 2))
    return True


# A song takes minutes and cannot be resumed. When the worker is asked to stop
# — a deployment, a reboot — it finishes what it is making and then goes, rather
# than throwing away fourteen minutes of work half a minute before the end.
_stopping = False


def _stop(signum, frame) -> None:
    global _stopping
    _stopping = True
    print("stop asked for; finishing the job in hand, then exiting", flush=True)


def main():
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    conn = db.connect(DB_PATH)
    db.init(conn)
    stale = jobs.reset_stale(conn)
    print(f"worker up · data {S.data_dir} · {stale} interrupted job(s) cleared", flush=True)
    while not _stopping:
        try:
            if not tick(conn):
                for _ in range(20):               # 2 s, but it notices a stop in 0.1
                    if _stopping:
                        break
                    time.sleep(0.1)
        except KeyboardInterrupt:
            return
        except Exception as e:
            print("worker error:", e, flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
