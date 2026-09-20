import os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db, library


@pytest.fixture
def conn():
    c = db.connect(":memory:"); db.init(c); return c


def test_init_creates_tables_and_wal(tmp_path):
    c = db.connect(tmp_path / "app.db"); db.init(c); db.init(c)      # twice: must be safe
    names = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
    assert {"songs", "jobs", "playlists", "playlist_items", "likes", "plays"} <= names
    assert c.execute("pragma journal_mode").fetchone()[0].lower() == "wal"


def test_page_slices_and_reports_total(conn):
    for i in range(120):
        library.add_song(conn, id=f"s{i:03d}", title=f"song {i}", model="yue2", seconds=60)
    first = library.page(conn, offset=0, limit=50)
    assert first["total"] == 120 and len(first["items"]) == 50
    assert library.page(conn, offset=100, limit=50)["total"] == 120
    assert len(library.page(conn, offset=100, limit=50)["items"]) == 20


def test_limit_is_clamped(conn):
    for i in range(30):
        library.add_song(conn, id=f"s{i}", title=f"t{i}")
    assert library.page(conn, limit=5000, max_limit=100)["limit"] == 100


def test_search_matches_lyrics_and_style(conn):
    library.add_song(conn, id="a", title="A", model="minimax", lyrics="one umbrella left")
    library.add_song(conn, id="b", title="B", model="minimax", style="lo-fi chill")
    assert [s["title"] for s in library.page(conn, q="umbrella")["items"]] == ["A"]
    assert [s["title"] for s in library.page(conn, q="lo-fi")["items"]] == ["B"]


def test_sort_long_and_filter_model(conn):
    library.add_song(conn, id="a", title="A", model="yue2", seconds=30)
    library.add_song(conn, id="b", title="B", model="minimax", seconds=200)
    assert [s["title"] for s in library.page(conn, sort="long")["items"]] == ["B", "A"]
    assert [s["title"] for s in library.page(conn, model="yue2")["items"]] == ["A"]


def test_likes_filter_and_toggle(conn):
    library.add_song(conn, id="a", title="A")
    library.add_song(conn, id="b", title="B")
    library.set_like(conn, "a", True)
    assert [s["title"] for s in library.page(conn, liked=True)["items"]] == ["A"]
    assert library.get_song(conn, "a")["liked"] is True
    library.set_like(conn, "a", False)
    assert library.page(conn, liked=True)["total"] == 0


def test_playlist_keeps_order(conn):
    for i in "abc":
        library.add_song(conn, id=i, title=i.upper())
    pid = library.create_playlist(conn, "Morning")
    for i in "abc":
        library.add_to_playlist(conn, pid, i)
    library.add_to_playlist(conn, pid, "a")                      # re-adding must not duplicate
    got = library.page(conn, playlist_id=pid)
    assert [s["title"] for s in got["items"]] == ["A", "B", "C"] and got["total"] == 3
    library.reorder_playlist(conn, pid, ["c", "b", "a"])
    assert [s["title"] for s in library.page(conn, playlist_id=pid)["items"]] == ["C", "B", "A"]
    assert library.playlists(conn)[0]["songs"] == 3


def test_song_paths_are_not_leaked_to_pages(conn):
    library.add_song(conn, id="a", title="A", wav_path="/secret/a.wav", mp3_path="/x/a.mp3")
    item = library.page(conn)["items"][0]
    assert "wav_path" not in item and "mp3_path" not in item
    assert item["has_mp3"] is True
    assert library.paths(conn, "a")["wav_path"] == "/secret/a.wav"


def test_tags_ride_along_with_each_song(conn):
    import tags
    library.add_song(conn, id="a", title="Rainy night", model="yue2",
                     style="lo-fi hip hop, 78 bpm, rain", lyrics="[Verse]\nrain", seconds=120)
    tags.rebuild(conn)
    item = library.page(conn)["items"][0]
    assert "Lo-fi" in item["tags"] and "Rainy" in item["tags"]
    assert library.page(conn, tag="Lo-fi")["total"] == 1
    assert library.page(conn, tag="Jazz")["total"] == 0
    assert [c["tag"] for c in tags.counts(conn, minimum=1)][:1] != []


def test_ids_filter_returns_only_those_songs(conn):
    for i in "abc":
        library.add_song(conn, id=i, title=i.upper())
    got = library.page(conn, ids=["c", "a"])
    assert got["total"] == 2 and {s["id"] for s in got["items"]} == {"a", "c"}


def test_removing_a_song_takes_its_files_with_it(conn, tmp_path):
    wav = tmp_path / "a.wav"
    cover = tmp_path / "a.png"
    wav.write_bytes(b"RIFF")
    cover.write_bytes(b"PNG")
    library.add_song(conn, id="s1", title="Junk", model="yue2", wav_path=str(wav))
    library.set_paths(conn, "s1", cover_path=str(cover), seconds=3)

    assert library.remove(conn, "s1") == {"removed": 1, "files": 2}
    assert not wav.exists() and not cover.exists()
    assert library.get_song(conn, "s1") is None
    assert library.remove(conn, "s1")["removed"] == 0     # removing twice is not an error


def test_shuffle_is_stable_for_one_seed_and_differs_between_seeds(conn):
    for i in range(12):
        library.add_song(conn, id=f"r{i}", title=f"Song {i}", model="yue2")

    def order(seed):
        return [s["id"] for s in library.page(conn, sort="random", seed=seed, limit=12)["items"]]

    assert order(7) == order(7)                      # paging must not reshuffle
    assert order(7) != order(8)                      # a new seed is a new order
    assert sorted(order(7)) == sorted(order(8))      # and nothing is lost either way


def test_liked_songs_come_first_when_sorted_by_like(conn):
    library.add_song(conn, id="a", title="A", model="yue2")
    library.add_song(conn, id="b", title="B", model="yue2")
    library.add_song(conn, id="c", title="C", model="yue2")
    library.set_like(conn, "c", True)

    assert [s["id"] for s in library.page(conn, sort="liked")["items"]][0] == "c"


def test_moving_the_data_directory_does_not_lose_the_files(conn, tmp_path):
    mp3dir = tmp_path / "studio" / "mp3"
    mp3dir.mkdir(parents=True)
    (mp3dir / "s1.mp3").write_bytes(b"ID3")
    library.add_song(conn, id="s1", title="Moved", model="yue2")
    stale = str(tmp_path / "old" / "mp3" / "s1.mp3")
    library.set_paths(conn, "s1", mp3_path=stale, seconds=9)
    assert not os.path.exists(library.paths(conn, "s1")["mp3_path"])   # the lie

    assert library.repair_paths(conn, {"mp3": str(mp3dir)}) == 1
    assert os.path.exists(library.paths(conn, "s1")["mp3_path"])       # the truth
    assert library.repair_paths(conn, {"mp3": str(mp3dir)}) == 0       # nothing left to fix
