#!/usr/bin/env bash
# Experiment 14: the six recognisers on LibriSpeech test-other (the hard half),
# then three repeats of each on BOTH halves for error bars. Same N=30, sorted.
# Runs one model at a time, card 0 only (the studio's one-model rule).
set -u
R=/root/Desktop/selfhostaudioai; cd "$R"
G=models/gguf
MODELS=(
 "qwen3_asr|$G/Qwen3-ASR-1.7B-GGUF/qwen3-asr-1.7b-q8_0.gguf|Qwen3-ASR 1.7B"
 "canary_asr|$G/Canary-180M-Flash-GGUF/canary-180m-flash-q8_0.gguf|Canary 180M Flash"
 "parakeet_tdt|$G/Parakeet-TDT-0.6B-v3-GGUF/parakeet-tdt-0.6b-v3-q8_0.gguf|Parakeet-TDT 0.6B"
 "qwen3_asr|$G/Qwen3-ASR-0.6B-GGUF/qwen3-asr-0.6b-q8_0.gguf|Qwen3-ASR 0.6B"
 "nemotron_asr|$G/Nemotron-3.5-ASR-Streaming-0.6B-GGUF/nemotron-3.5-asr-streaming-0.6b-q8_0.gguf|Nemotron-3.5 0.6B"
 "moonshine_asr|$G/Moonshine-Streaming-GGUF/moonshine-streaming-tiny-q8_0.gguf|Moonshine tiny"
)
export CUDA_VISIBLE_DEVICES=0
for rep in 1 2 3; do
  for subset in test-other test-clean; do
    for m in "${MODELS[@]}"; do
      IFS='|' read -r fam path label <<<"$m"
      echo "=== r$rep $subset $label"
      python3 bench/score_asr.py --family "$fam" --model "$path" --label "$label" \
        --n 30 --subset "$subset" --repeat "$rep"
    done
  done
done
echo "=== ALL DONE"
