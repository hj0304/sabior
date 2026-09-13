# ADR 0009. 베이스 모델은 실험 수치로 선정한다

- 날짜: 2026-09-13
- 상태: **확정** (선정 방식). 모델 자체는 W14 에 수치로 확정

## 맥락
09-07 조사에서 Qwen3.5-4B / 9B 를 1순위로 두었으나, Unsloth 공식 문서가 Qwen3.5 계열에 QLoRA(4bit) 학습을 권장하지 않으며 bf16 LoRA 기준 4B 에 10GB, 9B 에 22GB 가 필요하다고 명시한 것을 확인했다. 8GB 장비에서는 불가능하다. 벤치마크 순위만으로 고르면 이런 실수를 반복하므로, 이 장비에서 직접 측정한 수치로 고른다.

## 결정
1. **후보군**은 2025년 세대 텍스트 전용, 상용 가능 라이선스(Apache 2.0 / MIT) 모델로 한정한다.
   - 4B 급: `Qwen/Qwen3-4B-Instruct-2507`
   - 7~8B 급: `skt/A.X-4.0-Light`, `Qwen/Qwen3-8B`, 예비 `kakaocorp/kanana-1.5-8b-instruct-2505`
   - 대안: `google/gemma-4-E4B-it` (Apache 2.0, 총 8B, 멀티모달 구조) 는 위 후보가 모두 실패할 때만
2. **선정 기준과 측정 시점** (docs/model_selection_log.md 에 기록)

| 기준 | 측정 | 시점 | 탈락 조건 |
|---|---|---|---|
| VRAM 적합 | `scripts/vram_probe.py` peak VRAM, 스텝/초 | W2 | OOM 또는 seq 1024·batch 1 도 불가 |
| 추론 속도 | Ollama Q4_K_M tok/s, 4K 컨텍스트 | W9 | 10 tok/s 미만 |
| 툴콜 신뢰도 | 벤치마크 A/B 조건(베이스+도구)에서 JSON 스키마 준수율 | W11 | 80% 미만 |
| 파일럿 SFT | 500 샘플·1 에폭 학습 후 loss 곡선, 벤치마크 변화 | W13 | 개선 없음 또는 학습 불안정 |
| 한국어 품질 | judge 루브릭 점수(규정·용어 설명 문항) | W13 | 하위 |

3. **최종 확정은 W14** (SFT 2차) 에 두 개 후보의 정면 비교 결과로 한다. 그 전까지는 "주력 4B = Qwen3-4B-Instruct-2507" 가정으로 파이프라인을 만든다.
4. 제외: Qwen3.5 전 계열(QLoRA 부적합), EXAONE 3.5(비상업 라이선스), HyperCLOVA X SEED 8B Omni(any-to-any 멀티모달), MoE 30B 급, 14B 이상.

## 결과
- W2 VRAM 실측 대상: Qwen3-4B-Instruct-2507, A.X-4.0-Light, Qwen3-8B. 결과는 docs/vram_probe_log.md 에 자동 기록, 해석은 docs/model_selection_log.md 에.
- `finetune/configs/` 에 후보별 설정을 둔다. 모델을 바꿔도 데이터·평가는 동일하게 유지해 비교가 공정하도록 한다.
- 이유가 사라지면(예: Unsloth 가 Qwen3.5 QLoRA 를 지원) 후보군을 재검토한다.
