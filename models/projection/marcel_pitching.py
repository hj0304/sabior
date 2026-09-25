"""Marcel 투수 예측 (FIP 구성요소). 투수 예측 모델이 이겨야 할 베이스라인.

규칙 (Tango Marcel 투수판을 FIP 구성요소에 적용)
  1. 최근 3시즌 가중치 3/2/1 로 이닝(아웃)당 HR, BB, HBP, SO 비율을 합산한다.
  2. 리그 평균 134 이닝(402 아웃)을 더해 평균으로 회귀한다 (리그 비율도 3/2/1 가중).
  3. 나이 보정: 29세 기준, 어리면 해마다 +0.6%, 많으면 해마다 -0.3%. SO 는 곱하고 HR·BB·HBP 는 나눈다.
  4. 예상 이닝 = 0.5 × IP(t-1) + 0.1 × IP(t-2) + (선발 60, 불펜 25). 선발 = 직전 시즌 GS/G ≥ 0.5.
  5. FIP 는 target-1 시즌의 cFIP 로 계산한다.

입력은 pitching_as_of(season_cutoff(target - 1)) 로만 읽는다.
"""

from __future__ import annotations

import pandas as pd

from models.projection.marcel import age_adjustment
from stats.constants import load_constants

WEIGHTS = {1: 3.0, 2: 2.0, 3: 1.0}
REGRESS_OUTS = 134 * 3
EVENTS = ["hr", "bb", "hbp", "so"]


def _history(con, league: str, target: int) -> pd.DataFrame:
    return con.execute(
        """
        SELECT player_id, season, sum(COALESCE(ip_outs,0)) outs, sum(COALESCE(hr,0)) hr,
               sum(COALESCE(bb,0)) bb, sum(COALESCE(hbp,0)) hbp, sum(COALESCE(so,0)) so,
               sum(COALESCE(g,0)) g, sum(COALESCE(gs,0)) gs
        FROM pitching_as_of(season_cutoff(?))
        WHERE league = ? AND season BETWEEN ? AND ?
        GROUP BY player_id, season
        """,
        [target - 1, league, target - 3, target - 1],
    ).df()


def fip_from_rates(r: pd.DataFrame, c_fip: float) -> pd.Series:
    """아웃당 비율로 FIP. IP = outs/3 이므로 이닝당 = 아웃당 × 3."""
    return (13 * r["hr"] + 3 * (r["bb"] + r["hbp"]) - 2 * r["so"]) * 3 + c_fip


def project(con, league: str, target: int) -> pd.DataFrame:
    hist = _history(con, league, target)
    if hist.empty:
        return pd.DataFrame()
    hist["ago"] = target - hist["season"]
    hist["w"] = hist["ago"].map(WEIGHTS)

    lg_tot = hist.groupby("ago")[["outs", *EVENTS]].sum()
    lg_w = lg_tot.mul(pd.Series(WEIGHTS), axis=0).sum()
    lg_rate = lg_w[EVENTS] / lg_w["outs"]

    weighted = hist[["outs", *EVENTS]].mul(hist["w"], axis=0)
    weighted["player_id"] = hist["player_id"]
    agg = weighted.groupby("player_id").sum()
    rates = agg[EVENTS].add(REGRESS_OUTS * lg_rate, axis=1).div(agg["outs"] + REGRESS_OUTS, axis=0)

    births = (
        con.execute(
            "SELECT player_id, birth_date FROM players WHERE player_id IN (SELECT unnest(?::VARCHAR[]))",
            [list(agg.index)],
        )
        .df()
        .set_index("player_id")["birth_date"]
    )
    age = (
        pd.Timestamp(f"{target}-07-01") - pd.to_datetime(births.reindex(agg.index))
    ).dt.days / 365.25
    adj = age_adjustment(age.fillna(29.0))
    rates["so"] = rates["so"] * (1 + adj)
    for e in ("hr", "bb", "hbp"):
        rates[e] = rates[e] / (1 + adj)

    by_ago = hist.pivot_table(
        index="player_id", columns="ago", values=["outs", "g", "gs"], aggfunc="sum"
    )
    outs1 = by_ago["outs"].reindex(columns=[1, 2, 3]).fillna(0)
    g1 = by_ago["g"].reindex(columns=[1]).fillna(0)[1]
    gs1 = by_ago["gs"].reindex(columns=[1]).fillna(0)[1]
    starter = (gs1 / g1.where(g1 > 0, 1)) >= 0.5
    proj_ip = 0.5 * outs1[1] / 3 + 0.1 * outs1[2] / 3 + starter.map({True: 60, False: 25})

    c = load_constants(con, league, target - 1)
    out = rates.copy()
    out["proj_fip"] = fip_from_rates(rates, c.c_fip)
    out["proj_ip"] = proj_ip
    out["starter"] = starter
    out["age"] = age
    out["c_fip_prev"] = c.c_fip
    out["lg_era_prev"] = c.lg_era
    return out.reset_index()
