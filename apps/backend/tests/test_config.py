import importlib, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_inline_comments_in_env_are_ignored(monkeypatch):
    # systemd hands the whole line through, comment included
    monkeypatch.setenv("SERVE_MEDIA", "1   # dev only")
    monkeypatch.setenv("MP3_BITRATE", "192k  # louder")
    monkeypatch.setenv("APP_PORT", "8099 # not the default")
    import config
    importlib.reload(config)
    s = config.settings()
    assert s.serve_media is True and s.mp3_bitrate == "192k" and s.port == 8099


def test_quotes_are_stripped(monkeypatch):
    monkeypatch.setenv("OWNER_PASSWORD", '"hunter2"')
    import config
    importlib.reload(config)
    assert config.settings().owner_password == "hunter2"
