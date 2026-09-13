#!/usr/bin/env bash
# WSL2 Ubuntu 24.04 에서 sabior 파인튜닝 환경을 만든다. 사용자 sabior 로 실행.
#   wsl -d Ubuntu-24.04 -u sabior -- bash /mnt/c/Users/SSAFY/Desktop/sabior/scripts/wsl_setup.sh
# - 소스 트리는 Windows 체크아웃(/mnt/c/...)을 그대로 쓰고, venv 만 Linux 홈(~/.venvs/sabior)에 둔다.
# - HF 캐시는 Windows 쪽을 공유해 모델 가중치를 두 번 받지 않는다.
set -euo pipefail
REPO=/mnt/c/Users/SSAFY/Desktop/sabior
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/sabior"
export HF_HOME="/mnt/c/Users/SSAFY/.cache/huggingface"
export PYTHONIOENCODING=utf-8

echo "== apt =="
sudo apt-get update -qq
# build-essential: triton/torch 컴파일 경로가 C 컴파일러를 요구한다 (없으면 "Failed to find C compiler")
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git curl ca-certificates build-essential python3-dev >/dev/null

echo "== uv =="
if ! command -v uv >/dev/null 2>&1; then curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null 2>&1; fi
uv --version

if ! grep -q UV_PROJECT_ENVIRONMENT "$HOME/.bashrc"; then
cat >> "$HOME/.bashrc" <<'RC'
# sabior
export PATH="$HOME/.local/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/sabior"
export HF_HOME="/mnt/c/Users/SSAFY/.cache/huggingface"
export PYTHONIOENCODING=utf-8
alias sabior='cd /mnt/c/Users/SSAFY/Desktop/sabior'
RC
fi

echo "== uv sync (finetune) =="
cd "$REPO"
git config --global --add safe.directory "$REPO" || true
uv sync --group finetune 2>&1 | grep -vE "^\s*(Downloading|Downloaded|Prepared|Building|Built)" | tail -8

echo "== stack check =="
uv run --group finetune python -c "import torch, transformers, peft, bitsandbytes as bnb; print('torch', torch.__version__, 'cuda', torch.cuda.is_available(), torch.version.cuda, '| transformers', transformers.__version__, '| peft', peft.__version__, '| bnb', bnb.__version__); print('gpu', torch.cuda.get_device_name(0) if torch.cuda.is_available() else '-')"
echo "== done =="
