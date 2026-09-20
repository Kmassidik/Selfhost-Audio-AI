"""The library: songs, search, paging, likes, playlists, plays.

Everything a listener sees comes from here. Every query is parameterised and
every list is paged — a library of thousands must not become one huge reply.
"""
import json
import os
import time
import uuid

SORTS = {
    "new":    "created_at DESC, rowid DESC",
    "old":    "created_at ASC, rowid ASC",
    "long":   "seconds DESC",
    "short":  "seconds ASC",
    "model":  "model ASC, created_at DESC",
    "title":  "title COLLATE NOCASE ASC",
    # A liked song outranks an unliked one; within each group the newest first.
    "liked":  "(s.id IN (SELECT song_id FROM likes)) DESC, created_at DESC",
    "played": "(SELECT COUNT(*) FROM plays p WHERE p.song_id = s.id) DESC, created_at DESC",
    # Shuffle. The seed comes from the caller so paging through a shuffled
    # library keeps one order instead of reshuffling under the reader.
    "random": "",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]


def add_song(conn, *, id=None, title="Untitled", model="", seed="", style="", lyrics="",
             seconds=0.0, sample_rate=0, channels=0, created_at=None, wav_path="",
             mp3_path="", cover_path="", video_path="", source="generated") -> str:
    sid = id or new_id()
    conn.execute(
        """INSERT OR REPLACE INTO songs
           (id,title,model,seed,style,lyrics,seconds,sample_rate,channels,created_at,
            wav_path,mp3_path,cover_path,video_path,source,visible)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
        (sid, title, model, str(seed), style, lyrics, float(seconds or 0), int(sample_rate or 0),
         int(channels or 0), created_at or now(), wav_path, mp3_path, cover_path, video_path, source))
    conn.commit()
    return sid


def set_paths(conn, song_id, **paths) -> None:
    """Fill in mp3_path / cover_path / video_path once the media exists."""
    allowed = {"mp3_path", "cover_path", "video_path", "wav_path", "seconds",
               "sample_rate", "channels"}
    fields = {k: v for k, v in paths.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE songs SET {sets} WHERE id=?", (*fields.values(), song_id))
    conn.commit()


def _row(r, liked_ids=()) -> dict:
    d = dict(r)
    d["liked"] = d["id"] in liked_ids
    d["has_mp3"] = bool(d.pop("mp3_path", ""))
    d["has_video"] = bool(d.pop("video_path", ""))
    # When a cover is redrawn the file changes but its name does not, and the
    # browser was told to keep it forever. This stamp makes the URL change.
    cover = d.pop("cover_path", "")
    try:
        d["cover_v"] = int(os.path.getmtime(cover)) if cover else 0
    except OSError:
        d["cover_v"] = 0
    d.pop("wav_path", None)
    d.pop("visible", None)
    return d


def page(conn, q="", model="", liked=False, playlist_id=None, sort="new",
         offset=0, limit=50, max_limit=100, only_models=(), tag="", ids=(), seed=0) -> dict:
    """One page of the library, plus the total so the page can show progress.

    only_models narrows the whole library to a set of models. The platform is a
    music platform, so it passes the singing models and the speech takes stay
    in the database for the lab without ever showing up here.
    """
    limit = max(1, min(int(limit), max_limit))
    offset = max(0, int(offset))
    order = SORTS.get(sort, SORTS["new"])
    if sort == "random":
        order = f"shuffle(s.id, {int(seed) % 10 ** 9})"

    where = ["s.visible=1"]
    args = []
    if q:
        where.append("(s.title LIKE ? OR s.style LIKE ? OR s.lyrics LIKE ? OR s.model LIKE ?)")
        args += [f"%{q}%"] * 4
    if model:
        where.append("s.model=?")
        args.append(model)
    if liked:
        where.append("s.id IN (SELECT song_id FROM likes)")
    if only_models:
        where.append("s.model IN (%s)" % ",".join("?" * len(only_models)))
        args += list(only_models)
    if tag:
        where.append("s.id IN (SELECT song_id FROM song_tags WHERE tag=?)")
        args.append(tag)
    if ids:
        ids = list(ids)[:500]
        where.append("s.id IN (%s)" % ",".join("?" * len(ids)))
        args += ids

    join = ""
    if playlist_id is not None:
        join = "JOIN playlist_items pi ON pi.song_id = s.id AND pi.playlist_id = ?"
        args.insert(0, int(playlist_id))
        order = "pi.position ASC"

    sql_where = " AND ".join(where)
    total = conn.execute(
        f"SELECT COUNT(*) FROM songs s {join} WHERE {sql_where}", args).fetchone()[0]
    rows = conn.execute(
        f"SELECT s.* FROM songs s {join} WHERE {sql_where} ORDER BY {order} LIMIT ? OFFSET ?",
        (*args, limit, offset)).fetchall()
    got = tuple(r["id"] for r in rows)
    liked_ids, tag_map = set(), {}
    if got:
        marks = ",".join("?" * len(got))
        liked_ids = {r[0] for r in conn.execute(
            f"SELECT song_id FROM likes WHERE song_id IN ({marks})", got)}
        try:
            for r in conn.execute(
                    f"SELECT song_id, tag FROM song_tags WHERE song_id IN ({marks})", got):
                tag_map.setdefault(r[0], []).append(r[1])
        except Exception:
            pass                       # tags are a convenience, never a reason to fail
    items = []
    for r in rows:
        d = _row(r, liked_ids)
        d["tags"] = tag_map.get(r["id"], [])
        items.append(d)
    return {"items": items, "total": total, "offset": offset, "limit": limit}


def recently_played(conn, limit=6, only_models=()) -> list:
    """What was played last, newest first, one row per song."""
    where = "s.visible=1"
    args = []
    if only_models:
        where += " AND s.model IN (%s)" % ",".join("?" * len(only_models))
        args = list(only_models)
    rows = conn.execute(f"""
        SELECT s.*, MAX(p.played_at) AS last_played FROM plays p
        JOIN songs s ON s.id = p.song_id
        WHERE {where} GROUP BY s.id ORDER BY last_played DESC LIMIT ?""",
        (*args, limit)).fetchall()
    return [_row(r) for r in rows]


def get_song(conn, song_id) -> dict | None:
    r = conn.execute("SELECT * FROM songs WHERE id=? AND visible=1", (song_id,)).fetchone()
    if not r:
        return None
    liked = conn.execute("SELECT 1 FROM likes WHERE song_id=?", (song_id,)).fetchone()
    d = _row(r, {song_id} if liked else set())
    d["lyrics"] = r["lyrics"]
    d["style"] = r["style"]
    d["tags"] = [x[0] for x in conn.execute(
        "SELECT tag FROM song_tags WHERE song_id=?", (song_id,))]
    return d


def paths(conn, song_id) -> dict | None:
    """The on-disk paths. Used by the media and video routes, never sent to a page."""
    r = conn.execute(
        "SELECT wav_path, mp3_path, cover_path, video_path FROM songs WHERE id=?",
        (song_id,)).fetchone()
    return dict(r) if r else None


def repair_paths(conn, dirs: dict) -> int:
    """Point the rows at where the files actually are.

    A song records the absolute path of its audio, mp3, cover and video. Move
    the data directory — as this box did when the platform got its own folder —
    and every one of those paths is a lie, while the files themselves are fine.
    Playing still worked, because the media route builds its own path from the
    song id, but has_mp3 said "no" and video export had nothing to read.
    """
    kinds = {"wav_path": ("audio", ".wav"), "mp3_path": ("mp3", ".mp3"),
             "cover_path": ("covers", ".png"), "video_path": ("video", ".mp4")}
    fixed = 0
    for row in conn.execute("SELECT id, wav_path, mp3_path, cover_path, video_path FROM songs"):
        new = {}
        for column, (kind, ext) in kinds.items():
            old = row[column]
            if not old or os.path.exists(old) or kind not in dirs:
                continue
            candidate = os.path.join(dirs[kind], row["id"] + ext)
            if os.path.exists(candidate):
                new[column] = candidate
        if new:
            conn.execute("UPDATE songs SET " + ", ".join(f"{c}=?" for c in new)
                         + " WHERE id=?", (*new.values(), row["id"]))
            fixed += len(new)
    conn.commit()
    return fixed


def remove(conn, song_id: str) -> dict:
    """Take a song out of the library and delete what it left on disk.

    Used for a bad take, and for the songs the browser checks make. The row
    goes with the files: a row without files is the blank card this was
    written to stop.
    """
    row = conn.execute("SELECT wav_path, mp3_path, cover_path, video_path FROM songs "
                       "WHERE id=?", (song_id,)).fetchone()
    if not row:
        return {"removed": 0, "files": 0}
    gone = 0
    for path in row:
        if path and os.path.exists(path):
            os.remove(path)
            gone += 1
    conn.execute("DELETE FROM songs WHERE id=?", (song_id,))
    conn.commit()
    return {"removed": 1, "files": gone}


def set_like(conn, song_id, liked: bool) -> bool:
    if liked:
        conn.execute("INSERT OR IGNORE INTO likes (song_id, created_at) VALUES (?,?)",
                     (song_id, now()))
    else:
        conn.execute("DELETE FROM likes WHERE song_id=?", (song_id,))
    conn.commit()
    return liked


def count_play(conn, song_id, seconds=0.0) -> None:
    conn.execute("INSERT INTO plays (song_id, played_at, seconds_played) VALUES (?,?,?)",
                 (song_id, now(), float(seconds or 0)))
    conn.commit()


# ── playlists ────────────────────────────────────────────────────────
def create_playlist(conn, name) -> int:
    cur = conn.execute("INSERT INTO playlists (name, created_at, cover_seed) VALUES (?,?,?)",
                       (name, now(), uuid.uuid4().hex[:8]))
    conn.commit()
    return cur.lastrowid


def rename_playlist(conn, pid, name) -> None:
    conn.execute("UPDATE playlists SET name=? WHERE id=?", (name, pid))
    conn.commit()


def delete_playlist(conn, pid) -> None:
    conn.execute("DELETE FROM playlist_items WHERE playlist_id=?", (pid,))
    conn.execute("DELETE FROM playlists WHERE id=?", (pid,))
    conn.commit()


def playlists(conn) -> list:
    rows = conn.execute(
        """SELECT p.*, COUNT(pi.song_id) AS songs,
                  COALESCE(SUM(s.seconds), 0) AS seconds
           FROM playlists p
           LEFT JOIN playlist_items pi ON pi.playlist_id = p.id
           LEFT JOIN songs s ON s.id = pi.song_id
           GROUP BY p.id ORDER BY p.created_at DESC""").fetchall()
    return [dict(r) for r in rows]


def add_to_playlist(conn, pid, song_id) -> None:
    nxt = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM playlist_items WHERE playlist_id=?",
                       (pid,)).fetchone()[0]
    conn.execute("INSERT OR IGNORE INTO playlist_items (playlist_id, song_id, position) VALUES (?,?,?)",
                 (pid, song_id, nxt))
    conn.commit()


def remove_from_playlist(conn, pid, song_id) -> None:
    conn.execute("DELETE FROM playlist_items WHERE playlist_id=? AND song_id=?", (pid, song_id))
    conn.commit()


def reorder_playlist(conn, pid, song_ids) -> None:
    for i, sid in enumerate(song_ids):
        conn.execute("UPDATE playlist_items SET position=? WHERE playlist_id=? AND song_id=?",
                     (i, pid, sid))
    conn.commit()


def stats(conn, only_models=()) -> dict:
    """The counts the sidebar shows, over the same slice of the library."""
    where = "visible=1"
    args = []
    if only_models:
        where += " AND model IN (%s)" % ",".join("?" * len(only_models))
        args = list(only_models)
    one = lambda sql: conn.execute(sql, args).fetchone()[0]
    liked_where = ""
    if only_models:
        liked_where = " AND song_id IN (SELECT id FROM songs WHERE %s)" % where
    return {
        "songs": one(f"SELECT COUNT(*) FROM songs WHERE {where}"),
        "seconds": one(f"SELECT COALESCE(SUM(seconds),0) FROM songs WHERE {where}"),
        "liked": conn.execute(f"SELECT COUNT(*) FROM likes WHERE 1=1{liked_where}", args).fetchone()[0],
        "plays": conn.execute("SELECT COUNT(*) FROM plays").fetchone()[0],
        "models": [dict(r) for r in conn.execute(
            f"SELECT model, COUNT(*) AS songs FROM songs WHERE {where} GROUP BY model ORDER BY songs DESC", args)],
    }
