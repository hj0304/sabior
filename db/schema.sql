-- sabior 스키마 v1 (리그 중립)
-- 규칙
--   1. 모든 사실 테이블은 (league, season) 키와 known_at(그 행이 확정·인지된 날짜)을 가진다.
--   2. ID는 리그 접두를 붙인다: 'KBO_...', 'MLB_...'. 외부 ID 매핑은 player_external_ids 에.
--   3. 이닝은 아웃 수(ip_outs)로 저장한다. 표시용 변환은 stats.pitching.ip_display.
--   4. 금액은 DECIMAL + currency 로 저장한다. KBO는 KRW, MLB는 USD.
--   5. 외래키 제약은 두지 않는다 (ETL 재적재 편의). 정합성은 tests/ 와 backtest 누출 테스트로 검사한다.

CREATE TABLE IF NOT EXISTS leagues (
    league      VARCHAR PRIMARY KEY,          -- 'KBO', 'MLB'
    name        VARCHAR NOT NULL,
    country     VARCHAR
);

CREATE TABLE IF NOT EXISTS teams (
    team_id     VARCHAR PRIMARY KEY,          -- 'KBO_LG', 'MLB_NYA'
    league      VARCHAR NOT NULL,
    name        VARCHAR NOT NULL,
    short_name  VARCHAR,
    city        VARCHAR,
    founded     INTEGER,
    active      BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS parks (
    park_id     VARCHAR PRIMARY KEY,
    league      VARCHAR NOT NULL,
    name        VARCHAR NOT NULL,
    city        VARCHAR,
    opened      INTEGER,
    closed      INTEGER
);

CREATE TABLE IF NOT EXISTS players (
    player_id     VARCHAR PRIMARY KEY,
    league_origin VARCHAR,                    -- 최초 소속 리그
    name          VARCHAR NOT NULL,
    name_en       VARCHAR,
    birth_date    DATE,
    bats          VARCHAR,                    -- 'R','L','S'
    throws        VARCHAR,                    -- 'R','L'
    primary_pos   VARCHAR,
    debut_season  INTEGER,
    final_season  INTEGER
);

CREATE TABLE IF NOT EXISTS player_external_ids (
    player_id   VARCHAR NOT NULL,
    source      VARCHAR NOT NULL,             -- 'kbo', 'statiz', 'lahman', 'bbref', 'fangraphs'
    source_id   VARCHAR NOT NULL,
    PRIMARY KEY (player_id, source)
);

CREATE TABLE IF NOT EXISTS team_seasons (
    league          VARCHAR NOT NULL,
    season          INTEGER NOT NULL,
    team_id         VARCHAR NOT NULL,
    games           INTEGER,
    wins            INTEGER,
    losses          INTEGER,
    ties            INTEGER DEFAULT 0,
    runs_scored     INTEGER,
    runs_allowed    INTEGER,
    home_park_id    VARCHAR,
    final_rank      INTEGER,
    postseason      VARCHAR,                  -- 'KS_WIN','KS_LOSE','PO','SEMI_PO','WC', NULL
    known_at        DATE NOT NULL,
    PRIMARY KEY (league, season, team_id)
);

CREATE TABLE IF NOT EXISTS park_factors (
    league      VARCHAR NOT NULL,
    season      INTEGER NOT NULL,
    park_id     VARCHAR NOT NULL,
    pf_runs     DOUBLE,                       -- 1.00 = 중립
    pf_hr       DOUBLE,
    method      VARCHAR NOT NULL,             -- 'basic_1yr','regressed_3yr','statiz','fangraphs'
    known_at    DATE NOT NULL,
    PRIMARY KEY (league, season, park_id, method)
);

CREATE TABLE IF NOT EXISTS batting_seasons (
    league      VARCHAR NOT NULL,
    season      INTEGER NOT NULL,
    player_id   VARCHAR NOT NULL,
    team_id     VARCHAR NOT NULL,
    stint       INTEGER NOT NULL DEFAULT 1,   -- 시즌 내 소속 순번
    g           INTEGER,
    pa          INTEGER,
    ab          INTEGER,
    r           INTEGER,
    h           INTEGER,
    doubles     INTEGER,
    triples     INTEGER,
    hr          INTEGER,
    rbi         INTEGER,
    sb          INTEGER,
    cs          INTEGER,
    bb          INTEGER,
    ibb         INTEGER,
    so          INTEGER,
    hbp         INTEGER,
    sf          INTEGER,
    sh          INTEGER,
    gidp        INTEGER,
    known_at    DATE NOT NULL,
    PRIMARY KEY (league, season, player_id, team_id, stint)
);

CREATE TABLE IF NOT EXISTS pitching_seasons (
    league      VARCHAR NOT NULL,
    season      INTEGER NOT NULL,
    player_id   VARCHAR NOT NULL,
    team_id     VARCHAR NOT NULL,
    stint       INTEGER NOT NULL DEFAULT 1,
    g           INTEGER,
    gs          INTEGER,
    w           INTEGER,
    l           INTEGER,
    sv          INTEGER,
    hld         INTEGER,
    cg          INTEGER,
    sho         INTEGER,
    ip_outs     INTEGER,                      -- 이닝 x 3
    bf          INTEGER,                      -- 상대 타자 수
    h           INTEGER,
    r           INTEGER,
    er          INTEGER,
    hr          INTEGER,
    bb          INTEGER,
    ibb         INTEGER,
    so          INTEGER,
    hbp         INTEGER,
    wp          INTEGER,
    bk          INTEGER,
    known_at    DATE NOT NULL,
    PRIMARY KEY (league, season, player_id, team_id, stint)
);

CREATE TABLE IF NOT EXISTS fielding_seasons (
    league      VARCHAR NOT NULL,
    season      INTEGER NOT NULL,
    player_id   VARCHAR NOT NULL,
    team_id     VARCHAR NOT NULL,
    stint       INTEGER NOT NULL DEFAULT 1,
    pos         VARCHAR NOT NULL,
    g           INTEGER,
    gs          INTEGER,
    inn_outs    INTEGER,
    po          INTEGER,
    a           INTEGER,
    e           INTEGER,
    dp          INTEGER,
    pb          INTEGER,
    known_at    DATE NOT NULL,
    PRIMARY KEY (league, season, player_id, team_id, stint, pos)
);

-- 리그·연도별 상수. source 별로 여러 행이 있을 수 있다 (자체 계산 vs 공개값 대조).
CREATE TABLE IF NOT EXISTS league_constants (
    league          VARCHAR NOT NULL,
    season          INTEGER NOT NULL,
    source          VARCHAR NOT NULL,         -- 'computed', 'fangraphs_guts', 'statiz'
    w_bb            DOUBLE,
    w_hbp           DOUBLE,
    w_1b            DOUBLE,
    w_2b            DOUBLE,
    w_3b            DOUBLE,
    w_hr            DOUBLE,
    woba_scale      DOUBLE,
    lg_woba         DOUBLE,
    lg_r_per_pa     DOUBLE,
    lg_era          DOUBLE,
    c_fip           DOUBLE,
    runs_per_win    DOUBLE,
    known_at        DATE NOT NULL,
    PRIMARY KEY (league, season, source)
);

CREATE TABLE IF NOT EXISTS contracts (
    contract_id     VARCHAR PRIMARY KEY,
    league          VARCHAR NOT NULL,
    player_id       VARCHAR NOT NULL,
    team_id         VARCHAR NOT NULL,
    signed_date     DATE,
    season_start    INTEGER NOT NULL,         -- 계약 첫 시즌
    years           INTEGER,
    total_amount    DECIMAL(18,2),            -- 발표 총액
    guaranteed      DECIMAL(18,2),            -- 보장 총액
    options_amount  DECIMAL(18,2),            -- 옵션 최대치
    currency        VARCHAR NOT NULL,         -- 'KRW','USD'
    contract_type   VARCHAR NOT NULL,         -- 'FA','FA_RESIGN','EXTENSION','FOREIGN','ROOKIE','ANNUAL'
    fa_grade        VARCHAR,                  -- KBO FA 등급 'A','B','C' (해당 시)
    source_url      VARCHAR,
    known_at        DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS transactions (
    txn_id          VARCHAR PRIMARY KEY,
    league          VARCHAR NOT NULL,
    txn_date        DATE NOT NULL,
    txn_type        VARCHAR NOT NULL,         -- 'FA_SIGN','FA_COMP_PICK','FA_COMP_CASH','TRADE','RELEASE','SECOND_DRAFT','RETIRE'
    player_id       VARCHAR,
    from_team_id    VARCHAR,
    to_team_id      VARCHAR,
    related_txn_id  VARCHAR,                  -- 보상선수 행은 원 FA 계약 txn 을 가리킨다
    details         JSON,
    source_url      VARCHAR,
    known_at        DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    league          VARCHAR NOT NULL,
    draft_year      INTEGER NOT NULL,         -- 드래프트가 열린 연도 (KBO: 대상 시즌은 +1)
    round           INTEGER NOT NULL,
    pick            INTEGER NOT NULL,         -- 라운드 내 순번
    overall         INTEGER,
    team_id         VARCHAR NOT NULL,
    player_id       VARCHAR,                  -- 프로 등록 전이면 NULL
    player_name     VARCHAR NOT NULL,
    position        VARCHAR,
    school          VARCHAR,
    source_url      VARCHAR,
    known_at        DATE NOT NULL,
    PRIMARY KEY (league, draft_year, round, pick)
);

-- 규정 지식베이스. 규정 수치는 여기에만 존재한다.
CREATE TABLE IF NOT EXISTS rules (
    rule_id         VARCHAR PRIMARY KEY,
    league          VARCHAR NOT NULL,
    rule_type       VARCHAR NOT NULL,         -- 'FA_ELIGIBILITY','FA_GRADE','FA_COMPENSATION','SALARY_CAP','DRAFT','SECOND_DRAFT','FOREIGN_PLAYER'
    effective_from  INTEGER NOT NULL,         -- 적용 시작 시즌
    effective_to    INTEGER,                  -- NULL = 현행
    title           VARCHAR NOT NULL,
    summary         VARCHAR,
    body            VARCHAR,                  -- 원문 발췌
    params          JSON,                     -- 구조화 수치, 예: {"grade":"A","protected":20,"cash_pct":200}
    source_url      VARCHAR,
    known_at        DATE NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_log (
    run_id      VARCHAR PRIMARY KEY,
    source      VARCHAR NOT NULL,
    started_at  TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    rows        INTEGER,
    status      VARCHAR,                      -- 'running','ok','partial','failed'
    notes       VARCHAR
);

INSERT OR IGNORE INTO leagues VALUES ('KBO', 'KBO 리그', 'KR');
INSERT OR IGNORE INTO leagues VALUES ('MLB', 'Major League Baseball', 'US');
