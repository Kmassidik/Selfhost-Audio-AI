#!/usr/bin/env python3
"""Experiment 15: the three voices on the v2 (harder) prompts, scored by the ear.

For each voice x s2_* prompt: bench/run.py makes the audio (seed held), then
Qwen3-ASR 1.7B transcribes it and bench/score_wer.py scores it against the
prompt text. One model at a time, card 0. Standard library only.

    SELFHOSTAUDIO_ROOT=... python3 source/46_harder_speech.py
"""
import glob, json, os, re, subprocess, sys, time
R = os.environ.get("SELFHOSTAUDIO_ROOT", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(R, "bench"))
from score_wer import wer

G = "models/gguf"
VOICES = [  # (level, family, model, label, extra run.py args)
    ("L0", "kokoro_tts", f"{G}/Kokoro-82M-GGUF/kokoro-82m-q8_0.gguf", "Kokoro q8_0",
     ["--voice-id", "af_heart", "--language", "en-us"]),
    ("L1", "voxcpm2", f"{G}/VoxCPM2-GGUF/voxcpm2-q8_0.gguf", "VoxCPM2 q8_0",
     ["--extra", "--text-chunk-size 400"]),
    ("L2", "qwen3_tts", f"{G}/Qwen3-TTS-12Hz-1.7B-CustomVoice-GGUF/qwen3-tts-12hz-1.7b-customvoice-q8_0.gguf",
     "Qwen3-TTS q8_0", ["--extra", "--speaker Vivian"]),
]
EAR = f"{G}/Qwen3-ASR-1.7B-GGUF/qwen3-asr-1.7b-q8_0.gguf"
# How each prompt is scored. WER needs the spoken words and the written reference
# to be comparable: digits vs words are not, and a homograph is spelled the same
# whichever way it is said, so the ear cannot hear the difference. Both are kept
# as transcripts for a listener rather than given a misleading number.
SCORING = {"s2_homographs": "transcript (the ear writes the spelling, not the pronunciation)",
           "s2_numbers_hard": "transcript (digits in the reference, words in the audio)",
           "s2_tongue": "wer", "s2_long_list": "wer", "s2_codeswitch_id": "wer"}
SKIP = {("kokoro_tts", "s2_codeswitch_id"): "Kokoro has no Indonesian voice"}

CLI = os.path.join(R, "engines", "audiocpp", "build", "linux-cuda-full", "bin", "audiocpp_cli")
prompts = {p["id"]: p for p in json.load(open(os.path.join(R, "bench", "prompts.json")))["speech"]}
rows = []
for level, fam, model, label, extra in VOICES:
    for pid, how in SCORING.items():
        if (fam, pid) in SKIP:
            rows.append({"voice": label, "prompt": pid, "skipped": SKIP[(fam, pid)]}); continue
        r = subprocess.run([sys.executable, os.path.join(R, "bench", "run.py"), "--family", fam,
                            "--level", level, "--quant", "q8_0", "--model", model, "--prompt", pid,
                            "--label", label, "--seed", "20260915"] + extra,
                           capture_output=True, text=True, cwd=R)
        m = re.search(r'"run_id": "([^"]+)"', r.stdout)
        if r.returncode != 0 or not m:
            rows.append({"voice": label, "prompt": pid, "error": (r.stderr or r.stdout)[-300:]}); continue
        rid = m.group(1)
        res = json.load(open(os.path.join(R, "bench", "results", rid + ".json")))
        wav = os.path.join(R, "runs", rid, "out.wav"); w16 = wav[:-4] + "-16k.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-ar", "16000", "-ac", "1", w16])
        txt = w16 + ".txt"
        subprocess.run([CLI, "--task", "asr", "--family", "qwen3_asr", "--model", os.path.join(R, EAR),
                        "--backend", "cuda", "--audio", w16, "--text", "", "--text-out", txt],
                       capture_output=True, text=True)
        heard = open(txt).read().strip() if os.path.exists(txt) else ""
        row = {"voice": label, "prompt": pid, "run_id": rid, "duration_s": res["audio"]["duration_s"],
               "rtf_wall": res["rtf_wall"], "scoring": how, "heard": heard}
        if how == "wer":
            row.update(wer(prompts[pid]["text"], heard))
        rows.append(row)
        print(json.dumps({k: row.get(k) for k in ("voice", "prompt", "duration_s", "wer", "S", "D", "I")}), flush=True)
out = os.path.join(R, "bench", "results-ear", f"harder-v2-{int(time.time())}.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump({"date": time.strftime("%Y-%m-%dT%H:%M:%S"), "ear": "Qwen3-ASR 1.7B q8_0", "seed": 20260915,
           "rows": rows}, open(out, "w"), indent=2, ensure_ascii=False)
print("->", out)
