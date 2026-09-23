-- 0001_init.sql — the whole schema, built once. There is no email anywhere:
-- the owner signs in with a username and a password, and the password is
-- stored as an argon2id hash made by Bun itself.

CREATE TABLE users (
    id            TEXT PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'member',
    created_at    TEXT NOT NULL
);

CREATE TABLE sessions (
    id         TEXT PRIMARY KEY,               -- the cookie's value, random, never a user's
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE INDEX sessions_user ON sessions(user_id);

-- A visitor needs no account to listen, like or keep playlists: the cookie
-- names one of these rows the first time they write something.
CREATE TABLE listeners (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL DEFAULT 'anonymous',
    label       TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE TABLE songs (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL DEFAULT 'Untitled',
    model        TEXT NOT NULL DEFAULT '',
    seed         TEXT NOT NULL DEFAULT '',
    style        TEXT NOT NULL DEFAULT '',
    lyrics       TEXT NOT NULL DEFAULT '',
    seconds      REAL NOT NULL DEFAULT 0,
    sample_rate  INTEGER NOT NULL DEFAULT 0,
    channels     INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT 'generated',
    creator_id   TEXT NOT NULL DEFAULT '',
    visible      BOOLEAN NOT NULL DEFAULT TRUE,
    has_mp3      BOOLEAN NOT NULL DEFAULT FALSE,
    has_video    BOOLEAN NOT NULL DEFAULT FALSE,
    cover_v      INTEGER NOT NULL DEFAULT 0,
    formats      TEXT[] NOT NULL DEFAULT '{mp3}',
    search       TEXT
);
CREATE INDEX songs_created ON songs(created_at DESC);
CREATE INDEX songs_model   ON songs(model);
CREATE INDEX songs_creator ON songs(creator_id);
CREATE INDEX songs_search  ON songs USING GIN (to_tsvector('simple', search));

CREATE TABLE jobs (
    id          SERIAL PRIMARY KEY,
    song_id     TEXT REFERENCES songs(id) ON DELETE SET NULL,
    model       TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    params      JSONB NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'queued',
    progress    JSONB NOT NULL DEFAULT '{}',
    error       TEXT NOT NULL DEFAULT '',
    creator_id  TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    started_at  TEXT,
    finished_at TEXT,
    wall_s      REAL
);
CREATE INDEX jobs_status ON jobs(status, id);
CREATE INDEX jobs_creator ON jobs(creator_id);

CREATE TABLE likes (
    listener_id TEXT NOT NULL REFERENCES listeners(id) ON DELETE CASCADE,
    song_id     TEXT NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (listener_id, song_id)
);

CREATE TABLE plays (
    id             BIGSERIAL PRIMARY KEY,
    song_id        TEXT NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    listener_id    TEXT,
    played_at      TEXT NOT NULL,
    seconds_played REAL NOT NULL DEFAULT 0
);
CREATE INDEX plays_song ON plays(song_id);

CREATE TABLE tags (
    song_id TEXT NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    tag     TEXT NOT NULL,
    PRIMARY KEY (song_id, tag)
);
CREATE INDEX tags_tag ON tags(tag);

CREATE TABLE playlists (
    id          SERIAL PRIMARY KEY,
    listener_id TEXT NOT NULL REFERENCES listeners(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    cover_seed  TEXT NOT NULL DEFAULT '',
    share_id    TEXT UNIQUE NOT NULL
);
CREATE INDEX playlists_listener ON playlists(listener_id);

CREATE TABLE playlist_items (
    playlist_id INTEGER NOT NULL REFERENCES playlists(id) ON DELETE CASCADE,
    song_id     TEXT NOT NULL REFERENCES songs(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    PRIMARY KEY (playlist_id, song_id)
);
CREATE INDEX playlist_order ON playlist_items(playlist_id, position);
