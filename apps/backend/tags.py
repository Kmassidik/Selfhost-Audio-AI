"""Categories, worked out from the song itself.

Every song already carries the words that made it — the style prompt, the
lyrics, the model, the length. That is enough to sort a library into rows
without anyone tagging anything by hand, and it keeps working as songs are
added. Nothing here guesses at sound: it reads what was asked for.
"""
import re

# A tag is (label, group, patterns). The first pattern that appears in the
# song's own words wins. Order matters only for display.
GENRES = [
    ("Lo-fi",        r"lo-?fi"),
    ("Hip hop",      r"hip ?hop|boom bap|\brap\b|trap"),
    ("Neo soul",     r"neo.?soul|\bsoul\b|r&b|rnb"),
    ("Indie pop",    r"indie|\bpop\b"),
    ("Rock",         r"\brock\b|punk|metal|grunge"),
    ("Jazz",         r"\bjazz|swing|bossa"),
    ("Electronic",   r"electronic|synth|house|techno|edm|chiptune|8-bit"),
    ("Ambient",      r"ambient|drone|new age|meditat"),
    ("Cinematic",    r"cinematic|trailer|orchestra|epic|score"),
    ("Ballad",       r"ballad|slow dance"),
    ("Folk",         r"\bfolk\b|acoustic guitar|singer.?songwriter"),
    ("Funk",         r"\bfunk"),
]

MOODS = [
    ("Morning",   r"morning|sunrise|wake|朝"),
    ("Night",     r"night|midnight|late|夜|深夜"),
    ("Rainy",     r"rain|storm|umbrella|雨"),
    ("Chill",     r"chill|mellow|relax|calm|laid.?back|dreamy"),
    ("Upbeat",    r"upbeat|energetic|bright|happy|bouncy|driving"),
    ("Sad",       r"\bsad\b|melanchol|lonely|heartbreak|tender"),
    ("Focus",     r"focus|study|work|concentrat"),
]

LANGUAGES = [
    ("Japanese",   r"[぀-ヿ一-龯]|japanese|日本"),
    ("Indonesian", r"\bindonesian?\b|bahasa|jangan|kita |yang |tidak"),
    ("Mandarin",   r"mandarin|chinese|普通话"),
]


def _hits(text: str, table) -> list:
    out = []
    for label, pattern in table:
        if re.search(pattern, text, re.I):
            out.append(label)
    return out


def for_song(style: str = "", lyrics: str = "", model: str = "", seconds: float = 0) -> list:
    """Every category one song belongs to, most specific first."""
    words = f"{style}\n{lyrics}"
    tags = []

    tags += _hits(words, GENRES)[:2]          # two genres is plenty for a row
    tags += _hits(words, MOODS)[:2]
    langs = _hits(words, LANGUAGES)
    tags += langs
    if not langs and re.search(r"[A-Za-z]", lyrics or style):
        tags.append("English")

    tags.append("Instrumental" if not (lyrics or "").strip() else "Vocals")

    bpm = re.search(r"(?:bpm|tempo)\D{0,4}(\d{2,3})", words, re.I)
    if bpm:
        n = int(bpm.group(1))
        tags.append("Slow" if n < 85 else "Mid-tempo" if n < 110 else "Fast")

    if seconds >= 150:
        tags.append("Long play")
    elif 0 < seconds <= 45:
        tags.append("Short")

    seen = set()
    return [t for t in tags if not (t in seen or seen.add(t))]


def rebuild(conn) -> int:
    """Re-tag every song. Cheap enough to run whenever the rules change."""
    conn.execute("DELETE FROM song_tags")
    n = 0
    for r in conn.execute("SELECT id, style, lyrics, model, seconds FROM songs WHERE visible=1"):
        for tag in for_song(r["style"], r["lyrics"], r["model"], r["seconds"]):
            conn.execute("INSERT OR IGNORE INTO song_tags (song_id, tag) VALUES (?,?)",
                         (r["id"], tag))
            n += 1
    conn.commit()
    return n


def clean(given) -> list:
    """Tags as a person typed them: a list, or one comma-separated line.

    They become rows in the library, so they are trimmed, capitalised the way
    the built-in ones are, capped in length and in number, and de-duplicated.
    """
    if isinstance(given, str):
        given = given.split(",")
    out, seen = [], set()
    for raw in given or []:
        tag = re.sub(r"\s+", " ", str(raw)).strip(" ,.;")[:24]
        if not tag:
            continue
        tag = tag[0].upper() + tag[1:]
        if tag.lower() not in seen:
            seen.add(tag.lower())
            out.append(tag)
    return out[:8]


def tag_song(conn, song_id: str, given=()) -> list:
    """Tag one song, as it arrives from the worker."""
    r = conn.execute("SELECT style, lyrics, model, seconds FROM songs WHERE id=?",
                     (song_id,)).fetchone()
    if not r:
        return []
    tags = clean(given) + [t for t in for_song(r["style"], r["lyrics"], r["model"], r["seconds"])
                           if t.lower() not in {g.lower() for g in clean(given)}]
    for tag in tags:
        conn.execute("INSERT OR IGNORE INTO song_tags (song_id, tag) VALUES (?,?)", (song_id, tag))
    conn.commit()
    return tags


def counts(conn, only_models=(), minimum=2) -> list:
    """Which categories have enough songs to be worth a row."""
    where = "s.visible=1"
    args = []
    if only_models:
        where += " AND s.model IN (%s)" % ",".join("?" * len(only_models))
        args = list(only_models)
    rows = conn.execute(f"""
        SELECT t.tag, COUNT(*) AS songs FROM song_tags t
        JOIN songs s ON s.id = t.song_id
        WHERE {where} GROUP BY t.tag HAVING songs >= ?
        ORDER BY songs DESC, t.tag ASC""", (*args, minimum)).fetchall()
    return [dict(r) for r in rows]
