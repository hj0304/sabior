"""도구 레지스트리. pydantic 입력 모델에서 JSON 스키마를 뽑아 LLM 에 전달하고, 호출을 로그로 남긴다.

같은 도구 함수를 에이전트(함수 호출)와 FastAPI(app/api) 가 공유한다. 정의는 한 곳에만 둔다.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    fn: Callable[..., Any]

    def json_schema(self) -> dict:
        """Anthropic 형식."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
        }

    def openai_schema(self) -> dict:
        """OpenAI·Ollama 형식."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema(),
            },
        }


@dataclass
class ToolCallLog:
    name: str
    args: dict
    result: Any
    elapsed_ms: float
    error: str | None = None


@dataclass
class ToolRegistry:
    tools: dict[str, ToolSpec] = field(default_factory=dict)
    calls: list[ToolCallLog] = field(default_factory=list)

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self.tools:
            raise ValueError(f"duplicate tool: {spec.name}")
        self.tools[spec.name] = spec

    def schemas(self) -> list[dict]:
        return [t.json_schema() for t in self.tools.values()]

    def openai_schemas(self) -> list[dict]:
        return [t.openai_schema() for t in self.tools.values()]

    def call(self, name: str, args: dict) -> Any:
        """도구 실행. 알 수 없는 도구·잘못된 인자는 예외 대신 오류 봉투를 돌려준다 (모델이 스스로 고치게)."""
        t0 = time.perf_counter()
        if name not in self.tools:
            result = {
                "ok": False,
                "error": "unknown_tool",
                "detail": f"없는 도구: {name}. 가능: {list(self.tools)}",
            }
            self.calls.append(ToolCallLog(name, args, result, 0.0, error="unknown_tool"))
            return result
        spec = self.tools[name]
        try:
            parsed = spec.input_model(**(args or {}))
        except ValidationError as e:
            result = {
                "ok": False,
                "error": "invalid_args",
                "detail": e.errors(include_url=False)[:3],
            }
            self.calls.append(ToolCallLog(name, args, result, 0.0, error="invalid_args"))
            return result
        try:
            result = spec.fn(parsed)
        except Exception as e:
            result = {
                "ok": False,
                "error": "tool_error",
                "detail": f"{type(e).__name__}: {e}"[:300],
            }
            self.calls.append(
                ToolCallLog(name, args, result, (time.perf_counter() - t0) * 1000, error=str(e))
            )
            return result
        self.calls.append(ToolCallLog(name, args, result, (time.perf_counter() - t0) * 1000))
        return result

    def mark(self) -> int:
        """현재 로그 위치. 한 번의 에이전트 실행에서 쓴 호출만 잘라 보려고 쓴다."""
        return len(self.calls)

    def since(self, mark: int) -> list[ToolCallLog]:
        return self.calls[mark:]


registry = ToolRegistry()


def tool(name: str, description: str, input_model: type[BaseModel]):
    """사용: @tool("get_batting_season", "...", GetBattingSeasonInput)"""

    def deco(fn: Callable[..., Any]):
        registry.register(ToolSpec(name, description, input_model, fn))
        return fn

    return deco
