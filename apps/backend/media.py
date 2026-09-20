"""Everything that shells out to ffmpeg: MP3, cover art, MP4.

Why MP3 and not the WAV the models produce: the box's upload was measured at
2.5-4.4 MB/s on 2026-09-20. A WAV is 1.4 MB/s per listener, so the line carries
under two of them. MP3 at 128 kbit/s is 16 KB/s, which is about 155. The
library serves MP3; the WAV stays as the master for the owner.
"""
import hashlib
import os
import re
import struct
import subprocess

FFMPEG = os.environ.get("FFMPEG", "ffmpeg")
FFPROBE = os.environ.get("FFPROBE", "ffprobe")
COVER_W, COVER_H = 1280, 720


def _run(argv, timeout=1800):
    r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout).strip().splitlines()[-1][:300])
    return r


def probe(path: str) -> dict:
    """Length, sample rate and channels, straight from the file."""
    r = _run([FFPROBE, "-v", "error", "-select_streams", "a:0",
              "-show_entries", "stream=sample_rate,channels:format=duration",
              "-of", "default=nw=1:nk=1", path], timeout=60)
    vals = [v for v in r.stdout.split() if v]
    sr = int(vals[0]) if vals else 0
    ch = int(vals[1]) if len(vals) > 1 else 0
    dur = float(vals[2]) if len(vals) > 2 else 0.0
    return {"seconds": round(dur, 2), "sample_rate": sr, "channels": ch}


def to_mp3(src: str, out: str, bitrate: str = "128k") -> str:
    os.makedirs(os.path.dirname(out), exist_ok=True)
    _run([FFMPEG, "-y", "-loglevel", "error", "-i", src,
          "-c:a", "libmp3lame", "-b:a", bitrate, "-id3v2_version", "3", out])
    return out


def _rand(seed: str, n: int = 12):
    """A short, stable list of numbers in 0..1 for one song."""
    h = hashlib.sha256(str(seed).encode()).digest()
    return [h[i] / 255.0 for i in range(n)]


def _hsv(h, s, v):
    i = int(h * 6) % 6
    f = h * 6 - int(h * 6)
    p, q, t = v * (1 - s), v * (1 - f * s), v * (1 - (1 - f) * s)
    r, g, b = [(v, t, p), (q, v, p), (p, v, t), (p, q, v), (t, p, v), (v, p, q)][i]
    return [r * 255, g * 255, b * 255]


def _mix(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(3)]


def cover(seed: str, out: str, width=COVER_W, height=COVER_H) -> str:
    """Album art for one song, decided entirely by its seed.

    Three compositions — a low sun, a band of light, a drifting orb — each in
    the song's own two colours. Written as a PPM and converted by ffmpeg, so
    there is no image library to install on the box or in the container.
    """
    os.makedirs(os.path.dirname(out), exist_ok=True)
    r = _rand(seed)
    kind = int(r[0] * 3) % 3
    hue = r[1]
    hue2 = (hue + 0.10 + r[2] * 0.30) % 1.0

    deep = _hsv(hue, 0.60 + r[3] * 0.25, 0.10 + r[4] * 0.07)       # the dark end
    glow = _hsv(hue2, 0.55 + r[5] * 0.30, 0.65 + r[6] * 0.30)      # the lit end
    warm = _mix(glow, [255, 246, 230], 0.55)                        # light, never pure white
    ratio = width / height

    cx, cy = 0.25 + r[7] * 0.5, 0.22 + r[8] * 0.34
    rad = 0.09 + r[9] * 0.05
    band = 0.45 + r[10] * 0.25
    tilt = (r[11] - 0.5) * 0.5

    rows = []
    for y in range(height):
        fy = y / max(1, height - 1)
        line = bytearray()
        for x in range(width):
            fx = x / max(1, width - 1)
            if kind == 0:                                   # a low sun over a dark ground
                horizon = 0.60 + tilt * 0.15
                if fy > horizon:
                    t = (fy - horizon) / max(1e-6, 1 - horizon)
                    refl = max(0.0, 1 - abs(fx - cx) * 5) * max(0.0, 1 - t * 2.4) * 0.30
                    col = _mix([c * 0.55 for c in deep], glow, refl)
                else:
                    t = (fy / max(1e-6, horizon)) ** 1.5
                    d = ((fx - cx) ** 2 + ((fy - cy) * ratio) ** 2) ** 0.5
                    col = _mix(deep, glow, t * 0.85)
                    if d < rad:
                        col = _mix(col, warm, 0.80)
                    else:
                        col = _mix(col, warm, max(0.0, 1 - d / (rad * 3.6)) ** 2 * 0.55)
            elif kind == 1:                                 # a band of light across the field
                t = abs(fy - band + (fx - 0.5) * tilt)
                col = _mix(deep, glow, max(0.0, 1 - t * 3.2) ** 1.7)
                col = _mix(col, warm, max(0.0, 1 - t * 9.0) ** 2 * 0.5)
            else:                                           # a drifting orb in a colour field
                t = (fx * 0.5 + fy * 0.7)
                d = ((fx - cx) ** 2 + ((fy - cy) * ratio) ** 2) ** 0.5
                col = _mix(deep, glow, min(1.0, t) * 0.6)
                col = _mix(col, warm, max(0.0, 1 - d / (rad * 4.5)) ** 2 * 0.7)
            g = ((x * 7 + y * 13 + int(r[2] * 255)) % 9) - 4     # grain, against banding
            line += struct.pack("BBB", *(max(0, min(255, int(c + g))) for c in col))
        rows.append(bytes(line))

    ppm = out + ".ppm"
    with open(ppm, "wb") as f:
        f.write(b"P6\n%d %d\n255\n" % (width, height))
        f.writelines(rows)
    try:
        _run([FFMPEG, "-y", "-loglevel", "error", "-i", ppm, out], timeout=120)
    finally:
        os.remove(ppm)
    return out


