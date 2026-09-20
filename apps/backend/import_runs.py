"""Bring the songs the lab console already made into the library.

Safe to run again: a job id that is already a song is skipped.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import db
import library
import media
import tags

S = config.settings()
DIRS = config.media_dirs(S)


def run(conn, runs_dir: str, quiet=False) -> dict:
    out = {"imported": 0, "skipped": 0, "media": 0}
    for path in sorted(glob.glob(os.path.join(runs_dir, "*.json"))):
        try:
            j = json.load(open(path))
        except Exception:
            out["skipped"] += 1
            continue
        if not isinstance(j, dict) or j.get("status") != "done" or not j.get("file"):
            out["skipped"] += 1
            continue
        wav = os.path.join(runs_dir, j["file"])
        if not os.path.exists(wav):
            out["skipped"] += 1
            continue
        sid = j["id"]
        if conn.execute("SELECT 1 FROM songs WHERE id=?", (sid,)).fetchone():
            out["skipped"] += 1
            continue
        p = j.get("params") or {}
        library.add_song(conn, id=sid, title=j.get("title") or "Untitled",
                         model=j.get("model", ""), seed=str(p.get("seed", "")),
                         style=p.get("style") or p.get("prompt", ""),
                         lyrics=p.get("lyrics") or p.get("text", ""),
                         seconds=j.get("duration_s") or 0,
                         sample_rate=j.get("sample_rate") or 0,
                         channels=j.get("channels") or 0,
                         created_at=j.get("created") or j.get("finished") or library.now(),
                         wav_path=wav, source="imported")
        out["imported"] += 1
        try:
            mp3 = media.to_mp3(wav, os.path.join(DIRS["mp3"], f"{sid}.mp3"), S.mp3_bitrate)
            cover = media.fetch_cover(sid,
                                      os.path.join(DIRS["covers"], f"{sid}.png"),
                                      keywords=p.get("style") or p.get("prompt", ""),
                                      size=S.cover_size, source=S.cover_source)
            library.set_paths(conn, sid, mp3_path=mp3, cover_path=cover)
            tags.tag_song(conn, sid)
            out["media"] += 1
        except Exception as e:
            if not quiet:
                print(f"  media failed for {sid}: {e}", file=sys.stderr)
    return out


if __name__ == "__main__":
    conn = db.connect(os.path.join(S.data_dir, "app.db"))
    db.init(conn)
    runs_dir = sys.argv[1] if len(sys.argv) > 1 else S.runs_dir
    print(json.dumps(run(conn, runs_dir), indent=2))
