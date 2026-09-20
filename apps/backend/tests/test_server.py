import os, sys, importlib, json, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("OWNER_PASSWORD", "hunter2")
    monkeypatch.setenv("SERVE_MEDIA", "1")
    monkeypatch.setenv("ENABLE_VIDEO", "1")
    import config, db, library, server
    for m in (config, db, library, server):
        importlib.reload(m)
    c = db.shared(server.DB_PATH)
    library.add_song(c, id="s1", title="Good Morning Tokyo", model="minimax",
                     lyrics="朝のホーム", seconds=112, mp3_path="/x/s1.mp3")
    library.add_song(c, id="s2", title="One Umbrella Left", model="yue2", seconds=149)
    return TestClient(server.app), server, tmp_path


def test_healthz_and_library_paging(client):
    c, *_ = client
    assert c.get("/healthz").json()["ok"] is True
    got = c.get("/api/library?limit=1").json()
    assert got["total"] == 2 and len(got["items"]) == 1 and got["limit"] == 1


def test_search_and_song_detail(client):
    c, *_ = client
    assert c.get("/api/library?q=umbrella").json()["items"][0]["title"] == "One Umbrella Left"
    song = c.get("/api/song/s1").json()
    assert song["lyrics"] == "朝のホーム" and song["has_mp3"] is True
    assert c.get("/api/song/nope").status_code == 404


def test_public_can_like_and_count_plays(client):
    c, *_ = client
    assert c.post("/api/like/s1").json()["liked"] is True
    assert c.get("/api/library?liked=true").json()["total"] == 1
    assert c.post("/api/play/s1", json={"seconds": 30}).json()["ok"] is True


def test_creating_needs_the_owner_password(client):
    c, *_ = client
    assert c.post("/api/jobs", json={"model": "yue2", "params": {}}).status_code == 401
    ok = c.post("/api/jobs", json={"model": "yue2", "params": {"style": "lo-fi", "lyrics": "x"}},
                headers={"Authorization": "Bearer hunter2"})
    assert ok.status_code == 200 and ok.json()["queued"] == 1
    assert c.get("/api/jobs").status_code == 401
    assert c.get("/api/jobs", headers={"Authorization": "Bearer hunter2"}).json()["items"][0]["model"] == "yue2"


def test_unknown_model_is_refused(client):
    c, *_ = client
    r = c.post("/api/jobs", json={"model": "suno", "params": {}},
               headers={"Authorization": "Bearer hunter2"})
    assert r.status_code == 400


def test_ids_filter_fetches_a_browser_kept_playlist(client):
    c, *_ = client
    got = c.get("/api/library?ids=s2,s1").json()
    assert got["total"] == 2
    assert c.get("/api/library?ids=s2").json()["items"][0]["title"] == "One Umbrella Left"
    assert c.get("/api/library?ids=nope").json()["total"] == 0
    assert c.get("/api/playlists").status_code == 404      # the server keeps none


def test_media_serves_byte_ranges_and_hides_the_wav(client):
    c, server, tmp_path = client
    mp3 = os.path.join(server.DIRS["mp3"], "s1.mp3")
    open(mp3, "wb").write(b"0123456789" * 100)
    r = c.get("/media/mp3/s1.mp3", headers={"Range": "bytes=10-19"})
    assert r.status_code == 206 and r.headers["content-range"] == "bytes 10-19/1000"
    assert len(r.content) == 10
    assert c.get("/media/mp3/s1.mp3").status_code == 200
    open(os.path.join(server.DIRS["audio"], "s1.wav"), "wb").write(b"RIFF")
    assert c.get("/media/audio/s1.wav").status_code == 401          # masters are owner-only
    assert c.get("/media/audio/s1.wav", headers={"Authorization": "Bearer hunter2"}).status_code == 200
    assert c.get("/media/mp3/../../etc/passwd").status_code == 404


def test_video_export_is_queued_for_the_owner(client):
    c, *_ = client
    assert c.post("/api/video/s1").status_code == 401
    r = c.post("/api/video/s1", headers={"Authorization": "Bearer hunter2"})
    assert r.status_code == 200 and r.json()["queued"] is True


def test_home_switches_shape_for_a_small_library(client):
    c, server, _ = client
    home = c.get("/api/home").json()
    assert home["mode"] == "small"                 # two songs cannot fill six rows
    assert home["rows"] == [] and home["feature"]["id"] == "s2"


def test_home_rows_never_only_repeat(client):
    c, server, _ = client
    import db, library, tags
    conn = db.shared(server.DB_PATH)
    for i in range(20):
        library.add_song(conn, id=f"x{i}", title=f"Song {i}", model="yue2",
                         style="lo-fi chill 80 bpm" if i % 2 else "indie pop 120 bpm",
                         lyrics="la la", seconds=100 + i)
    tags.rebuild(conn)
    home = c.get("/api/home?rows=6&per_row=8").json()
    assert home["mode"] == "rows" and home["rows"][0]["title"] == "Latest"
    first = {s["id"] for s in home["rows"][0]["items"]}
    for row in home["rows"][1:]:
        fresh = [s for s in row["items"] if s["id"] not in first]
        assert len(fresh) >= 3, f"row {row['title']} only repeats the Latest row"


def test_a_missing_cover_is_drawn_rather_than_404(client):
    c, *_ = client
    r = c.get("/media/covers/20260101-000000-abcdef.png")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 0
