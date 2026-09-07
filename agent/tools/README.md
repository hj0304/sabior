# 도구 레이어 계획 (W2 초안, W9 구현)

LLM 이 호출하는 함수 집합. 입력은 pydantic 모델, 출력은 JSON 직렬화 가능한 dict. 모든 호출은 레지스트리에 로그로 남는다.

| 도구 | 입력 | 출력 | 데이터 소스 | 단계 |
|---|---|---|---|---|
| `search_player` | name, league? | 후보 선수 목록 (id, 이름, 생년, 포지션) | players | W9 |
| `get_batting_season` | player_id, season | 카운팅 스탯 + wOBA, wRC+ | batting_as_of, league_constants | W9 |
| `get_pitching_season` | player_id, season | 카운팅 스탯 + ERA, FIP, K% | pitching_as_of | W9 |
| `get_league_leaders` | stat, season, min_pa/min_ip, top_n | 순위표 | batting/pitching_as_of | W9 |
| `compare_players` | player_ids, stats, seasons | 비교표 | 위와 동일 | W9 |
| `get_team_season` | team_id, season | 승패, 득실점, 피타고리안 승률 | team_seasons_as_of | W9 |
| `project_player` | player_id, target_season | 점추정 + 50/80% 구간, Marcel 비교값 | models.projection | W9 |
| `project_team` | team_id, season, roster_assumptions? | 기대 승수, 순위 확률, PS 확률 | models.team_sim | W9 |
| `estimate_fa_value` | player_id, market_year | 총액·연수 구간, 비교 사례 | models.fa_value | W10 |
| `estimate_fa_destinations` | player_id, market_year | 팀별 확률 상위 3 + 근거 | models.fa_dest | W10 |
| `simulate_compensation` | signing_team_id, fa_grade, market_year | 유력 후보 5명 + 근거 | models.compensation | W10 |
| `list_fa_class` | market_year | 해당 시장 FA 자격자 목록 | contracts, transactions | W10 |
| `get_rule` | rule_type, season | 규정 요약 + params + 출처 | rules_as_of | W9 |
| `search_news` | query, date_from, date_to | 관련 기사 스니펫 | RAG 인덱스 | W10 |

## 규칙
- 모든 도구는 `as_of` 를 선택 인자로 받는다 (기본: 오늘). 평가·백테스트는 반드시 명시한다.
- 숫자를 반환할 때 단위와 계산에 쓴 상수의 source 를 함께 반환한다.
- 없는 선수·시즌은 빈 결과가 아니라 명시적 `not_found` 를 반환한다 (환각 함정 대응).
