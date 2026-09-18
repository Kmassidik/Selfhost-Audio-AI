#!/usr/bin/env bash
# PULL code from the box into git.
#
# The box is authoritative for code: it is edited there, it runs there, and it
# needs the GPU, the models and the build that only exist there. The Mac holds a
# copy so it can be committed and pushed — nothing more.
#
# The WRITING goes the other way: knowledge-base/ and planning/ are authored
# here and are never pulled from the box. Only source/ moves.
#
#   ./sync.sh          pull box source/ -> here, then show what changed
#   ./sync.sh --dry    show what would change, touch nothing
#   ./sync.sh --push   PUSH here -> box (rare: only to restore after data loss)
set -euo pipefail

BOX="${SELFHOSTAUDIO_BOX:-root@10.0.0.20}"            # LAN; Tailscale root@100.122.45.32 when off-site
SRC="${SELFHOSTAUDIO_ROOT:-/root/Desktop/selfhostaudioai}"
SSH="ssh -o ConnectTimeout=15"
# Resource forks reached the box once in a sibling project and turned up inside
# agent prompts. They are excluded on the way out as well as the way in.
EXCL=(--exclude '__pycache__' --exclude '*.pyc' --exclude '.DS_Store' --exclude '._*')

case "${1:-}" in
  --push)
    echo "  PUSHING  here -> $BOX:$SRC/source"
    echo "  This overwrites the authoritative copy. Ctrl-C within 5s to abort."
    sleep 5
    rsync -az --delete "${EXCL[@]}" -e "$SSH" source/ "$BOX:$SRC/source/"
    ;;
  --dry)
    echo "  (dry run) $BOX:$SRC/source -> source/"
    rsync -az --dry-run --delete "${EXCL[@]}" -e "$SSH" "$BOX:$SRC/source/" source/
    ;;
  *)
    echo "  pulling  $BOX:$SRC/source -> source/"
    rsync -az --delete "${EXCL[@]}" -e "$SSH" "$BOX:$SRC/source/" source/
    echo
    ls -1 source/
    echo
    git status --short source/ | sed 's/^/  /' || true
    ;;
esac
