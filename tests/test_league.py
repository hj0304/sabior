"""리그 상수 계산 테스트. 합계는 임의값, 기대값은 손계산."""

import pytest

from stats.league import RAW_WEIGHTS_REF, SeasonTotals, compute_constants

T = SeasonTotals(
    league="TEST",
    season=2024,
    pa=10000,
    ab=9000,
    h=2300,
    doubles=450,
    triples=40,
    hr=300,
    bb=800,
    ibb=50,
    hbp=100,
    sf=80,
    runs=1150,
    ip_outs=9000 * 3 // 4 * 1,  # 6750 outs = 2250 IP
    er=1000,
    p_hr=300,
    p_bb=800,
    p_hbp=100,
    p_so=2200,
)


def test_league_woba_equals_obp_after_scaling():
    c = compute_constants(T)
    # OBP = (2300 + 800 + 100) / (9000 + 800 + 100 + 80) = 3200 / 9980
    assert c.lg_woba == pytest.approx(3200 / 9980)
    # 스케일을 곱한 가중치로 리그 wOBA 를 다시 계산하면 OBP 와 같아야 한다
    ubb = T.bb - T.ibb
    num = (
        c.w_bb * ubb
        + c.w_hbp * T.hbp
        + c.w_1b * T.singles
        + c.w_2b * T.doubles
        + c.w_3b * T.triples
        + c.w_hr * T.hr
    )
    den = T.ab + T.bb - T.ibb + T.sf + T.hbp
    assert num / den == pytest.approx(c.lg_woba, rel=1e-9)


def test_weight_ratios_preserved():
    c = compute_constants(T)
    assert c.w_hr / c.w_bb == pytest.approx(RAW_WEIGHTS_REF["hr"] / RAW_WEIGHTS_REF["bb"], rel=1e-9)
    assert 1.0 < c.woba_scale < 1.6


def test_era_fip_constant_and_rpw():
    c = compute_constants(T)
    ip = 6750 / 3
    assert c.lg_era == pytest.approx(1000 * 9 / ip)
    # cFIP = lgERA - (13*300 + 3*(800+100) - 2*2200) / IP = lgERA - (3900 + 2700 - 4400) / 2250
    assert c.c_fip == pytest.approx(c.lg_era - 2200 / ip)
    assert c.lg_r_per_pa == pytest.approx(0.115)
    assert c.runs_per_win == pytest.approx(9 * (1150 / ip) * 1.5 + 3)
