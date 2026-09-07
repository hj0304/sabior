"""리그·연도별 상수.

선형 가중치(w_1b 등)와 wOBA 스케일은 득점 기대치(RE24)에서 나오므로 이벤트 단위 데이터가 필요하다.
W3 계획:
  - MLB: FanGraphs Guts 공개값을 source='fangraphs_guts' 로 적재해 자체 계산과 대조.
  - KBO: 시즌 집계로 근사(w_x 는 MLB 비율을 차용하고 lg_woba, woba_scale 만 KBO 로 재조정)한 뒤,
         이벤트 데이터가 확보되면 정식 계산으로 교체.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeagueConstants:
    league: str
    season: int
    w_bb: float
    w_hbp: float
    w_1b: float
    w_2b: float
    w_3b: float
    w_hr: float
    woba_scale: float
    lg_woba: float
    lg_r_per_pa: float
    lg_era: float
    c_fip: float
    runs_per_win: float = 10.0
    source: str = "manual"


def fip_constant(
    lg_era: float, lg_hr: int, lg_bb: int, lg_hbp: int, lg_so: int, lg_ip: float
) -> float:
    """cFIP = lgERA - (13*lgHR + 3*(lgBB+lgHBP) - 2*lgK) / lgIP

    리그 FIP 평균을 리그 ERA 와 같게 맞추는 상수. lg_ip 는 진짜 소수 이닝(1/3 단위).
    """
    if lg_ip <= 0:
        raise ValueError("lg_ip must be positive")
    return lg_era - (13 * lg_hr + 3 * (lg_bb + lg_hbp) - 2 * lg_so) / lg_ip


def load_constants(con, league: str, season: int, source: str | None = None) -> LeagueConstants:
    """league_constants 테이블에서 상수를 읽는다. source 를 주지 않으면 'computed' 우선."""
    q = "SELECT * FROM league_constants WHERE league = ? AND season = ?"
    params: list = [league, season]
    if source:
        q += " AND source = ?"
        params.append(source)
    q += " ORDER BY CASE source WHEN 'computed' THEN 0 ELSE 1 END LIMIT 1"
    cur = con.execute(q, params)
    row = cur.fetchone()
    if row is None:
        raise LookupError(f"league_constants 없음: {league} {season} {source or ''}")
    cols = [d[0] for d in cur.description]
    rec = dict(zip(cols, row, strict=True))
    return LeagueConstants(
        league=rec["league"],
        season=rec["season"],
        w_bb=rec["w_bb"],
        w_hbp=rec["w_hbp"],
        w_1b=rec["w_1b"],
        w_2b=rec["w_2b"],
        w_3b=rec["w_3b"],
        w_hr=rec["w_hr"],
        woba_scale=rec["woba_scale"],
        lg_woba=rec["lg_woba"],
        lg_r_per_pa=rec["lg_r_per_pa"],
        lg_era=rec["lg_era"],
        c_fip=rec["c_fip"],
        runs_per_win=rec["runs_per_win"] or 10.0,
        source=rec["source"],
    )
