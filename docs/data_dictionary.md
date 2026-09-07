# 데이터 사전 v1

스키마 원본은 `db/schema.sql`. 여기에는 컬럼 의미와 적재 규칙을 적는다. 테이블이 바뀌면 이 문서도 같은 커밋에서 바꾼다.

## 공통 규칙
- `league`: 'KBO' | 'MLB'. `season`: 정규시즌 연도.
- `known_at`: 이 행을 알 수 있게 된 날짜. 시즌 기록은 정규시즌 종료일(불명확하면 11-30), 계약은 발표일, 규정은 공표일. `*_as_of(d)` 매크로는 `known_at <= d` 만 보여준다.
- ID 접두: `KBO_`, `MLB_`. 외부 ID 는 `player_external_ids`.
- 이닝은 `ip_outs`(아웃 수). 표시 변환은 `stats.pitching.ip_display`.
- 금액은 `DECIMAL(18,2)` + `currency`. KBO 는 KRW 원 단위 정수, MLB 는 USD.

## 테이블

### players / player_external_ids
선수 마스터. `bats`/`throws` 는 'R','L','S'. `primary_pos` 는 커리어 기준 주 포지션(ETL 후처리로 채움).

### batting_seasons / pitching_seasons / fielding_seasons
시즌·팀·stint 단위 카운팅 스탯. 파생 지표(wOBA, FIP 등)는 저장하지 않고 `stats/` 로 계산한다.
- `pa`: 소스에 없으면 AB+BB+HBP+SF+SH 로 계산해 넣는다.
- `hld`(홀드): MLB Lahman 에는 없어 NULL.

### team_seasons
`postseason`: KBO 는 'KS_WIN','KS_LOSE','PO','SEMI_PO','WC', MLB 는 'WS_WIN','WS_LOSE','PO'. 진출 못 하면 NULL. `home_park_id` 는 Lahman 적재 시 구장 이름 문자열이 들어가며 W3 에 `parks` 로 정규화한다.

### league_constants
`source` 별로 여러 행 가능. 'computed' 는 자체 계산, 'fangraphs_guts' 는 공개값 대조용, 'statiz' 는 KBO 공개값 대조용. 도구는 'computed' 를 우선 읽는다.

### park_factors
`method` 별 여러 행 가능. 1.00 이 중립. 초기에는 'basic_1yr'(홈/원정 득점 비율 단순식)만.

### contracts
- `total_amount`: 발표 총액(옵션 포함). `guaranteed`: 보장액. `options_amount`: 옵션 최대치.
- `contract_type`: 'FA'(타 팀 이적), 'FA_RESIGN'(원소속 잔류), 'EXTENSION'(비FA 다년), 'FOREIGN', 'ROOKIE', 'ANNUAL'.
- `fa_grade`: KBO 등급제 이후 'A','B','C'. 이전 계약은 NULL.

### transactions
`txn_type`: 'FA_SIGN','FA_COMP_PICK'(보상선수 지명),'FA_COMP_CASH'(보상금만),'TRADE','RELEASE','SECOND_DRAFT','RETIRE'. 보상선수 행은 `related_txn_id` 로 원 FA 계약 행을 가리킨다. 구조화 세부는 `details` JSON.

### drafts
`draft_year` 는 드래프트가 열린 해. KBO 신인드래프트는 다음 시즌 대상이므로 2026년 9월 드래프트는 `draft_year=2026`. `player_id` 는 프로 등록 후 매핑.

### rules
규정 수치의 유일한 저장소. `params` JSON 예: `{"grade":"A","protected":20,"cash_pct_with_player":200,"cash_pct_only":300}` (예시 형식이며 실제 수치는 규약 원문으로 확인). `effective_to` NULL 은 현행. 반드시 `source_url` 과 함께 넣는다.

### ingest_log
ETL 실행 기록. 실패도 남긴다.
