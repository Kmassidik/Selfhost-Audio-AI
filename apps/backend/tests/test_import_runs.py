import os, sys, json, importlib, subprocess, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_imports_finished_jobs_once(tmp_path, monkeypatch):
    runs = tmp_path / "runs"; runs.mkdir()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=1", "-ac", "2", "-ar", "44100",
                    str(runs / "a.wav")], check=True)
    json.dump({"id": "a", "status": "done", "file": "a.wav", "title": "A song",
               "model": "minimax", "duration_s": 1.0, "sample_rate": 44100, "channels": 2,
               "params": {"seed": 5, "lyrics": "la"}}, open(runs / "a.json", "w"))
    json.dump({"id": "b", "status": "failed", "error": "boom"}, open(runs / "b.json", "w"))

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    import config, db, library, import_runs
    for m in (config, db, library, import_runs):
        importlib.reload(m)
    conn = db.connect(tmp_path / "data" / "app.db"); db.init(conn)

    first = import_runs.run(conn, str(runs), quiet=True)
    assert first == {"imported": 1, "skipped": 1, "media": 1}
    song = library.get_song(conn, "a")
    assert song["title"] == "A song" and song["has_mp3"] is True
    assert import_runs.run(conn, str(runs), quiet=True)["imported"] == 0      # idempotent
