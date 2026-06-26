"""
Phase 4 — 检索上下文 + LLM 代码问答

用法：
    python src/04_answer.py "G-code 从哪里进入系统？"
    python src/04_answer.py "halt emergency" --top-k 8 --json
    python src/04_answer.py --demo          # 跑 eval Q1–Q5

环境变量（或 industrial-cpp-kb-lab/.env）：
    LLM_PROVIDER   zhipu | openai（默认 zhipu）
    LLM_API_KEY    API 密钥（勿提交 git）
    LLM_MODEL      默认 glm-4-flash（zhipu）/ gpt-4o-mini（openai）
    LLM_BASE_URL   可选；zhipu 默认 https://open.bigmodel.cn/api/paas/v4
"""

import argparse
import importlib.util
import json
import os
import re
import sys
from collections.abc import Iterator
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    sys.exit("openai 未安装，请运行: pip install -r requirements.txt")

# ── 路径配置 ──────────────────────────────────────────────
LAB_ROOT = Path(__file__).parent.parent
PROMPT_PATH = LAB_ROOT / "prompts" / "code_qa.md"
ENV_PATH = LAB_ROOT / ".env"
EVAL_PATH = LAB_ROOT / "eval" / "eval_questions.json"

MAX_CONTEXT_CHUNKS = 8

DEFAULT_BASE_URL = {
    "zhipu": "https://open.bigmodel.cn/api/paas/v4",
    "openai": None,
}
DEFAULT_MODEL = {
    "zhipu": "glm-4-flash",
    "openai": "gpt-4o-mini",
}

CITE_RE = re.compile(
    r"`((?:src/)?[\w./-]+\.(?:cpp|h|hpp|c)):(\d+)(?:-\d+)?`",
    re.IGNORECASE,
)


def normalize_cite_path(path: str) -> str:
    p = path.replace("\\", "/")
    return p if p.startswith("src/") else f"src/{p.lstrip('/')}"


def citation_in_hits(file: str, line: int, hits: list[dict],
                     chunk_by_id: dict) -> bool:
    for h in hits:
        if h["file"] != file:
            continue
        chunk = chunk_by_id.get(h["chunk_id"])
        if chunk and chunk["start_line"] <= line <= chunk["end_line"]:
            return True
    return False


def validate_citations(answer: str, hits: list[dict],
                       chunk_by_id: dict) -> dict:
    """检查回答中的 `file:line` 是否落在检索 bundle 的 chunk 行范围内。"""
    valid: list[str] = []
    invalid: list[str] = []
    for m in CITE_RE.finditer(answer):
        cite = m.group(0)
        file = normalize_cite_path(m.group(1))
        line = int(m.group(2))
        if citation_in_hits(file, line, hits, chunk_by_id):
            valid.append(cite)
        else:
            invalid.append(cite)
    return {
        "valid": valid,
        "invalid": invalid,
        "ok": len(invalid) == 0 or (len(valid) > 0 and len(invalid) <= len(valid)),
    }


def load_dotenv(path: Path) -> None:
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


def import_search_module():
    path = Path(__file__).parent / "03_search.py"
    spec = importlib.util.spec_from_file_location("_kb_search", path)
    if spec is None or spec.loader is None:
        sys.exit(f"无法加载 {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_prompt_template(path: Path = PROMPT_PATH) -> str:
    if not path.is_file():
        sys.exit(f"prompt 不存在: {path}")
    return path.read_text(encoding="utf-8")


def trim_context_hits(hits: list[dict],
                      max_chunks: int = MAX_CONTEXT_CHUNKS) -> list[dict]:
    """截断 LLM 上下文：优先保留 primary，overview/header 不挤占实现 chunk。"""
    if len(hits) <= max_chunks:
        return hits
    primaries = [h for h in hits if h.get("bundle_role") == "primary"]
    others = [h for h in hits if h.get("bundle_role") != "primary"]
    primaries.sort(key=lambda h: -h["score"])
    others.sort(key=lambda h: -h["score"])
    if len(primaries) >= max_chunks:
        return primaries[:max_chunks]
    return primaries + others[: max_chunks - len(primaries)]


def format_context_chunks(hits: list[dict]) -> str:
    if not hits:
        return "（检索未返回任何 chunk）"
    blocks = []
    for i, h in enumerate(hits, 1):
        sym = h.get("symbol") or ""
        sym_start = h.get("symbol_start") or h.get("chunk_line_start") or h["line_start"]
        c_start = h.get("chunk_line_start", h["line_start"])
        c_end = h.get("chunk_line_end", h.get("line_end", h["line_start"]))
        role = h.get("bundle_role", "primary")
        blocks.append(
            f"#### [{i}] `{h['file']}:{sym_start}`  role={role}  type={h['type']}"
            f"  symbol={sym}  symbol_start={sym_start}  chunk_lines={c_start}-{c_end}"
            f"  score={h['score']}  source={h.get('source', '')}\n"
            f"```cpp\n{h['snippet']}\n```"
        )
    return "\n\n".join(blocks)


def build_prompt(template: str, question: str, hits: list[dict]) -> str:
    ctx = format_context_chunks(trim_context_hits(hits))
    return (
        template.replace("{{question}}", question.strip())
        .replace("{{context_chunks}}", ctx)
    )


def llm_config() -> tuple[str, str, str, str | None]:
    load_dotenv(ENV_PATH)
    provider = os.environ.get("LLM_PROVIDER", "zhipu").lower().strip()
    api_key = os.environ.get("LLM_API_KEY", "").strip()
    if not api_key:
        sys.exit(
            "未设置 LLM_API_KEY。请 export 或写入 industrial-cpp-kb-lab/.env\n"
            "参考 .env.example"
        )
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL.get(provider, "glm-4-flash"))
    base_url = os.environ.get("LLM_BASE_URL") or DEFAULT_BASE_URL.get(provider)
    if provider not in DEFAULT_MODEL and provider != "openai":
        # 未知 provider 仍尝试 openai 兼容接口
        if not base_url:
            sys.exit(f"未知 LLM_PROVIDER={provider}，请设置 LLM_BASE_URL")
    return provider, api_key, model, base_url


