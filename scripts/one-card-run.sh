#!/usr/bin/env bash
# Run one generation on one card while sampling the card's memory, so the peak
# is measured rather than guessed. Usage: one-card-run.sh <tag> <cmd...>
set -uo pipefail
TAG=$1; shift
OUTDIR=/root/Desktop/selfhostaudioai/runs/one-card
mkdir -p "$OUTDIR"
( while true; do nvidia-smi --query-gpu=index,memory.used --format=csv,noheader,nounits; sleep 0.5; done ) > "$OUTDIR/$TAG.mem" &
SAMPLER=$!
START=$(date +%s.%N)
"$@" > "$OUTDIR/$TAG.log" 2>&1
RC=$?
END=$(date +%s.%N)
kill $SAMPLER 2>/dev/null
echo "exit=$RC  wall=$(echo "$END - $START" | bc)s"
awk -F", " '{if ($1==0 && $2+0>p0) p0=$2; if ($1==1 && $2+0>p1) p1=$2; if ($1==2 && $2+0>p2) p2=$2}
     END{printf "peak MiB: card0=%d card1=%d card2=%d\n", p0, p1, p2}' "$OUTDIR/$TAG.mem"
tail -25 "$OUTDIR/$TAG.log"
