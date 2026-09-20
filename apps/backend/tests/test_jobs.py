import os, sys, pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import db, jobs, models


@pytest.fixture
def conn():
    c = db.connect(":memory:"); db.init(c); return c


def test_claim_returns_one_job_at_a_time(conn):
    a = jobs.enqueue(conn, "yue2", {"lyrics": "x"})
    jobs.enqueue(conn, "yue2", {"lyrics": "y"})
    assert jobs.claim(conn)["id"] == a
    assert jobs.claim(conn) is None                 # one card set, one running job
    jobs.finish(conn, a, song_id="s1")
    assert jobs.claim(conn)["model"] == "yue2"


def test_finish_records_error_and_status(conn):
    a = jobs.enqueue(conn, "yue2", {})
    jobs.claim(conn)
    jobs.finish(conn, a, error="boom")
    row = jobs.recent(conn)[0]
    assert row["status"] == "failed" and row["error"] == "boom"


def test_reset_stale_frees_the_queue(conn):
    a = jobs.enqueue(conn, "yue2", {}); jobs.claim(conn)
    assert jobs.claim(conn) is None
    assert jobs.reset_stale(conn) == 1
    assert jobs.queue_depth(conn) == {"queued": 0, "running": 0}


def test_minimax_command_carries_the_measured_defaults():
    argv, env = models.command(models.MODELS["minimax"],
                               {"lyrics": "x", "duration": 4000}, "/tmp/o.wav", "/root/x")
    assert argv[argv.index("--seconds") + 1] == "300"                  # exp 13a-3 cap
    assert env["PYTORCH_CUDA_ALLOC_CONF"] == "expandable_segments:True"  # exp 13a-2
    assert "CUDA_VISIBLE_DEVICES" not in env                            # all three cards
    assert env["HF_HUB_OFFLINE"] == "1"


def test_other_models_carry_their_defaults():
    v, _ = models.command(models.MODELS["voxcpm2"], {"text": "hi"}, "/tmp/o.wav", "/root/x")
    assert v[v.index("--text-chunk-size") + 1] == "400"                 # ch. 08
    y, _ = models.command(models.MODELS["yue2"], {"lyrics": "l"}, "/tmp/o.wav", "/root/x")
    assert "cot=melody" in y                                            # ch. 27
    s, _ = models.command(models.MODELS["stable-audio"], {"prompt": "p", "duration": 999},
                          "/tmp/o.wav", "/root/x")
    assert s[s.index("--duration-seconds") + 1] == "120"                # ch. 24
    k, _ = models.command(models.MODELS["kokoro"], {"text": "t", "voice": "ff_siwis"},
                          "/tmp/o.wav", "/root/x")
    assert k[k.index("--language") + 1] == "fr-fr"
    assert "--seed" in k                                                # ch. 06


def test_queue_positions_count_from_the_front(conn):
    a = jobs.enqueue(conn, "yue2", {"style": "a"}, "first")
    b = jobs.enqueue(conn, "yue2", {"style": "b"}, "second")
    c = jobs.enqueue(conn, "yue2", {"style": "c"}, "third")

    assert jobs.positions(conn) == {a: 1, b: 2, c: 3}

    jobs.claim(conn)                                   # a starts running
    by_id = {j["id"]: j for j in jobs.recent(conn)}
    assert by_id[a]["position"] == 0                   # running jobs are not in line
    assert by_id[b]["position"] == 1                   # and the rest move up
    assert by_id[c]["position"] == 2


def test_cancel_takes_a_waiting_job_out_of_the_line(conn):
    a = jobs.enqueue(conn, "yue2", {"style": "a"}, "first")
    b = jobs.enqueue(conn, "yue2", {"style": "b"}, "second")

    assert jobs.cancel(conn, a) is True
    assert jobs.positions(conn) == {b: 1}

    jobs.claim(conn)
    assert jobs.cancel(conn, b) is False      # running work is the worker's, not ours
