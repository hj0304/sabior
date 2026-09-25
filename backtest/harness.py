"""백테스트 하네스 (P2 W6, MLB 로 선행 구축).

컷오프 연도 t 마다: 모델은 season_cutoff(t-1) 시점 데이터만 보고 t 시즌을 예측하고, 실제 t 시즌 기록과 비교한다.
모든 모델과 베이스라인을 같은 대상 집합, 같은 지표로 비교한다.

대상 집합: t 시즌 실제 PA ≥ min_pa 이고 직전 3시즌에 PA > 0 인 선수 (신인 제외).
지표: 실제 PA 가중 RMSE, MAE, 상관계수 (wOBA 기준).

베이스라인
  - league_avg: 전년 리그 wOBA
  - last_year:  전년 본인 wOBA (전년 기록이 없으면 리그 평균)
  - marcel:     models/projection/marcel.py

사용:
    uv run python -m backtest.harness --league MLB --from 2015 --to 2025
"""

from __future__ import annotations

import argparse
from collections.abc import Callable

import numpy as np
import pandas as pd

from models.projection import marcel
from stats.constants import load_constants

ModelFn = Callable[
    [object, str, int], pd.Series
]  # (con, league, target) -> proj_woba indexed by player_id


def actual_woba(con, league: str, season: int) -> pd.DataFrame:
    """t 시즌 실제 wOBA 와 PA (season_cutoff(t) 시점)."""
    df = con.execute(
        """
        SELECT player_id, sum(COALESCE(pa,0)) pa, sum(COALESCE(h,0)) h, sum(COALESCE(doubles,0)) d,
               sum(COALESCE(triples,0)) t, sum(COALESCE(hr,0)) hr, sum(COALESCE(bb,0)) bb,
               sum(COALESCE(ibb,0)) ibb, sum(COALESCE(hbp,0)) hbp, sum(COALESCE(sf,0)) sf,
               sum(COALESCE(sh,0)) sh, sum(COALESCE(so,0)) so
        FROM batting_as_of(season_cutoff(?)) WHERE league = ? AND season = ?
        GROUP BY player_id
        """,
        [season, league, season],
    ).df()
    return _woba_from_counts(df, load_constants(con, league, season))


def _woba_from_counts(df: pd.DataFrame, c) -> pd.DataFrame:
    df = df.copy()
    df["s1"] = df["h"] - df["d"] - df["t"] - df["hr"]
    df["ubb"] = df["bb"] - df["ibb"]
    den = df["pa"] - df["ibb"] - df["sh"]
    num = (
        c.w_bb * df["ubb"]
        + c.w_hbp * df["hbp"]
        + c.w_1b * df["s1"]
        + c.w_2b * df["d"]
        + c.w_3b * df["t"]
        + c.w_hr * df["hr"]
    )
    df["woba"] = np.where(den > 0, num / den.where(den > 0, 1), np.nan)
    return df.set_index("player_id")[["pa", "woba"]]


def baseline_league_avg(con, league: str, target: int) -> pd.Series:
    prev = actual_woba(con, league, target - 1)
    lg = load_constants(con, league, target - 1).lg_woba
    return pd.Series(lg, index=prev.index, name="proj_woba")


def baseline_last_year(con, league: str, target: int) -> pd.Series:
    prev = actual_woba(con, league, target - 1)
    return prev["woba"].rename("proj_woba")


def model_marcel(con, league: str, target: int) -> pd.Series:
    return marcel.project(con, league, target).set_index("player_id")["proj_woba"]


def model_marcel_plus(con, league: str, target: int) -> pd.Series:
    from models.projection import marcel_plus

    return marcel_plus.project(con, league, target, marcel_plus.load_params()).set_index(
        "player_id"
    )["proj_woba"]


MODELS: dict[str, ModelFn] = {
    "league_avg": baseline_league_avg,
    "last_year": baseline_last_year,
    "marcel": model_marcel,
    "marcel_plus": model_marcel_plus,
}


def eligible(con, league: str, target: int, min_pa: int) -> pd.DataFrame:
    act = actual_woba(con, league, target)
    prior = con.execute(
        """
        SELECT DISTINCT player_id FROM batting_as_of(season_cutoff(?))
        WHERE league = ? AND season BETWEEN ? AND ? AND COALESCE(pa,0) > 0
        """,
        [target - 1, league, target - 3, target - 1],
    ).df()["player_id"]
    act = act[(act["pa"] >= min_pa) & act.index.isin(prior)]
    return act.dropna(subset=["woba"])


def score(pred: pd.Series, act: pd.DataFrame, fallback: float) -> dict:
    p = pred.reindex(act.index).fillna(fallback)
    err = p - act["woba"]
    w = act["pa"]
    return {
        "n": len(act),
        "rmse_w": float(np.sqrt((w * err**2).sum() / w.sum())),
        "mae": float(err.abs().mean()),
        "bias": float((w * err).sum() / w.sum()),
        "corr": float(np.corrcoef(p, act["woba"])[0, 1]) if p.std() > 0 else float("nan"),
    }


