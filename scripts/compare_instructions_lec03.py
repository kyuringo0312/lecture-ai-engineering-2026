"""第3回 宿題（基礎）: INSTRUCTIONS とツールの説明文を 1 か所ずつ変え、同じ質問でふるまいを比べる。

使い方:
    uv run python scripts/compare_instructions_lec03.py --repeat 2 --out lectures/03/results/basic.jsonl

app/agent.py と同じツールを登録したエージェントを、変更点ごとに組み立て直して実行する。
--trace と同じく、どのツールがどの引数で呼ばれたか、LLM を何回呼んだか（requests）を記録する。
"""

import argparse
import functools
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic_ai import Agent, DeferredToolRequests  # noqa: E402
from pydantic_ai.exceptions import ModelHTTPError  # noqa: E402
from pydantic_ai.messages import ToolCallPart  # noqa: E402

from app import tools  # noqa: E402
from app.agent import INSTRUCTIONS, build_model  # noqa: E402

MUST_SEARCH = "- 用語や講座に固有のことを答える前に、必ず search_glossary で用語集を確認する。\n"
SHOW_LECTURE = "- 回答の最後に、関係する回（第N回）を示す。\n"
ONE_TERM = 'query には調べたい用語を1つだけ入れる（例: "LoRA"）。'
assert MUST_SEARCH in INSTRUCTIONS and SHOW_LECTURE in INSTRUCTIONS and ONE_TERM in tools.search_glossary.__doc__

# 変更点ごとに (INSTRUCTIONS, search_glossary の説明文) を作る。どれも元から 1 か所だけ変える
VARIANTS = {
    "base": (INSTRUCTIONS, tools.search_glossary.__doc__),
    "no_must_search": (INSTRUCTIONS.replace(MUST_SEARCH, ""), tools.search_glossary.__doc__),
    "doc_bulk_query": (INSTRUCTIONS, tools.search_glossary.__doc__.replace(
        ONE_TERM, 'query には調べたい用語をまとめて入れる（例: "LoRA QLoRA"）。')),
    "quiz_at_end": (INSTRUCTIONS.replace(SHOW_LECTURE, "- 回答の最後に、確認問題を1問出す。\n"), tools.search_glossary.__doc__),
}
QUESTIONS = [
    "LoRAとQLoRAの違いは？",
    "AIE2026の講座で使う「lecNN-start タグ」とは何ですか？",
]


def build_agent(instructions: str, search_doc: str) -> Agent:
    @functools.wraps(tools.search_glossary)
    def search_glossary(query: str) -> str:
        return tools.search_glossary(query)

    search_glossary.__doc__ = search_doc
    a = Agent(instructions=instructions, output_type=[str, DeferredToolRequests])
    a.tool_plain(search_glossary)
    a.tool_plain(tools.get_lecture_summary)
    a.tool_plain(tools.make_quiz)
    a.tool_plain(tools.save_learning_log, requires_approval=True)
    return a


def run_once(a: Agent, model, variant: str, question: str, i: int) -> dict:
    record = {"variant": variant, "question": question, "run": i}
    t0 = time.perf_counter()
    try:
        result = a.run_sync(question, model=model)
    except ModelHTTPError as e:
        record.update(error=e.status_code, seconds=round(time.perf_counter() - t0, 1))
        return record
    calls = [{"tool": p.tool_name, "args": p.args_as_dict()} for m in result.all_messages() for p in m.parts if isinstance(p, ToolCallPart)]
    usage = result.usage
    output = result.output if isinstance(result.output, str) else repr(result.output)
    record.update(seconds=round(time.perf_counter() - t0, 1), tool_calls=calls, requests=usage.requests,
                  input_tokens=usage.input_tokens, output_tokens=usage.output_tokens, output=output)
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeat", type=int, default=2)
    parser.add_argument("--interval", type=float, default=20.0, help="無料枠の毎分の上限を超えないよう、実行の間に待つ秒数")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)

    model = build_model()
    n = 0
    for variant, (instructions, doc) in VARIANTS.items():
        a = build_agent(instructions, doc)
        for question in QUESTIONS:
            for i in range(1, args.repeat + 1):
                if n:
                    time.sleep(args.interval)
                n += 1
                record = run_once(a, model, variant, question, i)
                calls = ", ".join(f'{c["tool"]}({json.dumps(c["args"], ensure_ascii=False)})' for c in record.get("tool_calls", []))
                print(f"[{variant}] {question} #{i} requests={record.get('requests')} calls=[{calls}] error={record.get('error')}", flush=True)
                with args.out.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
