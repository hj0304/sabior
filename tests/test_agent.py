"""에이전트 루프·도구·근거 추적 채점 테스트 (LLM 없이 ScriptedAdapter 로)."""

from pathlib import Path

import pytest

from evals.graders.trace_check import trace_check

DB = Path(__file__).resolve().parents[1] / "data" / "sabior.duckdb"
needs_db = pytest.mark.skipif(not DB.exists(), reason="DB 없음")


def test_trace_check_supported_and_unsupported():
    tools = [
        {"ok": True, "data": {"woba": 0.4789, "wrc_plus": 213.94, "hr": 58, "note": "4년 100억"}}
    ]
    ans = "저지의 2024 wOBA 는 .479, wRC+ 는 214 이고 58홈런을 쳤다. 계약은 4년 100억. 타율은 .322"
    r = trace_check(ans, tools, "2024 시즌")
    assert ".322" in r["unsupported"]
    assert r["supported"] == r["total"] - 1
    # 퍼센트 변환 허용 (.303 → 30.3%)
    assert trace_check("K% 30.3%", [{"k_pct": 0.3028}])["unsupported"] == []


def test_trace_check_ignores_list_markers():
    r = trace_check("1. 첫째\n2. 둘째", [])
    assert r["total"] == 0 and r["minor_unsupported"] == []


def test_registry_error_envelopes():
    from agent.tools import registry

    assert registry.call("nope", {})["error"] == "unknown_tool"
    assert registry.call("get_batting_season", {"season": 2024})["error"] == "invalid_args"


@needs_db
def test_runner_loop_with_scripted_model_and_as_of_guard():
    from agent.adapters import ScriptedAdapter
    from agent.runner import run

    adapter = ScriptedAdapter(
        [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "a",
                        "name": "get_batting_season",
                        "arguments": {"player_id": "MLB_judgeaa01", "season": 2024},
                    }
                ],
            },
            {"content": "저지 2024 wRC+ 는 214 이다.\n근거: get_batting_season", "tool_calls": []},
        ]
    )
    r = run("저지 2024 wRC+?", adapter, as_of="2024-12-31", log=False)
    assert r.stopped == "final" and r.steps == 2
    assert r.tool_calls[0]["args"]["as_of"] == "2024-12-31"  # 모델이 안 넣어도 가드가 넣는다
    assert r.tool_calls[0]["ok"] is True
    assert r.trace["unsupported"] == []
    # 기준일 이전이면 같은 호출이 not_found 여야 한다 (미래 누출 방지)
    adapter2 = ScriptedAdapter(
        [
            {
                "content": "",
                "tool_calls": [
                    {
                        "id": "b",
                        "name": "get_batting_season",
                        "arguments": {"player_id": "MLB_judgeaa01", "season": 2024},
                    }
                ],
            },
            {"content": "그 기록은 아직 없습니다.", "tool_calls": []},
        ]
    )
    r2 = run("저지 2024 wRC+?", adapter2, as_of="2024-03-01", log=False)
    assert r2.tool_calls[0]["ok"] is False


@needs_db
def test_runner_stops_at_max_steps():
    from agent.adapters import ScriptedAdapter
    from agent.runner import run

    loop = {
        "content": "",
        "tool_calls": [{"id": "x", "name": "search_player", "arguments": {"name": "Judge"}}],
    }
    r = run("?", ScriptedAdapter([dict(loop) for _ in range(3)]), max_steps=3, log=False)
    assert r.stopped == "max_steps" and len(r.tool_calls) == 3
