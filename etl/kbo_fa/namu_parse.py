"""나무위키 'KBO 리그/역대 FA/<연도>' 문서의 계약 현황 표를 사실 데이터로 추출한다.

- 원문: data/raw/kbo_fa/namu/<연도>.html (문서당 1회만 받아 캐시, robots.txt 가 /w/ 를 허용)
- 추출하는 것은 계약 사실(선수, 등급, 원소속, 계약 구단, 연수, 총액, 보장액, 계약금, 연봉 총액, 옵션, 보상금, 보상선수,
  발표일)뿐이다. 문서의 서술·평가 문장은 가져오지 않는다.
- 나무위키는 2차 출처다. 공개 서비스에 쓰기 전에 행별로 기사·KBO 보도자료로 대조해 `verified` 를 채운다.

시장 연도 규칙: 문서 연도 = FA 계약 후 첫 시즌. '2026' 문서 = 2025년 11월 개장 시장 (market_year=2026).

사용:
    uv run python -m etl.kbo_fa.namu_parse            # data/processed/kbo_fa_contracts.csv 생성
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "kbo_fa" / "namu"
OUT = ROOT / "data" / "processed" / "kbo_fa_contracts.csv"
NAMU_URL = "https://namu.wiki/w/KBO%20%EB%A6%AC%EA%B7%B8/%EC%97%AD%EB%8C%80%20FA/{year}"

TEAMS = {
    "LG": "KBO_LG",
    "한화": "KBO_HH",
    "SSG": "KBO_SK",
    "SK": "KBO_SK",
    "삼성": "KBO_SS",
    "NC": "KBO_NC",
    "kt": "KBO_KT",
    "KT": "KBO_KT",
    "롯데": "KBO_LT",
    "KIA": "KBO_HT",
    "두산": "KBO_OB",
    "키움": "KBO_WO",
}


def team_id(raw: str | None) -> str | None:
    """'삼성', '삼성 라이온즈', 'kt wiz', 'SSG 랜더스' 등을 팀 ID 로."""
    if not raw:
        return None
    raw = raw.strip()
    if raw in TEAMS:
        return TEAMS[raw]
    for k, v in TEAMS.items():
        if raw.startswith(k) or raw.lower().startswith(k.lower()):
            return v
    return raw


FIELDS = [
    "market_year",
    "player_name",
    "fa_grade",
    "age",
    "prev_team",
    "new_team",
    "contract_type",
    "years_text",
    "years",
    "total_eok",
    "guaranteed_eok",
    "signing_bonus_eok",
    "salary_total_eok",
    "options_eok",
    "prev_salary_eok",
    "comp_cash_eok",
    "comp_player",
    "announced",
    "note",
    "guaranteed_derived",
    "source_url",
    "verified",
]


def clean(s: str) -> str:
    s = re.sub(r"\[[^\]]*\]", "", s)  # 각주·주석 표시 [2차], [22] 등
    return re.sub(r"\s+", " ", s).strip()


def table_grid(tb) -> list[list[str]]:
    """rowspan/colspan 을 풀어 2차원 격자로 만든다."""
    grid: list[list[str | None]] = []
    pending: dict[tuple[int, int], str] = {}
    for r, tr in enumerate(tb.find_all("tr")):
        row: list[str] = []
        c = 0
        cells = tr.find_all(["td", "th"])
        ci = 0
        while ci < len(cells) or (r, c) in pending:
            if (r, c) in pending:
                row.append(pending.pop((r, c)))
                c += 1
                continue
            cell = cells[ci]
            ci += 1
            text = clean(cell.get_text(" ", strip=True))
            if not text:  # 팀 로고만 있는 셀: 링크 제목 또는 이미지 대체 텍스트
                a = cell.find("a", title=True)
                img = cell.find("img", alt=True)
                text = clean(a["title"] if a else (img["alt"] if img else ""))
            rs = int(cell.get("rowspan", 1) or 1)
            cs = int(cell.get("colspan", 1) or 1)
            for k in range(cs):
                row.append(text)
                for dr in range(1, rs):
                    pending[(r + dr, c + k)] = text
            c += cs
        grid.append(row)
    return grid


def eok(s: str | None) -> float | None:
    """'4억 5,000만' → 4.5, '0.975억' → 0.975, '8,000만' → 0.8, '-' → None."""
    if not s:
        return None
    s = s.replace(",", "").replace(" ", "")
    if s in ("-", "", "없음"):
        return None
    m = re.fullmatch(r"(?:(\d+(?:\.\d+)?)억)?(?:(\d+)만)?원?", s)
    if not m or (m.group(1) is None and m.group(2) is None):
        return None
    return float(m.group(1) or 0) + float(m.group(2) or 0) / 10000


def parse_result(s: str) -> dict:
    """'3+1년 20억 (보장 18억)' → years_text '3+1', years 4, total 20, guaranteed 18."""
    out = {"years_text": None, "years": None, "total_eok": None, "guaranteed_eok": None}
    m = re.search(r"([\d+]+)\s*년", s)
    if m:
        out["years_text"] = m.group(1)
        out["years"] = sum(int(x) for x in m.group(1).split("+") if x)
    m = re.search(r"년\s*([\d.,]+억(?:\s*[\d,]+만)?|[\d,]+만)", s)
    if m:
        out["total_eok"] = eok(m.group(1))
    m = re.search(r"보장\s*([\d.,]+억(?:\s*[\d,]+만)?|[\d,]+만)", s)
    if m:
        out["guaranteed_eok"] = eok(m.group(1))
    return out


def find(grids, *keys) -> list[list[list[str]]]:
    hits = []
    for g in grids:
        head = " ".join(" ".join(r) for r in g[:2])
        if all(k in head for k in keys):
            hits.append(g)
    return hits


def header_rows(g: list[list[str]], key: str) -> tuple[list[str], list[list[str]]]:
    for i, r in enumerate(g[:3]):
        if key in r:
            return r, g[i + 1 :]
    return g[0], g[1:]


def _col(idx: dict, *cands) -> str | None:
    for c in cands:
        for h in idx:
            if c == h or c in h:
                return h
    return None


def parse_year(year: int) -> list[dict]:
    soup = BeautifulSoup((RAW / f"{year}.html").read_text(encoding="utf-8"), "lxml")
    grids = [table_grid(tb) for tb in soup.find_all("table")]
    url = NAMU_URL.format(year=year)

    # 0) FA 자격 명단: (이름, 팀) → 등급·나이·직전 연봉
    elig: dict[tuple[str, str], dict] = {}
    for g in grids:
        if not g or not ("선수" in g[0] and "인정년수" in g[0]):
            continue
        idx = {h: i for i, h in enumerate(g[0])}
        sal = _col(idx, "연봉")
        c_team = _col(idx, "팀", "구단", "소속")
        if c_team is None:
            continue
        for r in g[1:]:
            if len(r) < len(g[0]):
                continue
            key = (r[idx["선수"]], team_id(r[idx[c_team]]))
            elig[key] = {
                "fa_grade": (r[idx["등급"]] if "등급" in idx else "").strip() or None,
                "age": r[idx["나이"]].replace("세", "") if "나이" in idx else None,
                "prev_salary_eok": eok(r[idx[sal]].replace("원", "")) if sal else None,
            }

    # 1) 계약 현황 요약표 (2023~): 등급·보상금·보상선수·계약 결과
    summary: dict[tuple[str, str], dict] = {}
    for g in find(grids, "계약 결과"):
        head, body = header_rows(g, "선수")
        idx = {h: i for i, h in enumerate(head)}
        for r in body:
            if len(r) < len(head) or r[idx["선수"]] in ("", "선수"):
                continue
            get = lambda k, r=r, idx=idx: r[idx[k]] if k in idx and idx[k] < len(r) else None  # noqa: E731
            prev = team_id(get("소속") or get("원 소속"))
            res = get("계약 결과") or ""
            summary[(r[idx["선수"]], prev)] = {
                "fa_grade": (get("등급") or "").strip() or None,
                "new_team": team_id(get("계약 구단")),
                "result": res,
                "comp_cash_eok": eok(get("보상금")),
                "comp_player": (get("보상선수") or "").strip() or None,
                "note": get("비고"),
            }

    # 2) 이적·잔류 상세표 (전 연도): 계약 규모·계약금·연봉 총액·옵션·발표일
    detail: dict[tuple[str, str], dict] = {}
    for g in grids:
        head, body = header_rows(g, "이름")
        if "이름" not in head or not any("계약금" in h for h in head):
            continue
        idx = {h: i for i, h in enumerate(head)}
        moved = _col(idx, "계약팀", "계약 구단") is not None
        c_prev = (
            _col(idx, "원 소속", "원소속팀", "원 소속팀") if moved else _col(idx, "소속팀", "소속")
        )
        c_new = _col(idx, "계약팀", "계약 구단")
        c_size = _col(idx, "계약 규모")
        c_years = _col(idx, "계약기간")
        c_total = _col(idx, "총액")
        c_date = _col(idx, "발표", "계약일시")
        for r in body:
            if len(r) <= idx["이름"] or r[idx["이름"]] in ("", "이름"):
                continue
            get = lambda h, r=r, idx=idx: r[idx[h]] if h and idx[h] < len(r) else None  # noqa: E731
            prev = team_id(get(c_prev))
            size = get(c_size) if c_size else f"{get(c_years) or ''} {get(c_total) or ''}"
            detail[(r[idx["이름"]], prev)] = {
                "contract_type": "FA" if moved else "FA_RESIGN",
                "new_team": team_id(get(c_new)) if moved else prev,
                "announced": get(c_date),
                "size": size,
                "signing_bonus_eok": eok(get(_col(idx, "계약금"))),
                "salary_total_eok": eok(get(_col(idx, "총연봉", "연봉 총액"))),
                "options_eok": eok(get(_col(idx, "옵션"))),
                "comp_cash_eok": eok(get(_col(idx, "보상금"))),
                "comp_player": get(_col(idx, "보상선수")),
            }

    rows = []
    for key in sorted(set(summary) | set(detail), key=lambda k: (k[0], k[1] or "")):
        name, prev = key
        sm, d = summary.get(key, {}), detail.get(key, {})
        el = elig.get(key, {})
        parsed = parse_result(sm.get("result") or d.get("size") or "")
        if parsed["guaranteed_eok"] is None and d.get("size"):
            parsed["guaranteed_eok"] = parse_result(d["size"])["guaranteed_eok"]
        if parsed["years"] is None:
            continue  # 계약하지 않은 선수(미계약·은퇴·해외 진출 등)
        new = sm.get("new_team") or d.get("new_team")
        ctype = d.get("contract_type") or ("FA_RESIGN" if new == prev else "FA")
        if new and not str(new).startswith("KBO_"):
            ctype = "OVERSEAS"  # 해외 구단과 계약 (KBO FA 계약 아님)
        if (
            parsed["guaranteed_eok"] is None
            and d.get("signing_bonus_eok") is not None
            and d.get("salary_total_eok") is not None
        ):
            parsed["guaranteed_eok"] = round(d["signing_bonus_eok"] + d["salary_total_eok"], 4)
            parsed["guaranteed_derived"] = True
        comp_player = sm.get("comp_player") or d.get("comp_player")
        if comp_player and comp_player.strip("- ") == "":
            comp_player = None
        cash = sm.get("comp_cash_eok")
        rows.append(
            {
                "market_year": year,
                "player_name": name,
                "fa_grade": sm.get("fa_grade") or el.get("fa_grade"),
                "age": el.get("age"),
                "prev_team": prev,
                "new_team": new,
                "contract_type": ctype,
                **parsed,
                "signing_bonus_eok": d.get("signing_bonus_eok"),
                "salary_total_eok": d.get("salary_total_eok"),
                "options_eok": d.get("options_eok"),
                "prev_salary_eok": el.get("prev_salary_eok"),
                "comp_cash_eok": cash if cash is not None else d.get("comp_cash_eok"),
                "comp_player": comp_player,
                "announced": d.get("announced"),
                "note": sm.get("note")
                or (None if el else "FA 자격 명단에 없음 (해외 복귀 등, 등급 미적용)"),
                "source_url": url,
                "verified": "",
            }
        )
    return rows


def main() -> None:
    all_rows = []
    for year in range(2021, 2027):
        if not (RAW / f"{year}.html").exists():
            print(f"{year}: 원문 없음")
            continue
        rows = parse_year(year)
        all_rows += rows
        n_move = sum(r["contract_type"] == "FA" for r in rows)
        n_stay = sum(r["contract_type"] == "FA_RESIGN" for r in rows)
        miss = sum(r["total_eok"] is None for r in rows)
        print(f"{year}: {len(rows)}건 (이적 {n_move}, 잔류 {n_stay}, 총액 파싱 실패 {miss})")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_rows)
    print(f"저장: {OUT} ({len(all_rows)}건)")


if __name__ == "__main__":
    main()
