#!/usr/bin/env bash
# WSL2 에서 VRAM 실측을 돌린다. 사용:
#   wsl -d Ubuntu-24.04 -u sabior -- bash /mnt/c/Users/SSAFY/Desktop/sabior/scripts/wsl_probe.sh <model> <seq> <batch> [--ladder]
set -euo pipefail
REPO=/mnt/c/Users/SSAFY/Desktop/sabior
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/sabior"
export HF_HOME="/mnt/c/Users/SSAFY/.cache/huggingface"
export PYTHONIOENCODING=utf-8 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
MODEL="$1"; SEQ="$2"; BATCH="$3"; shift 3
cd "$REPO"
uv run --group finetune python scripts/vram_probe.py --model "$MODEL" --seq-len "$SEQ" --batch "$BATCH" --env wsl2 "$@" 2>&1 \
  | grep -vE 'it/s|UserWarning|FutureWarning|warnings.warn' | tail -40
