"""Marcel+ : Marcel 을 이벤트 그룹별 회귀 강도·시즌 가중치로 일반화한 타자 예측 (P2 W6, 모델 v1 후보).

바꾼 점 (Marcel 대비)
  - 회귀 타석을 이벤트 그룹별로 둔다. 삼진·볼넷처럼 빨리 안정되는 이벤트는 적게, 단타(BABIP 영향)는 많이 회귀.
      k_bb  : so, ubb, ibb, hbp
      power : hr, d, t
      contact : s1
      misc  : sf, sh
  - 시즌 가중치와 나이 보정 계수도 파라미터로 둔다.
  - 파라미터는 학습 시즌(기본 2011~2019)의 백테스트 RMSE 로만 고르고, 평가 시즌(2021~2025)은 건드리지 않는다.

입력 캐시: 같은 target 을 여러 파라미터로 평가하므로 as_of 조회 결과를 target 별로 한 번만 읽는다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import numpy as np
import pandas as pd

from models.projection.marcel import EVENTS, GOOD, _add_events, _history, woba_from_rates
from stats.constants import load_constants

GROUPS = {
    "k_bb": ["so", "ubb", "ibb", "hbp"],
    "power": ["hr", "d", "t"],
    "contact": ["s1"],
    "misc": ["sf", "sh"],
}


@dataclass(frozen=True)
class Params:
    w1: float = 5.0
    w2: float = 4.0
    w3: float = 3.0
    r_k_bb: float = 1200.0
    r_power: float = 1200.0
    r_contact: float = 1200.0
    r_misc: float = 1200.0
    age_peak: float = 29.0
    age_young: float = 0.006
    age_old: float = 0.003
    # 표본이 적은 선수는 리그 평균보다 약하다 (출장 시간 자체가 실력 신호). 좋은 이벤트의 회귀 목표를
    # (1 - low_pen × (1 - 신뢰도)) 배로 낮춘다. 신뢰도 = 가중 PA / (가중 PA + 1200). 0 이면 Marcel 과 같다.
    low_pen: float = 0.0

    def regress(self) -> dict[str, float]:
        out = {}
        for g, evs in GROUPS.items():
            for e in evs:
                out[e] = getattr(self, f"r_{g}")
        return out


MARCEL = Params()


def load_params(name: str = "marcel_plus_mlb_v1") -> Params:
    import json
    from pathlib import Path

    d = json.loads(
        (Path(__file__).with_name("params") / f"{name}.json").read_text(encoding="utf-8")
    )
    return Params(**{k: v for k, v in d.items() if not k.startswith("_")})


class Inputs:
    """target 시즌 예측에 필요한 as_of 입력 묶음 (누출 없음: 전부 season_cutoff(target-1) 기준)."""

    def __init__(self, con, league: str, target: int):
        hist = _add_events(_history(con, league, target))
        hist["ago"] = target - hist["season"]
        self.hist = hist
        ids = list(hist["player_id"].unique())
        births = (
            con.execute(
                "SELECT player_id, birth_date FROM players WHERE player_id IN (SELECT unnest(?::VARCHAR[]))",
                [ids],
            )
            .df()
            .set_index("player_id")["birth_date"]
        )
        self.age = (
            (pd.Timestamp(f"{target}-07-01") - pd.to_datetime(births.reindex(ids))).dt.days / 365.25
        ).fillna(29.0)
        self.constants = load_constants(con, league, target - 1)
        self.target = target


_CACHE: dict[tuple, Inputs] = {}


def inputs(con, league: str, target: int) -> Inputs:
    key = (id(con), league, target)
    if key not in _CACHE:
        _CACHE[key] = Inputs(con, league, target)
    return _CACHE[key]


def compute(inp: Inputs, p: Params) -> pd.DataFrame:
    hist = inp.hist
    w = hist["ago"].map({1: p.w1, 2: p.w2, 3: p.w3})
    pos = hist[~hist["is_pitcher"]]
    wpos = pos["ago"].map({1: p.w1, 2: p.w2, 3: p.w3})
    lg = pos[["pa", *EVENTS]].mul(wpos, axis=0).sum()
    lg_rate = lg[EVENTS] / lg["pa"]

    weighted = hist[["pa", *EVENTS]].mul(w, axis=0)
    weighted["player_id"] = hist["player_id"]
    agg = weighted.groupby("player_id").sum()

    reg = pd.Series(p.regress())
    rel = agg["pa"] / (agg["pa"] + 1200.0)
    target_mult = 1 - p.low_pen * (1 - rel)
    rates = pd.DataFrame(index=agg.index)
    for e in EVENTS:
        tgt = lg_rate[e] * (target_mult if e in GOOD else 1.0)
        rates[e] = (agg[e] + reg[e] * tgt) / (agg["pa"] + reg[e])

    age = inp.age.reindex(agg.index).fillna(29.0)
    adj = (p.age_peak - age).clip(lower=0) * p.age_young - (age - p.age_peak).clip(
        lower=0
    ) * p.age_old
    for e in GOOD:
        rates[e] = rates[e] * (1 + adj)

    out = rates
    out["proj_woba"] = woba_from_rates(rates, inp.constants)
    out["w_pa"] = agg["pa"]
    return out


def project(con, league: str, target: int, p: Params = MARCEL) -> pd.DataFrame:
    return compute(inputs(con, league, target), p).reset_index()


# ---------------------------------------------------------------- 학습 (좌표 하강)

GRID = {
    "low_pen": [0.0, 0.03, 0.06, 0.10, 0.15],
    "r_k_bb": [300, 600, 1200, 1800, 2600],
    "r_power": [700, 1200, 1800, 2600, 3600],
    "r_contact": [1200, 1800, 2600, 3600, 5000],
    "r_misc": [600, 1200, 2400],
    "w1": [5.0, 6.0, 7.0],
    "w3": [1.0, 2.0, 3.0],
    "age_old": [0.002, 0.003, 0.005],
    "age_young": [0.004, 0.006, 0.009],
}


class Evaluator:
    def __init__(self, con, league: str, seasons: list[int], min_pa: int = 300):
        from backtest.harness import eligible

        self.con, self.league, self.seasons = con, league, seasons
        self.act = {t: eligible(con, league, t, min_pa) for t in seasons}
        self.inp = {t: inputs(con, league, t) for t in seasons}

    def rmse(self, p: Params) -> float:
        vals = []
        for t in self.seasons:
            act = self.act[t]
            if act.empty:
                continue
            pred = compute(self.inp[t], p)["proj_woba"].reindex(act.index)
            pred = pred.fillna(self.inp[t].constants.lg_woba)
            err = pred - act["woba"]
            vals.append(np.sqrt((act["pa"] * err**2).sum() / act["pa"].sum()))
        return float(np.mean(vals))


def fit(
    con, league: str, train: list[int], rounds: int = 3, verbose: bool = True
) -> tuple[Params, float]:
    ev = Evaluator(con, league, train)
    best = MARCEL
    best_score = ev.rmse(best)
    if verbose:
        print(f"start (Marcel) train RMSE {best_score:.5f}")
    for r in range(rounds):
        improved = False
        for name, values in GRID.items():
            for v in values:
                cand = replace(best, **{name: float(v)})
                s = ev.rmse(cand)
                if s < best_score - 1e-7:
                    best, best_score, improved = cand, s, True
            if verbose:
                print(f"  round {r + 1} {name:10s} -> {getattr(best, name):>7} | {best_score:.5f}")
        if not improved:
            break
    return best, best_score


def main() -> None:
    import argparse
    import json

    from db.init_db import default_db_path, init_db

    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="MLB")
    ap.add_argument("--train", default="2011-2019")
    ap.add_argument("--test", default="2021-2025")
    a = ap.parse_args()
    rng = lambda s: list(range(int(s.split("-")[0]), int(s.split("-")[1]) + 1))  # noqa: E731
    con = init_db(default_db_path())
    params, train_score = fit(con, a.league, rng(a.train))
    test = Evaluator(con, a.league, rng(a.test))
    base = test.rmse(MARCEL)
    new = test.rmse(params)
    print("\nparams:", json.dumps(asdict(params), ensure_ascii=False))
    print(f"test {a.test}: Marcel {base:.5f} -> Marcel+ {new:.5f} ({(new / base - 1) * 100:+.1f}%)")
    con.close()


if __name__ == "__main__":
    main()
