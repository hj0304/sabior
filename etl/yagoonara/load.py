"""야구나라 파일을 sabior 스키마로 적재한다. 매핑은 mapping.yaml.

사용:
    uv run python -m etl.yagoonara.load --dir data/raw/yagoonara/2026-09-20 --dry-run
    uv run python -m etl.yagoonara.load --dir data/raw/yagoonara/2026-09-20

동작:
  1. mapping.yaml 을 읽어 섹션(players, batting, pitching, team_seasons)별 파일을 DuckDB 로 읽는다.
  2. 컬럼을 스키마 이름으로 바꾸고, 팀 표기를 team_id 로, 선수 source_id 를 내부 player_id 로 바꾼다.
  3. known_at 을 채우고 INSERT OR REPLACE 한다. --dry-run 은 행 수와 누락 컬럼만 출력한다.
"""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime
from pathlib import Path

import duckdb
import yaml

from db.init_db import default_db_path, init_db
from stats.pitching import outs_from_ip

ROOT = Path(__file__).resolve().parents[2]
MAPPING = Path(__file__).with_name("mapping.yaml")

TRANSFORMS = {
    "ip_to_outs": lambda v: None if v in (None, "") else outs_from_ip(v),
}

BATTING_COLS = [
    "g",
    "pa",
    "ab",
    "r",
    "h",
    "doubles",
    "triples",
    "hr",
    "rbi",
    "sb",
    "cs",
    "bb",
    "ibb",
    "so",
    "hbp",
    "sf",
    "sh",
    "gidp",
]
PITCHING_COLS = [
    "g",
    "gs",
    "w",
    "l",
    "sv",
    "hld",
    "cg",
    "sho",
    "ip_outs",
    "bf",
    "h",
    "r",
    "er",
    "hr",
    "bb",
    "ibb",
    "so",
    "hbp",
    "wp",
    "bk",
]
TEAM_COLS = ["games", "wins", "losses", "ties", "runs_scored", "runs_allowed", "final_rank"]


def load_mapping() -> dict:
    return yaml.safe_load(MAPPING.read_text(encoding="utf-8"))


def read_section(
    con: duckdb.DuckDBPyConnection, base: Path, section: dict
) -> tuple[list[dict], list[str]]:
    """섹션 파일을 읽어 스키마 컬럼명으로 바꾼 dict 행 목록과, 파일에 없는 컬럼 목록을 돌려준다."""
    path = base / section["file"]
    if not path.exists():
        raise FileNotFoundError(path)
    rel = con.execute(
        f"SELECT * FROM read_csv_auto('{path.as_posix()}', header=true, all_varchar=true)"
    )
    file_cols = [d[0] for d in rel.description]
    rows = [dict(zip(file_cols, r, strict=True)) for r in rel.fetchall()]
    colmap: dict[str, str | None] = section.get("columns", {})
    missing = [k for k, v in colmap.items() if v and v not in file_cols]
    transforms = section.get("transform", {})
    out = []
    for r in rows:
        o = {}
        for schema_col, file_col in colmap.items():
            v = r.get(file_col) if file_col else None
            if schema_col in transforms:
                v = TRANSFORMS[transforms[schema_col]](v)
            o[schema_col] = v
        out.append(o)
    return out, missing


def player_id_for(source_id: str | None, name: str | None, birth: str | None) -> str:
    if source_id:
        return f"KBO_Y{source_id}"
    key = f"{name}_{birth or 'x'}".replace(" ", "")
    return f"KBO_N{key}"


