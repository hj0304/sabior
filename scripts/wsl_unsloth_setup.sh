#!/usr/bin/env bash
# WSL2 venv 에 unsloth 그룹을 추가 설치한다.
#   wsl -d Ubuntu-24.04 -u sabior -- bash /mnt/c/Users/SSAFY/Desktop/sabior/scripts/wsl_unsloth_setup.sh
set -euo pipefail
REPO=/mnt/c/Users/SSAFY/Desktop/sabior
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/sabior"
export HF_HOME="/mnt/c/Users/SSAFY/.cache/huggingface"
export PYTHONIOENCODING=utf-8
cd "$REPO"
echo "== uv sync --group finetune --group unsloth =="
uv sync --group finetune --group unsloth 2>&1 | grep -vE '^\s*(Downloading|Downloaded|Prepared|Building|Built)' | tail -15
echo "== check =="
uv run --group finetune --group unsloth python -c 'import unsloth, torch, transformers, peft; print("unsloth", unsloth.__version__, "| torch", torch.__version__, "| transformers", transformers.__version__, "| peft", peft.__version__)'
echo "== done =="
