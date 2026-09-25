"""팀 성적 예측 (P2 W7). 선수 예측 → 팀 득실점 → Pythagenpat 승률 → 몬테카를로 승수·순위·포스트시즌 확률.

흐름 (목표 시즌 t, 입력은 season_cutoff(t-1) 시점만)
  1. 선수 예측: 타자 Marcel+ (wOBA), 투수 Marcel (FIP).
  2. 출장 분배(roster_mode)
       - prior_roster : t-1 시즌 소속팀 기준, 타석·이닝 비중 = Marcel 예상 PA·IP. 누출 없음. 오프시즌 이적 미반영.
       - actual_usage : t 시즌 실제 팀별 PA·IP 분배. 출장 시간이 누출되므로 "예측 성능만 떼어 보는" 평가용.
       - user         : 호출자가 준 로스터 (웹·에이전트용. KBO FA 영입 가정 등)
  3. 팀 득점 = 팀 타석 × (lgR/PA + (팀 wOBA − lg wOBA) / wOBA scale)
     팀 실점 = 팀 이닝 × 팀 FIP / 9 × (lg 실점 / lg 자책)
     리그 평균 득점·실점이 t-1 리그 경기당 득점 × 경기 수가 되도록 정규화한다 (득점 환경 수준 제거).
  4. 승률 = Pythagenpat (지수 = ((RS+RA)/G)^0.287), 리그 평균 .500 으로 맞춘다.
  5. 몬테카를로: 시즌마다 팀 실력 오차 N(0, σ) 를 더하고 승수 ~ Binomial(G, p). σ 는 직전 시즌들의 예측 잔차에서
     이항 잡음을 뺀 값 (호출자가 주입, 기본 0.035).
  6. 순위는 sub_league(MLB AL/NL, KBO 는 리그 전체)별. 포스트시즌은 sub_league 별 상위 k 팀 (지구 우승 규정 무시 근사).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from models.projection import marcel_pitching, marcel_plus
from stats.constants import load_constants

REPLACEMENT_WOBA_GAP = 0.025  # 예측이 없는 타자(신인 등): 리그 wOBA − 0.025
REPLACEMENT_FIP_GAP = 0.60  # 예측이 없는 투수: 리그 ERA + 0.60


def postseason_slots(league: str, season: int) -> int:
    """sub_league 당 포스트시즌 진출 팀 수."""
    if league == "KBO":
        return 5 if season >= 2015 else 4
    if season == 2020:
        return 8
    if season >= 2022:
        return 6
    if season >= 2012:
        return 5
    return 4


def league_env(con, league: str, season: int) -> dict:
    """season 시즌 리그 환경 (팀 평균 타석·이닝·득점, R/ER). 투수 타석 제외."""
    b = con.execute(
        """
        WITH p AS (SELECT player_id, sum(COALESCE(g,0)) pg FROM pitching_as_of(season_cutoff(?))
                   WHERE league = ? AND season = ? GROUP BY player_id),
             b AS (SELECT player_id, sum(COALESCE(g,0)) g, sum(COALESCE(pa,0)) pa
                   FROM batting_as_of(season_cutoff(?)) WHERE league = ? AND season = ? GROUP BY player_id)
        SELECT sum(b.pa) FROM b LEFT JOIN p USING (player_id) WHERE COALESCE(p.pg, 0) < b.g / 2.0
        """,
        [season, league, season] * 2,
    ).fetchone()[0]
    t = con.execute(
        """
        SELECT count(*), sum(games), sum(runs_scored) FROM team_seasons_as_of(season_cutoff(?))
        WHERE league = ? AND season = ?
        """,
        [season, league, season],
    ).fetchone()
    p = con.execute(
        "SELECT sum(ip_outs), sum(r), sum(er) FROM pitching_as_of(season_cutoff(?)) WHERE league = ? AND season = ?",
        [season, league, season],
    ).fetchone()
    n_teams, games, runs = t
    return {
        "team_pa_per_g": b / games,
        "team_ip_per_g": p[0] / 3 / games,
        "runs_per_team_g": runs / games,
        "r_per_er": p[1] / p[2],
        "n_teams": n_teams,
    }


def _usage(con, league: str, season: int, kind: str) -> pd.DataFrame:
    """실제 출장 분배 (player_id, team_id, weight). kind = 'bat' (PA, 투수 제외) | 'pit' (IP)."""
    if kind == "bat":
        return con.execute(
            """
            WITH p AS (SELECT player_id, sum(COALESCE(g,0)) pg FROM pitching_as_of(season_cutoff(?))
                       WHERE league = ? AND season = ? GROUP BY player_id),
                 tot AS (SELECT player_id, sum(COALESCE(g,0)) g FROM batting_as_of(season_cutoff(?))
                         WHERE league = ? AND season = ? GROUP BY player_id)
            SELECT b.player_id, b.team_id, sum(COALESCE(b.pa,0)) AS weight
            FROM batting_as_of(season_cutoff(?)) b
            JOIN tot USING (player_id) LEFT JOIN p USING (player_id)
            WHERE b.league = ? AND b.season = ? AND COALESCE(p.pg, 0) < tot.g / 2.0
            GROUP BY b.player_id, b.team_id
            """,
            [season, league, season] * 3,
        ).df()
    return con.execute(
        """
        SELECT player_id, team_id, sum(COALESCE(ip_outs,0)) / 3.0 AS weight
        FROM pitching_as_of(season_cutoff(?)) WHERE league = ? AND season = ?
        GROUP BY player_id, team_id
        """,
        [season, league, season],
    ).df()


def _main_team(usage: pd.DataFrame) -> pd.DataFrame:
    """선수별 비중이 가장 큰 팀 하나."""
    return usage.sort_values("weight", ascending=False).drop_duplicates("player_id")[
        ["player_id", "team_id"]
    ]


def build_usage(
    con, league: str, target: int, mode: str, bat_proj, pit_proj
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if mode == "actual_usage":
        return _usage(con, league, target, "bat"), _usage(con, league, target, "pit")
    if mode == "prior_roster":
        bt = _main_team(_usage(con, league, target - 1, "bat")).merge(
            bat_proj[["player_id", "proj_pa"]], on="player_id"
        )
        pt = _main_team(_usage(con, league, target - 1, "pit")).merge(
            pit_proj[["player_id", "proj_ip"]], on="player_id"
        )
        return bt.rename(columns={"proj_pa": "weight"}), pt.rename(columns={"proj_ip": "weight"})
    raise ValueError(mode)


def team_strength(
    con, league: str, target: int, mode: str = "prior_roster", bat_usage=None, pit_usage=None
) -> pd.DataFrame:
    """팀별 예측 득점·실점·기대 승률. bat_usage/pit_usage 를 주면 mode='user'."""
    c = load_constants(con, league, target - 1)
    env = league_env(con, league, target - 1)
    bp = marcel_plus.project(con, league, target, marcel_plus.load_params())
    bp["proj_pa"] = marcel_plus_pa(con, league, target, bp)
    pp = marcel_pitching.project(con, league, target)
    if bat_usage is None:
        bat_usage, pit_usage = build_usage(con, league, target, mode, bp, pp)
    else:
        mode = "user"

    bu = bat_usage.merge(bp[["player_id", "proj_woba"]], on="player_id", how="left")
    bu["proj_woba"] = bu["proj_woba"].fillna(c.lg_woba - REPLACEMENT_WOBA_GAP)
    pu = pit_usage.merge(pp[["player_id", "proj_fip"]], on="player_id", how="left")
    pu["proj_fip"] = pu["proj_fip"].fillna(c.lg_era + REPLACEMENT_FIP_GAP)

    tw = bu.groupby("team_id").apply(
        lambda d: np.average(d["proj_woba"], weights=d["weight"]), include_groups=False
    )
    tf = pu.groupby("team_id").apply(
        lambda d: np.average(d["proj_fip"], weights=d["weight"]), include_groups=False
    )

    teams = con.execute(
        """
        SELECT team_id, games, sub_league, division FROM team_seasons_as_of(season_cutoff(?))
        WHERE league = ? AND season = ?
        """,
        [target, league, target],
    ).df()
    if teams.empty:  # 목표 시즌 일정이 아직 없으면 t-1 팀 목록과 경기 수를 쓴다
        teams = con.execute(
            """
            SELECT team_id, games, sub_league, division FROM team_seasons_as_of(season_cutoff(?))
            WHERE league = ? AND season = ?
            """,
            [target - 1, league, target - 1],
        ).df()
    df = teams.set_index("team_id")
    df["team_woba"] = tw.reindex(df.index).fillna(c.lg_woba)
    df["team_fip"] = tf.reindex(df.index).fillna(c.lg_era)
    g = df["games"]
    rs = env["team_pa_per_g"] * g * (c.lg_r_per_pa + (df["team_woba"] - c.lg_woba) / c.woba_scale)
    ra = env["team_ip_per_g"] * g * df["team_fip"] / 9 * env["r_per_er"]
    target_runs = env["runs_per_team_g"] * g
    df["proj_rs"] = rs * target_runs.mean() / rs.mean()
    df["proj_ra"] = ra * target_runs.mean() / ra.mean()
    x = ((df["proj_rs"] + df["proj_ra"]) / g) ** 0.287
    wp = df["proj_rs"] ** x / (df["proj_rs"] ** x + df["proj_ra"] ** x)
    df["exp_wpct"] = wp - (wp.mean() - 0.5)
    df["exp_wins"] = df["exp_wpct"] * g
    df["roster_mode"] = mode
    return df.reset_index()


def marcel_plus_pa(con, league: str, target: int, bp: pd.DataFrame) -> pd.Series:
    """Marcel 예상 타석 (0.5·PA(t-1) + 0.1·PA(t-2) + 200). Marcel+ 는 타석을 따로 내지 않아 Marcel 식을 쓴다."""
    from models.projection import marcel

    m = marcel.project(con, league, target).set_index("player_id")["proj_pa"]
    return bp["player_id"].map(m).fillna(200.0).to_numpy()


def simulate(
    strength: pd.DataFrame,
    league: str,
    season: int,
    sigma: float = 0.035,
    n_sims: int = 10000,
    seed: int = 0,
) -> pd.DataFrame:
    """몬테카를로. 반환: 팀별 승수 분위, 포스트시즌 확률, 순위 확률(JSON 용 dict)."""
    rng = np.random.default_rng(seed)
    s = strength.reset_index(drop=True)
    n = len(s)
    g = s["games"].to_numpy()
    p = s["exp_wpct"].to_numpy()
    talent = np.clip(p[None, :] + rng.normal(0, sigma, (n_sims, n)), 0.2, 0.8)
    wins = rng.binomial(g[None, :].repeat(n_sims, 0), talent).astype(float)
    wins_tb = wins + rng.random((n_sims, n)) * 1e-3  # 동률 무작위 처리

    groups = s["sub_league"].fillna("ALL").to_numpy()
    k = postseason_slots(league, season)
    ranks = np.zeros_like(wins, dtype=int)
    for grp in np.unique(groups):
        idx = np.where(groups == grp)[0]
        order = np.argsort(-wins_tb[:, idx], axis=1)
        r = np.empty_like(order)
        np.put_along_axis(r, order, np.arange(1, len(idx) + 1)[None, :].repeat(n_sims, 0), axis=1)
        ranks[:, idx] = r
    out = s[["team_id", "sub_league", "games", "proj_rs", "proj_ra", "exp_wpct", "exp_wins"]].copy()
    for q in (10, 25, 50, 75, 90):
        out[f"wins_p{q}"] = np.percentile(wins, q, axis=0)
    out["postseason_prob"] = (ranks <= k).mean(axis=0)
    out["rank_probs"] = [
        {
            int(r): float((ranks[:, j] == r).mean())
            for r in range(1, (groups == groups[j]).sum() + 1)
        }
        for j in range(n)
    ]
    out["sigma"] = sigma
    return out


MODEL_VERSION = "team_sim_v1"


def store(con, league: str, season: int, sim: pd.DataFrame, as_of: str, mode: str) -> int:
    """simulate() 결과를 team_sim_results 에 저장한다 (에이전트·웹이 읽는 배치 산출물)."""
    import json

    for r in sim.itertuples(index=False):
        con.execute(
            """
            INSERT OR REPLACE INTO team_sim_results
                (league, season, team_id, model_version, as_of, roster_mode, proj_rs, proj_ra, exp_wpct,
                 exp_wins, wins_p10, wins_p25, wins_p50, wins_p75, wins_p90, postseason_prob, rank_probs,
                 assumptions)
            VALUES (?, ?, ?, ?, ?::DATE, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                league,
                season,
                r.team_id,
                MODEL_VERSION,
                as_of,
                mode,
                r.proj_rs,
                r.proj_ra,
                r.exp_wpct,
                r.exp_wins,
                r.wins_p10,
                r.wins_p25,
                r.wins_p50,
                r.wins_p75,
                r.wins_p90,
                r.postseason_prob,
                json.dumps(r.rank_probs),
                json.dumps(
                    {
                        "sigma": r.sigma,
                        "roster_mode": mode,
                        "note": "전년 로스터 + Marcel 예상 출장",
                    }
                ),
            ],
        )
    return len(sim)


