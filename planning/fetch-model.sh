#!/bin/bash
# Resumable model fetch. curl -C - picks up where it left off, so a dropped
# connection costs the last chunk and not the whole file.
#
#   ./fetch-model.sh <owner>/<repo> <path/inside/repo.gguf> [subdir]
#
# The sibling's version of this script hardcoded its box path, which is the
# exact mistake selfhostgenai flagged in its own README. This one does not.
set -euo pipefail
ROOT="${SELFHOSTAUDIO_ROOT:-/root/Desktop/selfhostaudioai}"
repo="$1"; file="$2"; sub="${3:-gguf}"
dest="$ROOT/models/$sub"
mkdir -p "$dest"
out="$(basename "$file")"
cd "$dest"
setsid nohup curl -fL --http1.1 --retry 8 --retry-delay 5 -C - -o "$out" \
  "https://huggingface.co/$repo/resolve/main/$file" \
  </dev/null > "/tmp/fetch-$out.log" 2>&1 &
disown
echo "fetching $out -> $dest"
echo "  tail -f /tmp/fetch-$out.log"
