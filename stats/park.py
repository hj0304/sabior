"""파크팩터 (P1 W3).

지금 지원하는 방법
  - `lahman_bpf`: Lahman Teams.csv 의 BPF(타자 파크팩터, 100 기준, Pete Palmer 방식 3년 평균)를 팀·시즌 단위로 적재한다.
    홈/원정 절반씩을 이미 반영한 값이라 wRC+ 공식의 PF 로 그대로(÷100) 쓴다.
    park_factors.park_id 에는 구장 대신 팀 ID(예: 'MLB_NYA')를 넣는다. 한 시즌 한 팀 = 한 홈구장이라는 근사.
  - KBO: 시즌 합계만으로는 홈/원정 분리가 안 되므로 `basic_1yr` 는 홈·원정 득실점 데이터가 들어오면 추가한다.

사용:
    uv run python -m stats.park --load-lahman
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAHMAN_TEAMS = ROOT / "data" / "raw" / "mlb" / "lahman" / "Teams.csv"
DEFAULT_METHOD = {"MLB": "lahman_bpf", "KBO": "basic_1yr"}


def load_lahman_bpf(con) -> int:
    con.execute(
        f"""
        INSERT OR REPLACE INTO park_factors (league, season, park_id, pf_runs, pf_hr, method, known_at)
        SELECT 'MLB', yearID, 'MLB_' || teamID, BPF / 100.0, NULL, 'lahman_bpf', make_date(yearID, 11, 30)
        FROM read_csv_auto('{LAHMAN_TEAMS.as_posix()}', header=true)
        WHERE BPF IS NOT NULL
        """
    )
    return con.execute("SELECT count(*) FROM park_factors WHERE method = 'lahman_bpf'").fetchone()[
        0
    ]


def team_park_factor(
    con, league: str, team_id: str, season: int, method: str | None = None
) -> float:
    """팀·시즌 파크팩터. 없으면 1.0 (중립)."""
    method = method or DEFAULT_METHOD.get(league, "basic_1yr")
    row = con.execute(
        """
        SELECT pf_runs FROM park_factors_as_of(season_cutoff(?))
        WHERE league = ? AND season = ? AND park_id = ? AND method = ?
        """,
        [season, league, season, team_id, method],
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else 1.0


def player_park_factor(
    con, league: str, player_id: str, season: int, method: str | None = None
) -> float:
    """여러 팀을 거친 선수는 팀별 PA 가중 평균."""
    rows = con.execute(
        """
        SELECT team_id, sum(COALESCE(pa, 0)) FROM batting_as_of(season_cutoff(?))
        WHERE player_id = ? AND season = ? GROUP BY team_id
        """,
        [season, player_id, season],
    ).fetchall()
    total = sum(pa for _, pa in rows)
    if not total:
        return 1.0
    return sum(team_park_factor(con, league, t, season, method) * pa for t, pa in rows) / total


def main() -> None:
    from db.init_db import default_db_path, init_db

    ap = argparse.ArgumentParser()
    ap.add_argument("--load-lahman", action="store_true")
    args = ap.parse_args()
    con = init_db(default_db_path())
    if args.load_lahman:
        print(f"lahman_bpf rows: {load_lahman_bpf(con):,}")
    con.close()


if __name__ == "__main__":
    main()