def fetch_cover(seed: str, out: str, keywords: str = "", size: int = 640,
                source: str = "picsum", timeout: int = 25) -> str:
    """A real photograph for the cover, the same one for the same song.

    Picsum serves Unsplash photographs and is deterministic per seed, so a song
    keeps its cover forever. LoremFlickr matches keywords from the song's style,
    which fits the mood better but carries mixed Flickr licences. If the box is
    offline, the drawn cover in cover() takes over — a song always has art.
    """
    import urllib.request
    key = hashlib.sha256(str(seed).encode()).hexdigest()[:12]
    if source == "gradient":
        return cover(seed, out, size, size)
    if source == "loremflickr":
        words = ",".join([w for w in re.findall(r"[A-Za-z]{4,}", keywords)][:3]) or "music"
        url = f"https://loremflickr.com/{size}/{size}/{words}?lock={int(key[:6], 16)}"
    else:
        url = f"https://picsum.photos/seed/{key}/{size}/{size}"

    os.makedirs(os.path.dirname(out), exist_ok=True)
    raw = out + ".dl"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "music-studio/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            if not (r.headers.get("content-type", "").startswith("image/")):
                raise RuntimeError("not an image")
            data = r.read()
        if len(data) < 2000:
            raise RuntimeError("image too small to be real")
        with open(raw, "wb") as f:
            f.write(data)
        _run([FFMPEG, "-y", "-loglevel", "error", "-i", raw, "-vf",
              f"scale={size}:{size}:force_original_aspect_ratio=increase,crop={size}:{size}",
              out], timeout=120)
        return out
    except Exception:
        return cover(seed, out, size, size)       # offline, or the service is down
    finally:
        if os.path.exists(raw):
            os.remove(raw)


# The cover takes its colour from what the song IS, not from which model made it:
# a morning song is amber, a night song indigo, rain is steel blue. A shelf of
# covers then reads as a mood board rather than a list of engines.
TAG_HUE = {"Morning": 32, "Night": 250, "Rainy": 205, "Chill": 175, "Upbeat": 335,
           "Sad": 222, "Focus": 190, "Lo-fi": 30, "Hip hop": 300, "Jazz": 42,
           "Electronic": 265, "Ambient": 195, "Cinematic": 14, "Indie pop": 340,
           "Rock": 6, "Folk": 62, "Neo soul": 285, "Ballad": 315, "Funk": 46,
           "Japanese": 350, "Instrumental": 168}
DEFAULT_HUE = 28


def hue_for(tags_in_order) -> int:
    for t in tags_in_order or ():
        if t in TAG_HUE:
            return TAG_HUE[t]
    return DEFAULT_HUE
