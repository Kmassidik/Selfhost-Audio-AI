#!/usr/bin/env python3
"""Rebuild the comparison from bench/results/ and nothing else.

A hand-maintained table drifts from the measurements within a week. This reads
the JSON files only, so a number that was never measured cannot appear in it.

    python3 bench/table.py            # all results
    python3 bench/table.py --level L0
"""
import argparse, glob, json, os, statistics

ROOT = os.environ.get("SELFHOSTAUDIO_ROOT",
                      os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ap = argparse.ArgumentParser()
ap.add_argument("--level")
ap.add_argument("--family")
a = ap.parse_args()

rows = [json.load(open(f)) for f in glob.glob(os.path.join(ROOT, "bench/results/*.json"))]
if a.level:
    rows = [r for r in rows if r["level"] == a.level]
if a.family:
    rows = [r for r in rows if r["family"] == a.family]
if not rows:
    raise SystemExit("no results")
rows.sort(key=lambda r: (r["level"], r["family"], r["quant"], r["prompt_id"]))

hdr = ("level", "family", "quant", "prompt", "audio s", "wall s", "rtf", "peak c0", "rate", "ch")
w = (5, 11, 6, 14, 8, 7, 7, 8, 6, 3)
print("  ".join(h.rjust(x) if i >= 4 else h.ljust(x) for i, (h, x) in enumerate(zip(hdr, w))))
print("  ".join("-" * x for x in w))
for r in rows:
    au = r["audio"]
    vals = (r["level"], r["family"], r["quant"], r["prompt_id"],
            f"{au['duration_s']:.3f}", f"{r['wall_s']:.2f}",
            f"{r['rtf_wall']:.3f}" if r["rtf_wall"] else "-",
            str(r["peak_vram_mib"].get("0", 0)), str(au["sample_rate"]), str(au["channels"]))
    print("  ".join(v.rjust(x) if i >= 4 else v.ljust(x) for i, (v, x) in enumerate(zip(vals, w))))

# ── The two-length fit ────────────────────────────────────────────────
# The one-shot CLI reloads the model every run, so wall-clock RTF is dominated
# by a fixed cost that has nothing to do with the model. Two durations give the
# slope (real generation cost) and the intercept (that fixed cost).
print()
for key in sorted({(r["level"], r["family"], r["quant"]) for r in rows}):
    grp = [r for r in rows if (r["level"], r["family"], r["quant"]) == key]
    pts = sorted({(r["audio"]["duration_s"], r["wall_s"]) for r in grp})
    if len(pts) < 2:
        continue
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    den = sum((x - mx) ** 2 for x in xs)
    if den == 0:
        continue
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / den
    icept = my - slope * mx
    print(f"{'·'.join(key)}: fixed overhead {icept:6.2f} s  |  "
          f"generation RTF {slope:6.4f}  ({1/slope:5.1f}x real time)  "
          f"from {len(pts)} durations")
print("\nRTF above includes model load. The fit separates it. "
      "VRAM sampled at 5 Hz — a spike under 200 ms is missed.")
