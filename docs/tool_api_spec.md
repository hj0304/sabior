# 도구 API 명세 v0 (W2 초안, W9 구현)

에이전트가 호출하는 도구는 전부 FastAPI 엔드포인트다 (웹서비스 로드맵 경계 1). 에이전트의 함수호출 레지스트리(`agent/tools/registry.py`)는 이 엔드포인트를 감싼 얇은 클라이언트가 되고, 웹 프론트는 같은 엔드포인트를 직접 부른다.

## 공통 규칙

- 기본 경로 `/v1`. 모든 조회 엔드포인트는 `as_of` (YYYY-MM-DD, 기본 오늘) 쿼리 파라미터를 받고, DB 조회는 `*_as_of(as_of)` 매크로만 쓴다.
- 응답은 항상 다음 봉투를 쓴다.

```json
{
  "ok": true,
  "as_of": "2025-02-01",
  "data": {},
  "sources": [{"table": "batting_seasons", "source": "yagoonara", "known_at": "2024-11-30"}],
  "constants": {"league": "KBO", "season": 2024, "source": "computed"},
  "warnings": ["PA 는 SF 역산 근사값"]
}
```

- 없는 선수·시즌·데이터는 200 이 아니라 **404 + `{"ok": false, "error": "not_found", "detail": "..."}`** 로 답한다. 에이전트는 이 응답을 "모른다"로 바꿔 말해야 한다 (환각 함정 대응).
- 수치는 반올림하지 않은 값과 표시용 문자열을 함께 준다 (`"woba": 0.3974, "woba_str": ".397"`).
- 예측·추정 응답은 점추정과 함께 `p10, p25, p50, p75, p90` 분위와 `model_version`, `baseline` 을 반드시 포함한다.
- 모든 호출은 `tool_calls` 로그 테이블에 남긴다 (endpoint, params, elapsed_ms, as_of, session_id).

## 엔드포인트

| 메서드·경로 | 역할 | 주요 파라미터 | 응답 data | 단계 |
|---|---|---|---|---|
| `GET /v1/players/search` | 선수 검색 | `q`(이름), `league`, `season?` | `[{player_id, name, birth_date, primary_pos, teams:[...]}]` | W9 |
| `GET /v1/players/{player_id}` | 선수 프로필 | | `{player_id, name, birth_date, bats, throws, debut_season, external_ids}` | W9 |
| `GET /v1/players/{player_id}/batting` | 시즌별 타격 | `season?`, `stats?`(쉼표) | `[{season, team_id, pa, ab, ..., woba, wraa, wrc_plus, iso, babip}]` | W9 |
| `GET /v1/players/{player_id}/pitching` | 시즌별 투구 | `season?` | `[{season, team_id, ip, ip_outs, bf, so, bb, ..., era, fip, whip, k_pct, bb_pct}]` | W9 |
| `GET /v1/leaders` | 리더보드 | `stat`, `season`, `league`, `player_type`, `min_pa|min_ip`, `top_n` | `[{rank, player_id, name, team_id, value, qualified}]` | W9 |
| `POST /v1/compare` | 선수 비교 | body `{player_ids, stats, seasons}` | `{rows: [...], table_markdown}` | W9 |
| `GET /v1/teams/{team_id}/seasons/{season}` | 팀 시즌 | | `{wins, losses, ties, runs_scored, runs_allowed, pythagorean_wpct, final_rank, postseason}` | W9 |
| `GET /v1/league/constants` | 리그 상수 | `league`, `season` | `{w_bb, w_hbp, w_1b, w_2b, w_3b, w_hr, woba_scale, lg_woba, lg_r_per_pa, lg_era, c_fip, source}` | W9 |
| `GET /v1/projections/players/{player_id}` | 선수 예측 | `target_season`, `stat?` | `{stat, point, p10..p90, baseline_marcel, reliability, model_version}` | W9 |
| `GET /v1/projections/teams/{team_id}` | 팀 예측 | `season`, `assumptions?` | `{exp_wins, wins_p10..p90, rank_probs:{1:..,10:..}, postseason_prob, assumptions}` | W9 |
| `GET /v1/fa/class` | FA 자격자 목록 | `market_year` | `[{player_id, name, grade, age, war_3y, prev_team}]` | W10 |
| `GET /v1/fa/value/{player_id}` | FA 금액 추정 | `market_year` | `{total_p10..p90, years_p10..p90, comparables:[3], n_train, model_version}` | W10 |
| `GET /v1/fa/destinations/{player_id}` | 행선지 확률 | `market_year` | `{probs:[{team_id, p, reasons:[...]}], stay_prob}` | W10 |
| `POST /v1/compensation/simulate` | 보상선수 시뮬 | body `{signing_team_id, fa_grade, market_year}` | `{protected_est:[20], candidates:[{player_id, score, reasons}], cash_alternative}` | W10 |
| `GET /v1/rules` | 규정 조회 | `rule_type`, `season`, `league` | `[{rule_id, title, summary, params, effective_from, effective_to, source_url}]` | W9 |
| `GET /v1/news/search` | 계약·이적 기사 검색 | `q`, `date_from`, `date_to` | `[{title, date, snippet, url}]` | W10 |
| `GET /v1/health` | 상태 | | `{db_ok, last_ingest, model_versions}` | W9 |

## 배치 산출물 테이블 (경계 2, W6~W8 에 생성)

예측 엔드포인트는 실시간 계산이 아니라 야간 배치가 채운 테이블을 읽는다.

| 테이블 | 키 | 주요 컬럼 |
|---|---|---|
| `projections` | league, target_season, player_id, stat, model_version, as_of | point, p10, p25, p50, p75, p90, baseline, reliability, created_at |
| `team_sim_results` | league, season, team_id, model_version, as_of | exp_wins, wins_p10..p90, rank_probs(JSON), postseason_prob, assumptions(JSON) |
| `fa_estimates` | league, market_year, player_id, model_version, as_of | total_p10..p90, years_p10..p90, comparables(JSON), dest_probs(JSON), stay_prob |
| `tool_calls` | call_id | session_id, endpoint, params(JSON), status, elapsed_ms, as_of, created_at |

## 에이전트 쪽 매핑

레지스트리의 도구 이름은 엔드포인트와 1:1 이다. `search_player → /players/search`, `get_batting_season → /players/{id}/batting`, `get_league_leaders → /leaders`, `project_player → /projections/players/{id}`, `estimate_fa_value → /fa/value/{id}`, `get_rule → /rules` 등. 도구 설명 문구와 JSON 스키마는 엔드포인트의 pydantic 모델에서 자동 생성한다 (한 곳에서만 정의).

## 미결

- 인증: 비공개 베타까지는 없음. 공개 시 API 키 + 일일 한도.
- 캐시: 조회 엔드포인트는 `as_of` 포함 키로 응답 캐시 (배치 갱신 시 무효화).
- 페이지네이션: `/leaders`, `/news/search` 는 `limit`, `offset`.
