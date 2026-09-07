"""도구 레지스트리. pydantic 입력 모델에서 JSON 스키마를 뽑아 LLM 에 전달하고, 호출을 로그로 남긴다."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


@dataclass
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    fn: Callable[..., Any]

    def json_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_model.model_json_schema(),
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

    def call(self, name: str, args: dict) -> Any:
        spec = self.tools[name]
        parsed = spec.input_model(**args)
        t0 = time.perf_counter()
        try:
            result = spec.fn(parsed)
        except Exception as e:
            self.calls.append(
                ToolCallLog(name, args, None, (time.perf_counter() - t0) * 1000, error=str(e))
            )
            raise
        self.calls.append(ToolCallLog(name, args, result, (time.perf_counter() - t0) * 1000))
        return result


registry = ToolRegistry()


def tool(name: str, description: str, input_model: type[BaseModel]):
    """사용: @tool("get_batting_season", "...", GetBattingSeasonInput)"""

    def deco(fn: Callable[..., Any]):
        registry.register(ToolSpec(name, description, input_model, fn))
        return fn

    return deco
