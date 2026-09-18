#!/usr/bin/env python3
"""ch.34 — the three projects on this machine, joined.

  sibling 2 (selfhostllm)   Llama-3-8B, its own llama-server  -> writes lyrics
  this project              YuE2-3B                           -> sings them
  this project              Canary 180M                       -> checks the words survived

Sibling 1 (selfhostgenai, the video model) is NOT run: its runtime is marked
do-not-touch in both siblings' notes, and 217 GB of someone else's working
state is not something to start casually. Stated in the chapter, not hidden.

The sibling's files are used READ-ONLY: its binary is executed and its weights
are read. Nothing in /root/Desktop/selfhostllm is written.
"""
import json, os, re, struct, subprocess, time, urllib.request, sys
ROOT = os.environ.get("SELFHOSTAUDIO_ROOT", "/root/Desktop/selfhostaudioai")
SIB = "/root/Desktop/selfhostllm"
LLAMA = f"{SIB}/engines/llamacpp/build/bin/llama-server"
LLM = f"{SIB}/models/gguf/Meta-Llama-3-8B-Instruct-Q4_K_M.gguf"
CLI = f"{ROOT}/engines/audiocpp/build/linux-cuda-full/bin/audiocpp_cli"
OUT = f"{ROOT}/runs/l10-siblings"; os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, f"{ROOT}/bench")
from score_wer import wer

def log(m): print(m, flush=True)
T = {}

# ── 1 · sibling 2 writes the words ────────────────────────────────────
env = dict(os.environ, CUDA_VISIBLE_DEVICES="1")
srv = subprocess.Popen([LLAMA, "-m", LLM, "-ngl", "99", "-c", "4096",
                        "--host", "127.0.0.1", "--port", "8096", "--seed", "20260915"],
                       env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
t0 = time.time()
ready = False
for _ in range(120):   # readiness is a real completion, not /health — sibling 2's own lesson
    try:
        r = urllib.request.Request("http://127.0.0.1:8096/v1/chat/completions",
            data=json.dumps({"messages":[{"role":"user","content":"ok"}],"max_tokens":1}).encode(),
            headers={"Content-Type":"application/json"})
        urllib.request.urlopen(r, timeout=5).read(); ready = True; break
    except Exception:
        time.sleep(1)
T["llm_load"] = time.time() - t0
if not ready:
    srv.kill(); sys.exit("llama-server never became ready")

prompt = ("Write short song lyrics about three second-hand graphics cards in a tower under a desk "
          "that finally learned to sing. Use exactly this structure and nothing else: a line "
          "'[Verse]', four lines, a line '[Chorus]', four lines. Plain English, no title, no notes.")
body = {"messages":[{"role":"user","content":prompt}], "temperature":0, "seed":20260915,
        "max_tokens":220}
t0 = time.time()
r = urllib.request.Request("http://127.0.0.1:8096/v1/chat/completions",
    data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
raw = json.loads(urllib.request.urlopen(r, timeout=120).read())["choices"][0]["message"]["content"]
T["llm_write"] = time.time() - t0
srv.terminate(); srv.wait(timeout=20)       # never leave a sibling's engine resident

# keep only the tagged block; models add chatter
m = re.search(r"\[Verse\].*", raw, re.S)
lyrics = (m.group(0) if m else raw).strip()
lyrics = "\n".join(l for l in lyrics.splitlines() if l.strip())
open(f"{OUT}/lyrics.txt","w").write(lyrics + "\n")
log("=== LYRICS, written by sibling 2's Llama-3-8B ===")
log(lyrics)

# ── 2 · this project sings them ───────────────────────────────────────
song = f"{OUT}/song.wav"
t0 = time.time()
p = subprocess.run([CLI,"--task","gen","--family","yue2","--model",f"{ROOT}/models/gguf/Yue2-3B-GGUF",
    "--backend","cuda","--device","0","--threads","8","--lyrics",lyrics,
    "--request-option","style=English, indie pop, bright acoustic guitar, soft drums, warm lead vocal",
    "--request-option","cot=melody","--request-option","num_inference_steps=8",
    "--session-option","yue2.model_gguf=yue2-3b-q4_0.gguf",
    "--session-option","yue2.vae_gguf=yue2-vae-f16.gguf",
    "--seed","20260915","--out",song], capture_output=True, text=True)
T["sing"] = time.time() - t0
if p.returncode != 0 or not os.path.exists(song):
    sys.exit("YuE2 failed: " + (p.stderr or p.stdout)[-300:])
b = open(song,"rb").read(); d = b.find(b"data"); n = struct.unpack("<I", b[d+4:d+8])[0]
i = b.find(b"fmt "); ch, sr = struct.unpack("<HI", b[i+10:i+16]); dur = n/(sr*ch*2)

# ── 3 · the ear checks the words survived ─────────────────────────────
wav16 = f"{OUT}/song16k.wav"
subprocess.run(["ffmpeg","-y","-loglevel","error","-i",song,"-ar","16000","-ac","1",wav16])
t0 = time.time()
q = subprocess.run([CLI,"--task","asr","--family","canary_asr",
    "--model",f"{ROOT}/models/gguf/Canary-180M-Flash-GGUF/canary-180m-flash-q8_0.gguf",
    "--backend","cuda","--device","2","--audio",wav16,"--text","","--text-out",f"{OUT}/heard.txt"],
    capture_output=True, text=True)
T["listen"] = time.time() - t0
heard = open(f"{OUT}/heard.txt").read().strip() if os.path.exists(f"{OUT}/heard.txt") else ""
sung_words = re.sub(r"\[[^\]]+\]", " ", lyrics)
w = wer(sung_words, heard)

log("\n=== HEARD, by Canary, from the sung audio ===")
log(heard or "(nothing)")
log("\n=== THE PIPELINE ===")
log(f"  sibling 2 LLM load    {T['llm_load']:7.1f} s   card 1")
log(f"  sibling 2 writes      {T['llm_write']:7.1f} s")
log(f"  YuE2 sings            {T['sing']:7.1f} s   card 0   -> {dur:.1f} s of {sr} Hz {ch}ch music")
log(f"  Canary listens        {T['listen']:7.1f} s   card 2")
log(f"  end to end            {sum(T.values()):7.1f} s")
log(f"\n  sung-lyric word error rate {w['wer']:.3f}  (S {w['S']} D {w['D']} I {w['I']} of {w['ref_words']} words)")
json.dump({"lyrics":lyrics,"heard":heard,"timing":T,"song_s":dur,"wer":w},
          open(f"{OUT}/result.json","w"), indent=2)
