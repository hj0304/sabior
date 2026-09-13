# 베이스 모델 선정 실험 기록

ADR 0009 의 기준에 따라 후보를 이 장비(RTX 4070 Laptop 8GB)에서 직접 측정하고 W14 에 확정한다. 원자료는 docs/vram_probe_log.md (자동 기록), MLflow 실험 `sabior-sft`, evals/reports/.

## 후보

| 모델 | 크기 | 라이선스 | 구조 | 상태 |
|---|---|---|---|---|
| `Qwen/Qwen3-4B-Instruct-2507` | 4B | Apache 2.0 | Qwen3, 텍스트 전용, non-thinking | 후보 (4B 주력 가정) |
| `skt/A.X-4.0-Light` | 7B | Apache 2.0 | Qwen2.5 기반, 텍스트 전용 | 후보 |
| `Qwen/Qwen3-8B` | 8B | Apache 2.0 | Qwen3, 하이브리드 thinking | 후보 |
| `kakaocorp/kanana-1.5-8b-instruct-2505` | 8B | Apache 2.0 | Llama 계열 | 예비 |
| `google/gemma-4-E4B-it` | 유효 4.5B / 총 8B | Apache 2.0 | 멀티모달 | 대안 |

## 1. VRAM 적합 (W2)

측정: `scripts/vram_probe.py`, QLoRA nf4, rank 16, gradient checkpointing, 3 스텝. 환경 컬럼에 win-native / wsl2 구분.

| 모델 | seq | batch | peak VRAM (GB) | 스텝/초 | 상태 | 환경 | 일시 |
|---|---|---|---|---|---|---|---|
| Qwen3-4B-Instruct-2507 | 2048 | 2 | | | | | |
| A.X-4.0-Light | 1024 | 1 | | | | | |
| Qwen3-8B | 1024 | 1 | | | | | |

해석:

- **측정 환경은 WSL2 로 일원화한다 (2026-09-13).** Windows 네이티브 CUDA 는 VRAM 이 부족하면 OOM 을 내는 대신 시스템 RAM(공유 GPU 메모리)으로 넘친다. A.X 4.0 Light seq 1024·batch 1 이 "peak 24.4GB, ok" 로 기록되고 3 스텝에 약 90 분이 걸린 것이 그 증거다. 8GB 카드에서 24GB 는 불가능한 수치이므로 Windows 네이티브 행(`win-native`)은 전부 무효 처리한다. `scripts/vram_probe.py` 는 이제 peak 가 총 VRAM 의 97% 를 넘으면 `spill` 로 표기한다.
- WSL2 에서는 Windows 가 디스플레이 등으로 약 1.1GB 를 선점해 실제 가용 VRAM 은 약 6.9GB 다. 예산표는 이 값을 기준으로 다시 쓴다.
- Qwen3-4B nf4 가중치 + LoRA(rank 16) 적재 직후 할당량은 3.34GB (WSL2 측정). 나머지 약 3.5GB 가 활성값·옵티마이저·체크포인트 재계산에 쓸 수 있는 여유다.
- WSL2 첫 실행에서 "Failed to find C compiler" 오류 → `build-essential` 설치로 해결 (triton/torch 컴파일 경로가 gcc 를 요구). `scripts/wsl_setup.sh` 에 반영할 것.

## 2. 추론 속도 (W9)

측정: Ollama Q4_K_M, 4K 컨텍스트, 같은 프롬프트 3회 평균.

| 모델 | tok/s | 첫 토큰 지연(ms) | 메모리 | 비고 |
|---|---|---|---|---|

## 3. 툴콜 신뢰도 (W11, 조건 B: 베이스 + 도구)

| 모델 | JSON 스키마 준수율 | 도구 선택 정확도 | 환각 함정 거절률 | 비고 |
|---|---|---|---|---|

## 4. 파일럿 SFT (W13)

측정: 동일 데이터 500 샘플, 1 에폭, 동일 lr·rank. 벤치마크 v0 재실행.

| 모델 | 최종 train loss | eval loss | 벤치마크 정답률 (전/후) | 근거 추적성 (전/후) | 학습 시간 | 비고 |
|---|---|---|---|---|---|---|

## 5. 한국어 품질 (W13)

측정: 규정·용어 설명 문항 25개, judge 루브릭 1~5점 평균 + 수동 표본 5개.

| 모델 | judge 평균 | 수동 표본 평균 | 비고 |
|---|---|---|---|

## 결정 (W14)

- 4B 주력:
- 최종 후보:
- 이유:
