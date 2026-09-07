"""지표 엔진 단위 테스트. 상수는 임의값이고 기대값은 손으로 계산했다."""

import pytest

from stats import LeagueConstants, fip, fip_constant, plate_appearances, woba, wraa, wrc_plus
from stats.pitching import ip_display, outs_from_ip, parse_ip

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

# 가상의 타자: AB 500, H 158 (1B 100, 2B 30, 3B 3, HR 25), BB 55 (IBB 5), HBP 5, SF 5, SH 0
BATTER = dict(ab=500, bb=55, ibb=5, hbp=5, h=158, doubles=30, triples=3, hr=25, sf=5)


def test_plate_appearances():
    assert plate_appearances(ab=500, bb=55, hbp=5, sf=5, sh=0) == 565


def test_woba_hand_computed():
    # 분자 = .69*50 + .72*5 + .89*100 + 1.27*30 + 1.62*3 + 2.10*25 = 222.56
    # 분모 = 500 + 55 - 5 + 5 + 5 = 560
    assert woba(C, **BATTER) == pytest.approx(222.56 / 560, rel=1e-9)


def test_wraa_and_wrc_plus():
    w = woba(C, **BATTER)
    pa = 565
    # wRAA = (0.397428... - 0.320) / 1.25 * 565 = 약 35.0
    assert wraa(C, w, pa) == pytest.approx(34.9977, abs=1e-3)
    # 중립 구장, lgwRC/PA = lgR/PA 근사: (wRAA/PA + 0.12) / 0.12 * 100 = 약 151.6
    assert wrc_plus(C, w, pa) == pytest.approx(151.62, abs=0.05)
    # 리그 평균 타자는 정의상 100
    assert wrc_plus(C, C.lg_woba, 600) == pytest.approx(100.0)
    # 타자 친화 구장(PF 1.10)이면 같은 성적에 wRC+ 가 낮아진다
    assert wrc_plus(C, w, pa, park_factor=1.10) < wrc_plus(C, w, pa)


def test_fip_hand_computed():
    # (13*20 + 3*(40+5) - 2*180) / 180 + 3.10 = 35/180 + 3.10
    assert fip(C, hr=20, bb=40, hbp=5, so=180, ip=180.0) == pytest.approx(35 / 180 + 3.10, rel=1e-9)


def test_fip_constant():
    # 4.20 - (13*5000 + 3*(15000+2000) - 2*40000) / 43000 = 4.20 - 36000/43000
    assert fip_constant(4.20, 5000, 15000, 2000, 40000, 43000.0) == pytest.approx(
        4.20 - 36000 / 43000
    )


def test_ip_notation_roundtrip():
    assert parse_ip("180.1") == pytest.approx(180 + 1 / 3)
    assert parse_ip("180.2") == pytest.approx(180 + 2 / 3)
    assert parse_ip("180") == 180.0
    assert outs_from_ip("180.1") == 541
    assert ip_display(541) == "180.1"
    with pytest.raises(ValueError):
        parse_ip("180.3")
