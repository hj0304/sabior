# 벤치마크 문항 (questions.jsonl)

한 줄에 한 문항. 목표 200문항, W2 에 v0 100문항.

## 필드

| 필드 | 설명 |
|---|---|
| `id` | `Q` + 3자리 |
| `category` | `stat_lookup` `player_projection` `team_projection` `fa_value` `fa_destination` `compensation` `draft` `rule_explain` `hallucination_trap` |
| `question` | 사용자가 실제로 물을 법한 한국어 문장 |
| `as_of` | 답변 시점 (YYYY-MM-DD). 이 날짜 이후 데이터는 보이지 않아야 한다 |
| `answer_type` | `number` `interval` `ranking` `probabilities` `text` `refusal` |
| `expected` | 정답. number 는 값, interval 은 실제값, ranking/probabilities 는 정답 항목, refusal 은 null |
| `tolerance` | number 채점 허용오차 (절대값 또는 `"rel:0.02"`) |
| `grader` | `numeric` `interval` `topk` `rubric` `refusal` |
| `tags` | 자유 태그 (선수 id, 시즌 등). SFT 오염 제거에 사용 |
| `status` | `draft` `verified` `template` |
| `notes` | 채점 시 주의점 |

## 카테고리별 목표 문항 수

| 카테고리 | 목표 | v0 |
|---|---|---|
| stat_lookup | 40 | 20 |
| player_projection | 30 | 15 |
| team_projection | 20 | 10 |
| fa_value | 20 | 10 |
| fa_destination | 15 | 8 |
| compensation | 15 | 7 |
| draft | 10 | 5 |
| rule_explain | 25 | 12 |
| hallucination_trap | 25 | 13 |

## 규칙
- `expected` 는 DB 에서 도구로 뽑은 값으로 채운다. 기억으로 적지 않는다.
- 예측 문항의 `as_of` 는 대상 시즌 시작 전이어야 한다 (예: 2025 시즌 예측이면 2025-03-01 이전).
- `status: verified` 는 expected 를 두 번 이상 확인한 문항에만 붙인다.
- `template` 문항은 `{player}`, `{team}` 자리를 실제 값으로 채워 여러 문항으로 인스턴스화한다.
