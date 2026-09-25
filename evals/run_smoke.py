"""스모크 평가: 에이전트를 소수 문항에 돌려 도구 사용·거절·근거 추적성·지연을 기록한다.

채점 (자동, 거친 기준)
  - tools_ok  : must_tools 를 모두 호출했는가
  - refusal_ok: expect=refusal 이면 답변에 '없/모르/알 수 없/데이터가' 류 표현이 있고 근거 없는 숫자가 없는가
  - content_ok: expected_numbers / expected_names 가 답변에 들어 있는가
  - trace     : 답변 숫자 중 도구 결과로 뒷받침되는 비율
사용:
    uv run python -m evals.run_smoke --model ollama:qwen3:4b-instruct
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from agent.adapters import make_adapter
from agent.runner import run

ROOT = Path(__file__).resolve().parents[1]
REFUSAL = re.compile(r"없|모르|알 수 없|확인할 수 없|제공되지 않|데이터가|기록이 아직|지원하지")


def grade(item: dict, r) -> dict:
    names = [c["name"] for c in r.tool_calls]
    tools_ok = all(t in names for t in item.get("must_tools", []))
    ans = r.answer
    content_ok = all(
        re.search(rf"(?<!\d){n}(?!\d)", ans) for n in map(str, item.get("expected_numbers", []))
    ) and all(
        re.search(n, ans) for n in item.get("expected_names", [])
    )  # 'Judge|저지' 처럼 대안 허용
    refusal_ok = None
    if item["expect"] == "refusal":
        refusal_ok = bool(REFUSAL.search(ans)) and not r.trace["unsupported"]
    return {
        "id": item["id"],
        "category": item["category"],
        "expect": item["expect"],
        "tools": names,
        "tools_ok": tools_ok if item["expect"] == "answer" else None,
        "content_ok": content_ok if item["expect"] == "answer" else None,
        "refusal_ok": refusal_ok,
        "trace_score": round(r.trace["score"], 3),
        "unsupported": r.trace["unsupported"],
        "steps": r.steps,
        "elapsed_s": r.elapsed_s,
        "stopped": r.stopped,
        "answer": ans,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="ollama:qwen3:4b-instruct")
    ap.add_argument("--file", default=str(ROOT / "evals" / "benchmark" / "smoke_v0.jsonl"))
    a = ap.parse_args()
    items = [
        json.loads(line)
        for line in Path(a.file).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    adapter = make_adapter(a.model)
    rows = []
    for it in items:
        r = run(it["question"], adapter, it.get("as_of"))
        g = grade(it, r)
        rows.append(g)
        flag = {True: "O", False: "X", None: "-"}
        print(
            f"{g['id']} tools {flag[g['tools_ok']]} content {flag[g['content_ok']]} refusal {flag[g['refusal_ok']]} "
            f"trace {g['trace_score']:.2f} {g['elapsed_s']:>5.1f}s  {g['tools']}"
        )
    ans = [g for g in rows if g["expect"] == "answer"]
    ref = [g for g in rows if g["expect"] == "refusal"]
    summary = {
        "model": adapter.name,
        "run_at": datetime.now().isoformat(timespec="seconds"),
        "n": len(rows),
        "tools_ok": sum(g["tools_ok"] for g in ans) / max(1, len(ans)),
        "content_ok": sum(g["content_ok"] for g in ans) / max(1, len(ans)),
        "refusal_ok": sum(g["refusal_ok"] for g in ref) / max(1, len(ref)),
        "trace_mean": sum(g["trace_score"] for g in rows) / len(rows),
        "latency_mean_s": sum(g["elapsed_s"] for g in rows) / len(rows),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    out = (
        ROOT
        / "evals"
        / "reports"
        / f"smoke_{adapter.name.replace(':', '_').replace('/', '_')}.json"
    )
    out.write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(f"저장: {out}")


if __name__ == "__main__":
    main()