def to_int(v):
    if v in (None, ""):
        return None
    try:
        return int(float(v))
    except ValueError:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dir", required=True, help="받은 파일이 있는 폴더 (data/raw/yagoonara/<날짜>)"
    )
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    base = (ROOT / args.dir) if not Path(args.dir).is_absolute() else Path(args.dir)
    m = load_mapping()
    teams = m["teams"]
    source = m["source"]
    league = m["league"]

    con = init_db(default_db_path())
    run_id = str(uuid.uuid4())
    if not args.dry_run:
        con.execute(
            "INSERT INTO ingest_log VALUES (?, ?, ?, NULL, NULL, 'running', ?)",
            [run_id, source, datetime.now(), str(base)],
        )
    total = 0
    try:
        # players
        if "players" in m and (base / m["players"]["file"]).exists():
            rows, missing = read_section(con, base, m["players"])
            print(f"players: {len(rows)} rows, missing cols: {missing}")
            if not args.dry_run:
                for r in rows:
                    pid = player_id_for(r.get("source_id"), r.get("name"), r.get("birth_date"))
                    con.execute(
                        "INSERT OR REPLACE INTO players (player_id, league_origin, name, birth_date, bats, "
                        "throws, primary_pos, debut_season, source) "
                        "VALUES (?, ?, ?, TRY_CAST(? AS DATE), ?, ?, ?, ?, ?)",
                        [
                            pid,
                            league,
                            r.get("name"),
                            r.get("birth_date"),
                            r.get("bats"),
                            r.get("throws"),
                            r.get("primary_pos"),
                            to_int(r.get("debut_season")),
                            source,
                        ],
                    )
                    if r.get("source_id"):
                        con.execute(
                            "INSERT OR REPLACE INTO player_external_ids VALUES (?, ?, ?)",
                            [pid, source, str(r["source_id"])],
                        )
                total += len(rows)

        # batting / pitching
        for sec, cols, table in (
            ("batting", BATTING_COLS, "batting_seasons"),
            ("pitching", PITCHING_COLS, "pitching_seasons"),
        ):
            if sec not in m or not (base / m[sec]["file"]).exists():
                continue
            rows, missing = read_section(con, base, m[sec])
            print(f"{sec}: {len(rows)} rows, missing cols: {missing}")
            if args.dry_run:
                continue
            for r in rows:
                season = to_int(r.get("season"))
                team_id = teams.get(r.get("team"))
                if season is None or team_id is None:
                    raise ValueError(f"season/team 매핑 실패: {r}")
                pid = player_id_for(r.get("player_source_id"), r.get("name"), None)
                if sec == "pitching":
                    r["ip_outs"] = r.pop("ip", None)
                vals = [to_int(r.get(c)) for c in cols]
                placeholders = ", ".join("?" * len(cols))
                con.execute(
                    f"INSERT OR REPLACE INTO {table} (league, season, player_id, team_id, stint, "
                    f"{', '.join(cols)}, known_at, source) "
                    f"VALUES (?, ?, ?, ?, 1, {placeholders}, make_date(?, 11, 30), ?)",
                    [league, season, pid, team_id, *vals, season, source],
                )
            total += len(rows)

        # team seasons
        if "team_seasons" in m and (base / m["team_seasons"]["file"]).exists():
            rows, missing = read_section(con, base, m["team_seasons"])
            print(f"team_seasons: {len(rows)} rows, missing cols: {missing}")
            if not args.dry_run:
                for r in rows:
                    season = to_int(r.get("season"))
                    team_id = teams.get(r.get("team"))
                    vals = [to_int(r.get(c)) for c in TEAM_COLS]
                    con.execute(
                        "INSERT OR REPLACE INTO team_seasons (league, season, team_id, games, wins, losses, ties, "
                        "runs_scored, runs_allowed, final_rank, known_at, source) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, make_date(?, 11, 30), ?)",
                        [league, season, team_id, *vals, season, source],
                    )
                total += len(rows)

        if not args.dry_run:
            con.execute(
                "UPDATE ingest_log SET finished_at = ?, rows = ?, status = 'ok' WHERE run_id = ?",
                [datetime.now(), total, run_id],
            )
            print(f"적재 완료: {total} rows (source={source})")
    except Exception as e:
        if not args.dry_run:
            con.execute(
                "UPDATE ingest_log SET finished_at = ?, status = 'failed', notes = ? WHERE run_id = ?",
                [datetime.now(), str(e)[:500], run_id],
            )
        raise
    finally:
        con.close()


if __name__ == "__main__":
    main()
