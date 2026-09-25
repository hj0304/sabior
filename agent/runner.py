"""함수 호출 루프 러너 (P3 W9).

흐름: system + user → 모델 → (도구 호출이 있으면 실행 → tool 메시지 추가 → 모델) 반복 → 최종 답변.
- as_of 가드: 기준일을 주면 as_of 인자를 받는 모든 도구 호출에 강제로 넣는다 (모델이 빠뜨려도 미래 누출 없음).
- 모든 실행을 JSONL 로 남긴다 (data/agent_logs/). SFT 데이터 합성과 평가에 재사용한다.
- 최종 답변은 evals.graders.trace_check 로 숫자 근거 추적성을 검사한다.

사용:
    uv run python -m agent.runner "애런 저지 2024 wRC+ 알려줘" --model ollama:qwen3:4b-instruct
    uv run python -m agent.runner "..." --as-of 2025-02-01
"""

from __future__ import annotations

import argparse
import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from agent.adapters import make_adapter
from agent.tools import registry

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "agent" / "prompts" / "system_v1.md"
LOG_DIR = ROOT / "data" / "agent_logs"
MAX_TOOL_RESULT_CHARS = 6000


def system_prompt(as_of: str | None) -> str:
    line = (
        f"기준일은 {as_of} 이다. 이 날짜 이후의 사건·기록은 모른다고 답한다."
        if as_of
        else f"오늘은 {date.today().isoformat()} 이다."
    )
    return PROMPT.read_text(encoding="utf-8").replace("{as_of_line}", line)


@dataclass
class RunResult:
    run_id: str
    question: str
    answer: str
    model: str
    as_of: str | None
    steps: int
    tool_calls: list[dict] = field(default_factory=list)
    elapsed_s: float = 0.0
    stopped: str = "final"  # final | max_steps | error
    trace: dict | None = None


def _accepts_as_of(name: str) -> bool:
    spec = registry.tools.get(name)
    return bool(spec and "as_of" in spec.input_model.model_fields)


def run(
    question: str, adapter, as_of: str | None = None, max_steps: int = 6, log: bool = True
) -> RunResult:
    from evals.graders.trace_check import trace_check

    t0 = time.time()
    messages: list[dict] = [
        {"role": "system", "content": system_prompt(as_of)},
        {"role": "user", "content": question},
    ]
    calls_log: list[dict] = []
    answer, stopped, steps = "", "max_steps", 0
    for step in range(1, max_steps + 1):
        steps = step
        try:
            resp = adapter.chat(messages, None)
        except Exception as e:
            answer, stopped = f"[모델 호출 실패] {type(e).__name__}: {e}", "error"
            break
        if not resp["tool_calls"]:
            answer, stopped = resp["content"], "final"
            break
        messages.append(
            {"role": "assistant", "content": resp["content"], "tool_calls": resp["tool_calls"]}
        )
        for c in resp["tool_calls"]:
            args = dict(c["arguments"] or {})
            if as_of and _accepts_as_of(c["name"]):
                args["as_of"] = as_of  # as_of 가드
            t1 = time.perf_counter()
            result = registry.call(c["name"], args)
            text = json.dumps(result, ensure_ascii=False, default=str)
            if len(text) > MAX_TOOL_RESULT_CHARS:
                text = text[:MAX_TOOL_RESULT_CHARS] + ' ... (잘림)"}'
            calls_log.append(
                {
                    "name": c["name"],
                    "args": args,
                    "ok": result.get("ok"),
                    "result": result,
                    "ms": round((time.perf_counter() - t1) * 1000, 1),
                }
            )
            messages.append(
                {"role": "tool", "content": text, "tool_call_id": c["id"], "name": c["name"]}
            )
    else:
        answer = answer or "[도구 호출 한도 초과로 답변을 마치지 못했다]"

    res = RunResult(
        run_id=uuid.uuid4().hex[:12],
        question=question,
        answer=answer,
        model=adapter.name,
        as_of=as_of,
        steps=steps,
        tool_calls=calls_log,
        elapsed_s=round(time.time() - t0, 2),
        stopped=stopped,
    )
    res.trace = trace_check(
        answer, [c["result"] for c in calls_log], question, [c["args"] for c in calls_log]
    )
    if log:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        with (LOG_DIR / f"{datetime.now():%Y%m%d}.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(res), ensure_ascii=False, default=str) + "\n")
    return res


def main() -> None:
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--model", default="ollama:qwen3:4b-instruct")
    ap.add_argument("--as-of", default=None)
    ap.add_argument("--max-steps", type=int, default=6)
    a = ap.parse_args()
    r = run(a.question, make_adapter(a.model), a.as_of, a.max_steps)
    for c in r.tool_calls:
        print(
            f"  [도구] {c['name']}({json.dumps(c['args'], ensure_ascii=False)}) ok={c['ok']} {c['ms']}ms"
        )
    print(f"\n{r.answer}\n")
    t = r.trace
    print(
        f"--- {r.model} | {r.steps}단계 | {r.elapsed_s}s | 숫자 근거 {t['supported']}/{t['total']}"
        + (f" | 근거 없는 숫자: {t['unsupported']}" if t["unsupported"] else "")
    )


if __name__ == "__main__":
    main()
