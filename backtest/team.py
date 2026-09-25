"""팀 성적 예측 백테스트 (P2 W7).

비교 대상 (모두 승률 → 162경기 환산 승수로 평가)
  - flat_500   : 모두 .500
  - last_wpct  : 전년 승률
  - regressed  : .500 + 0.5 × (전년 승률 − .500)   (회귀 계수 0.5 는 관례값, 튜닝하지 않음)
  - model_prior  : 팀 시뮬레이터, prior_roster (누출 없음)
  - model_actual : 팀 시뮬레이터, actual_usage (출장 시간 누출, 예측 성능 상한 참고용)
  - model_blend  : .500 + a·(model_prior − .500) + b·(전년 피타고리안 − .500). a, b 는 직전 5시즌 OLS (누출 없음)

지표: 승수 MAE, RMSE (162경기 환산), 상관계수. 포스트시즌 확률은 Brier 점수 (기준: 진출 팀 수 / 팀 수).
몬테카를로 σ 는 직전 5시즌의 prior_roster 잔차 분산에서 이항 잡음을 뺀 값으로 시즌마다 다시 잡는다 (누출 없음).

사용:
    uv run python -m backtest.team --league MLB --from 2015 --to 2025
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from models.team_sim.sim import postseason_slots, simulate, team_strength


def actual(con, league: str, season: int) -> pd.DataFrame:
    return (
        con.execute(
            """
        SELECT team_id, games, wins, sub_league, postseason IS NOT NULL AS made_po
        FROM team_seasons_as_of(season_cutoff(?)) WHERE league = ? AND season = ?
        """,
            [season, league, season],
        )
        .df()
        .set_index("team_id")
    )


def prev_wpct(con, league: str, season: int) -> pd.Series:
    a = actual(con, league, season - 1)
    return a["wins"] / a["games"]


def prev_pythag(con, league: str, season: int) -> pd.Series:
    """전년 Pythagenpat 승률."""
    d = (
        con.execute(
            """
        SELECT team_id, games, runs_scored rs, runs_allowed ra FROM team_seasons_as_of(season_cutoff(?))
        WHERE league = ? AND season = ?
        """,
            [season - 1, league, season - 1],
        )
        .df()
        .set_index("team_id")
    )
    x = ((d["rs"] + d["ra"]) / d["games"]) ** 0.287
    return d["rs"] ** x / (d["rs"] ** x + d["ra"] ** x)


def fit_blend(rows: list[tuple[float, float, float]]) -> tuple[float, float]:
    """(model − .5, pythag − .5, actual − .5) 목록으로 절편 없는 OLS. 표본이 적으면 (1, 0)."""
    if len(rows) < 30:
        return 1.0, 0.0
    arr = np.array(rows)
    coef, *_ = np.linalg.lstsq(arr[:, :2], arr[:, 2], rcond=None)
    return float(coef[0]), float(coef[1])


def _metrics(pred_wpct: pd.Series, act: pd.DataFrame) -> dict:
    p = pred_wpct.reindex(act.index).fillna(0.5)
    err = (p - act["wins"] / act["games"]) * 162
    return {
        "mae": float(err.abs().mean()),
        "rmse": float(np.sqrt((err**2).mean())),
        "corr": float(np.corrcoef(p, act["wins"] / act["games"])[0, 1])
        if p.std() > 0
        else float("nan"),
    }


def sigma_from_residuals(resid: list[tuple[float, float, int]]) -> float:
    """(예측 승률, 실제 승률, 경기 수) 목록 → 실력 오차 σ = sqrt(max(0, var(잔차) − 평균 이항분산))."""
    if len(resid) < 30:
        return 0.035
    arr = np.array(resid)
    r = arr[:, 1] - arr[:, 0]
    binom = (arr[:, 0] * (1 - arr[:, 0]) / arr[:, 2]).mean()
    return float(np.sqrt(max(0.0, r.var() - binom)))


def run(
    con, league: str, start: int, end: int, warmup: int = 5
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, po_rows = [], []
    history: dict[int, list[tuple[float, float, int]]] = {}
    blend_hist: dict[int, list[tuple[float, float, float]]] = {}
    blend_coefs = []
    for t in range(start - warmup, end + 1):
        act = actual(con, league, t)
        if act.empty:
            continue
        prior = team_strength(con, league, t, "prior_roster").set_index("team_id")
        history[t] = [
            (
                prior.loc[i, "exp_wpct"],
                act.loc[i, "wins"] / act.loc[i, "games"],
                act.loc[i, "games"],
            )
            for i in act.index
            if i in prior.index
        ]
        pyth = prev_pythag(con, league, t)
        blend_hist[t] = [
            (
                prior.loc[i, "exp_wpct"] - 0.5,
                pyth.get(i, 0.5) - 0.5,
                act.loc[i, "wins"] / act.loc[i, "games"] - 0.5,
            )
            for i in act.index
            if i in prior.index
        ]
        if t < start:
            continue
        sigma = sigma_from_residuals([x for s in range(t - warmup, t) for x in history.get(s, [])])
        a_coef, b_coef = fit_blend([x for s in range(t - warmup, t) for x in blend_hist.get(s, [])])
        blend_coefs.append({"season": t, "a_model": a_coef, "b_pythag": b_coef})
        actual_mode = team_strength(con, league, t, "actual_usage").set_index("team_id")
        last = prev_wpct(con, league, t)
        preds = {
            "flat_500": pd.Series(0.5, index=act.index),
            "last_wpct": last,
            "regressed": 0.5 + 0.5 * (last - 0.5),
            "model_prior": prior["exp_wpct"],
            "model_actual": actual_mode["exp_wpct"],
            "model_blend": 0.5
            + a_coef * (prior["exp_wpct"] - 0.5)
            + b_coef * (pyth.reindex(prior.index).fillna(0.5) - 0.5),
        }
        for name, p in preds.items():
            rows.append({"season": t, "model": name, "sigma": sigma, **_metrics(p, act)})

        sim = simulate(prior.reset_index(), league, t, sigma=sigma).set_index("team_id")
        base = postseason_slots(league, t) * act["sub_league"].fillna("ALL").nunique() / len(act)
        made = act["made_po"].astype(float)
        po_rows.append(
            {
                "season": t,
                "sigma": sigma,
                "brier_model": float(
                    ((sim["postseason_prob"].reindex(act.index) - made) ** 2).mean()
                ),
                "brier_base": float(((base - made) ** 2).mean()),
                "wins_cover80": float(
                    (
                        (act["wins"] >= sim["wins_p10"].reindex(act.index))
                        & (act["wins"] <= sim["wins_p90"].reindex(act.index))
                    ).mean()
                ),
            }
        )
    print(pd.DataFrame(blend_coefs).round(3).to_string(index=False))
    return pd.DataFrame(rows), pd.DataFrame(po_rows)


def main() -> None:
    from db.init_db import default_db_path, init_db

    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="MLB")
    ap.add_argument("--from", dest="start", type=int, required=True)
    ap.add_argument("--to", dest="end", type=int, required=True)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    con = init_db(default_db_path())
    res, po = run(con, a.league, a.start, a.end)
    pd.set_option("display.width", 160)
    print("승수 MAE (162경기 환산)")
    print(res.pivot(index="season", columns="model", values="mae").round(2))
    print()
    print(res.groupby("model")[["mae", "rmse", "corr"]].mean().sort_values("mae").round(3))
    print("\n포스트시즌 확률 Brier / 승수 80% 구간 적중")
    print(po.round(3).to_string(index=False))
    print(po[["brier_model", "brier_base", "wins_cover80"]].mean().round(3).to_string())
    if a.out:
        res.to_csv(a.out, index=False)
        po.to_csv(a.out.replace(".csv", "_postseason.csv"), index=False)
    con.close()


if __name__ == "__main__":
    main()
