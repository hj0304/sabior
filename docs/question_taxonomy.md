# 질문 분류 체계 v1

에이전트가 받을 질문을 유형별로 나누고, 각 유형이 필요로 하는 도구와 답변 형식을 정한다. 벤치마크 카테고리와 1:1 대응한다.

| 카테고리 | 하위 유형 | 예시 질문 | 필요 도구 | 답변 형식 | 채점 |
|---|---|---|---|---|---|
| `stat_lookup` | 단일 조회 | 2024년 OO의 wRC+는? | search_player, get_batting_season | 수치 + 리그 평균 대비 한 줄 해석 | numeric |
| | 순위 | 2024년 wRC+ 상위 5명 | get_league_leaders | 순위표 | topk |
| | 비교 | A와 B 중 누가 더 좋은 타자? | compare_players | 비교표 + 결론 먼저 | rubric |
| | 해석 | ERA와 FIP 괴리가 뜻하는 것 | get_pitching_season | 지표 설명 + 해당 선수 수치 | rubric |
| `player_projection` | 타자 | 내년 wRC+ 예측 | project_player | 점추정 + 50/80% 구간 + Marcel 비교 | interval |
| | 투수 | 내년 FIP 예측 | project_player | 동일 | interval |
| | 커리어 | 30대 중반에 어떻게 될까 | project_player (다년) | 연도별 구간 + 에이징 커브 설명 | rubric |
| `team_projection` | 승수 | 내년 몇 승? | project_team | 기대 승수 + 분포 | interval |
| | 순위/PS | 가을야구 확률 | project_team | 순위별 확률 | interval |
| | 가정 변경 | OO 영입하면 몇 승 늘어? | project_team(roster_assumptions) | 차이 + 가정 명시 | rubric |
| `fa_value` | 총액 | FA 총액 예상 | estimate_fa_value | 총액·연수 구간 + 비교 사례 3 | interval |
| `fa_destination` | 행선지 | 어느 팀으로? | estimate_fa_destinations, get_team_season | 상위 3팀 확률 + 근거 | topk |
| `compensation` | 보상선수 | 누가 유력? | simulate_compensation, get_rule | 후보 5명 + 근거 + 보상금 대안 | topk |
| `draft` | 상위 픽 | 1라운드 후보 | (W8 결정) | 후보군 + 신뢰도 낮음 표기 | topk |
| `rule_explain` | 규정 | FA 등급 기준 | get_rule | 요약 + 적용 연도 + 출처 | rubric |
| | 용어 | wRC+ 가 뭐야 | 없음 | 정의 + 해석 예시 | rubric |
| `hallucination_trap` | 미래 시즌 | 2027 홈런왕 | search/get -> not_found | 모른다 | refusal |
| | 없는 선수 | 홍길동 wRC+ | search_player -> not_found | 모른다 | refusal |
| | 없는 데이터 | 2015 배럴 비율 | 도구 없음 | 데이터 없음 | refusal |

## 공통 규칙
- 모든 답변은 결론을 먼저 말하고, 마지막 줄에 사용한 도구를 요약한다.
- 예측·FA 답변은 점추정 단독을 금지한다. 구간 또는 확률이 없으면 형식 위반으로 채점한다.
- `as_of` 이후의 데이터를 근거로 쓰면 누출로 채점한다.
