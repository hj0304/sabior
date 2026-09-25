"""팀 시뮬레이터 테스트. 합성 데이터 단위 테스트 + Lahman DB 통합 테스트."""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from models.team_sim.sim import postseason_slots, simulate


def test_postseason_slots():
    assert postseason_slots("KBO", 2024) == 5
    assert postseason_slots("MLB", 2024) == 6
    assert postseason_slots("MLB", 2019) == 5
    assert postseason_slots("MLB", 2020) == 8


def _synthetic(n=10, league_group=None):
    wp = np.linspace(0.42, 0.58, n)
    return pd.DataFrame(
        {
            "team_id": [f"T{i}" for i in range(n)],
            "sub_league": league_group,
            "games": 144,
            "proj_rs": 700.0,
            "proj_ra": 700.0,
            "exp_wpct": wp,
            "exp_wins": wp * 144,
        }
    )


def test_simulate_probabilities_are_consistent():
    s = _synthetic()
    out = simulate(s, "KBO", 2024, sigma=0.04, n_sims=4000, seed=1)
    # 순위 확률은 팀마다 합이 1
    for rp in out["rank_probs"]:
        assert sum(rp.values()) == pytest.approx(1.0)
    # 포스트시즌 확률 합 = 진출 팀 수 (KBO 5)
    assert out["postseason_prob"].sum() == pytest.approx(5.0)
    # 강한 팀일수록 진출 확률이 높다
    assert out["postseason_prob"].is_monotonic_increasing
    # 승수 중앙값은 기대 승수 근처
    assert np.abs(out["wins_p50"] - out["exp_wins"]).max() < 3


DB = Path(__file__).resolve().parents[1] / "data" / "sabior.duckdb"


@pytest.mark.skipif(not DB.exists(), reason="Lahman DB 없음")
def test_team_strength_mlb_2024():
    from models.team_sim.sim import team_strength

    con = duckdb.connect(str(DB), read_only=True)
    st = team_strength(con, "MLB", 2024, "prior_roster")
    con.close()
    assert len(st) == 30
    assert st["exp_wpct"].mean() == pytest.approx(0.5, abs=1e-9)
    assert st["exp_wins"].between(60, 105).all()
