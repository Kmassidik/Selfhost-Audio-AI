#!/bin/bash
# Set up MiniMax-Music3 through MiniMax's own diffusers pipeline, which can
# stream the 8B language model from system RAM layer by layer — the feature
# audio.cpp lacks (ch.37).
#
# The package set MIRRORS the one the first sibling project proved on this box
# (torch 2.11 + cu128, diffusers dev with ModularPipeline and
# apply_group_offloading). It is a separate environment on purpose: installing
# into the sibling's venv could break its working state, and its runtime is
# marked do-not-touch.
set -euo pipefail
R="${SELFHOSTAUDIO_ROOT:?}"
E=$R/engines/minimax-py
W=$R/models/hf/MiniMax-Music3
export PATH=/root/.local/bin:$PATH
mkdir -p $E $W
cd $E
[ -d .venv ] || uv venv --python 3.12 -q
echo "=== torch (cu128, same as the sibling) ==="
uv pip install -q --python .venv/bin/python "torch==2.11.0" --index-url https://download.pytorch.org/whl/cu128
echo "=== diffusers dev + friends ==="
uv pip install -q --python .venv/bin/python "git+https://github.com/huggingface/diffusers" \
    transformers accelerate huggingface_hub safetensors soundfile sentencepiece
.venv/bin/python -c "import torch,diffusers,transformers;print('torch',torch.__version__,'cuda',torch.cuda.is_available(),'| diffusers',diffusers.__version__,'| transformers',transformers.__version__)"
.venv/bin/python -c "from diffusers import ModularPipeline, ComponentsManager; from diffusers.hooks import apply_group_offloading; print('ModularPipeline, ComponentsManager, apply_group_offloading: ok')"
# NOTE: the snapshot_download below STALLED on this box (0-byte partial files,
# ~1 KB/s). Weights were fetched with 40b_minimax_music3_fetch.sh instead —
# curl --http1.1, selfhostgenai tune #4, "beat HF throttling".
echo "=== weights (53 GB) ==="
.venv/bin/python - <<PY
from huggingface_hub import snapshot_download
p = snapshot_download("MiniMaxAI/MiniMax-Music3", local_dir="$W", max_workers=4)
print("weights at", p)
PY
du -sh $W
echo "=== SETUP DONE ==="
