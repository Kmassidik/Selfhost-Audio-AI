#!/usr/bin/env bash
# The model manager stalled at a few MB in an hour; curl fetched HeartMuLa's
# 11 GB at about 10 MB/s. Same files, plainer tool.
set -euo pipefail
R=/root/Desktop/selfhostaudioai
DIR=$R/models/MiniMax-Music3-GGUF
BASE=https://huggingface.co/audio-cpp/MiniMax-Music3-GGUF/resolve/main
mkdir -p "$DIR/config" "$DIR/tokenizer"
for f in config.json \
         config/language_model.json config/rvq_depth_decoder.json \
         config/condition_encoder.json config/transformer.json config/vocoder.json \
         tokenizer/tokenizer.json tokenizer/tokenizer_config.json \
         language_model_q4_0.gguf rvq_depth_decoder_q8_0.gguf \
         condition_encoder.gguf transformer_q4_0.gguf vocoder.gguf; do
  echo "--- $f"
  curl --http1.1 -sL --retry 20 --retry-all-errors -C - -o "$DIR/$f" "$BASE/$f"
  ls -l "$DIR/$f"
done
du -sh "$DIR"