def call_llm(prompt: str, provider: str, api_key: str, model: str,
             base_url: str | None) -> str:
    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return (resp.choices[0].message.content or "").strip()


def call_llm_stream(prompt: str, provider: str, api_key: str, model: str,
                    base_url: str | None) -> Iterator[str]:
    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        stream=True,
    )
    for chunk in stream:
        yield chunk.choices[0].delta.content or ""


def answer_stream(question: str, top_k: int = 5,
                  search_mod=None) -> tuple[list[dict], Iterator[str]]:
    kb = search_mod or import_search_module()
    if not kb._CHUNKS:
        kb.load_index()

    hits = kb.search(question, top_k=top_k, bundle=True)
    template = load_prompt_template()
    prompt = build_prompt(template, question, hits)
    provider, api_key, model, base_url = llm_config()
    return hits, call_llm_stream(prompt, provider, api_key, model, base_url)


def answer(question: str, top_k: int = 5, search_mod=None) -> dict:
    kb = search_mod or import_search_module()
    if not kb._CHUNKS:
        kb.load_index()

    hits = kb.search(question, top_k=top_k, bundle=True)
    template = load_prompt_template()
    prompt = build_prompt(template, question, hits)
    provider, api_key, model, base_url = llm_config()
    text = call_llm(prompt, provider, api_key, model, base_url)
    cites = validate_citations(text, hits, kb._CHUNK_BY_ID)

    return {
        "question": question,
        "top_k": top_k,
        "hits": hits,
        "answer": text,
        "provider": provider,
        "model": model,
        "citations": cites,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="检索 + LLM 代码问答")
    p.add_argument("question", nargs="?", help="用户问题")
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--json", action="store_true", help="JSON 输出（不含完整 prompt）")
    p.add_argument("--demo", action="store_true", help="依次运行 eval Q1–Q5")
    p.add_argument("--show-context", action="store_true", help="打印检索 context 摘要")
    return p.parse_args()


def print_result(result: dict, show_context: bool = False) -> None:
    print("=" * 60)
    print(f"Q: {result['question']}")
    print(f"model: {result['provider']} / {result['model']}  "
          f"chunks: {len(result['hits'])}")
    if show_context:
        print("\n--- context ---")
        for h in result["hits"]:
            role = h.get("bundle_role", "primary")
            print(f"  {h['file']}:{h['line_start']}  {h.get('symbol', '')}  "
                  f"role={role}  [{h['score']}]")
    cites = result.get("citations")
    if cites:
        mark = "OK" if cites["ok"] else "WARN"
        print(f"\n--- 引用校验 [{mark}] ---")
        if cites["valid"]:
            print(f"  valid: {cites['valid'][:5]}")
        if cites["invalid"]:
            print(f"  invalid: {cites['invalid'][:5]}")
    print("\n--- answer ---\n")
    print(result["answer"])
    print()


def main() -> None:
    args = parse_args()
    kb = import_search_module()
    kb.load_index()

    if args.demo:
        data = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
        for q in data["questions"]:
            result = answer(q["question"], top_k=args.top_k, search_mod=kb)
            print_result(result, show_context=args.show_context)
        return

    if not args.question:
        print("请提供 question，或使用 --demo", file=sys.stderr)
        sys.exit(1)

    result = answer(args.question, top_k=args.top_k, search_mod=kb)
    if args.json:
        out = {k: v for k, v in result.items() if k != "hits"}
        out["context_citations"] = [
            {"file": h["file"], "line_start": h["line_start"],
             "symbol": h.get("symbol", ""), "bundle_role": h.get("bundle_role"),
             "score": h["score"]}
            for h in result["hits"]
        ]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return

    print_result(result, show_context=args.show_context)


if __name__ == "__main__":
    main()
