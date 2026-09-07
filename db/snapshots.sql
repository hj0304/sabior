-- as_of 스냅샷 매크로.
-- 백테스트·평가 코드는 원 테이블 대신 이 매크로를 통해서만 데이터를 본다.
-- d 이후에 알려진(known_at > d) 행은 보이지 않으므로 미래 정보 누출을 구조적으로 막는다.

CREATE OR REPLACE MACRO batting_as_of(d) AS TABLE
    SELECT * FROM batting_seasons WHERE known_at <= d::DATE;

CREATE OR REPLACE MACRO pitching_as_of(d) AS TABLE
    SELECT * FROM pitching_seasons WHERE known_at <= d::DATE;

CREATE OR REPLACE MACRO fielding_as_of(d) AS TABLE
    SELECT * FROM fielding_seasons WHERE known_at <= d::DATE;

CREATE OR REPLACE MACRO team_seasons_as_of(d) AS TABLE
    SELECT * FROM team_seasons WHERE known_at <= d::DATE;

CREATE OR REPLACE MACRO league_constants_as_of(d) AS TABLE
    SELECT * FROM league_constants WHERE known_at <= d::DATE;

CREATE OR REPLACE MACRO park_factors_as_of(d) AS TABLE
    SELECT * FROM park_factors WHERE known_at <= d::DATE;

CREATE OR REPLACE MACRO contracts_as_of(d) AS TABLE
    SELECT * FROM contracts WHERE known_at <= d::DATE;

CREATE OR REPLACE MACRO transactions_as_of(d) AS TABLE
    SELECT * FROM transactions WHERE known_at <= d::DATE;

CREATE OR REPLACE MACRO drafts_as_of(d) AS TABLE
    SELECT * FROM drafts WHERE known_at <= d::DATE;

-- 규정은 "그 시점에 알려져 있고, 대상 시즌에 유효한" 행만 보인다.
CREATE OR REPLACE MACRO rules_as_of(d, season) AS TABLE
    SELECT * FROM rules
    WHERE known_at <= d::DATE
      AND effective_from <= season
      AND (effective_to IS NULL OR effective_to >= season);

-- 백테스트 컷오프 관례: season 시즌의 기록까지 보이는 시점.
-- 시즌 기록의 known_at 은 ETL 에서 그 시즌의 정규시즌 종료일(또는 보수적으로 11-30)로 넣는다.
CREATE OR REPLACE MACRO season_cutoff(season) AS make_date(season, 12, 31);
