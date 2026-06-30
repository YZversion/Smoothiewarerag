"""
LLM Query Planner — 将自然语言问题拆解为多个源码检索 query。

不回答问题；失败时返回 fallback QueryPlan，不抛异常阻断检索。
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = LAB_ROOT / "prompts" / "query_planner.md"
ENV_PATH = LAB_ROOT / ".env"

DEFAULT_BASE_URL = {
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "openai": None,
}
DEFAULT_MODEL = {
    "zhipu": "glm-4-flash",
    "openai": "gpt-4o-mini",
}

VALID_INTENTS = frozenset({
    "symbol_lookup", "entry_point", "call_flow", "error_trace",
    "module_summary", "config_lookup", "unknown",
})

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


@dataclass
class QueryPlan:
    intent: str = "unknown"
    normalized_question: str = ""
    entities: list[str] = field(default_factory=list)
    symbols: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)
    must_have: list[str] = field(default_factory=list)
    target_kinds: list[str] = field(default_factory=list)
    notes: str = ""
    planner_fallback: bool = False

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "normalized_question": self.normalized_question,
            "entities": list(self.entities),
            "symbols": list(self.symbols),
            "search_queries": list(self.search_queries),
            "must_have": list(self.must_have),
            "target_kinds": list(self.target_kinds),
            "notes": self.notes,
            "planner_fallback": self.planner_fallback,
        }


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = val


def fallback_plan(question: str, *, reason: str = "") -> QueryPlan:
    q = question.strip()
    return QueryPlan(
        intent="unknown",
        normalized_question=q,
        search_queries=[q] if q else [],
        notes=reason or "planner fallback: using raw query only",
        planner_fallback=True,
    )


def build_query_planner_prompt(question: str, path: Path = PROMPT_PATH) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"query planner prompt not found: {path}")
    template = path.read_text(encoding="utf-8")
    return template.replace("{{QUESTION}}", question.strip())


def _extract_json_text(text: str) -> str:
    text = text.strip()
    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()
    m = _JSON_OBJECT_RE.search(text)
    if m:
        return m.group(0)
    return text


def _as_str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if item is None:
            continue
        s = str(item).strip()
        if s:
            out.append(s)
    return out


def parse_query_plan(text: str, question: str = "") -> QueryPlan:
    try:
        raw = json.loads(_extract_json_text(text))
    except (json.JSONDecodeError, TypeError):
        return fallback_plan(question, reason="planner fallback: JSON parse failed")

    if not isinstance(raw, dict):
        return fallback_plan(question, reason="planner fallback: expected JSON object")

    intent = str(raw.get("intent", "unknown")).strip()
    if intent not in VALID_INTENTS:
        intent = "unknown"

    normalized = str(raw.get("normalized_question", question)).strip() or question.strip()
    search_queries = _as_str_list(raw.get("search_queries"))
    if not search_queries and question.strip():
        search_queries = [question.strip()]

    return QueryPlan(
        intent=intent,
        normalized_question=normalized,
        entities=_as_str_list(raw.get("entities")),
        symbols=_as_str_list(raw.get("symbols")),
        search_queries=search_queries,
        must_have=_as_str_list(raw.get("must_have")),
        target_kinds=_as_str_list(raw.get("target_kinds")),
        notes=str(raw.get("notes", "")).strip(),
        planner_fallback=False,
    )


def _llm_settings() -> tuple[str, str, str, str | None] | None:
    load_dotenv()
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        return None
    provider = os.environ.get("LLM_PROVIDER", "zhipu").lower().strip()
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL.get(provider, "glm-4-flash"))
    base_url = os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL.get(provider)
    return provider, api_key, model, base_url


def plan_query(question: str, *, timeout: float = 15.0) -> QueryPlan:
    q = question.strip()
    if not q:
        return fallback_plan(q, reason="planner fallback: empty question")

    settings = _llm_settings()
    if settings is None:
        return fallback_plan(q, reason="planner fallback: LLM_API_KEY not set")

    provider, api_key, model, base_url = settings
    try:
        from openai import OpenAI
    except ImportError:
        return fallback_plan(q, reason="planner fallback: openai package not installed")

    try:
        prompt = build_query_planner_prompt(q)
    except OSError as exc:
        return fallback_plan(q, reason=f"planner fallback: {exc}")

    kwargs: dict = {"api_key": api_key, "timeout": timeout, "max_retries": 0}
    if base_url:
        kwargs["base_url"] = base_url

    try:
        client = OpenAI(**kwargs)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            return fallback_plan(q, reason="planner fallback: empty LLM response")
        return parse_query_plan(content, q)
    except Exception as exc:
        return fallback_plan(q, reason=f"planner fallback: {exc}")