CJK_FONT = os.environ.get("COVER_FONT_CJK", "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc")
LATIN_FONT = os.environ.get("COVER_FONT", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

_drawtext = None


def has_drawtext() -> bool:
    """Whether this ffmpeg can set type. Checked once."""
    global _drawtext
    if _drawtext is None:
        try:
            out = subprocess.run([FFMPEG, "-hide_banner", "-filters"],
                                 capture_output=True, text=True, timeout=20).stdout
            _drawtext = " drawtext " in out
        except Exception:
            _drawtext = False
    return _drawtext


def _font_for(text: str) -> str:
    """A Japanese title needs a font that has the characters."""
    if re.search(r"[\u3040-\u30ff\u4e00-\u9faf\uac00-\ud7af]", text):
        for path in (CJK_FONT, CJK_FONT.replace("NotoSansCJK", "NotoSerifCJK")):
            if os.path.exists(path):
                return path
    return LATIN_FONT if os.path.exists(LATIN_FONT) else CJK_FONT


def _wrap(title: str, per_line: int = 15, lines: int = 2) -> list:
    """Break a title into at most two lines, on spaces where possible."""
    title = re.sub(r"\s*[—–-]\s*(YuE2|MiniMax[^()]*|Stable Audio).*$", "", title).strip()
    title = re.sub(r"\s*\([^)]*\)\s*$", "", title).strip() or "Untitled"
    out, current = [], ""
    for word in title.split():
        if len(current) + len(word) + 1 > per_line and current:
            out.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
        if len(out) == lines:
            break
    if current and len(out) < lines:
        out.append(current)
    if not out:
        out = [title[:per_line]]
    if len(out) == lines and len(title) > sum(len(o) + 1 for o in out):
        out[-1] = out[-1][:per_line - 1] + "…"
    return out


def art_cover(song_id: str, out: str, title: str = "", model: str = "", style: str = "",
              label: str = "", size: int = 640, source: str = "picsum", attempt: int = 0,
              tags_in_order=()) -> str:
    """A record sleeve: a photograph, graded to one colour, with the title set on it.

    No image model. The photograph comes from Picsum (Unsplash's library); ffmpeg
    turns it to a duotone in the song's colour, fades the lower half to black so
    type can sit there, adds grain, and prints the title and its category. If
    anything is missing — no network, no drawtext — cover() draws one instead.
    """
    os.makedirs(os.path.dirname(out), exist_ok=True)
    photo = out + ".src.png"
    text_files = []
    try:
        fetch_cover(f"{song_id}-{attempt}" if attempt else song_id, photo,
                    keywords=style, size=size * 2, source=source)
        if not has_drawtext():
            os.replace(photo, out)
            return out

        hue = hue_for(tags_in_order)
        lines = _wrap(title or "Untitled")
        font = _font_for(title)
        big = int(size * 0.086)
        small = int(size * 0.030)
        pad = int(size * 0.078)
        base_y = size - pad - (len(lines) - 1) * int(big * 1.16) - big

        draws = []
        for i, line in enumerate(lines):
            tf = f"{out}.line{i}.txt"
            with open(tf, "w") as f:
                f.write(line)
            text_files.append(tf)
            draws.append(f"drawtext=textfile='{tf}':fontfile='{font}':fontcolor=white:"
                         f"fontsize={big}:x={pad}:y={base_y + i * int(big * 1.16)}:"
                         f"shadowcolor=black@0.45:shadowx=0:shadowy=2")
        if label:
            mf = f"{out}.meta.txt"
            with open(mf, "w") as f:
                f.write(label.upper())
            text_files.append(mf)
            draws.append(f"drawtext=textfile='{mf}':fontfile='{LATIN_FONT}':fontcolor=white@0.78:"
                         f"fontsize={small}:x={pad}:y={base_y - int(small * 2.4)}")

        # A real gradient, computed per pixel: the top stays open, the bottom goes
        # to near-black so the type has somewhere to sit. Stacked boxes showed
        # their edges, which looked like a mistake rather than a design.
        f = r"clip(1-0.92*max(0\,(Y-0.34*H)/(0.66*H))\,0.08\,1)"
        fade = f"geq=r='r(X,Y)*{f}':g='g(X,Y)*{f}':b='b(X,Y)*{f}'"

        chain = ",".join([
            f"scale={size}:{size}:force_original_aspect_ratio=increase",
            f"crop={size}:{size}",
            "format=gray",                                   # a duotone starts from grey
            "format=yuv444p",                                # colorize needs somewhere to put colour
            f"colorize=hue={hue}:saturation=0.75:lightness=0.04",
            "curves=preset=increase_contrast",
            "eq=brightness=-0.02:contrast=1.12:saturation=1.6",
            "format=rgb24",
            fade,
            "noise=alls=6:allf=t+u",                         # grain, so it is not glassy
            *draws,
        ])
        _run([FFMPEG, "-y", "-loglevel", "error", "-i", photo, "-vf", chain, out], timeout=180)
        return out
    except Exception:
        return cover(song_id, out, size, size)
    finally:
        for f in [photo, *text_files]:
            if f and os.path.exists(f):
                os.remove(f)


def to_mp4(audio: str, cover_png: str, out: str, bitrate: str = "256k") -> str:
    """A still-image video, exactly as long as the audio.

    The length is taken from the audio and passed as -t. Without it, a looping
    image made a 3:16 video of a 2:14 song (2026-09-19).
    """
    os.makedirs(os.path.dirname(out), exist_ok=True)
    seconds = probe(audio)["seconds"]
    _run([FFMPEG, "-y", "-loglevel", "error", "-loop", "1", "-framerate", "1",
          "-i", cover_png, "-i", audio, "-map", "0:v", "-map", "1:a",
          "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p", "-r", "1",
          "-c:a", "aac", "-b:a", bitrate, "-t", f"{seconds:.3f}",
          "-movflags", "+faststart", out])
    return out
