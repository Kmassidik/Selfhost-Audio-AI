import json, os, sys, importlib, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db, jobs, library, registry


def test_catalog_loads_and_validates():
    models = registry.models()
    assert {"minimax", "yue2", "stable-audio"} <= set(models)
    assert registry.music_ids()
    for m in models.values():
        assert m["engine"] in registry.ENGINES


def test_audiocpp_command_carries_measured_defaults():
    argv, env = registry.command("yue2", {"lyrics": "x", "style": "indie"}, "/tmp/o.wav", "/root/x")
    assert "cot=melody" in argv                                  # ch. 27
    assert argv[argv.index("--out") + 1] == "/tmp/o.wav"
    assert "--seed" in argv                                      # ch. 06
    s, _ = registry.command("stable-audio", {"style": "lo-fi", "duration": 9999},
                            "/tmp/o.wav", "/root/x")
    assert s[s.index("--duration-seconds") + 1] == "120"         # ch. 24


def test_python_command_takes_all_three_cards():
    argv, env = registry.command("minimax", {"style": "lo-fi", "lyrics": "x", "duration": 9999},
                                 "/tmp/o.wav", "/root/x")
    assert argv[argv.index("--seconds") + 1] == "300"            # exp. 13
    assert env["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"
    assert "CUDA_VISIBLE_DEVICES" not in env


def test_a_new_model_needs_no_code(tmp_path, monkeypatch):
    """The whole point: a file appears, the app offers it."""
    monkeypatch.setattr(registry, "CATALOG", str(tmp_path))
    registry._cache.update(mtime=0, models={})
    (tmp_path / "newthing.json").write_text(json.dumps({
        "id": "newthing", "name": "New Thing", "kind": "sing", "engine": "audiocpp",
        "outcome": {"title": "Something new", "blurb": "", "order": 4},
        "run": {"task": "gen", "family": "newthing", "gguf": "New/new-q8.gguf",
                "args": ["--text", "{style}"]},
        "fields": ["style"], "cards": 1, "rate": 0.5}))
    assert "newthing" in registry.models()
    assert [o["title"] for o in registry.outcomes()] == ["Something new"]
    argv, _ = registry.command("newthing", {"style": "jazz"}, "/tmp/o.wav", "/root/x")
    assert "jazz" in argv and argv[argv.index("--family") + 1] == "newthing"


def test_a_broken_file_is_refused_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "CATALOG", str(tmp_path))
    registry._cache.update(mtime=0, models={})
    (tmp_path / "broken.json").write_text('{"id": "broken", "name": "Broken"}')
    with pytest.raises(registry.BadModel):
        registry.models()


def test_the_estimate_learns_from_finished_jobs():
    conn = db.connect(":memory:"); db.init(conn)
    assert registry.measured_rate(conn, "yue2", 0.4) == (0.4, "estimated")
    for i in range(3):
        library.add_song(conn, id=f"s{i}", model="yue2", seconds=100)
        job = jobs.enqueue(conn, "yue2", {})
        jobs.claim(conn)
        jobs.finish(conn, job, song_id=f"s{i}", wall_s=50)          # half real time
    assert registry.measured_rate(conn, "yue2", 0.4) == (0.5, "measured")


def test_a_model_is_not_handed_an_empty_field():
    assert registry.missing("yue2", {"style": "", "lyrics": "x"}) == ["style"]
    assert registry.missing("yue2", {"style": "lo-fi", "lyrics": "x"}) == []
    with pytest.raises(registry.BadModel):
        registry.command("yue2", {"lyrics": "x"}, "/tmp/out.wav", "/root")


def test_a_package_directory_can_be_named_instead_of_one_file(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "CATALOG", str(tmp_path))
    registry._cache.update(mtime=0, models={})
    (tmp_path / "pack.json").write_text(json.dumps({
        "id": "pack", "name": "Packaged", "kind": "sing", "engine": "audiocpp",
        "run": {"family": "minimax_music3", "model_path": "models/MiniMax-Music3-GGUF",
                "args": ["--text", "{style}"]},
        "fields": ["style"], "cards": 1, "rate": 1.0}))
    argv, _ = registry.command("pack", {"style": "pop"}, "/tmp/o.wav", "/root/x")
    assert argv[argv.index("--model") + 1] == "/root/x/models/MiniMax-Music3-GGUF"


@pytest.mark.parametrize("given, seconds", [
    (150, 150), (150.7, 150), ("150", 150), (" 150 ", 150), ("2:45", 165), ("0:30", 30),
])
def test_a_length_can_be_written_the_ways_people_write_lengths(given, seconds):
    assert registry.as_seconds(given) == seconds


@pytest.mark.parametrize("given", ["🎵", "two minutes", "", "2:", ":30", "2:3:4", None, True, "-5", "1e3"])
def test_anything_that_is_not_a_length_is_refused(given):
    with pytest.raises(registry.BadModel):
        registry.as_seconds(given)


def test_length_is_predicted_from_the_words_the_model_sang():
    conn = db.connect(":memory:")
    db.init(conn)
    for i, (seconds, words) in enumerate([(120, 80), (150, 100), (180, 120), (60, 40)]):
        library.add_song(conn, id=f"w{i}", title=f"W{i}", model="yue2",
                         lyrics="[Verse]\n" + " ".join(["la"] * words))
        library.set_paths(conn, f"w{i}", seconds=seconds)

    assert registry.seconds_per_word(conn, "yue2") == 1.5        # every song here is 1.5
    assert registry.seconds_per_word(conn, "minimax") == 0.0     # nothing measured yet