def main() -> None:
    import argparse

    from db.init_db import default_db_path, init_db

    ap = argparse.ArgumentParser(description="팀 시즌 예측 (전년 로스터 기준)")
    ap.add_argument("--league", default="MLB")
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument(
        "--sigma", type=float, default=0.055, help="팀 실력 오차 σ (MLB 최근 백테스트 0.055~0.059)"
    )
    ap.add_argument("--store", action="store_true", help="team_sim_results 에 저장")
    a = ap.parse_args()
    con = init_db(default_db_path())
    st = team_strength(con, a.league, a.season, "prior_roster")
    sim = simulate(st, a.league, a.season, sigma=a.sigma).sort_values("exp_wins", ascending=False)
    names = dict(con.execute("SELECT team_id, name FROM teams").fetchall())
    for r in sim.itertuples(index=False):
        print(
            f"{names.get(r.team_id, r.team_id):<24s} {r.sub_league or '':3s} RS {r.proj_rs:5.0f} RA {r.proj_ra:5.0f}"
            f"  기대 {r.exp_wins:5.1f}승 (80%: {r.wins_p10:.0f}~{r.wins_p90:.0f})  PS {r.postseason_prob:5.1%}"
        )
    if a.store:
        n = store(con, a.league, a.season, sim, f"{a.season - 1}-12-31", "prior_roster")
        print(f"\nteam_sim_results 에 {n} 팀 저장")
    con.close()


if __name__ == "__main__":
    main()
