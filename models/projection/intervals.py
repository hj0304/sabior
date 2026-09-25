"""예측 구간 (경험적 잔차 분위). 타자 wOBA 용.

방법
  1. 목표 시즌 t 의 구간을 만들 때, t-lookback ~ t-1 시즌에 대해 Marcel 을 다시 돌려 (실제 - 예측) 잔차를 모은다.
     이 시즌들의 실제 기록은 season_cutoff(t-1) 시점에 이미 알려져 있으므로 누출이 없다.
  2. 잔차를 예측 신뢰도(reliability = 가중 PA / (가중 PA + 1200)) 구간별로 나눠 분위(p10, p25, p50, p75, p90)를 구한다.
  3. t 시즌 예측값에 해당 신뢰도 구간의 잔차 분위를 더한다.

해석: 잔차 표본은 "그 시즌 PA ≥ min_pa 로 뛴 선수"라 구간은 "주전으로 뛴다면"의 조건부 구간이다.
출장 시간 자체의 불확실성은 proj_pa 쪽에서 따로 다룬다.
"""

from __future__ import annotations

import pandas as pd

from models.projection import marcel

QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]
BINS = [0.0, 0.55, 0.70, 1.0]  # 신뢰도 구간: 낮음 / 중간 / 높음


def _residuals(con, league: str, season: int, min_pa: int) -> pd.DataFrame:
    from backtest.harness import eligible

    act = eligible(con, league, season, min_pa)
    proj = marcel.project(con, league, season).set_index("player_id")
    df = proj.join(act, how="inner")
    df["resid"] = df["woba"] - df["proj_woba"]
    return df[["reliability", "resid"]]


def calibrate(con, league: str, target: int, lookback: int = 5, min_pa: int = 300) -> pd.DataFrame:
    """target 시즌용 신뢰도 구간별 잔차 분위표. 행: 구간, 열: p10..p90, n."""
    parts = []
    for s in range(target - lookback, target):
        try:
            parts.append(_residuals(con, league, s, min_pa))
        except LookupError:
            continue
    res = pd.concat(parts) if parts else pd.DataFrame(columns=["reliability", "resid"])
    res["bin"] = pd.cut(res["reliability"], BINS, include_lowest=True)
    q = res.groupby("bin", observed=False)["resid"].quantile(QUANTILES).unstack()
    q.columns = [f"p{int(x * 100)}" for x in q.columns]
    q["n"] = res.groupby("bin", observed=False).size()
    # 표본이 적은 구간은 전체 분위로 대체
    overall = res["resid"].quantile(QUANTILES).to_numpy()
    for i in q.index:
        if q.loc[i, "n"] < 30:
            q.loc[i, [f"p{int(x * 100)}" for x in QUANTILES]] = overall
    return q


def project_with_intervals(con, league: str, target: int, lookback: int = 5) -> pd.DataFrame:
    proj = marcel.project(con, league, target)
    table = calibrate(con, league, target, lookback)
    bins = pd.cut(proj["reliability"], BINS, include_lowest=True)
    for col in [f"p{int(x * 100)}" for x in QUANTILES]:
        proj[col] = proj["proj_woba"] + bins.map(table[col]).astype(float).to_numpy()
    proj["reliability_bin"] = bins.astype(str)
    return proj


def coverage(con, league: str, start: int, end: int, min_pa: int = 300) -> pd.DataFrame:
    """백테스트: 시즌별로 80% 구간(p10~p90), 50% 구간(p25~p75)이 실제값을 덮는 비율."""
    from backtest.harness import eligible

    rows = []
    for t in range(start, end + 1):
        act = eligible(con, league, t, min_pa)
        if act.empty:
            continue
        p = project_with_intervals(con, league, t).set_index("player_id").join(act, how="inner")
        rows.append(
            {
                "season": t,
                "n": len(p),
                "cover80": float(((p["woba"] >= p["p10"]) & (p["woba"] <= p["p90"])).mean()),
                "cover50": float(((p["woba"] >= p["p25"]) & (p["woba"] <= p["p75"])).mean()),
                "width80": float((p["p90"] - p["p10"]).mean()),
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    import argparse

    from db.init_db import default_db_path, init_db

    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="MLB")
    ap.add_argument("--from", dest="start", type=int, default=2018)
    ap.add_argument("--to", dest="end", type=int, default=2025)
    a = ap.parse_args()
    con = init_db(default_db_path())
    cov = coverage(con, a.league, a.start, a.end)
    print(cov.round(3).to_string(index=False))
    print(
        f"\n평균 80% 구간 적중률 {cov['cover80'].mean():.3f}, 50% 구간 {cov['cover50'].mean():.3f}, "
        f"80% 구간 평균 폭 {cov['width80'].mean():.3f}"
    )
    print("\n2025 시즌용 잔차 분위표:")
    print(calibrate(con, a.league, 2025).round(4))
    con.close()


if __name__ == "__main__":
    main()
