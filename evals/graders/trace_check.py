"""근거 추적성 채점: 답변 속 숫자가 모두 도구 결과(또는 질문)에 있는가.

규칙
  - 답변에서 숫자를 뽑는다 ('.397', '0.397', '39.7%', '100억', '4년', '2,639').
  - 도구 결과 JSON 의 모든 숫자(문자열 속 숫자 포함)와 질문 속 숫자를 근거 집합으로 만든다.
  - 답변 숫자가 근거 숫자와 같으면(반올림 오차 허용, ×100·÷100 변환 허용) 근거 있음.
  - 면제: 목록 번호("1."), 0~10 의 작은 정수가 단독으로 나올 때(순위·개수 서술이 많음)는 면제하지 않고 근거를 찾되,
    찾지 못해도 'minor' 로 따로 센다. 최종 점수는 major(작은 정수 제외) 기준.
반환: {"total", "supported", "unsupported": [...], "minor_unsupported": [...], "score"}
"""

from __future__ import annotations

import json
import re

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}(?:T[\d:.]+)?")


def _numbers_in_text(s: str) -> list[tuple[str, float]]:
    out = []
    s = DATE_RE.sub(" ", s)  # 날짜는 숫자로 세지 않는다 ('2026-09-25' 의 '-09' 오탐 방지)
    for m in re.finditer(r"[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?|(?<!\d)\.\d+", s):
        raw = m.group(0)
        # 목록 번호 "1." / "2)" 는 제외
        tail = s[m.end() : m.end() + 1]
        head = s[max(0, m.start() - 1) : m.start()]
        if (
            tail in (".", ")")
            and (m.start() == 0 or head in ("\n", " "))
            and re.fullmatch(r"\d", raw)
        ):
            nxt = s[m.end() + 1 : m.end() + 2]
            if nxt in (" ", "\n", ""):
                continue
        try:
            out.append((raw, float(raw.replace(",", ""))))
        except ValueError:
            continue
    return out


def _collect(obj, acc: list[float]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _collect(v, acc)
    elif isinstance(obj, list):
        for v in obj:
            _collect(v, acc)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, int | float):
        acc.append(float(obj))
    elif isinstance(obj, str):
        acc.extend(v for _, v in _numbers_in_text(obj))


def _matches(x: float, evidence: list[float]) -> bool:
    for e in evidence:
        for cand in (e, e * 100, e / 100):
            if cand == 0 and x == 0:
                return True
            if abs(x - cand) <= max(0.0015, abs(cand) * 0.006):
                return True
            # 반올림 표기: 소수 자릿수에 맞춰 반올림했을 때 같으면 인정
            for nd in (0, 1, 2, 3):
                if round(cand, nd) == x:
                    return True
    return False


def trace_check(
    answer: str, tool_results: list, question: str = "", tool_args: list | None = None
) -> dict:
    """tool_args: 모델이 도구에 넘긴 인자 (예: min_pa=502). 인자에 쓴 숫자도 근거로 인정한다."""
    evidence: list[float] = []
    for r in tool_results:
        _collect(r, evidence)
    for a in tool_args or []:
        _collect(a, evidence)
    evidence.extend(v for _, v in _numbers_in_text(question))
    nums = _numbers_in_text(answer)
    unsupported, minor = [], []
    total = supported = 0
    for raw, x in nums:
        is_minor = x.is_integer() and 0 <= x <= 10
        ok = _matches(x, evidence)
        if is_minor:
            if not ok:
                minor.append(raw)
            continue
        total += 1
        if ok:
            supported += 1
        else:
            unsupported.append(raw)
    return {
        "total": total,
        "supported": supported,
        "unsupported": unsupported,
        "minor_unsupported": minor,
        "score": 1.0 if total == 0 else supported / total,
    }


def check_log_line(line: str) -> dict:
    r = json.loads(line)
    return trace_check(
        r["answer"],
        [c["result"] for c in r["tool_calls"]],
        r["question"],
        [c["args"] for c in r["tool_calls"]],
    )
