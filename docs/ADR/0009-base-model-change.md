# ADR 0009. 베이스 모델을 2025년 세대 텍스트 전용 모델로 변경

- 날짜: 2026-09-13
- 상태: **제안** (사용자 확인 대기)

## 맥락
09-07 조사에서 Qwen3.5-4B / 9B 를 1순위로 두었다. 09-13 재조사에서 Unsloth 공식 문서가 Qwen3.5 계열에 QLoRA(4bit) 학습을 권장하지 않으며 bf16 LoRA 기준 4B 에 10GB, 9B 에 22GB 가 필요하다고 명시한 것을 확인했다. 8GB 장비에서는 4B 도 불가능하다. Qwen3.5 는 비전-언어 통합 구조이기도 하다.

## 결정 (제안)
- 반복 실험: `Qwen/Qwen3-4B-Instruct-2507` (텍스트 전용, non-thinking, 툴콜, Apache 2.0)
- 최종 후보: `skt/A.X-4.0-Light` (7B, 한국어 특화, Apache 2.0) 와 `Qwen/Qwen3-8B` (범용, Apache 2.0) 를 W14 에 정면 비교
- 예비: `kakaocorp/kanana-1.5-8b-instruct-2505`
- 제외: Qwen3.5 전 계열, EXAONE 3.5 (비상업 라이선스, 웹서비스 확장과 충돌), HyperCLOVA X SEED 8B Omni (any-to-any 멀티모달), MoE 30B 급

## 결과
- 라이선스가 모두 Apache 2.0 이라 웹서비스 확장에 걸림돌이 없다.
- W2 VRAM 실측 대상이 위 세 모델로 바뀐다. `finetune/configs/` 와 README 의 예시 명령을 갱신했다.
- 이유가 사라지면(예: Unsloth 가 Qwen3.5 QLoRA 를 지원) 재검토한다.
