"""SQLite, one file, write-ahead logging.

The database holds facts; the data/ volume holds bytes. Every write here is
small (a like, a play, a job's status) so a single writer is ample: the load
this has to survive is people listening, and listening is reads.
"""
import hashlib
import os
import sqlite3
import threading

SCHEMA = """
CREATE TABLE IF NOT EXISTS songs (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    model        TEXT NOT NULL DEFAULT '',
    seed         TEXT NOT NULL DEFAULT '',
    style        TEXT NOT NULL DEFAULT '',
    lyrics       TEXT NOT NULL DEFAULT '',
    seconds      REAL NOT NULL DEFAULT 0,
    sample_rate  INTEGER NOT NULL DEFAULT 0,
    channels     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    wav_path     TEXT NOT NULL DEFAULT '',
    mp3_path     TEXT NOT NULL DEFAULT '',
    cover_path   TEXT NOT NULL DEFAULT '',
    video_path   TEXT NOT NULL DEFAULT '',
    source       TEXT NOT NULL DEFAULT 'generated',
    visible      INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS songs_created ON songs(created_at DESC);
CREATE INDEX IF NOT EXISTS songs_model   ON songs(model);

CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id     TEXT,
    model       TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    params      TEXT NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'queued',
    error       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    started_at  TEXT,
    finished_at TEXT,
    wall_s      REAL
);
CREATE INDEX IF NOT EXISTS jobs_status ON jobs(status, id);

CREATE TABLE IF NOT EXISTS playlists (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL,
    cover_seed TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS playlist_items (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    song_id     TEXT NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    PRIMARY KEY (playlist_id, song_id)
);
CREATE INDEX IF NOT EXISTS playlist_order ON playlist_items(playlist_id, position);

CREATE TABLE IF NOT EXISTS likes (
    song_id    TEXT PRIMARY KEY REFERENCES songs(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS song_tags (
    song_id TEXT NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    tag     TEXT NOT NULL,
    PRIMARY KEY (song_id, tag)
);
CREATE INDEX IF NOT EXISTS song_tags_tag ON song_tags(tag);

CREATE TABLE IF NOT EXISTS plays (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id         TEXT NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    played_at       TEXT NOT NULL,
    seconds_played  REAL NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS plays_song ON plays(song_id);
"""

_local = threading.local()


def connect(path) -> sqlite3.Connection:
    """A connection with the settings that make SQLite behave under many readers."""
    path = str(path)
    if path != ":memory:":
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")       # readers never block the writer
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    # A seeded shuffle. SQLite's random() changes on every row read, which
    # reshuffles the library between pages and shows the same song twice; this
    # gives one stable order per seed, so paging through a shuffle works.
    conn.create_function(
        "shuffle", 2,
        lambda song_id, seed: int(hashlib.md5(f"{seed}:{song_id}".encode()).hexdigest()[:12], 16),
        deterministic=True)
    return conn


def init(conn: sqlite3.Connection) -> None:
    """Create everything that is missing. Safe to call on every start."""
    conn.executescript(SCHEMA)
    conn.commit()


def shared(path) -> sqlite3.Connection:
    """One connection per thread, made on first use.

    A single connection shared across request threads serialises everything and
    shows up as latency under load; one per thread is what SQLite expects.
    """
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _local.conn = connect(path)
        init(conn)
    return conn
