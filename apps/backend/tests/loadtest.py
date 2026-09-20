#!/usr/bin/env python3
"""100 people listening at once — does the app hold up?

Each simulated listener picks a song and asks for it the way a browser does:
a first byte range, then more as it plays. Reports p50/p95/p99, errors, and
throughput, so "it should be fine" becomes a number.

    python3 tests/loadtest.py --base http://10.0.0.20:8095 --listeners 100 --seconds 120
"""
import argparse
import json
import random
import statistics
import threading
import time
import urllib.request

stop = threading.Event()
lock = threading.Lock()
lat, errors, bytes_read = [], [], 0


def get(url, rng=None, timeout=20):
    req = urllib.request.Request(url)
    if rng:
        req.add_header("Range", f"bytes={rng[0]}-{rng[1]}")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read()
    return time.time() - t0, len(body), r.status if hasattr(r, "status") else 200


def listener(base, songs, chunk):
    global bytes_read
    while not stop.is_set():
        song = random.choice(songs)
        offset = 0
        try:
            ms, n, _ = get(f"{base}/api/library?limit=20&offset={random.randint(0, 40)}")
            with lock:
                lat.append(ms)
            for _ in range(8):                       # about 8 chunks of a song
                if stop.is_set():
                    return
                ms, n, _ = get(f"{base}/media/mp3/{song}.mp3", (offset, offset + chunk - 1))
                offset += n
                with lock:
                    lat.append(ms)
                    bytes_read += n
                if n < chunk:
                    break
                time.sleep(chunk / 16000)            # play it at 128 kbit/s, like a browser
        except Exception as e:
            with lock:
                errors.append(str(e)[:80])
            time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8095")
    ap.add_argument("--listeners", type=int, default=100)
    ap.add_argument("--seconds", type=int, default=120)
    ap.add_argument("--chunk", type=int, default=256 * 1024)
    a = ap.parse_args()

    page = json.load(urllib.request.urlopen(f"{a.base}/api/library?limit=100"))
    songs = [s["id"] for s in page["items"] if s["has_mp3"]]
    if not songs:
        raise SystemExit("no songs with an MP3 to test against")
    print(f"{len(songs)} songs · {a.listeners} listeners · {a.seconds}s")

    threads = [threading.Thread(target=listener, args=(a.base, songs, a.chunk), daemon=True)
               for _ in range(a.listeners)]
    t0 = time.time()
    for t in threads:
        t.start()
        time.sleep(0.01)                             # ramp up, do not thundering-herd
    time.sleep(a.seconds)
    stop.set()
    for t in threads:
        t.join(timeout=5)
    wall = time.time() - t0

    s = sorted(lat)
    pct = lambda p: round(s[int(len(s) * p)] * 1000, 1) if s else None
    result = {
        "listeners": a.listeners, "seconds": round(wall, 1), "requests": len(s),
        "p50_ms": pct(0.50), "p95_ms": pct(0.95), "p99_ms": pct(0.99),
        "max_ms": round(max(s) * 1000, 1) if s else None,
        "errors": len(errors), "error_sample": errors[:3],
        "throughput_MBps": round(bytes_read / wall / 1e6, 2),
        "per_listener_KBps": round(bytes_read / wall / a.listeners / 1e3, 1),
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    main()
