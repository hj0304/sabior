"""Lahman 적재 DB 가 있을 때만 도는 통합 테스트. 공개 수치(FanGraphs, 기억값)와 대조.

기대값 출처: FanGraphs 2024 선수 페이지의 wOBA, wRC+ (전사 시점의 기억값이라 재확인 대상).
파크팩터·리그(AL/NL) 분리가 아직 없으므로 wRC+ 허용 오차는 8, wOBA 는 0.006 으로 둔다.
"""

from pathlib import Path

import duckdb
import pytest

from stats.player import batting_line, pitching_line

DB = Path(__file__).resolve().parents[1] / "data" / "sabior.duckdb"

pytestmark = pytest.mark.skipif(not DB.exists(), reason="data/sabior.duckdb 없음 (Lahman 미적재)")


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(DB), read_only=True)
    has = c.execute(
        "SELECT count(*) FROM batting_seasons WHERE league='MLB' AND season=2024"
    ).fetchone()[0]
    if not has:
        pytest.skip("MLB 2024 행 없음")
    yield c
    c.close()


# (player_id, season, wOBA, wRC+) FanGraphs 공개값 기억 전사
CASES = [
    ("MLB_judgeaa01", 2024, 0.479, 218),  # Aaron Judge
    ("MLB_ohtansh01", 2024, 0.431, 181),  # Shohei Ohtani
    ("MLB_sotoju01", 2024, 0.421, 180),  # Juan Soto
]


@pytest.mark.parametrize("pid,season,exp_woba,exp_wrc_plus", CASES)
def test_batting_matches_public_values(con, pid, season, exp_woba, exp_wrc_plus):
    b = batting_line(con, pid, season)
    assert b is not None, pid
    assert b["woba"] == pytest.approx(exp_woba, abs=0.006)
    assert b["wrc_plus"] == pytest.approx(exp_wrc_plus, abs=8)


def test_pitching_line_basic(con):
    # Tarik Skubal 2024: ERA 2.39, 228 K, 192.0 IP (Lahman IPouts 576)
    p = pitching_line(con, "MLB_skubata01", 2024)
    assert p is not None
    assert p["ip"] == pytest.approx(192.0, abs=0.4)
    assert p["era"] == pytest.approx(2.39, abs=0.03)
    assert 2.0 < p["fip"] < 3.0


def test_leak_guard_as_of(con):
    # 2024 시즌 시작 전 시점에서는 2024 라인이 보이지 않아야 한다
    assert batting_line(con, "MLB_judgeaa01", 2024, as_of="2024-03-01") is None
