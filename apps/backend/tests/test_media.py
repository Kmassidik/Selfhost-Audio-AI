import os, subprocess, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import media


def sine(path, seconds=1.0):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                    "-i", f"sine=frequency=440:duration={seconds}",
                    "-ac", "2", "-ar", "44100", path], check=True)
    return path


def test_mp3_keeps_the_length(tmp_path):
    wav = sine(str(tmp_path / "a.wav"), 1.0)
    mp3 = media.to_mp3(wav, str(tmp_path / "out" / "a.mp3"), "128k")
    assert os.path.exists(mp3)
    assert abs(media.probe(mp3)["seconds"] - 1.0) < 0.2


def test_cover_is_deterministic_and_the_right_size(tmp_path):
    a = media.cover("seed-1", str(tmp_path / "a.png"), 320, 180)
    b = media.cover("seed-1", str(tmp_path / "b.png"), 320, 180)
    c = media.cover("seed-2", str(tmp_path / "c.png"), 320, 180)
    assert open(a, "rb").read() == open(b, "rb").read()      # same song, same cover
    assert open(a, "rb").read() != open(c, "rb").read()      # different song, different cover
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
                          "-of", "csv=p=0", a], capture_output=True, text=True).stdout
    assert out.strip().startswith("320,180")


def test_mp4_matches_the_audio_length(tmp_path):
    wav = sine(str(tmp_path / "a.wav"), 2.0)
    png = media.cover("s", str(tmp_path / "c.png"), 320, 180)
    mp4 = media.to_mp4(wav, png, str(tmp_path / "v" / "a.mp4"))
    assert abs(media.probe(mp4)["seconds"] - 2.0) < 0.2       # the 2026-09-19 bug


def test_fetch_cover_falls_back_when_offline(tmp_path, monkeypatch):
    import urllib.request
    def boom(*a, **k):
        raise OSError("no network")
    monkeypatch.setattr(urllib.request, "urlopen", boom)
    out = media.fetch_cover("seed-9", str(tmp_path / "c.png"), size=160, source="picsum")
    assert os.path.exists(out)                       # a song always has art
    same = media.fetch_cover("seed-9", str(tmp_path / "c2.png"), size=160, source="picsum")
    assert open(out, "rb").read() == open(same, "rb").read()


def test_fetch_cover_downloads_a_photo(tmp_path):
    out = media.fetch_cover("seed-42", str(tmp_path / "p.png"), size=200, source="picsum")
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=width,height",
                        "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
    assert r.startswith("200,200")                   # cropped square, whatever arrived


def test_typed_tags_lead_the_ones_read_from_the_song():
    import tags as tagger
    assert tagger.clean(" lo-fi , Study ,, lo-fi ") == ["Lo-fi", "Study"]
    assert tagger.clean(["one", "two", "three", "four", "five",
                         "six", "seven", "eight", "nine"]) == [
        "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight"]
    assert tagger.clean("") == []