def run(
    con, league: str, start: int, end: int, min_pa: int = 300, models: dict | None = None
) -> pd.DataFrame:
    models = models or MODELS
    rows = []
    for t in range(start, end + 1):
        act = eligible(con, league, t, min_pa)
        if act.empty:
            continue
        lg_prev = load_constants(con, league, t - 1).lg_woba
        for name, fn in models.items():
            rows.append({"season": t, "model": name, **score(fn(con, league, t), act, lg_prev)})
    return pd.DataFrame(rows)


def summarize(res: pd.DataFrame) -> pd.DataFrame:
    return (
        res.groupby("model")
        .agg(
            seasons=("season", "nunique"),
            n=("n", "sum"),
            rmse_w=("rmse_w", "mean"),
            mae=("mae", "mean"),
            bias=("bias", "mean"),
            corr=("corr", "mean"),
        )
        .sort_values("rmse_w")
    )


# ---------------------------------------------------------------- 투수 (FIP)


def actual_fip(con, league: str, season: int) -> pd.DataFrame:
    df = con.execute(
        """
        SELECT player_id, sum(COALESCE(ip_outs,0)) outs, sum(COALESCE(hr,0)) hr, sum(COALESCE(bb,0)) bb,
               sum(COALESCE(hbp,0)) hbp, sum(COALESCE(so,0)) so
        FROM pitching_as_of(season_cutoff(?)) WHERE league = ? AND season = ?
        GROUP BY player_id
        """,
        [season, league, season],
    ).df()
    c = load_constants(con, league, season)
    ip = df["outs"] / 3
    df["fip"] = np.where(
        ip > 0,
        (13 * df["hr"] + 3 * (df["bb"] + df["hbp"]) - 2 * df["so"]) / ip.where(ip > 0, 1) + c.c_fip,
        np.nan,
    )
    df["ip"] = ip
    # 점수 함수가 'pa'·'woba' 이름을 기대하므로 가중치=이닝, 대상=FIP 로 맞춘다
    return df.set_index("player_id").rename(columns={"ip": "pa", "fip": "woba"})[["pa", "woba"]]


def p_baseline_league_avg(con, league: str, target: int) -> pd.Series:
    prev = actual_fip(con, league, target - 1)
    return pd.Series(load_constants(con, league, target - 1).lg_era, index=prev.index)


def p_baseline_last_year(con, league: str, target: int) -> pd.Series:
    return actual_fip(con, league, target - 1)["woba"]


def p_model_marcel(con, league: str, target: int) -> pd.Series:
    from models.projection import marcel_pitching

    return marcel_pitching.project(con, league, target).set_index("player_id")["proj_fip"]


P_MODELS: dict[str, ModelFn] = {
    "league_avg": p_baseline_league_avg,
    "last_year": p_baseline_last_year,
    "marcel": p_model_marcel,
}


def run_pitching(con, league: str, start: int, end: int, min_ip: float = 80) -> pd.DataFrame:
    rows = []
    for t in range(start, end + 1):
        act = actual_fip(con, league, t)
        prior = con.execute(
            """
            SELECT DISTINCT player_id FROM pitching_as_of(season_cutoff(?))
            WHERE league = ? AND season BETWEEN ? AND ? AND COALESCE(ip_outs,0) > 0
            """,
            [t - 1, league, t - 3, t - 1],
        ).df()["player_id"]
        act = act[(act["pa"] >= min_ip) & act.index.isin(prior)].dropna(subset=["woba"])
        if act.empty:
            continue
        lg_prev = load_constants(con, league, t - 1).lg_era
        for name, fn in P_MODELS.items():
            rows.append({"season": t, "model": name, **score(fn(con, league, t), act, lg_prev)})
    return pd.DataFrame(rows)


def main() -> None:
    from db.init_db import default_db_path, init_db

    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="MLB")
    ap.add_argument("--kind", choices=["batting", "pitching"], default="batting")
    ap.add_argument("--from", dest="start", type=int, required=True)
    ap.add_argument("--to", dest="end", type=int, required=True)
    ap.add_argument("--min-pa", type=int, default=300, help="타자 최소 PA")
    ap.add_argument("--min-ip", type=float, default=80, help="투수 최소 이닝")
    ap.add_argument("--out", default=None, help="시즌별 결과 CSV 경로")
    a = ap.parse_args()
    con = init_db(default_db_path())
    if a.kind == "batting":
        res = run(con, a.league, a.start, a.end, a.min_pa)
    else:
        res = run_pitching(con, a.league, a.start, a.end, a.min_ip)
    pd.set_option("display.width", 140)
    print(f"[{a.kind}] 대상 지표: {'wOBA (PA 가중)' if a.kind == 'batting' else 'FIP (IP 가중)'}")
    print(res.pivot(index="season", columns="model", values="rmse_w").round(4))
    print()
    print(summarize(res).round(4))
    if a.out:
        res.to_csv(a.out, index=False)
    con.close()


if __name__ == "__main__":
    main()
