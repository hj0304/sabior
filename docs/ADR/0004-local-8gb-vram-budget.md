# ADR 0004. 로컬 4070 Laptop 8GB 를 기준으로 4B 주력, 8B QLoRA 최종

- 날짜: 2026-09-04
- 상태: 확정 (W1 실측 후 수치 갱신)

## 맥락
학습 장비는 갤럭시북4 울트라의 RTX 4070 Laptop 한 장, VRAM 8GB (nvidia-smi 8188 MiB).

## 결정
반복 실험은 1.7B-4B QLoRA, 최종 후보는 7-8B QLoRA(seq 1024, batch 1, gradient checkpointing). 14B 이상은 로컬에서 시도하지 않는다. OOM 이나 8시간 초과 시 클라우드를 쓰되 P4 전체에서 1-2회로 제한한다. 파인튜닝 환경은 WSL2 Ubuntu 를 권장한다.

## 결과
`scripts/vram_probe.py` 로 W1 에 실측하고 `docs/vram_probe_log.md` 와 Notion 예산표를 갱신한다.

## 갱신 (2026-09-13)
- **학습과 VRAM 측정은 WSL2 Ubuntu 24.04 에서만 한다.** Windows 네이티브 CUDA 는 VRAM 초과 시 OOM 대신 시스템 RAM 으로 넘쳐(공유 GPU 메모리) 측정이 무효가 되고 속도가 수십 배 느려진다. 실측 로그의 `win-native` 행은 참고용으로만 남긴다.
- WSL2 에서 실제 가용 VRAM 은 약 6.9GB (Windows 가 약 1.1GB 선점). 예산표의 8GB 를 6.9GB 로 읽는다.
- 환경: `scripts/wsl_setup.sh` (uv, venv ~/.venvs/sabior, HF 캐시 공유) + `build-essential`. 실측은 `scripts/wsl_probe.sh`.
