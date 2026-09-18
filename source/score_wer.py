#!/usr/bin/env python3
"""Word error rate for generated speech. Standard library only.

    python3 bench/score_wer.py --run-dir runs/L0-kokoro_tts-q8_0-s_paragraph-...
    python3 bench/score_wer.py --all

Transcribes each generated file with a recogniser and compares against the
frozen prompt it came from.

WHAT THIS MEASURES, AND WHAT IT DOES NOT
----------------------------------------
It measures intelligibility: did the words arrive. It is completely deaf to
tone, pace, emotion and whether the voice is the right voice — a monotone that
pronounces everything correctly scores a perfect zero.

The recogniser's own error rate is the floor under every number here. A model
scored against a recogniser weak in its language will look broken when it is
not. The recogniser is recorded in every result for that reason.

THE NORMALISATION PROBLEM, STATED RATHER THAN HIDDEN
----------------------------------------------------
The frozen prompt s_normalize contains "2026-09-15" and "+44 20 7946 0958".
Speech contains words, and the recogniser writes words. Comparing those to the
digits in the prompt scores every model as catastrophically wrong, which says
nothing about any of them. Prompts whose reference text contains digits are
therefore reported SEPARATELY and by transcript, not by score.
"""
import argparse, glob, json, os, re, subprocess, sys, time

ROOT = os.environ.get("SELFHOSTAUDIO_ROOT",
                      os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ASR_MODEL = os.environ.get(
    "ASR_MODEL", "models/gguf/Qwen3-ASR-1.7B-GGUF/qwen3-asr-1.7b-q8_0.gguf")
ASR_FAMILY = "qwen3_asr"


def cli():
    build = os.environ.get("AUDIOCPP_BUILD", "linux-cuda-full")
    return os.path.join(ROOT, "engines", "audiocpp", "build", build, "bin", "audiocpp_cli")


def transcribe(wav):
    out = f"/tmp/asr-{os.getpid()}-{int(time.time()*1000)}.txt"
    r = subprocess.run([cli(), "--task", "asr", "--family", ASR_FAMILY,
                        "--model", os.path.join(ROOT, ASR_MODEL),
                        "--backend", "cuda", "--audio", wav,
                        "--text", "", "--text-out", out],
                       capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        return None
    t = open(out).read().strip()
    os.remove(out)
    return t


def words(s):
    """Lowercase, drop punctuation, split. Deliberately crude and symmetric:
    both sides get the identical treatment, so the comparison is fair even
    where the treatment is wrong."""
    s = s.lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9'\s]", " ", s)
    return s.split()


def wer(ref, hyp):
    """Levenshtein distance over words, plus the breakdown.

    Substitutions, deletions and insertions are weighted equally. That is the
    standard definition and it is a choice, not a law: a skipped word and a
    mispronounced one are not equally bad to a listener."""
    r, h = words(ref), words(hyp)
    n, m = len(r), len(h)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(d[i-1][j] + 1, d[i][j-1] + 1,
                          d[i-1][j-1] + (r[i-1] != h[j-1]))
    # walk back for the S/D/I split
    i, j, S = n, m, 0
    D = I = 0
    while i > 0 or j > 0:
        if i > 0 and j > 0 and d[i][j] == d[i-1][j-1] + (r[i-1] != h[j-1]):
            if r[i-1] != h[j-1]:
                S += 1
            i, j = i-1, j-1
        elif i > 0 and d[i][j] == d[i-1][j] + 1:
            D += 1; i -= 1
        else:
            I += 1; j -= 1
    return {"wer": round(d[n][m] / n, 4) if n else None,
            "S": S, "D": D, "I": I, "ref_words": n, "hyp_words": m}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--run-dir")
    a = ap.parse_args()

    prompts = json.load(open(os.path.join(ROOT, "bench/prompts.json")))
    text_of = {p["id"]: p.get("text", "") for p in prompts["speech"]}
    # a reference containing digits cannot be compared to transcribed words
    digits = {pid for pid, t in text_of.items() if re.search(r"\d", t)}

    results = [json.load(open(f))
               for f in glob.glob(os.path.join(ROOT, "bench/results/*.json"))]
    results = [r for r in results if r["prompt_id"] in text_of]
    results.sort(key=lambda r: (r["prompt_id"], r["family"], r["quant"]))

    scored, transcripts = [], []
    for r in results:
        wav = os.path.join(ROOT, "runs", r["run_id"], "out.wav")
        if not os.path.exists(wav):
            continue
        hyp = transcribe(wav)
        if hyp is None:
            print(f"  !! transcription failed: {r['run_id']}", file=sys.stderr)
            continue
        row = {"family": r["family"], "quant": r["quant"], "prompt": r["prompt_id"],
               "duration_s": r["audio"]["duration_s"], "transcript": hyp,
               "asr_model": ASR_MODEL}
        if r["prompt_id"] in digits:
            transcripts.append(row)
        else:
            row.update(wer(text_of[r["prompt_id"]], hyp))
            scored.append(row)

    print(f"{'prompt':<14}{'family':<12}{'quant':<7}{'audio':>7}{'WER':>8}"
          f"{'S':>4}{'D':>4}{'I':>4}{'ref':>5}{'hyp':>5}")
    print("-" * 74)
    for row in scored:
        print(f"{row['prompt']:<14}{row['family']:<12}{row['quant']:<7}"
              f"{row['duration_s']:>7.2f}{row['wer']:>8.3f}"
              f"{row['S']:>4}{row['D']:>4}{row['I']:>4}"
              f"{row['ref_words']:>5}{row['hyp_words']:>5}")

    if transcripts:
        print("\nREPORTED BY TRANSCRIPT, NOT BY SCORE")
        print("(reference text contains digits; speech contains words)")
        for row in transcripts:
            print(f"\n  {row['family']} {row['quant']} · {row['prompt']} · "
                  f"{row['duration_s']:.2f}s")
            print(f"    {row['transcript']}")

    out = os.path.join(ROOT, "bench", "raw", "wer.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"scored": scored, "transcripts": transcripts,
               "asr_model": ASR_MODEL,
               "date": time.strftime("%Y-%m-%dT%H:%M:%S")}, open(out, "w"), indent=2)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
