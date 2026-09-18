#!/usr/bin/env python3
"""Measure one audio generation run. Standard library only.

    python3 bench/run.py --family kokoro_tts --level L0 --quant q8_0 \
        --model models/gguf/Kokoro-82M-GGUF/kokoro-82m-q8_0.gguf \
        --prompt s_paragraph --label "L0 · Kokoro-82M · q8_0"

Writes exactly one JSON to bench/results/. No JSON, no run.

Why standard library only: the harness must never fail because a model's
environment installed an incompatible version of something. selfhostllm holds
this line and it has paid off.
"""
import argparse, json, os, shlex, struct, subprocess, sys, time, hashlib, threading

ROOT = os.environ.get("SELFHOSTAUDIO_ROOT",
                      os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def wav_facts(path):
    """Read the format off the FILE, never off the model card."""
    b = open(path, "rb").read()
    i = b.find(b"fmt ")
    ch, sr, _, _, bits = struct.unpack("<HIIHH", b[i + 10:i + 24])
    d = b.find(b"data")
    n = struct.unpack("<I", b[d + 4:d + 8])[0]
    return {"sample_rate": sr, "channels": ch, "bit_depth": bits,
            "samples": n // (bits // 8) // ch,
            "duration_s": round(n / (sr * ch * bits // 8), 4),
            "bytes_per_second": sr * ch * bits // 8,
            "sha256": hashlib.sha256(b).hexdigest()}


class GpuSampler(threading.Thread):
    """Poll every card at 5 Hz. A spike shorter than 200 ms is missed, and the
    result says so — the sibling recorded the same caveat."""
    def __init__(self):
        super().__init__(daemon=True)
        self.peak, self.stop = {}, False

    def run(self):
        while not self.stop:
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=index,memory.used",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=5).stdout
                for line in out.strip().splitlines():
                    i, m = [x.strip() for x in line.split(",")]
                    self.peak[int(i)] = max(self.peak.get(int(i), 0), int(m))
            except Exception:
                pass
            time.sleep(0.2)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--family", required=True)
    p.add_argument("--level", required=True)
    p.add_argument("--quant", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--prompt", required=True, help="id from bench/prompts.json")
    p.add_argument("--label", required=True)
    p.add_argument("--backend", default="cuda")
    p.add_argument("--voice-id", default=None,
                   help="kokoro only; other families use --speaker or --voice-ref via --extra")
    p.add_argument("--language", default=None)
    p.add_argument("--task", default="tts")
    p.add_argument("--seed", type=int, default=None,
                   help="omit to measure the DEFAULT behaviour, which may not be deterministic")
    # One shell-quoted string, not nargs="*": argparse consumes a bare
    # "--speaker Vivian" as an unknown option of its own and refuses the run.
    p.add_argument("--extra", default="",
                   help='pass-through engine flags, quoted: --extra "--speaker Vivian"')
    a = p.parse_args()

    prompts = json.load(open(os.path.join(ROOT, "bench", "prompts.json")))
    entry = next((x for x in prompts["speech"] + prompts["music"]
                  if x["id"] == a.prompt), None)
    if entry is None:
        sys.exit(f"unknown prompt id {a.prompt} — prompts.json is frozen")
    text = entry.get("text") or entry.get("lyrics") or ""

    run_id = f"{a.level}-{a.family}-{a.quant}-{a.prompt}-{int(time.time())}"
    out_dir = os.path.join(ROOT, "runs", run_id)
    os.makedirs(out_dir, exist_ok=True)
    out_wav = os.path.join(out_dir, "out.wav")

    # The "full" build carries all 61 model families. The earlier narrow build
    # is kept because a five-family binary is 379 MB against 919 MB, but the
    # default is full: a missing family costs a whole rebuild to discover.
    build = os.environ.get("AUDIOCPP_BUILD", "linux-cuda-full")
    cli = os.path.join(ROOT, "engines", "audiocpp", "build", build, "bin", "audiocpp_cli")
    cmd = [cli, "--task", a.task, "--family", a.family,
           "--model", os.path.join(ROOT, a.model) if not os.path.isabs(a.model) else a.model,
           "--backend", a.backend, "--text", text, "--out", out_wav]
    if a.language:
        cmd += ["--language", a.language]
    if a.voice_id:
        cmd += ["--voice-id", a.voice_id]
    if a.seed is not None:
        cmd += ["--seed", str(a.seed)]
    cmd += shlex.split(a.extra)

    s = GpuSampler(); s.start()
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True)
    wall = time.time() - t0
    s.stop = True; s.join(timeout=2)

    if proc.returncode != 0 or not os.path.exists(out_wav):
        sys.exit(f"run failed rc={proc.returncode}\n{proc.stderr[-2000:]}")

    w = wav_facts(out_wav)
    # RTF uses the duration of the file PRODUCED, never the duration requested.
    # A model asked for four minutes that delivers three has not been fast.
    result = {
        "run_id": run_id, "label": a.label, "level": a.level,
        "family": a.family, "quant": a.quant, "backend": a.backend, "task": a.task,
        "prompt_id": a.prompt, "seed": a.seed,
        "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "wall_s": round(wall, 3),
        "rtf_wall": round(wall / w["duration_s"], 4) if w["duration_s"] else None,
        "audio": w,
        "peak_vram_mib": dict(sorted(s.peak.items())),
        "cmd": cmd, "extra": a.extra,
        "caveats": [
            "VRAM sampled at 5 Hz — a spike shorter than 200 ms is missed.",
            "rtf_wall INCLUDES model load and CUDA warmup. For the one-shot CLI "
            "that is most of it — see rtf_generate in the two-length fit.",
        ],
    }
    path = os.path.join(ROOT, "bench", "results", run_id + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    json.dump(result, open(path, "w"), indent=2)
    print(json.dumps({k: result[k] for k in
                      ("run_id", "wall_s", "rtf_wall", "peak_vram_mib")}, indent=2))
    print(f"-> {path}")


if __name__ == "__main__":
    main()
