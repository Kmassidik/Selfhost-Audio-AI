#!/usr/bin/env bash
# The smallest published MiniMax language-model component is q4_0 at 6.01 GB,
# which leaves too little of a 7,840 MiB card for the AR stage. Fetch the bf16
# component (17.17 GB) so we can quantize it further ourselves.
set -euo pipefail
D=/root/Desktop/selfhostaudioai/models/MiniMax-Music3-GGUF
curl --http1.1 -sL --retry 20 --retry-all-errors -C - \
  -o "$D/language_model_bf16.gguf" \
  https://huggingface.co/audio-cpp/MiniMax-Music3-GGUF/resolve/main/language_model_bf16.gguf
ls -l "$D/language_model_bf16.gguf"
