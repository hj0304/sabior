"""타격 지표. 모든 함수는 카운팅 스탯과 LeagueConstants 를 받아 값을 돌려주는 순수 함수다."""

from __future__ import annotations

from stats.constants import LeagueConstants


def plate_appearances(ab: int, bb: int, hbp: int, sf: int, sh: int) -> int:
    """PA = AB + BB + HBP + SF + SH"""
    return ab + bb + hbp + sf + sh


def singles(h: int, doubles: int, triples: int, hr: int) -> int:
    return h - doubles - triples - hr


def woba(
    c: LeagueConstants,
    *,
    ab: int,
    bb: int,
    ibb: int,
    hbp: int,
    h: int,
    doubles: int,
    triples: int,
    hr: int,
    sf: int,
) -> float:
    """wOBA = (wBB*uBB + wHBP*HBP + w1B*1B + w2B*2B + w3B*3B + wHR*HR) / (AB + BB - IBB + SF + HBP)

    uBB = BB - IBB. 분모에서 고의사구는 제외한다 (FanGraphs 정의).
    """
    ubb = bb - ibb
    x1b = singles(h, doubles, triples, hr)
    num = (
        c.w_bb * ubb
        + c.w_hbp * hbp
        + c.w_1b * x1b
        + c.w_2b * doubles
        + c.w_3b * triples
        + c.w_hr * hr
    )
    den = ab + bb - ibb + sf + hbp
    if den <= 0:
        raise ValueError("wOBA denominator must be positive")
    return num / den


def wraa(c: LeagueConstants, woba_value: float, pa: int) -> float:
    """wRAA = ((wOBA - lgwOBA) / wOBAscale) * PA"""
    return (woba_value - c.lg_woba) / c.woba_scale * pa


def wrc(c: LeagueConstants, woba_value: float, pa: int) -> float:
    """wRC = wRAA + lgR/PA * PA"""
    return wraa(c, woba_value, pa) + c.lg_r_per_pa * pa


def wrc_plus(
    c: LeagueConstants,
    woba_value: float,
    pa: int,
    park_factor: float = 1.0,
    lg_wrc_per_pa: float | None = None,
) -> float:
    """wRC+ = ((wRAA/PA + lgR/PA) + (lgR/PA - PF*lgR/PA)) / (lgwRC/PA) * 100

    park_factor 는 1.00 이 중립. lg_wrc_per_pa 를 주지 않으면 lgR/PA 로 근사한다
    (FanGraphs 는 투수 타석을 제외한 리그 wRC/PA 를 쓴다. W3 에서 정식값으로 교체).
    """
    if pa <= 0:
        raise ValueError("pa must be positive")
    lg_wrc_pa = lg_wrc_per_pa if lg_wrc_per_pa is not None else c.lg_r_per_pa
    wraa_pa = wraa(c, woba_value, pa) / pa
    park_adj = c.lg_r_per_pa - park_factor * c.lg_r_per_pa
    return (wraa_pa + c.lg_r_per_pa + park_adj) / lg_wrc_pa * 100


def iso(ab: int, h: int, doubles: int, triples: int, hr: int) -> float:
    """ISO = (2B + 2*3B + 3*HR) / AB"""
    if ab <= 0:
        raise ValueError("ab must be positive")
    return (doubles + 2 * triples + 3 * hr) / ab


def babip(ab: int, h: int, hr: int, so: int, sf: int) -> float:
    """BABIP = (H - HR) / (AB - K - HR + SF)"""
    den = ab - so - hr + sf
    if den <= 0:
        raise ValueError("BABIP denominator must be positive")
    return (h - hr) / den
