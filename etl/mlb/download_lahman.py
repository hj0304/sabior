"""Lahman Baseball Databank (Chadwick Bureau 유지 버전)을 내려받아 data/raw/mlb/lahman 에 푼다.

출처: https://github.com/chadwickbureau/baseballdatabank  (CC BY-SA 3.0)
사용: uv run python etl/mlb/download_lahman.py
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "mlb" / "lahman"
URL = "https://github.com/chadwickbureau/baseballdatabank/archive/refs/heads/master.zip"
WANTED = {
    "People.csv",
    "Batting.csv",
    "Pitching.csv",
    "Fielding.csv",
    "Teams.csv",
    "Parks.csv",
    "Salaries.csv",
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"downloading {URL}")
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        resp = client.get(URL)
        resp.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(resp.content))
    n = 0
    for info in zf.infolist():
        name = Path(info.filename).name
        if name in WANTED:
            (OUT / name).write_bytes(zf.read(info))
            n += 1
            print(f"  {name}")
    print(f"saved {n} files to {OUT}")


if __name__ == "__main__":
    main()
