import os, sys, importlib, subprocess, types, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def wk(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SELFHOSTAUDIO_ROOT", str(tmp_path / "root"))
    monkeypatch.setenv("COVER_SOURCE", "gradient")      # tests never touch the network
    import config, db, library, jobs, worker
    for m in (config, db, library, jobs, worker):
        importlib.reload(m)
    conn = db.connect(worker.DB_PATH); db.init(conn)
    return worker, jobs, library, conn


def fake_run_ok(argv, **kw):
    out = argv[argv.index("--out") + 1]
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=1", "-ac", "2", "-ar", "44100", out],
                   check=True)
    return types.SimpleNamespace(returncode=0, stdout="", stderr="")


def fake_run_fail(argv, **kw):
    return types.SimpleNamespace(returncode=1, stdout="", stderr="CUDA out of memory\n")


def test_tick_makes_a_song_with_mp3_and_cover(wk):
    worker, jobs, library, conn = wk
    jobs.enqueue(conn, "yue2", {"style": "lo-fi", "lyrics": "x", "seed": 7}, title="Test song")
    assert worker.tick(conn, run=fake_run_ok) is True
    assert worker.tick(conn, run=fake_run_ok) is False          # queue empty again
    song = library.page(conn)["items"][0]
    assert song["title"] == "Test song" and song["has_mp3"] is True
    paths = library.paths(conn, song["id"])
    assert os.path.exists(paths["mp3_path"]) and os.path.exists(paths["cover_path"])
    assert 0.8 < song["seconds"] < 1.2
    assert jobs.recent(conn)[0]["status"] == "done"


def test_a_failed_run_records_the_error_and_no_song(wk):
    worker, jobs, library, conn = wk
    jobs.enqueue(conn, "yue2", {"style": "lo-fi", "lyrics": "x"})
    worker.tick(conn, run=fake_run_fail)
    assert library.page(conn)["total"] == 0
    row = jobs.recent(conn)[0]
    assert row["status"] == "failed" and "out of memory" in row["error"]


def test_video_job_renders_from_the_mp3(wk):
    worker, jobs, library, conn = wk
    jobs.enqueue(conn, "yue2", {"style": "lo-fi", "lyrics": "x"}); worker.tick(conn, run=fake_run_ok)
    sid = library.page(conn)["items"][0]["id"]
    jobs.enqueue(conn, "video", {"song_id": sid})
    assert worker.tick(conn) is True
    assert os.path.exists(library.paths(conn, sid)["video_path"])
