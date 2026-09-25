"""KBO FA 계약 규모 추정 MVP (P2 W8).

대상: FA 계약 총액(발표 총액, 옵션 포함)과 연수.
피처 (표본이 시장당 15~20건이라 5개로 제한)
  - log(직전 연봉), 나이, 34세 이상 여부, 등급 A, 등급 B (C 가 기준)
  - 성적 피처(WAR 등)는 야구나라 데이터가 오면 추가한다. 지금은 직전 연봉이 성적의 대리 변수다.
모델: 로그 총액 릿지 회귀. 구간은 학습 잔차(로그)의 경험적 분위. 연수는 나이·등급의 선형 회귀를 1~6 으로 자른다.
입력: contracts_as_of(as_of) 만 읽는다. 시장 t 를 예측할 때는 시장 t 개장 전(t-1 년 11월 1일)까지 발표된 계약만 학습한다.

비교 사례: 학습 계약 중 (등급 같음) 에서 나이·로그 연봉 표준화 거리 기준 가장 가까운 3건.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

EOK = 100_000_000
FEATURES = ["log_salary", "age", "age34", "grade_a", "grade_b"]
QUANTILES = [0.10, 0.25, 0.50, 0.75, 0.90]


def market_open(market_year: int) -> str:
    """시장 t 개장 시점 (t-1 년 11월 1일). 이 날짜 이전 발표 계약만 학습에 쓴다."""
    return f"{market_year - 1}-11-01"


def load_contracts(con, as_of: str, league: str = "KBO") -> pd.DataFrame:
    df = con.execute(
        """
        SELECT contract_id, player_id, team_id, prev_team_id, season_start AS market_year, years, years_text,
               total_amount / 1e8 AS total_eok, prev_salary / 1e8 AS prev_salary_eok, age_at_signing AS age,
               fa_grade, contract_type, signed_date
        FROM contracts_as_of(?::DATE)
        WHERE league = ? AND contract_type IN ('FA', 'FA_RESIGN')
        """,
        [as_of, league],
    ).df()
    df["player_name"] = df["contract_id"].str.split("_").str[3]
    return df


def features(df: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=df.index)
    x["log_salary"] = np.log(df["prev_salary_eok"].clip(lower=0.3))
    x["age"] = df["age"].astype(float)
    x["age34"] = (df["age"] >= 34).astype(float)
    x["grade_a"] = (df["fa_grade"] == "A").astype(float)
    x["grade_b"] = (df["fa_grade"] == "B").astype(float)
    return x


@dataclass
class FAValueModel:
    alpha: float = 1.0
    coef: np.ndarray | None = None
    mu: np.ndarray | None = None
    sd: np.ndarray | None = None
    resid_q: np.ndarray | None = None
    years_coef: np.ndarray | None = None
    train: pd.DataFrame | None = None

    def fit(self, df: pd.DataFrame) -> FAValueModel:
        df = df.dropna(subset=["prev_salary_eok", "age", "fa_grade", "total_eok"]).copy()
        x = features(df)[FEATURES].to_numpy()
        self.mu, self.sd = x.mean(0), x.std(0) + 1e-9
        z = np.c_[np.ones(len(x)), (x - self.mu) / self.sd]
        y = np.log(df["total_eok"].to_numpy())
        reg = self.alpha * np.eye(z.shape[1])
        reg[0, 0] = 0  # 절편은 규제하지 않는다
        self.coef = np.linalg.solve(z.T @ z + reg, z.T @ y)
        resid = y - z @ self.coef
        self.resid_q = np.quantile(resid, QUANTILES)
        # 연수: 나이·등급 선형
        zy = np.c_[np.ones(len(x)), df["age"].to_numpy(), x[:, 3], x[:, 4]]
        self.years_coef = np.linalg.lstsq(zy, df["years"].to_numpy(dtype=float), rcond=None)[0]
        self.train = df
        return self

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        x = features(df)[FEATURES].to_numpy()
        z = np.c_[np.ones(len(x)), (x - self.mu) / self.sd]
        mu = z @ self.coef
        out = pd.DataFrame(index=df.index)
        out["pred_total_eok"] = np.exp(mu + self.resid_q[2])  # 중앙값 기준 점추정
        for q, r in zip(QUANTILES, self.resid_q, strict=True):
            out[f"p{int(q * 100)}"] = np.exp(mu + r)
        zy = np.c_[np.ones(len(x)), df["age"].to_numpy(dtype=float), x[:, 3], x[:, 4]]
        out["pred_years"] = np.clip(np.round(zy @ self.years_coef), 1, 6)
        return out

    def comparables(self, row: pd.Series, k: int = 3) -> pd.DataFrame:
        t = self.train
        same = t[t["fa_grade"] == row["fa_grade"]] if row.get("fa_grade") in ("A", "B", "C") else t
        if len(same) < k:
            same = t
        a = (same["age"] - row["age"]) / 3.0
        s = (np.log(same["prev_salary_eok"]) - np.log(max(row["prev_salary_eok"], 0.3))) / 0.5
        d = np.sqrt(a**2 + s**2)
        cols = [
            "market_year",
            "player_name",
            "fa_grade",
            "age",
            "prev_salary_eok",
            "years_text",
            "total_eok",
            "contract_type",
        ]
        return same.assign(dist=d).nsmallest(k, "dist")[cols]

    def describe(self) -> pd.Series:
        return pd.Series(self.coef, index=["intercept", *FEATURES])


def fit_as_of(con, market_year: int, alpha: float = 1.0) -> FAValueModel:
    return FAValueModel(alpha=alpha).fit(load_contracts(con, market_open(market_year)))


@dataclass
class SalaryMultipleModel:
    """MVP 추정기 (v0). 총액 = 직전 연봉 × 등급별 (총액/연봉) 중앙 배수, 구간 = 학습 로그 잔차의 분위.

    2023~2026 시장 백테스트에서 회귀 모델과 로그 RMSE 가 비슷하고(.966 vs .992) 중앙 오차율은 가장 낮았으며(.474),
    80% 구간 적중률이 명목값에 가장 가까웠다(.782). 성적 피처가 없는 지금은 가장 단순한 이 방식을 쓴다.
    """

    log_mult: pd.Series | None = None
    resid_q: np.ndarray | None = None
    years_coef: np.ndarray | None = None
    train: pd.DataFrame | None = None

    def fit(self, df: pd.DataFrame) -> SalaryMultipleModel:
        df = df.dropna(subset=["prev_salary_eok", "age", "fa_grade", "total_eok"]).copy()
        lm = np.log(df["total_eok"] / df["prev_salary_eok"])
        self.log_mult = lm.groupby(df["fa_grade"]).median()
        self.resid_q = np.quantile(lm - df["fa_grade"].map(self.log_mult), QUANTILES)
        x = features(df)
        zy = np.c_[np.ones(len(df)), df["age"].to_numpy(dtype=float), x["grade_a"], x["grade_b"]]
        self.years_coef = np.linalg.lstsq(zy, df["years"].to_numpy(dtype=float), rcond=None)[0]
        self.train = df
        return self

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        base = np.log(df["prev_salary_eok"].clip(lower=0.3)) + df["fa_grade"].map(
            self.log_mult
        ).fillna(self.log_mult.median())
        out = pd.DataFrame(index=df.index)
        out["pred_total_eok"] = np.exp(base + self.resid_q[2])
        for q, r in zip(QUANTILES, self.resid_q, strict=True):
            out[f"p{int(q * 100)}"] = np.exp(base + r)
        x = features(df)
        zy = np.c_[np.ones(len(df)), df["age"].to_numpy(dtype=float), x["grade_a"], x["grade_b"]]
        out["pred_years"] = np.clip(np.round(zy @ self.years_coef), 1, 6)
        return out

    comparables = FAValueModel.comparables


def estimate(con, market_year: int, fa_grade: str, age: int, prev_salary_eok: float) -> dict:
    """에이전트·웹용 단건 추정. 시장 개장 전 데이터로 학습한 MVP 추정기를 쓴다."""
    m = SalaryMultipleModel().fit(load_contracts(con, market_open(market_year)))
    row = pd.DataFrame([{"fa_grade": fa_grade, "age": age, "prev_salary_eok": prev_salary_eok}])
    p = m.predict(row).iloc[0]
    comps = m.comparables(row.iloc[0])
    return {
        "market_year": market_year,
        "total_eok": {k: round(float(p[k]), 1) for k in ["p10", "p25", "p50", "p75", "p90"]},
        "years": int(p["pred_years"]),
        "comparables": comps.round(1).to_dict(orient="records"),
        "n_train": len(m.train),
        "model_version": "fa_value_salary_mult_v0",
        "caveat": "성적 피처 없음. 시장에서 외면받는 1년 소액 계약(34세 이상 18%)은 구간 하단보다 낮게 나올 수 있다.",
    }
