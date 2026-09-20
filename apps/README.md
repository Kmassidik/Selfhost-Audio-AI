# Music Studio

A self-hosted music platform for the songs this box makes: a public listener app
and an owner-only creator app.

```
apps/
  backend/    the service (FastAPI + SQLite) and the graphics-card worker
  frontend/   two self-contained pages: music.html (listen), create.html (create)
  docker/     Dockerfile, compose, Caddy, systemd units, .env.example
data/         the volume: app.db, audio/ mp3/ covers/ video/   (never in git)
```

## Run it on the box (no Docker needed)

```bash
cd apps/backend && uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
cp ../docker/.env.example ../docker/.env        # set OWNER_PASSWORD before going public
.venv/bin/python import_runs.py                 # bring in the songs already made
cp ../docker/selfhostaudio-*.service /etc/systemd/system/ && systemctl daemon-reload
systemctl enable --now selfhostaudio-app selfhostaudio-worker
```

The site is then at `http://10.0.0.20:8095` — library at `/`, creating at `/create`.

## Run it behind a domain

```bash
cd apps/docker && cp .env.example .env          # set DOMAIN and OWNER_PASSWORD
docker compose --env-file .env up -d            # app + caddy, automatic HTTPS
systemctl start selfhostaudio-worker            # the cards stay outside Docker
```

Put Cloudflare in front of the domain if more than a handful of people listen:
the box uploads 2.5–4.4 MB/s, which is about 155 listeners at 128 kbit/s, and
the edge serves everyone after the first.

## Why it is shaped this way

- **The worker is not in a container.** It needs CUDA, the 17 GB engine build and
  27 GB of weights. The public half is 150 MB and restarts in a second.
- **MP3 to listeners, WAV for the owner.** A WAV is 1.4 MB/s per listener; the
  line carries under two of them. MP3 at 128 kbit/s carries about 155.
- **One model at a time.** MiniMax-Music3 needs all three cards, so jobs queue
  rather than share. The worker waits for the driver to report the cards free
  before loading the next model.
- **Every default is a measurement** from the knowledge base: see `backend/models.py`,
  where each one carries the chapter that earned it.

## Tests

```bash
cd apps/backend && .venv/bin/python -m pytest tests -q          # 28 unit tests, no card needed
node tests/ui/browser-checks.mjs                                # 15 browser checks (needs Chrome)
.venv/bin/python tests/loadtest.py --listeners 100 --seconds 120
```

## QA checklist (five minutes)

1. Open `http://10.0.0.20:8095` — the grid fills with your songs and covers.
2. Click a card. It plays, the bottom bar fills in, the right panel shows the lyrics.
3. Let it run 30 seconds. **Playback must not stop** when the library refreshes.
4. Type `umbrella` in search — the grid narrows. Clear it — the grid comes back.
5. Press the heart. Open **Liked** in the sidebar — the song is there.
6. Sign in (bottom left) with the owner password from `apps/docker/.env`.
7. Make a playlist with **+**, then "Add to playlist" from the right panel.
8. Open `/create`, pick YuE2, paste lyrics, press **Create song**. It appears in
   Jobs as `queued`, then `running`, then in the library about a minute later.
9. Open the site on your phone (same network): one column, player at the bottom,
   no sideways scrolling.
10. Sign out. Confirm **Create song** is refused — that is what protects the cards
    when the site is on a domain.

## Where things are

| | |
|---|---|
| Site | `http://10.0.0.20:8095` (`/` listen, `/create` make) |
| Owner password | `apps/docker/.env` → `OWNER_PASSWORD` |
| Songs, database, covers | `data/studio/` on the box |
| Services | `systemctl status selfhostaudio-app selfhostaudio-worker` |
| Logs | `journalctl -u selfhostaudio-worker -f` |
