"""The generation queue.

The web app never touches a graphics card: it writes a row here. The worker,
which lives on the box beside the cards, claims one row at a time. One at a
time is not a simplification — a MiniMax song needs all three cards (ch. 39),
so a second job would fail, not share.
"""
import json
import time

QUEUED, RUNNING, DONE, FAILED = "queued", "running", "done", "failed"


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def enqueue(conn, model: str, params: dict, title: str = "") -> int:
    cur = conn.execute(
        "INSERT INTO jobs (model, title, params, status, created_at) VALUES (?,?,?,?,?)",
        (model, title, json.dumps(params, ensure_ascii=False), QUEUED, now()))
    conn.commit()
    return cur.lastrowid


def claim(conn):
    """The oldest queued job, marked running — or None if one is already running."""
    busy = conn.execute("SELECT 1 FROM jobs WHERE status=?", (RUNNING,)).fetchone()
    if busy:
        return None
    row = conn.execute("SELECT * FROM jobs WHERE status=? ORDER BY id LIMIT 1",
                       (QUEUED,)).fetchone()
    if not row:
        return None
    conn.execute("UPDATE jobs SET status=?, started_at=? WHERE id=? AND status=?",
                 (RUNNING, now(), row["id"], QUEUED))
    conn.commit()
    d = dict(row)
    d["params"] = json.loads(d["params"] or "{}")
    d["status"] = RUNNING
    return d


def finish(conn, job_id, song_id=None, error="", wall_s=None) -> None:
    conn.execute(
        "UPDATE jobs SET status=?, song_id=?, error=?, finished_at=?, wall_s=? WHERE id=?",
        (FAILED if error else DONE, song_id, error[-300:], now(), wall_s, job_id))
    conn.commit()


def positions(conn) -> dict:
    """Where each waiting job stands in line: 1 is next off the rank.

    One job runs at a time, so the queue is simply the order the rows were
    written in. Telling someone "third in line" is the difference between a
    page that looks stuck and a page that looks busy.
    """
    rows = conn.execute("SELECT id FROM jobs WHERE status=? ORDER BY id", (QUEUED,)).fetchall()
    return {r["id"]: i + 1 for i, r in enumerate(rows)}


def recent(conn, limit=50, status="") -> list:
    sql = "SELECT * FROM jobs"
    args = []
    if status:
        sql += " WHERE status=?"
        args.append(status)
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(int(limit))
    place = positions(conn)
    out = []
    for r in conn.execute(sql, args):
        d = dict(r)
        d["params"] = json.loads(d["params"] or "{}")
        d["position"] = place.get(d["id"], 0)
        out.append(d)
    return out


def cancel(conn, job_id: int) -> bool:
    """Take a waiting job out of the line. One already running belongs to the
    cards, and stopping it half-way would leave a part-written file behind."""
    cur = conn.execute("DELETE FROM jobs WHERE id=? AND status=?", (job_id, QUEUED))
    conn.commit()
    return cur.rowcount > 0


def queue_depth(conn) -> dict:
    q = conn.execute("SELECT COUNT(*) FROM jobs WHERE status=?", (QUEUED,)).fetchone()[0]
    r = conn.execute("SELECT COUNT(*) FROM jobs WHERE status=?", (RUNNING,)).fetchone()[0]
    return {"queued": q, "running": r}


def reset_stale(conn) -> int:
    """A job marked running when the worker starts was interrupted by a restart."""
    cur = conn.execute(
        "UPDATE jobs SET status=?, error=? WHERE status=?",
        (FAILED, "interrupted — the worker restarted", RUNNING))
    conn.commit()
    return cur.rowcount
