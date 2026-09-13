"""스키마와 as_of 매크로 테스트. 임시 DuckDB 에 스키마를 적용하고 누출 방지가 동작하는지 확인한다."""

import pytest

from db.init_db import init_db

EXPECTED_TABLES = {
    "leagues",
    "teams",
    "parks",
    "players",
    "player_external_ids",
    "team_seasons",
    "park_factors",
    "batting_seasons",
    "pitching_seasons",
    "fielding_seasons",
    "league_constants",
    "contracts",
    "transactions",
    "drafts",
    "rules",
    "ingest_log",
}


@pytest.fixture
def con(tmp_path):
    c = init_db(tmp_path / "t.duckdb")
    yield c
    c.close()


def test_tables_exist(con):
    tables = {r[0] for r in con.execute("SELECT table_name FROM duckdb_tables()").fetchall()}
    assert EXPECTED_TABLES <= tables


def test_leagues_seeded(con):
    leagues = {r[0] for r in con.execute("SELECT league FROM leagues").fetchall()}
    assert leagues == {"KBO", "MLB"}


def test_fact_tables_have_source_column(con):
    # v1.1 (ADR 0008): 소스가 바뀌어도 스키마는 유지되도록 사실 테이블마다 source 컬럼
    for t in [
        "players",
        "team_seasons",
        "batting_seasons",
        "pitching_seasons",
        "fielding_seasons",
        "contracts",
        "transactions",
        "drafts",
    ]:
        cols = {
            r[0]
            for r in con.execute(
                f"SELECT column_name FROM duckdb_columns() WHERE table_name = '{t}'"
            ).fetchall()
        }
        assert "source" in cols, t


def test_init_is_idempotent(tmp_path):
    p = tmp_path / "t.duckdb"
    init_db(p).close()
    init_db(p).close()


def test_as_of_hides_future_rows(con):
    con.execute(
        "INSERT INTO batting_seasons (league, season, player_id, team_id, stint, pa, known_at) VALUES "
        "('KBO', 2023, 'KBO_X', 'KBO_LG', 1, 500, DATE '2023-11-30'), "
        "('KBO', 2024, 'KBO_X', 'KBO_LG', 1, 520, DATE '2024-11-30')"
    )
    rows = con.execute("SELECT season FROM batting_as_of(DATE '2024-01-01')").fetchall()
    assert [r[0] for r in rows] == [2023]
    n = con.execute("SELECT count(*) FROM batting_as_of(season_cutoff(2024))").fetchone()[0]
    assert n == 2


def test_rules_as_of_respects_effective_range(con):
    con.execute(
        "INSERT INTO rules (rule_id, league, rule_type, effective_from, effective_to, title, known_at) VALUES "
        "('r1', 'KBO', 'FA_GRADE', 2020, NULL, '등급제', DATE '2019-11-01'), "
        "('r0', 'KBO', 'FA_GRADE', 2000, 2019, '등급제 이전', DATE '2000-01-01')"
    )

    def ids(d: str, season: int) -> set[str]:
        return {
            r[0]
            for r in con.execute(
                f"SELECT rule_id FROM rules_as_of(DATE '{d}', {season})"
            ).fetchall()
        }

    assert ids("2024-01-01", 2024) == {"r1"}
    assert ids("2024-01-01", 2018) == {"r0"}
    # 2019-10 시점에는 등급제가 아직 공표되지 않았다
    assert ids("2019-10-01", 2020) == set()
