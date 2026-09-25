"""LLM 어댑터. 공통 인터페이스: chat(messages, tools) -> {"content": str, "tool_calls": [{"id", "name", "arguments"}]}

messages 는 내부 공통 형식을 쓴다.
    {"role": "system"|"user"|"assistant"|"tool", "content": str,
     "tool_calls": [...] (assistant 만), "tool_call_id": str, "name": str (tool 만)}
각 어댑터가 공급자 형식으로 바꾼다.

- OllamaAdapter : 로컬 (기본 qwen3:4b-instruct). 조건 B/C 용.
- AnthropicAdapter : 프론티어 API (기본 claude-sonnet-5). 조건 A 용. ANTHROPIC_API_KEY 필요.
- ScriptedAdapter : 테스트용. 미리 정한 응답을 순서대로 돌려준다.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field

import httpx


@dataclass
class OllamaAdapter:
    model: str = "qwen3:4b-instruct"
    host: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    )
    temperature: float = 0.2
    num_ctx: int = 8192
    timeout: float = 300.0

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def _convert(self, messages: list[dict]) -> list[dict]:
        out = []
        for m in messages:
            if m["role"] == "assistant" and m.get("tool_calls"):
                out.append(
                    {
                        "role": "assistant",
                        "content": m.get("content") or "",
                        "tool_calls": [
                            {"function": {"name": c["name"], "arguments": c["arguments"]}}
                            for c in m["tool_calls"]
                        ],
                    }
                )
            elif m["role"] == "tool":
                out.append({"role": "tool", "content": m["content"], "tool_name": m.get("name")})
            else:
                out.append({"role": m["role"], "content": m["content"]})
        return out

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        from agent.tools import registry

        body = {
            "model": self.model,
            "messages": self._convert(messages),
            "tools": registry.openai_schemas() if tools is None else tools,
            "stream": False,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
        }
        r = httpx.post(f"{self.host}/api/chat", json=body, timeout=self.timeout)
        r.raise_for_status()
        msg = r.json()["message"]
        calls = []
        for c in msg.get("tool_calls") or []:
            args = c["function"].get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"_raw": args}
            calls.append(
                {"id": uuid.uuid4().hex[:8], "name": c["function"]["name"], "arguments": args}
            )
        return {"content": msg.get("content") or "", "tool_calls": calls}


@dataclass
class AnthropicAdapter:
    model: str = "claude-sonnet-5"
    max_tokens: int = 2048
    temperature: float = 0.2
    timeout: float = 120.0

    @property
    def name(self) -> str:
        return f"anthropic:{self.model}"

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        from agent.tools import registry

        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY 가 없다 (.env 에 설정)")
        system = "\n".join(m["content"] for m in messages if m["role"] == "system")
        conv = []
        for m in messages:
            if m["role"] == "system":
                continue
            if m["role"] == "assistant" and m.get("tool_calls"):
                blocks = [{"type": "text", "text": m["content"]}] if m.get("content") else []
                blocks += [
                    {"type": "tool_use", "id": c["id"], "name": c["name"], "input": c["arguments"]}
                    for c in m["tool_calls"]
                ]
                conv.append({"role": "assistant", "content": blocks})
            elif m["role"] == "tool":
                block = {
                    "type": "tool_result",
                    "tool_use_id": m["tool_call_id"],
                    "content": m["content"],
                }
                if conv and conv[-1]["role"] == "user" and isinstance(conv[-1]["content"], list):
                    conv[-1]["content"].append(block)
                else:
                    conv.append({"role": "user", "content": [block]})
            else:
                conv.append({"role": m["role"], "content": m["content"]})
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "system": system,
            "messages": conv,
            "tools": registry.schemas() if tools is None else tools,
        }
        r = httpx.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
            timeout=self.timeout,
        )
        r.raise_for_status()
        data = r.json()
        text = "".join(b.get("text", "") for b in data["content"] if b["type"] == "text")
        calls = [
            {"id": b["id"], "name": b["name"], "arguments": b.get("input") or {}}
            for b in data["content"]
            if b["type"] == "tool_use"
        ]
        return {"content": text, "tool_calls": calls}


@dataclass
class ScriptedAdapter:
    """테스트용: responses 를 순서대로 돌려준다."""

    responses: list[dict]
    name: str = "scripted"
    seen: list[list[dict]] = field(default_factory=list)

    def chat(self, messages: list[dict], tools: list[dict]) -> dict:
        self.seen.append(list(messages))
        return self.responses.pop(0)


def make_adapter(spec: str):
    """'ollama:qwen3:4b-instruct' | 'anthropic:claude-sonnet-5' | 'ollama' | 'anthropic'."""
    kind, _, model = spec.partition(":")
    if kind == "ollama":
        return OllamaAdapter(model=model) if model else OllamaAdapter()
    if kind == "anthropic":
        return AnthropicAdapter(model=model) if model else AnthropicAdapter()
    raise ValueError(spec)
