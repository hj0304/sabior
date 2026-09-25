"""Marcel 타자 예측 (Tom Tango 의 "가장 단순한 예측 시스템"). 모든 예측 모델이 이겨야 할 베이스라인.

규칙
  1. 최근 3시즌 가중치 5/4/3 으로 이벤트별 타석당 비율을 합산한다.
  2. 리그 평균 1200 타석을 더해 평균으로 회귀한다 (리그 비율도 같은 5/4/3 가중).
  3. 나이 보정: 29세 기준, 어리면 해마다 +0.6%, 많으면 해마다 -0.3% (좋은 이벤트 비율에 곱한다).
  4. 예상 타석 = 0.5 × PA(t-1) + 0.1 × PA(t-2) + 200.

입력은 batting_as_of(season_cutoff(target - 1)) 로만 읽는다 (미래 누출 금지).
wOBA 는 target-1 시즌의 리그 상수로 계산한다 (target 시즌 상수는 예측 시점에 알 수 없다).
리그 평균에서는 투수 타석을 뺀다 (그 시즌 투구 경기 수 ≥ 타격 경기 수 / 2 인 선수 제외).
"""

from __future__ import annotations

import pandas as pd

from stats.constants import load_constants

WEIGHTS = {1: 5.0, 2: 4.0, 3: 3.0}  # 몇 시즌 전: 가중치
REGRESS_PA = 1200.0
EVENTS = ["s1", "d", "t", "hr", "ubb", "ibb", "hbp", "sf", "sh", "so"]
GOOD = ["s1", "d", "t", "hr", "ubb", "hbp"]


def _history(con, league: str, target: int) -> pd.DataFrame:
    """target 직전 3시즌 선수별 이벤트 합계 (stint 합산). 투수 여부 플래그 포함."""
    return con.execute(
        """
        WITH b AS (
            SELECT player_id, season,
                   sum(COALESCE(pa,0)) pa, sum(COALESCE(h,0)) h, sum(COALESCE(doubles,0)) d,
                   sum(COALESCE(triples,0)) t, sum(COALESCE(hr,0)) hr, sum(COALESCE(bb,0)) bb,
                   sum(COALESCE(ibb,0)) ibb, sum(COALESCE(hbp,0)) hbp, sum(COALESCE(sf,0)) sf,
                   sum(COALESCE(sh,0)) sh, sum(COALESCE(so,0)) so, sum(COALESCE(g,0)) g
            FROM batting_as_of(season_cutoff(?))
            WHERE league = ? AND season BETWEEN ? AND ?
            GROUP BY player_id, season
        ), p AS (
            SELECT player_id, season, sum(COALESCE(g,0)) pg
            FROM pitching_as_of(season_cutoff(?))
            WHERE league = ? AND season BETWEEN ? AND ?
            GROUP BY player_id, season
        )
        SELECT b.*, COALESCE(p.pg, 0) AS pg
        FROM b LEFT JOIN p USING (player_id, season)
        """,
        [target - 1, league, target - 3, target - 1] * 2,
    ).df()


def _add_events(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["s1"] = df["h"] - df["d"] - df["t"] - df["hr"]
    df["ubb"] = df["bb"] - df["ibb"]
    df["is_pitcher"] = df["pg"] >= df["g"] / 2
    return df


def woba_from_rates(r: pd.DataFrame, c) -> pd.Series:
    """이벤트 비율(타석당)로 wOBA. 분모 = PA - IBB - SH."""
    num = (
        c.w_bb * r["ubb"]
        + c.w_hbp * r["hbp"]
        + c.w_1b * r["s1"]
        + c.w_2b * r["d"]
        + c.w_3b * r["t"]
        + c.w_hr * r["hr"]
    )
    return num / (1.0 - r["ibb"] - r["sh"])


def age_adjustment(age: pd.Series) -> pd.Series:
    return (29 - age).clip(lower=0) * 0.006 - (age - 29).clip(lower=0) * 0.003


def project(con, league: str, target: int) -> pd.DataFrame:
    """target 시즌 타자 예측. 반환: player_id, proj_pa, proj_woba, 이벤트 비율, age, n_seasons."""
    hist = _add_events(_history(con, league, target))
    if hist.empty:
        return pd.DataFrame()
    hist["ago"] = target - hist["season"]
    hist["w"] = hist["ago"].map(WEIGHTS)

    # 리그 비율 (투수 제외, 5/4/3 가중)
    pos = hist[~hist["is_pitcher"]]
    lg_tot = pos.groupby("ago")[["pa", *EVENTS]].sum()
    lg_w = lg_tot.mul(pd.Series(WEIGHTS), axis=0).sum()
    lg_rate = lg_w[EVENTS] / lg_w["pa"]

    # 선수별 가중 합
    wcols = ["pa", *EVENTS]
    weighted = hist[wcols].mul(hist["w"], axis=0)
    weighted["player_id"] = hist["player_id"]
    agg = weighted.groupby("player_id").sum()
    rates = (agg[EVENTS].add(REGRESS_PA * lg_rate, axis=1)).div(agg["pa"] + REGRESS_PA, axis=0)

    # 나이 (target 시즌 7월 1일 기준)
    ids = list(agg.index)
    births = (
        con.execute(
            "SELECT player_id, birth_date FROM players WHERE player_id IN (SELECT unnest(?::VARCHAR[]))",
            [ids],
        )
        .df()
        .set_index("player_id")["birth_date"]
    )
    birth = pd.to_datetime(births.reindex(agg.index))
    age = (pd.Timestamp(f"{target}-07-01") - birth).dt.days / 365.25
    adj = age_adjustment(age.fillna(29.0))
    for e in GOOD:
        rates[e] = rates[e] * (1 + adj)

    pa_by_ago = (
        hist.pivot_table(index="player_id", columns="ago", values="pa", aggfunc="sum")
        .reindex(columns=[1, 2, 3], fill_value=0)
        .fillna(0)
    )
    proj_pa = 0.5 * pa_by_ago[1] + 0.1 * pa_by_ago[2] + 200

    c = load_constants(con, league, target - 1)
    out = rates.copy()
    out["proj_woba"] = woba_from_rates(rates, c)
    out["proj_pa"] = proj_pa
    out["age"] = age
    out["n_seasons"] = (pa_by_ago > 0).sum(axis=1)
    out["lg_woba_prev"] = c.lg_woba
    return out.reset_index()
