#!/usr/bin/env python3
"""Experiment 16: ACE-Step 1.5 turbo at 6 bits (q6_k, converted here from the
published bf16 package) on one 8 GB card, the frozen m_song_short prompt,
10 / 30 / 60 s asked, seed 20260915. Whole-card memory sampled on all 3 cards.
"""
import json, os, struct, subprocess, sys, threading, time
R = os.environ.get("SELFHOSTAUDIO_ROOT", "/root/Desktop/selfhostaudioai")
CLI = f"{R}/engines/audiocpp/build/linux-cuda-full/bin/audiocpp_cli"
MODEL = f"{R}/models/gguf/ACE-Step1.5-GGUF/turbo/" + os.environ.get("ACE_FILE", "ace-step-1.5-turbo-q6_k.gguf")
OUT = f"{R}/runs/l16-ace-q6k"; os.makedirs(OUT, exist_ok=True)
e = [x for x in json.load(open(f"{R}/bench/prompts.json"))["music"] if x["id"] == "m_song_short"][0]

peak = [0, 0, 0]; stop = [False]
def sample():
    while not stop[0]:
        try:
            g = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                               capture_output=True, text=True, timeout=5).stdout.split()
            for i in range(3): peak[i] = max(peak[i], int(g[i]))
        except Exception: pass
        time.sleep(0.2)

def wav_s(p):
    b = open(p, "rb").read(4096); i = b.find(b"fmt "); ch, sr = struct.unpack("<HI", b[i+10:i+16])
    bits = struct.unpack("<H", b[i+22:i+24])[0]; d = b.find(b"data")
    return round(struct.unpack("<I", b[d+4:d+8])[0] / (sr * ch * bits // 8), 2), sr, ch

res = []
for secs in [int(x) for x in os.environ.get("ACE_SECONDS", "10,30,60").split(",")]:
    peak[:] = [0, 0, 0]; stop[0] = False
    t = threading.Thread(target=sample, daemon=True); t.start()
    wav = f"{OUT}/song-{secs}s.wav"
    cmd = [CLI, "--task", "gen", "--family", "ace_step", "--model", MODEL, "--backend", "cuda",
           "--device", "0", "--task-route", "text2music", "--text", e["style"], "--lyrics", e["lyrics"],
           "--duration-seconds", str(secs), "--seed", "20260915", "--out", wav] + os.environ.get("ACE_EXTRA", "").split()
    t0 = time.time(); r = subprocess.run(cmd, capture_output=True, text=True); wall = time.time() - t0
    stop[0] = True; t.join(timeout=2)
    row = {"asked_s": secs, "ok": r.returncode == 0 and os.path.exists(wav), "wall_s": round(wall, 1),
           "peak_mib": list(peak), "model": os.path.basename(MODEL),
           "extra": os.environ.get("ACE_EXTRA", "")}
    if row["ok"]:
        d, sr, ch = wav_s(wav); row.update(audio_s=d, sample_rate=sr, channels=ch, rtf=round(wall / d, 3), file=wav)
    else:
        row["error"] = ((r.stderr or r.stdout).strip().splitlines() or ["?"])[-3:]
    res.append(row); print(json.dumps(row), flush=True)
json.dump(res, open(f"{OUT}/result-{int(time.time())}.json", "w"), indent=2)
