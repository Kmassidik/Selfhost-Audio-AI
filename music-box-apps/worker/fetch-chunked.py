#!/usr/bin/env python3
"""A resumable, chunked downloader for this box.

Why it exists: a single long-lived connection to Hugging Face starts at 5 MB/s
and then the server closes it (measured: 336 MB of 8 GB, then
"transfer closed with 7689437947 bytes remaining"). Short ranged requests are
fast and reliable here, so this fetches many of them in parallel, remembers
which chunks are done, and resumes without redoing them.

    fetch-chunked.py <url> <out> [--chunk-mb 16] [--workers 8] [--token-file ~/.cache/huggingface/token]
"""
import argparse
import json
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request

DONE_LOCK = threading.Lock()


def head_size(url, headers):
    req = urllib.request.Request(url, method="GET", headers={**headers, "Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        cr = r.headers.get("Content-Range")
        if cr and "/" in cr:
            return int(cr.split("/")[-1])
        length = r.headers.get("Content-Length")
        if length:
            return int(length)
    raise RuntimeError("could not learn the file size")


def fetch_chunk(url, headers, start, end, path, tries=30):
    """One ranged read, fetched by curl.

    Measured on this box: the same 1 MB range took 241 s through Python's
    urllib (~4 KB/s) and 2 s through curl (3.9 MB/s). It is not the link and
    not HTTP/2 — curl is fast on HTTP/1.1 too — so the bytes come from curl.
    """
    want = end - start + 1
    tmp = "%s.chunk%d" % (path, start)
    cmd = ["curl", "-fsSL", "--max-time", "180", "-r", "%d-%d" % (start, end), "-o", tmp]
    for key, value in headers.items():
        cmd += ["-H", "%s: %s" % (key, value)]
    cmd.append(url)

    for attempt in range(1, tries + 1):
        try:
            done = subprocess.run(cmd, capture_output=True, timeout=200)
            if done.returncode == 0 and os.path.getsize(tmp) == want:
                with open(tmp, "rb") as src, open(path, "r+b") as dst:
                    dst.seek(start)
                    dst.write(src.read())
                os.remove(tmp)
                return True
            raise RuntimeError("curl exit %s, %s of %s bytes" % (
                done.returncode, os.path.getsize(tmp) if os.path.exists(tmp) else 0, want))
        except Exception as e:
            if attempt == tries:
                print("  chunk %s-%s failed: %s" % (start, end, str(e)[:90]), flush=True)
                if os.path.exists(tmp):
                    os.remove(tmp)
                return False
            time.sleep(min(15, 2 * attempt))
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--chunk-mb", type=int, default=2)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--token-file", default=os.path.expanduser("~/.cache/huggingface/token"))
    # a ranged GET for the size hangs on this box's Hugging Face path; the size
    # can be passed instead (it is in the hub listing, or in curl's own
    # "transfer closed with N bytes remaining" message)
    ap.add_argument("--size", type=int, default=0)
    args = ap.parse_args()

    headers = {"User-Agent": "dalang-music-box/1.0"}
    if args.token_file and os.path.exists(args.token_file):
        headers["Authorization"] = "Bearer " + open(args.token_file).read().strip()

    size = args.size or head_size(args.url, headers)
    chunk = args.chunk_mb * 1024 * 1024
    count = (size + chunk - 1) // chunk
    state_path = args.out + ".chunks"
    done = set()
    if os.path.exists(state_path):
        done = set(json.load(open(state_path)))
    if not os.path.exists(args.out):
        with open(args.out, "wb") as f:
            f.truncate(size)

    todo = [i for i in range(count) if i not in done]
    print("size %.2f GB in %d chunks, %d already done" % (size / 1e9, count, len(done)), flush=True)
    queue = list(todo)
    lock = threading.Lock()
    started = time.time()
    session_bytes = [0]   # only what THIS run fetched: a resume is not throughput

    def worker():
        while True:
            with lock:
                if not queue:
                    return
                i = queue.pop(0)
            start, end = i * chunk, min(size, (i + 1) * chunk) - 1
            if fetch_chunk(args.url, headers, start, end, args.out, tries=12):
                with DONE_LOCK:
                    done.add(i)
                    session_bytes[0] += end - start + 1
                    json.dump(sorted(done), open(state_path, "w"))
                    if len(done) % 10 == 0 or len(done) == count:
                        elapsed = max(1, time.time() - started)
                        rate = session_bytes[0] / elapsed if session_bytes[0] else 0
                        left = (count - len(done)) * chunk / rate if rate else float("inf")
                        eta = ("%d min" % (left / 60)) if left < 3600 else (
                              "%.1f h" % (left / 3600) if left != float("inf") else "unknown")
                        print("  %d/%d chunks · %.1f MB/s this run · %.0f%% · %s left"
                              % (len(done), count, rate / 1e6, 100 * len(done) / count, eta),
                              flush=True)

    threads = [threading.Thread(target=worker) for _ in range(args.workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if len(done) == count and os.path.getsize(args.out) == size:
        os.remove(state_path)
        print("complete: %s (%.2f GB)" % (args.out, size / 1e9))
    else:
        print("incomplete: %d/%d chunks — run again to resume" % (len(done), count))


if __name__ == "__main__":
    main()
