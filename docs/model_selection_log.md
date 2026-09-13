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

**유효 측정 (2026-09-13 21:12~21:25, WSL2, 하드 캡 6.6GB, 순정 HF QLoRA nf4, rank 16, gradient checkpointing, bf16 임베딩·lm_head, train 모드)**

| 모델 | 적재 (GB) | 성공한 최대 설정 | peak (GB) | 스텝/초 | 실패한 설정 | 판정 (순정 HF 기준) |
|---|---|---|---|---|---|---|
| Qwen3-4B-Instruct-2507 | 2.59 | seq 1536 × batch 1 | 6.18 | 0.28 (약 430 tok/s) | 2048×1 OOM (5.88 에서 캡 초과), 2048×2 OOM | 통과. 2048 은 로짓(151,936 vocab × fp32) 때문에 실패 |
| A.X-4.0-Light (7B) | 4.65 | seq 768 × batch 1 | 6.15 | 0.35 (약 270 tok/s) | 1024×1 OOM | 조건부. 기준(1024×1)에 미달이나 여유가 0.2GB 수준 → Unsloth 재측정 후 판정 |
| Qwen3-8B | 5.82 | 없음 | - | - | 1024, 768, 512 × 1 모두 OOM | 탈락 후보. 가중치만 5.82GB 라 활성값 여유 0.8GB. lm_head 양자화·8bit 옵티마이저·Unsloth 로 512~768 은 가능할 수 있으나 실용성 낮음 |

무효 측정 (참고): `win-native` 행 전부, 그리고 21:11 이전 `wsl2` 행 (eval 모드로 체크포인팅 미적용 + sysmem 스필). docs/vram_probe_log.md 에 그대로 남겨 둔다.

해석:

- **병목은 활성값이 아니라 로짓이다.** Qwen 계열은 vocab 이 151,936 이라 seq 2048 에서 fp32 로짓만 1.24GB, 그 grad 까지 2.5GB 가 순간적으로 든다. Unsloth·Liger 의 chunked/fused cross-entropy 는 이걸 피하므로 Unsloth 에서는 4B seq 2048, A.X seq 1024 가 들어갈 가능성이 높다. → W2 남은 작업: Unsloth 설치 후 `--unsloth` 모드 재측정.
- **학습 시간 어림 (4B, seq 1536, 순정 HF):** 430 tok/s → SFT 3천 샘플 × 1,500 토큰 = 4.5M 토큰 ≈ 2.9 시간/에폭. A.X 는 약 4.6 시간/에폭. 야간 1회 학습으로 감당 가능.
- **Qwen3-8B 는 이 장비의 한계 밖.** 후보에서 내리고, 8B 급 비교 상대는 A.X 4.0 Light 로 한다. 예비인 Kanana 1.5 8B 도 같은 이유로 제외.

- **측정 환경은 WSL2 로 일원화한다 (2026-09-13).** Windows 네이티브 CUDA 는 VRAM 이 부족하면 OOM 을 내는 대신 시스템 RAM(공유 GPU 메모리)으로 넘친다. A.X 4.0 Light seq 1024·batch 1 이 "peak 24.4GB, ok" 로 기록되고 3 스텝에 약 90 분이 걸린 것이 그 증거다. 8GB 카드에서 24GB 는 불가능한 수치이므로 Windows 네이티브 행(`win-native`)은 전부 무효 처리한다. `scripts/vram_probe.py` 는 이제 peak 가 총 VRAM 의 97% 를 넘으면 `spill` 로 표기한다.
- WSL2 에서는 Windows 가 디스플레이 등으로 약 1.1GB 를 선점해 실제 가용 VRAM 은 약 6.9GB 다. 예산표는 이 값을 기준으로 다시 쓴다.
- Qwen3-4B nf4 가중치 + LoRA(rank 16) 적재 직후 할당량은 3.34GB (WSL2 측정). 나머지 약 3.5GB 가 활성값·옵티마이저·체크포인트 재계산에 쓸 수 있는 여유다.
- WSL2 첫 실행에서 "Failed to find C compiler" 오류 → `build-essential` 설치로 해결 (triton/torch 컴파일 경로가 gcc 를 요구). `scripts/wsl_setup.sh` 에 반영.
- **하드 캡 도입.** 드라이버의 sysmem fallback 을 막기 위해 `torch.cuda.set_per_process_memory_fraction` 으로 (가용 6.9GB − 0.3GB) = 6.6GB 캡을 건다. 초과 시 진짜 OOM.
- **fp32 업캐스트 제거 효과.** `prepare_model_for_kbit_training` 을 쓰지 않고 bf16 을 유지하자 적재량이 Qwen3-4B 3.34 → 2.59GB, A.X 7B 6.03 → 4.65GB, Qwen3-8B 8.15 → 5.82GB 로 줄었다 (LoRA rank 16 포함).
- **eval 모드 함정 (2026-09-13 21:11 측정).** 세 모델 모두 seq 512 에서도 OOM 이었고 활성값이 토큰당 약 6.6MB 로 나왔다. 원인은 `from_pretrained` 가 eval 모드로 로드하고 transformers 가 `self.training` 일 때만 gradient checkpointing 을 적용하기 때문. `model.train()` 한 줄이 빠져 체크포인팅이 무효였다. Trainer 를 쓰면 자동이지만 직접 루프를 짤 때 반드시 기억할 것. 수정 후 재측정.

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
