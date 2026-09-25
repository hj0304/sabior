"""도구 공통: DB 연결, 응답 봉투, not_found.

응답 봉투 (docs/tool_api_spec.md)
    {"ok": true, "as_of": "...", "data": {...}, "sources": [...], "warnings": [...]}
    {"ok": false, "error": "not_found", "detail": "..."}
에이전트는 ok=false 를 받으면 "모른다/데이터 없음"으로 답해야 한다 (환각 함정 대응).
"""

from __future__ import annotations

import math
import os
from datetime import date
from functools import lru_cache
from pathlib import Path

import duckdb
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def con() -> duckdb.DuckDBPyConnection:
    path = ROOT / os.environ.get("SABIOR_DB_PATH", "data/sabior.duckdb")
    return duckdb.connect(str(path), read_only=True)


class AsOf(BaseModel):
    as_of: str | None = Field(
        None, description="기준일 YYYY-MM-DD. 이 날짜 이후 알려진 데이터는 쓰지 않는다. 비우면 오늘"
    )

    def as_of_date(self) -> str:
        return self.as_of or date.today().isoformat()


def _clean(v):
    """JSON 직렬화 가능한 값으로 (NaN → None, numpy → python, 소수 4자리)."""
    if isinstance(v, dict):
        return {k: _clean(x) for k, x in v.items()}
    if isinstance(v, list | tuple):
        return [_clean(x) for x in v]
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, float):
        return None if math.isnan(v) else round(v, 4)
    if isinstance(v, date):
        return v.isoformat()
    return v


def ok(
    data, as_of: str, sources: list[str] | None = None, warnings: list[str] | None = None
) -> dict:
    return {
        "ok": True,
        "as_of": as_of,
        "data": _clean(data),
        "sources": sources or [],
        "warnings": warnings or [],
    }


def not_found(detail: str) -> dict:
    return {"ok": False, "error": "not_found", "detail": detail}
