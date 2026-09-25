"""FA 금액 추정 테스트. 합성 데이터 단위 테스트 + DB 통합 테스트."""

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from models.fa_value.model import SalaryMultipleModel, market_open


def _synthetic(n=60, seed=0):
    rng = np.random.default_rng(seed)
    grade = rng.choice(["A", "B", "C"], n)
    sal = rng.uniform(1, 6, n)
    mult = pd.Series(grade).map({"A": 15, "B": 9, "C": 5}).to_numpy()
    return pd.DataFrame(
        {
            "fa_grade": grade,
            "prev_salary_eok": sal,
            "age": rng.integers(27, 38, n),
            "total_eok": sal * mult * np.exp(rng.normal(0, 0.3, n)),
            "years": rng.integers(1, 6, n),
            "market_year": 2024,
            "player_name": [f"p{i}" for i in range(n)],
            "years_text": "4",
            "contract_type": "FA",
        }
    )


def test_salary_multiple_recovers_multiples_and_orders_quantiles():
    df = _synthetic()
    m = SalaryMultipleModel().fit(df)
    assert np.exp(m.log_mult["A"]) == pytest.approx(15, rel=0.2)
    assert np.exp(m.log_mult["C"]) == pytest.approx(5, rel=0.2)
    p = m.predict(df.head(5))
    cols = ["p10", "p25", "p50", "p75", "p90"]
    assert (p[cols].diff(axis=1).iloc[:, 1:] > 0).all().all()
    assert p["pred_years"].between(1, 6).all()


def test_market_open():
    assert market_open(2026) == "2025-11-01"


DB = Path(__file__).resolve().parents[1] / "data" / "sabior.duckdb"


@pytest.mark.skipif(not DB.exists(), reason="DB 없음")
def test_training_data_respects_market_open():
    from models.fa_value.model import load_contracts

    con = duckdb.connect(str(DB), read_only=True)
    tr = load_contracts(con, market_open(2026))
    con.close()
    if tr.empty:
        pytest.skip("KBO FA 계약 미적재")
    # 2026 시장(2025-11 개장) 계약은 학습 데이터에 없어야 한다
    assert tr["market_year"].max() <= 2025
    assert (pd.to_datetime(tr["signed_date"]) < "2025-11-01").all()
