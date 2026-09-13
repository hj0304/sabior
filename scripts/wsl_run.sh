#!/usr/bin/env bash
# WSL2 venv 에서 임의 명령을 실행한다 (finetune + unsloth 그룹 고정, 환경변수 세팅).
#   wsl -d Ubuntu-24.04 -u sabior -- bash /mnt/c/Users/SSAFY/Desktop/sabior/scripts/wsl_run.sh python scripts/prequantize.py --model ... --out ...
set -euo pipefail
REPO=/mnt/c/Users/SSAFY/Desktop/sabior
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/sabior"
export HF_HOME="/mnt/c/Users/SSAFY/.cache/huggingface"
export PYTHONIOENCODING=utf-8 HF_HUB_DISABLE_PROGRESS_BARS=1 TOKENIZERS_PARALLELISM=false
cd "$REPO"
exec uv run --group finetune --group unsloth "$@"
