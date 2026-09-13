"""SABR 가 Box 공유 폴더로 배포하는 Lahman Baseball Database(2025판) CSV 를 내려받는다.

출처: https://sabr.org/lahman-database/  (Chadwick Bureau GitHub 저장소는 2026년 기준 소멸)
Box 공유 폴더 페이지에 포함된 파일 목록(typedID, name)을 읽어 파일별 다운로드 URL 로 받는다.
이용 조건은 함께 받는 readme2025.txt 를 확인한다 (출처 표기 요구).

사용: uv run python etl/mlb/download_lahman.py [--all]
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "mlb" / "lahman"
SHARED = "y1prhc795jk8zvmelfd3jq7tl389y6cd"  # SABR 'Comma-delimited version' 공유 링크
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
WANTED = [
    "People.csv",
    "Batting.csv",
    "Pitching.csv",
    "Fielding.csv",
    "Teams.csv",
    "Parks.csv",
    "Salaries.csv",
    "readme2025.txt",
]


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=180).read()


def _items(html: str) -> dict[str, str]:
    """페이지에 박힌 Box.postStreamData JSON 에서 {파일명: typedID} 를 뽑는다."""
    key = "Box.postStreamData = "
    i = html.find(key)
    items: dict[str, str] = {}
    if i >= 0:
        j = html.find("{", i)
        depth, k, in_str, esc = 0, j, False, False
        while k < len(html):
            c = html[k]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        break
            k += 1
        try:
            data = json.loads(html[j : k + 1])

            def walk(o):
                if isinstance(o, dict):
                    if str(o.get("typedID", "")).startswith("f_") and "name" in o:
                        items.setdefault(o["name"], o["typedID"])
                    for v in o.values():
                        walk(v)
                elif isinstance(o, list):
                    for v in o:
                        walk(v)

            walk(data)
        except json.JSONDecodeError:
            pass
    if not items:  # 폴백: typedID 근처의 name
        for m in re.finditer(r'"typedID":"(f_\d+)"', html):
            window = html[max(0, m.start() - 1500) : m.end() + 1500]
            names = re.findall(r'"name":"([^"]+)"', window)
            if names:
                items.setdefault(names[0], m.group(1))
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="폴더의 모든 파일을 받는다")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    html = _get(f"https://sabr.box.com/s/{SHARED}").decode("utf-8", "replace")
    items = _items(html)
    if not items:
        raise SystemExit(
            "Box 페이지에서 파일 목록을 찾지 못했습니다. 페이지 구조가 바뀌었을 수 있습니다."
        )
    names = sorted(items) if args.all else WANTED
    for name in names:
        fid = items.get(name)
        if not fid:
            print(f"MISSING {name}")
            continue
        data = _get(
            f"https://sabr.box.com/index.php?rm=box_download_shared_file&shared_name={SHARED}&file_id={fid}"
        )
        if b"<html" in data[:300].lower():
            print(f"NOT A FILE {name}")
            continue
        (OUT / name).write_bytes(data)
        print(f"{name:20s} {len(data):>12,d} bytes")
    print(f"saved to {OUT}")


if __name__ == "__main__":
    main()
