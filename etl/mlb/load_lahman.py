"""Lahman CSV 를 sabior 스키마(league='MLB', source='lahman')로 적재한다.

- 이닝: Lahman 의 IPouts 를 ip_outs 로 그대로 사용
- PA: Lahman 에 없어 AB+BB+HBP+SF+SH 로 계산
- known_at: 해당 시즌 11-30 (보수적 시즌 종료 시점)
- ID: 'MLB_' + playerID / teamID
- team_seasons.home_park_id 에는 Lahman 의 park 이름 문자열이 들어간다 (parks 테이블 정규화는 W3)
- 파일 위치: data/raw/mlb/lahman/*.csv (SABR 배포판 zip 의 core/ 또는 최상위 CSV 를 그대로 복사)

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
SOURCE = "lahman"


def _csv(name: str) -> str:
    path = RAW / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} 없음. SABR Lahman CSV 를 data/raw/mlb/lahman/ 에 두세요.")
    return f"read_csv_auto('{path.as_posix()}', header=true)"


def _count(con, table: str) -> int:
    return con.execute(f"SELECT count(*) FROM {table} WHERE source = '{SOURCE}'").fetchone()[0]


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
            (player_id, league_origin, name, name_en, birth_date, bats, throws, primary_pos,
             debut_season, final_season, source)
        SELECT 'MLB_' || playerID, 'MLB',
               COALESCE(NULLIF(trim(concat_ws(' ', nameFirst, nameLast)), ''), playerID),
               COALESCE(NULLIF(trim(concat_ws(' ', nameFirst, nameLast)), ''), playerID),
               CASE WHEN birthYear IS NULL OR birthMonth IS NULL OR birthDay IS NULL THEN NULL
                    ELSE TRY_CAST(birthYear || '-' || lpad(birthMonth::VARCHAR, 2, '0') || '-'
                                  || lpad(birthDay::VARCHAR, 2, '0') AS DATE) END,
               bats, throws, NULL,
               TRY_CAST(substr(CAST(debut AS VARCHAR), 1, 4) AS INTEGER),
               TRY_CAST(substr(CAST(finalGame AS VARCHAR), 1, 4) AS INTEGER),
               '{SOURCE}'
        FROM {people}
        """
    )
    con.execute(
        f"""
        INSERT OR REPLACE INTO player_external_ids (player_id, source, source_id)
        SELECT 'MLB_' || playerID, 'lahman', playerID FROM {people}
        UNION ALL
        SELECT 'MLB_' || playerID, 'bbref', bbrefID FROM {people} WHERE bbrefID IS NOT NULL
        """
    )
    counts["players"] = _count(con, "players")

    con.execute(
        f"""
        INSERT OR REPLACE INTO teams (team_id, league, name, short_name, city, founded, active)
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
            (league, season, team_id, games, wins, losses, ties, runs_scored, runs_allowed,
             home_park_id, final_rank, postseason, known_at, source, sub_league, division)
        SELECT 'MLB', yearID, 'MLB_' || teamID, G, W, L, 0, R, RA, park, Rank,
               CASE WHEN WSWin = 'Y' THEN 'WS_WIN'
                    WHEN LgWin = 'Y' THEN 'WS_LOSE'
                    WHEN DivWin = 'Y' OR WCWin = 'Y' THEN 'PO' END,
               {KNOWN_AT}, '{SOURCE}', lgID, divID
        FROM {teams}
        """
    )
    counts["team_seasons"] = _count(con, "team_seasons")

    con.execute(
        f"""
        INSERT OR REPLACE INTO batting_seasons
            (league, season, player_id, team_id, stint, g, pa, ab, r, h, doubles, triples, hr, rbi,
             sb, cs, bb, ibb, so, hbp, sf, sh, gidp, known_at, source)
        SELECT 'MLB', yearID, 'MLB_' || playerID, 'MLB_' || teamID, stint,
               G, COALESCE(AB, 0) + COALESCE(BB, 0) + COALESCE(HBP, 0) + COALESCE(SF, 0) + COALESCE(SH, 0),
               AB, R, H, "2B", "3B", HR, RBI, SB, CS, BB, IBB, SO, HBP, SF, SH, GIDP,
               {KNOWN_AT}, '{SOURCE}'
        FROM {batting}
        """
    )
    counts["batting_seasons"] = _count(con, "batting_seasons")

    con.execute(
        f"""
        INSERT OR REPLACE INTO pitching_seasons
            (league, season, player_id, team_id, stint, g, gs, w, l, sv, hld, cg, sho, ip_outs, bf,
             h, r, er, hr, bb, ibb, so, hbp, wp, bk, known_at, source)
        SELECT 'MLB', yearID, 'MLB_' || playerID, 'MLB_' || teamID, stint,
               G, GS, W, L, SV, NULL, CG, SHO, IPouts, BFP, H, R, ER, HR, BB, IBB, SO, HBP, WP, BK,
               {KNOWN_AT}, '{SOURCE}'
        FROM {pitching}
        """
    )
    counts["pitching_seasons"] = _count(con, "pitching_seasons")

    con.execute(
        f"""
        INSERT OR REPLACE INTO fielding_seasons
            (league, season, player_id, team_id, stint, pos, g, gs, inn_outs, po, a, e, dp, pb,
             known_at, source)
        SELECT 'MLB', yearID, 'MLB_' || playerID, 'MLB_' || teamID, stint, POS,
               G, GS, InnOuts, PO, A, E, DP, PB, {KNOWN_AT}, '{SOURCE}'
        FROM {fielding}
        """
    )
    counts["fielding_seasons"] = _count(con, "fielding_seasons")
    return counts


def main() -> None:
    con = init_db(default_db_path())
    run_id = str(uuid.uuid4())
    con.execute(
        "INSERT INTO ingest_log VALUES (?, ?, ?, NULL, NULL, 'running', NULL)",
        [run_id, SOURCE, datetime.now()],
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
