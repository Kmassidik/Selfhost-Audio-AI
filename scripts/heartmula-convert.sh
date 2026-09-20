#!/usr/bin/env bash
# Wait for the f16 download to finish, then make the two quantized packages this
# box can actually load. The published files are 11.2 GB (f16) and 7.66 GB
# (q8_0); neither fits a 7,840 MiB card, so the conversion is the experiment
# (experiment 18).
set -euo pipefail
ROOT=/root/Desktop/selfhostaudioai
DIR=$ROOT/models/gguf/HeartMuLa-GGUF
GGUF=$ROOT/engines/audiocpp/build/linux-cuda-full/bin/audiocpp_gguf
EXPECT=11204759552

while systemctl is-active --quiet dl-heartmula; do sleep 20; done
SIZE=$(stat -c%s "$DIR/heartmula-f16.gguf")
[ "$SIZE" = "$EXPECT" ] || { echo "download short: $SIZE of $EXPECT"; exit 1; }
echo "f16 complete: $SIZE bytes"

for T in q4_k q5_k; do
  OUT=$DIR/heartmula-$T.gguf
  if [ -f "$OUT" ]; then echo "$T already made"; continue; fi
  echo "=== $T ==="
  "$GGUF" --input "$DIR/heartmula-f16.gguf" --family heartmula \
      --type "$T" --output "$OUT" --overwrite 2>&1 | tail -20
  ls -l "$OUT"
done
