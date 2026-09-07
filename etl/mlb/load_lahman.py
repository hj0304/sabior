"""Lahman CSV 를 sabior 스키마(league='MLB')로 적재한다.

- 이닝: Lahman 의 IPouts 를 ip_outs 로 그대로 사용
- PA: Lahman 에 없어 AB+BB+HBP+SF+SH 로 계산
- known_at: 해당 시즌 11-30 (보수적 시즌 종료 시점)
- ID: 'MLB_' + playerID / teamID
- team_seasons.home_park_id 에는 Lahman 의 park 이름 문자열이 들어간다 (parks 테이블 정규화는 W3)

사용: uv run python etl/mlb/load_lahman.py
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from db.init_db import default_db_path, init_db

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "mlb" / "lahman"
KNOWN_AT = "make_date(yearID, 11, 30)"


def _csv(name: str) -> str:
    path = RAW / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} 없음. 먼저 etl/mlb/download_lahman.py 를 실행하세요.")
    return f"read_csv_auto('{path.as_posix()}', header=true)"


def load(con) -> dict[str, int]:
    people, batting, pitching, fielding, teams = (
        _csv("People"),
        _csv("Batting"),
        _csv("Pitching"),
        _csv("Fielding"),
        _csv("Teams"),
    )
    counts: dict[str, int] = {}

    con.execute(
        f"""
        INSERT OR REPLACE INTO players
        SELECT 'MLB_' || playerID, 'MLB',
               nameFirst || ' ' || nameLast, nameFirst || ' ' || nameLast,
               CASE WHEN birthYear IS NULL OR birthMonth IS NULL OR birthDay IS NULL THEN NULL
                    ELSE TRY_CAST(birthYear || '-' || lpad(birthMonth::VARCHAR, 2, '0') || '-'
                                  || lpad(birthDay::VARCHAR, 2, '0') AS DATE) END,
               bats, throws, NULL,
               TRY_CAST(substr(debut, 1, 4) AS INTEGER), TRY_CAST(substr(finalGame, 1, 4) AS INTEGER)
        FROM {people}
        """
    )
    con.execute(
        f"""
        INSERT OR REPLACE INTO player_external_ids
        SELECT 'MLB_' || playerID, 'lahman', playerID FROM {people}
        UNION ALL
        SELECT 'MLB_' || playerID, 'bbref', bbrefID FROM {people} WHERE bbrefID IS NOT NULL
        """
    )
    counts["players"] = con.execute(
        "SELECT count(*) FROM players WHERE league_origin = 'MLB'"
    ).fetchone()[0]

    con.execute(
        f"""
        INSERT OR REPLACE INTO teams
        SELECT 'MLB_' || teamID, 'MLB', name, teamID, NULL, founded, TRUE
        FROM (
            SELECT teamID, name,
                   min(yearID) OVER (PARTITION BY teamID) AS founded,
                   row_number() OVER (PARTITION BY teamID ORDER BY yearID DESC) AS rn
            FROM {teams}
        ) WHERE rn = 1
        """
    )
    con.execute(
        f"""
        INSERT OR REPLACE INTO team_seasons
        SELECT 'MLB', yearID, 'MLB_' || teamID, G, W, L, 0, R, RA, park, Rank,
               CASE WHEN WSWin = 'Y' THEN 'WS_WIN'
                    WHEN LgWin = 'Y' THEN 'WS_LOSE'
                    WHEN DivWin = 'Y' OR WCWin = 'Y' THEN 'PO' END,
               {KNOWN_AT}
        FROM {teams}
        """
    )
    counts["team_seasons"] = con.execute(
        "SELECT count(*) FROM team_seasons WHERE league = 'MLB'"
    ).fetchone()[0]

    con.execute(
        f"""
        INSERT OR REPLACE INTO batting_seasons
        SELECT 'MLB', yearID, 'MLB_' || playerID, 'MLB_' || teamID, stint,
               G, COALESCE(AB, 0) + COALESCE(BB, 0) + COALESCE(HBP, 0) + COALESCE(SF, 0) + COALESCE(SH, 0),
               AB, R, H, "2B", "3B", HR, RBI, SB, CS, BB, IBB, SO, HBP, SF, SH, GIDP,
               {KNOWN_AT}
        FROM {batting}
        """
    )
    counts["batting_seasons"] = con.execute(
        "SELECT count(*) FROM batting_seasons WHERE league = 'MLB'"
    ).fetchone()[0]

    con.execute(
        f"""
        INSERT OR REPLACE INTO pitching_seasons
        SELECT 'MLB', yearID, 'MLB_' || playerID, 'MLB_' || teamID, stint,
               G, GS, W, L, SV, NULL, CG, SHO, IPouts, BFP, H, R, ER, HR, BB, IBB, SO, HBP, WP, BK,
               {KNOWN_AT}
        FROM {pitching}
        """
    )
    counts["pitching_seasons"] = con.execute(
        "SELECT count(*) FROM pitching_seasons WHERE league = 'MLB'"
    ).fetchone()[0]

    con.execute(
        f"""
        INSERT OR REPLACE INTO fielding_seasons
        SELECT 'MLB', yearID, 'MLB_' || playerID, 'MLB_' || teamID, stint, POS,
               G, GS, InnOuts, PO, A, E, DP, PB, {KNOWN_AT}
        FROM {fielding}
        """
    )
    counts["fielding_seasons"] = con.execute(
        "SELECT count(*) FROM fielding_seasons WHERE league = 'MLB'"
    ).fetchone()[0]
    return counts


def main() -> None:
    con = init_db(default_db_path())
    run_id = str(uuid.uuid4())
    con.execute(
        "INSERT INTO ingest_log VALUES (?, 'lahman', ?, NULL, NULL, 'running', NULL)",
        [run_id, datetime.now()],
    )
    try:
        counts = load(con)
        con.execute(
            "UPDATE ingest_log SET finished_at = ?, rows = ?, status = 'ok', notes = ? WHERE run_id = ?",
            [datetime.now(), sum(counts.values()), str(counts), run_id],
        )
        for k, v in counts.items():
            print(f"{k:20s} {v:>10,d}")
    except Exception as e:
        con.execute(
            "UPDATE ingest_log SET finished_at = ?, status = 'failed', notes = ? WHERE run_id = ?",
            [datetime.now(), str(e)[:500], run_id],
        )
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
