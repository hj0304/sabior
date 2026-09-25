"""Marcel 예측과 백테스트 하네스 테스트. 단위 테스트는 항상, 통합 테스트는 Lahman DB 가 있을 때만."""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from models.projection import marcel, marcel_pitching
from stats.constants import LeagueConstants

C = LeagueConstants(
    league="TEST",
    season=2024,
    w_bb=0.69,
    w_hbp=0.72,
    w_1b=0.89,
    w_2b=1.27,
    w_3b=1.62,
    w_hr=2.10,
    woba_scale=1.25,
    lg_woba=0.320,
    lg_r_per_pa=0.12,
    lg_era=4.20,
    c_fip=3.10,
)


def test_age_adjustment():
    ages = pd.Series([24.0, 29.0, 35.0])
    adj = marcel.age_adjustment(ages)
    assert adj.tolist() == pytest.approx([0.03, 0.0, -0.018])


def test_woba_from_rates_matches_counts():
    # 타석 600: 1B 100, 2B 30, 3B 3, HR 25, uBB 50, IBB 5, HBP 5, SF 5, SH 0
    r = (
        pd.DataFrame(
            [
                {
                    "s1": 100,
                    "d": 30,
                    "t": 3,
                    "hr": 25,
                    "ubb": 50,
                    "ibb": 5,
                    "hbp": 5,
                    "sf": 5,
                    "sh": 0,
                }
            ]
        )
        / 600
    )
    num = 0.69 * 50 + 0.72 * 5 + 0.89 * 100 + 1.27 * 30 + 1.62 * 3 + 2.10 * 25
    assert marcel.woba_from_rates(r, C).iloc[0] == pytest.approx(num / (600 - 5 - 0))


def test_fip_from_rates():
    # 180 이닝 = 540 아웃: HR 20, BB 40, HBP 5, SO 180
    r = pd.DataFrame([{"hr": 20, "bb": 40, "hbp": 5, "so": 180}]) / 540
    assert marcel_pitching.fip_from_rates(r, 3.10).iloc[0] == pytest.approx(35 / 180 + 3.10)


DB = Path(__file__).resolve().parents[1] / "data" / "sabior.duckdb"
needs_db = pytest.mark.skipif(not DB.exists(), reason="Lahman DB 없음")


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect(str(DB), read_only=True)
    yield c
    c.close()


@needs_db
def test_marcel_history_has_no_future_rows(con):
    # 2024 예측에 쓰는 입력은 2021~2023 뿐이어야 한다
    h = marcel._history(con, "MLB", 2024)
    assert h["season"].max() == 2023 and h["season"].min() == 2021
    hp = marcel_pitching._history(con, "MLB", 2024)
    assert hp["season"].max() == 2023


@needs_db
def test_marcel_projection_sane(con):
    p = marcel.project(con, "MLB", 2024).set_index("player_id")
    judge = p.loc["MLB_judgeaa01"]
    # 평균 회귀 때문에 실제(.479)보다 낮고 리그 평균보다는 한참 높아야 한다
    assert 0.37 < judge["proj_woba"] < 0.46
    assert 400 < judge["proj_pa"] < 700


@needs_db
def test_marcel_beats_baselines(con):
    from backtest.harness import run, run_pitching, summarize

    s = summarize(run(con, "MLB", 2023, 2024))
    assert s.loc["marcel", "rmse_w"] < s.loc["league_avg", "rmse_w"] < s.loc["last_year", "rmse_w"]
    sp = summarize(run_pitching(con, "MLB", 2023, 2024))
    assert sp.loc["marcel", "rmse_w"] < sp.loc["league_avg", "rmse_w"]


@needs_db
def test_intervals_monotone_and_calibrated(con):
    from models.projection.intervals import calibrate, coverage

    q = calibrate(con, "MLB", 2025)
    cols = ["p10", "p25", "p50", "p75", "p90"]
    assert (q[cols].diff(axis=1).iloc[:, 1:] >= 0).all().all()
    cov = coverage(con, "MLB", 2024, 2025)
    assert 0.70 < cov["cover80"].mean() < 0.90
