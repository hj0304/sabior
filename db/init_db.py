"""DuckDB 파일을 만들고 schema.sql, snapshots.sql 을 적용한다. 여러 번 실행해도 안전하다.

사용:
    uv run python db/init_db.py                 # data/sabior.duckdb
    uv run python db/init_db.py --path other.duckdb
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_FILES = [ROOT / "db" / "schema.sql", ROOT / "db" / "snapshots.sql"]


def default_db_path() -> Path:
    return ROOT / os.environ.get("SABIOR_DB_PATH", "data/sabior.duckdb")


def init_db(path: Path | str) -> duckdb.DuckDBPyConnection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(path))
    for f in SCHEMA_FILES:
        con.execute(f.read_text(encoding="utf-8"))
    return con


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=None, help="DuckDB 파일 경로 (기본: data/sabior.duckdb)")
    args = ap.parse_args()
    path = Path(args.path) if args.path else default_db_path()
    con = init_db(path)
    tables = [
        r[0] for r in con.execute("SELECT table_name FROM duckdb_tables() ORDER BY 1").fetchall()
    ]
    macros = [
        r[0]
        for r in con.execute(
            "SELECT DISTINCT function_name FROM duckdb_functions() "
            "WHERE function_type = 'table_macro' ORDER BY 1"
        ).fetchall()
    ]
    print(f"DB: {path}")
    print(f"tables ({len(tables)}): {', '.join(tables)}")
    print(f"as_of macros ({len(macros)}): {', '.join(macros)}")
    con.close()


if __name__ == "__main__":
    main()
