# 베이스 모델 후보 (2026-09-13 재조사)

## 결론

지난 조사(09-07)에서 1순위로 두었던 **Qwen3.5 계열은 이 장비에서 부적합**하다. Unsloth 공식 문서가 "Qwen3.5 는 MoE·dense 를 가리지 않고 QLoRA(4bit) 학습을 권장하지 않는다(양자화 오차가 평소보다 크다)"고 명시하고, bf16 LoRA 기준 VRAM 요구량을 4B 10GB, 9B 22GB 로 적는다. 8GB 노트북에서는 4B 조차 불가능하다. 또 Qwen3.5 는 비전-언어 통합 모델이라 첫 파인튜닝 경험으로는 구조가 복잡하다.

따라서 **2025년 세대의 텍스트 전용 모델**로 돌아간다. 이 세대는 QLoRA 4bit 학습이 검증되어 있고 Unsloth 가 4B·8B 4bit 변형을 직접 배포한다.

| 역할 | 모델 | 이유 |
|---|---|---|
| 반복 실험 (4B) | `Qwen/Qwen3-4B-Instruct-2507` | 텍스트 전용, non-thinking 전용(think 블록 없음 → SFT 데이터 단순), 툴콜 지원, BFCL-v3 61.9, Apache 2.0, 컨텍스트 262K |
| 최종 후보 1 (7B, 한국어 특화) | `skt/A.X-4.0-Light` | Qwen2.5 기반 7B, Apache 2.0. KMMLU 64.15, **Ko-MT-Bench 79.50**(Qwen3-8B 64.06), Ko-IFEval 72.99. hermes 툴콜 파서 지원. 컨텍스트 16K(충분) |
| 최종 후보 2 (8B, 범용·추론) | `Qwen/Qwen3-8B` | KMMLU 63.53, LiveBench 50.20(추론 강함), 하이브리드 thinking, 툴콜. Apache 2.0 |
| 예비 | `kakaocorp/kanana-1.5-8b-instruct-2505` | Apache 2.0, Ko-MT-Bench 76.30, FunctionChatBench 58. KMMLU 48.28 은 약점 |

**W14 ablation 을 "A.X 4.0 Light vs Qwen3-8B" 정면 비교로 잡는다.** 한국어 특화 모델과 범용 모델 중 어느 쪽이 도구 호출 에이전트 SFT 에 더 잘 맞는지가 이 프로젝트의 핵심 학습 포인트가 된다.

## 비교표 (모델 카드 수치, A.X 4.0 Light 카드의 비교표 인용)

| 지표 | A.X 4.0 Light 7B | Qwen3-8B | Kanana-1.5 8B | EXAONE-3.5 7.8B |
|---|---|---|---|---|
| KMMLU | 64.15 | 63.53 | 48.28 | 53.76 |
| KMMLU-pro | 50.28 | 50.71 | 37.63 | 40.11 |
| CLIcK (한국 문화·언어) | 68.05 | 62.71 | 61.30 | 64.30 |
| Ko-MT-Bench | 79.50 | 64.06 | 76.30 | 81.06 |
| Ko-IFEval | 72.99 | 73.39 | 69.96 | 65.01 |
| MMLU | 75.43 | 82.89 | 68.82 | 72.20 |
| LiveBench | 37.10 | 50.20 | 29.40 | 40.20 |
| 라이선스 | Apache 2.0 | Apache 2.0 | Apache 2.0 | 비상업 연구용 |

## 제외한 후보와 이유

| 모델 | 이유 |
|---|---|
| Qwen3.5-4B / 9B (2026-03) | QLoRA 비권장, bf16 LoRA 4B = 10GB. VLM 구조 |
| Qwen3.6-35B-A3B, Qwen3.8-27B | 크기 초과 |
| Gemma 4 E4B (2026-04, Apache 2.0) | 유효 4.5B 지만 총 8B, 텍스트·이미지·오디오 입력 통합 구조. 툴콜은 지원. 대안으로 남기되 첫 실험에는 부적합 |
| EXAONE 3.5 7.8B | Ko-MT-Bench 최고지만 비상업 라이선스 → 웹서비스 확장과 충돌. EXAONE 4.x/K-EXAONE 은 33B 이상만 공개 |
| HyperCLOVA X SEED 8B Omni (2025-12) | any-to-any 멀티모달, safetensors 11B, 자체 라이선스. 텍스트 SFT 베이스로는 무겁다 |
| Kanana-2 30B-A3B (2026-01) | MoE 총 30B → 4bit 로도 약 16GB |
| Mi:dm 2.0 (KT, MIT) | Base 11.5B 는 초과, Mini 2.3B 는 너무 작음 |
| A.X K1 / K2 (SKT, 2026) | 519B / 688B |

## 실측 계획 (W2)

```bash
uv run --group finetune python scripts/vram_probe.py --model Qwen/Qwen3-4B-Instruct-2507 --seq-len 2048 --batch 2
uv run --group finetune python scripts/vram_probe.py --model skt/A.X-4.0-Light --seq-len 1024 --batch 1
uv run --group finetune python scripts/vram_probe.py --model Qwen/Qwen3-8B --seq-len 1024 --batch 1
```

## 출처
- Unsloth Qwen3.5 가이드: https://unsloth.ai/docs/models/qwen3.5/fine-tune
- Unsloth Qwen3 가이드: https://unsloth.ai/docs/models/tutorials/qwen3-how-to-run-and-fine-tune
- Qwen3-4B-Instruct-2507: https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507
- A.X 4.0 Light: https://huggingface.co/skt/A.X-4.0-Light
- Qwen3.5-4B / 9B: https://huggingface.co/Qwen/Qwen3.5-4B , https://huggingface.co/Qwen/Qwen3.5-9B
- Kanana 1.5 8B: https://huggingface.co/kakaocorp/kanana-1.5-8b-instruct-2505
- Gemma 4 E4B: https://huggingface.co/google/gemma-4-E4B-it
- HyperCLOVA X SEED 8B Omni: https://huggingface.co/naver-hyperclovax/HyperCLOVAX-SEED-Omni-8B
