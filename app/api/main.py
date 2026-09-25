"""FastAPI: 에이전트와 같은 도구를 HTTP 로 노출한다 (웹서비스 로드맵 경계 1).

uv run --group serve uvicorn app.api.main:app --reload
GET  /v1/health
GET  /v1/tools                 도구 목록과 입력 스키마
POST /v1/tools/{name}          도구 실행 (body = 인자 JSON). 응답 봉투는 에이전트와 같다
POST /v1/ask                   에이전트 질의 {"question", "model"?, "as_of"?}
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agent.tools import registry

app = FastAPI(title="sabior API", version="0.1.0")


@app.get("/v1/health")
def health() -> dict:
    from agent.tools.base import con

    n = con().execute("SELECT count(*) FROM batting_seasons").fetchone()[0]
    return {"ok": True, "batting_rows": n, "tools": len(registry.tools)}


@app.get("/v1/tools")
def list_tools() -> list[dict]:
    return registry.schemas()


@app.post("/v1/tools/{name}")
def call_tool(name: str, args: dict) -> dict:
    if name not in registry.tools:
        raise HTTPException(404, f"없는 도구: {name}")
    return registry.call(name, args)


class Ask(BaseModel):
    question: str
    model: str = "ollama:qwen3:4b-instruct"
    as_of: str | None = None


@app.post("/v1/ask")
def ask(q: Ask) -> dict:
    from dataclasses import asdict

    from agent.adapters import make_adapter
    from agent.runner import run

    return asdict(run(q.question, make_adapter(q.model), q.as_of))
