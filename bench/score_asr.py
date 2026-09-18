#!/usr/bin/env python3
"""Measure a speech recogniser against real human speech with known transcripts.

    python3 bench/score_asr.py --family qwen3_asr --label "Qwen3-ASR 1.7B q8_0" \
        --model models/gguf/Qwen3-ASR-1.7B-GGUF/qwen3-asr-1.7b-q8_0.gguf --n 20

WHY REAL SPEECH AND NOT OURS
----------------------------
A recogniser scored on audio this project generated measures the PAIR, with no
way to separate the voice's errors from the listener's. LibriSpeech test-clean
is read audiobooks with verified transcripts, and is the set almost every
published word error rate is quoted on — so our numbers can sit beside theirs.

WHAT IS HELD FIXED
------------------
The same utterances, in the same order, for every recogniser. The selection is
deterministic (sorted, first N) so a later run compares against the same audio.
"""
import argparse, glob, json, os, re, subprocess, sys, time, threading

ROOT = os.environ.get("SELFHOSTAUDIO_ROOT",
                      os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "bench"))
from score_wer import wer, words  # one definition of the metric, not two


def cli():
    build = os.environ.get("AUDIOCPP_BUILD", "linux-cuda-full")
    return os.path.join(ROOT, "engines", "audiocpp", "build", build, "bin", "audiocpp_cli")


def corpus(n, subset="test-clean"):
    """(id, wav_path, reference) for the first n utterances, deterministically.

    test-other is LibriSpeech's harder half: the same audiobooks, but the speakers
    the reference recogniser found hardest. Published rates are quoted on both."""
    base = os.path.join(ROOT, "data", "LibriSpeech", subset)
    refs = {}
    for t in sorted(glob.glob(os.path.join(base, "*", "*", "*.trans.txt"))):
        for line in open(t):
            uid, _, text = line.strip().partition(" ")
            refs[uid] = text
    out = []
    for f in sorted(glob.glob(os.path.join(base, "*", "*", "*.flac")))[:n]:
        uid = os.path.basename(f)[:-5]
        if uid in refs:
            out.append((uid, f, refs[uid]))
    return out


def to_wav(flac, dest):
    """audio.cpp may not read FLAC. Convert once, reuse for every recogniser."""
    if os.path.exists(dest):
        return dest
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", flac,
                        "-ar", "16000", "-ac", "1", dest], capture_output=True)
    return dest if r.returncode == 0 and os.path.exists(dest) else None


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True); self.peak = 0; self.stop = False
    def run(self):
        while not self.stop:
            try:
                o = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                                    "--format=csv,noheader,nounits"],
                                   capture_output=True, text=True, timeout=5).stdout
                self.peak = max(self.peak, int(o.split("\n")[0]))
            except Exception:
                pass
            time.sleep(0.15)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--quant", default="q8_0")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--extra", default="")
    ap.add_argument("--subset", default="test-clean", choices=["test-clean", "test-other"])
    ap.add_argument("--repeat", type=int, default=1, help="run index, for error bars across repeats")
    a = ap.parse_args()
    import shlex

    items = corpus(a.n, a.subset)
    if not items:
        sys.exit(f"no corpus — is data/LibriSpeech/{a.subset} present?")

    wav_dir = os.path.join(ROOT, "data", "wav16" if a.subset == "test-clean" else "wav16-" + a.subset)
    os.makedirs(wav_dir, exist_ok=True)

    rows, tot_audio, tot_wall = [], 0.0, 0.0
    s = Sampler(); s.start()
    for uid, flac, ref in items:
        wav = to_wav(flac, os.path.join(wav_dir, uid + ".wav"))
        if wav is None:
            print(f"  !! could not convert {uid}", file=sys.stderr); continue
        import struct
        b = open(wav, "rb").read(); d = b.find(b"data")
        nb = struct.unpack("<I", b[d+4:d+8])[0]
        dur = nb / 32000.0                      # 16 kHz mono 16-bit
        out = f"/tmp/asr-{uid}.txt"
        cmd = [cli(), "--task", "asr", "--family", a.family,
               "--model", os.path.join(ROOT, a.model), "--backend", "cuda",
               "--audio", wav, "--text", "", "--text-out", out] + shlex.split(a.extra)
        t0 = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True)
        wall = time.time() - t0
        hyp = open(out).read().strip() if os.path.exists(out) else ""
        if os.path.exists(out):
            os.remove(out)
        if r.returncode != 0:
            print(f"  !! {uid} failed: {(r.stderr or '')[-120:]}", file=sys.stderr)
            continue
        m = wer(ref, hyp)
        m.update({"id": uid, "duration_s": round(dur, 3), "wall_s": round(wall, 3),
                  "ref": ref, "hyp": hyp})
        rows.append(m); tot_audio += dur; tot_wall += wall
    s.stop = True; s.join(timeout=2)

    # Corpus word error rate is total edits over total reference words — NOT the
    # mean of per-utterance rates, which over-weights short utterances.
    E = sum(r["S"] + r["D"] + r["I"] for r in rows)
    N = sum(r["ref_words"] for r in rows)
    res = {"label": a.label, "family": a.family, "quant": a.quant,
           "utterances": len(rows), "audio_s": round(tot_audio, 2),
           "wall_s": round(tot_wall, 2),
           "rtf": round(tot_wall / tot_audio, 4) if tot_audio else None,
           "corpus_wer": round(E / N, 4) if N else None,
           "S": sum(r["S"] for r in rows), "D": sum(r["D"] for r in rows),
           "I": sum(r["I"] for r in rows), "ref_words": N,
           "peak_vram_mib": s.peak, "date": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "corpus": f"LibriSpeech {a.subset}, first N sorted", "subset": a.subset,
           "repeat": a.repeat,
           "rows": rows}
    p = os.path.join(ROOT, "bench", "results-asr",
                     f"{a.family}-{a.quant}-{a.subset}-r{a.repeat}-{int(time.time())}.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(res, open(p, "w"), indent=2)
    print(f"  {a.label:<30} WER {res['corpus_wer']:.4f}  RTF {res['rtf']:.4f}  "
          f"peak {res['peak_vram_mib']} MiB  ({res['utterances']} utts, "
          f"{res['audio_s']:.0f}s audio)")


if __name__ == "__main__":
    main()
