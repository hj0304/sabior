"""개발 환경 점검: Python, GPU, torch/CUDA, WSL 배포판, Ollama.

사용: uv run python scripts/check_env.py
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys


def run(cmd: list[str], encoding: str | None = None) -> str:
    try:
        out = subprocess.run(cmd, capture_output=True, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        return f"(실행 실패: {e})"
    raw = out.stdout or out.stderr
    if encoding:
        return raw.decode(encoding, errors="replace").strip()
    for enc in ("utf-8", "utf-16", "cp949"):
        try:
            return raw.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace").strip()


def main() -> None:
    # Windows 콘솔이 cp949 여도 한국어가 깨지지 않게
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(f"Python      : {sys.version.split()[0]}  ({sys.executable})")
    print(f"OS          : {platform.system()} {platform.release()}")
    gpu = run(
        [
            "nvidia-smi",
            "--query-gpu=name,memory.total,memory.used,driver_version",
            "--format=csv,noheader",
        ]
    )
    print(f"nvidia-smi  : {gpu}")
    try:
        import torch  # type: ignore

        cuda = torch.cuda.is_available()
        dev = torch.cuda.get_device_name(0) if cuda else "-"
        print(f"torch       : {torch.__version__}  cuda={cuda}  device={dev}")
        if cuda:
            free, total = torch.cuda.mem_get_info()
            print(f"VRAM        : free {free / 2**30:.2f} GB / total {total / 2**30:.2f} GB")
    except ImportError:
        print("torch       : 미설치 (uv sync --group finetune)")
    if platform.system() == "Windows":
        print("WSL 배포판  :")
        for line in run(["wsl", "-l", "-v"], encoding="utf-16").splitlines():
            if line.strip():
                print(f"    {line.rstrip()}")
    print(f"ollama      : {run(['ollama', '--version']) if shutil.which('ollama') else '미설치'}")
    print(f"uv          : {run(['uv', '--version']) if shutil.which('uv') else '미설치'}")


if __name__ == "__main__":
    main()
