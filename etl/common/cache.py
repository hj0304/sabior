"""요청 간격을 지키고 원본을 디스크에 캐시하는 fetcher.

원칙
  - 같은 URL 은 두 번 받지 않는다 (force=True 일 때만 재요청).
  - 요청 간 최소 간격을 지킨다 (기본 2초).
  - User-Agent 에 프로젝트명과 연락처를 넣는다 (.env 의 SABIOR_CONTACT).
  - 응답 원문과 메타(URL, 시각, 상태코드)를 나란히 저장한다.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]


class CachedFetcher:
    def __init__(
        self,
        source: str,
        min_interval: float = 2.0,
        cache_dir: Path | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.source = source
        self.min_interval = min_interval
        self.cache_dir = cache_dir or ROOT / "data" / "raw" / source / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        contact = os.environ.get("SABIOR_CONTACT", "")
        ua = "sabior-research/0.1 (personal sabermetrics research"
        ua += f"; {contact})" if contact else ")"
        self._client = httpx.Client(
            headers={"User-Agent": ua}, timeout=timeout, follow_redirects=True
        )
        self._last_request = 0.0

    @staticmethod
    def _key(url: str, params: dict | None) -> str:
        raw = url + ("?" + json.dumps(params, sort_keys=True, ensure_ascii=False) if params else "")
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _wait(self) -> None:
        elapsed = time.monotonic() - self._last_request
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def get(self, url: str, params: dict | None = None, force: bool = False) -> str:
        key = self._key(url, params)
        body_path = self.cache_dir / f"{key}.html"
        meta_path = self.cache_dir / f"{key}.json"
        if body_path.exists() and not force:
            return body_path.read_text(encoding="utf-8")

        self._wait()
        resp = self._client.get(url, params=params)
        self._last_request = time.monotonic()
        resp.raise_for_status()

        body_path.write_text(resp.text, encoding="utf-8")
        meta = {
            "url": str(resp.url),
            "status": resp.status_code,
            "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source": self.source,
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        return resp.text

    def close(self) -> None:
        self._client.close()
