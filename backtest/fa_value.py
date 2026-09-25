"""FA 계약 규모 백테스트 (P2 W8). 시장 t 를 시장 t 개장 전 데이터로만 학습해 예측한다.

대상 시장: 2023~2026 (2021~2022 는 학습 전용 워밍업).
비교
  - grade_median : 학습 데이터 등급별 총액 중앙값
  - salary_mult  : 직전 연봉 × 학습 데이터 등급별 (총액/직전 연봉) 중앙값
  - regression   : models/fa_value/model.py FAValueModel (로그 총액 릿지, 비교용)
  구간·연수는 MVP 추정기 SalaryMultipleModel 기준으로 평가한다.
지표: 중앙 절대 백분율 오차(MdAPE), 평균 절대 오차(억), 로그 RMSE, 80%·50% 구간 적중률, 연수 정확도(±1년).

사용: uv run python -m backtest.fa_value
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from models.fa_value.model import FAValueModel, SalaryMultipleModel, load_contracts, market_open


def targets(con, market_year: int) -> pd.DataFrame:
    """시장 t 의 실제 계약 (시장 종료 후 시점에서 조회)."""
    df = load_contracts(con, f"{market_year}-12-31")
    return df[df["market_year"] == market_year].dropna(
        subset=["prev_salary_eok", "age", "fa_grade"]
    )


def run(
    con, markets=(2023, 2024, 2025, 2026), alpha: float = 1.0
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, preds = [], []
    for t in markets:
        train = load_contracts(con, market_open(t))
        test = targets(con, t)
        m = FAValueModel(alpha=alpha).fit(train)
        p_reg = m.predict(test)
        p = SalaryMultipleModel().fit(train).predict(test)  # MVP 추정기: 구간·연수 평가 대상
        g_med = train.groupby("fa_grade")["total_eok"].median()
        mult = (train["total_eok"] / train["prev_salary_eok"]).groupby(train["fa_grade"]).median()
        cand = {
            "grade_median": test["fa_grade"].map(g_med),
            "salary_mult": test["prev_salary_eok"] * test["fa_grade"].map(mult),
            "regression": p_reg["pred_total_eok"],
        }
        y = test["total_eok"]
        for name, pred in cand.items():
            ape = (pred - y).abs() / y
            rows.append(
                {
                    "market": t,
                    "model": name,
                    "n_train": len(train),
                    "n": len(test),
                    "mdape": float(ape.median()),
                    "mae_eok": float((pred - y).abs().mean()),
                    "log_rmse": float(np.sqrt(((np.log(pred) - np.log(y)) ** 2).mean())),
                }
            )
        cov80 = ((y >= p["p10"]) & (y <= p["p90"])).mean()
        cov50 = ((y >= p["p25"]) & (y <= p["p75"])).mean()
        yrs = (p["pred_years"] - test["years"]).abs() <= 1
        rows[-1].update(
            {"cover80": float(cov80), "cover50": float(cov50), "years_within1": float(yrs.mean())}
        )
        preds.append(test.assign(**{c: p[c] for c in p.columns}))
    return pd.DataFrame(rows), pd.concat(preds)


def main() -> None:
    from db.init_db import default_db_path, init_db

    con = init_db(default_db_path())
    res, preds = run(con)
    pd.set_option("display.width", 200)
    print(res.pivot(index="market", columns="model", values="mdape").round(3))
    print()
    summ = res.groupby("model")[["mdape", "mae_eok", "log_rmse"]].mean().sort_values("log_rmse")
    print(summ.round(3))
    m = res[res.model == "regression"]  # 구간·연수 값은 마지막 행(MVP 추정기 기준)에 기록됨
    print(
        f"\nMVP(salary_mult) 80% 구간 적중 {m.cover80.mean():.3f}, 50% 구간 {m.cover50.mean():.3f}, "
        f"연수 ±1년 {m.years_within1.mean():.3f}"
    )
    print("\n오차 큰 사례 (MVP 추정기):")
    preds["ratio"] = preds["pred_total_eok"] / preds["total_eok"]
    cols = [
        "market_year",
        "player_name",
        "fa_grade",
        "age",
        "prev_salary_eok",
        "total_eok",
        "pred_total_eok",
        "p10",
        "p90",
    ]
    print(
        preds.reindex(
            preds["ratio"].apply(lambda r: abs(np.log(r))).sort_values(ascending=False).index
        )[cols]
        .head(8)
        .round(1)
        .to_string(index=False)
    )
    res.to_csv("evals/reports/backtest_kbo_fa_value.csv", index=False)
    con.close()


if __name__ == "__main__":
    main()
