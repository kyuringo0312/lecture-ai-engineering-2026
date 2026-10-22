"""第1回 宿題（基礎・発展）: 同じ質問を、モデルや temperature を変えて繰り返し実行し、
回答・応答時間・トークン数を JSONL に記録して、表にまとめる。

使い方:
    # モデルを変えて比べる（基礎・発展）
    uv run python -m app.compare --models gemini-3.5-flash-lite gemini-3.8-flash \\
        --questions "LoRAとは何ですか？" "AIE2026の講座の宿題にある「3レベル」とは何ですか？" \\
        --repeat 3 --out lectures/01/results/models.jsonl

    # temperature を変えて比べる（基礎）
    uv run python -m app.compare --temperatures 0 1 2 --repeat 3 \\
        --out lectures/01/results/temperature.jsonl

    # 記録済みの JSONL を表にするだけ
    uv run python -m app.compare --summary lectures/01/results/models.jsonl

無料枠のレート制限（1分あたりのリクエスト数）を超えないよう、呼び出しの間に --interval 秒待つ。
"""

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path

from google import genai
from google.genai import errors, types

from app.ask import DEFAULT_QUESTION
from app.config import MODEL, api_error_message, get_api_key

# 429（レート制限）のときに待つ秒数
RATE_LIMIT_WAIT = 60


def run_once(client: genai.Client, model: str, question: str, temperature: float | None) -> dict:
    """1回だけ質問し、回答・応答時間・トークン数（失敗したらエラー）を dict にする。"""
    config = types.GenerateContentConfig(temperature=temperature) if temperature is not None else None
    record = {"model": model, "temperature": temperature, "question": question}
    start = time.perf_counter()
    try:
        response = client.models.generate_content(model=model, contents=question, config=config)
    except errors.APIError as e:
        record["seconds"] = round(time.perf_counter() - start, 2)
        record["error"] = e.code
        record["message"] = api_error_message(e.code, e.message)
        return record
    record["seconds"] = round(time.perf_counter() - start, 2)
    usage = response.usage_metadata
    record["input_tokens"] = usage.prompt_token_count if usage else None
    record["output_tokens"] = usage.candidates_token_count if usage else None
    record["thought_tokens"] = (usage.thoughts_token_count or 0) if usage else None
    record["total_tokens"] = usage.total_token_count if usage else None
    record["text"] = response.text
    return record


def summarize(records: list[dict]) -> str:
    """モデル・temperature・質問ごとに、成功数と応答時間・トークン数の平均を Markdown の表にする。"""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in records:
        groups[(r["model"], r["temperature"], r["question"])].append(r)

    lines = [
        "| モデル | temperature | 質問 | 成功/回数 | 応答時間 平均(最小〜最大) 秒 | 入力 | 出力 平均 | 思考 平均 | 合計 平均 | 回答の文字数 平均 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for (model, temperature, question), rs in groups.items():
        ok = [r for r in rs if "error" not in r]
        temp = "既定" if temperature is None else temperature
        if not ok:
            codes = ",".join(str(r["error"]) for r in rs)
            lines.append(f"| {model} | {temp} | {question} | 0/{len(rs)}（{codes}） | - | - | - | - | - | - |")
            continue
        secs = [r["seconds"] for r in ok]

        def mean(key: str) -> str:
            return f"{statistics.mean(r[key] or 0 for r in ok):.0f}"

        chars = statistics.mean(len(r["text"] or "") for r in ok)
        lines.append(
            f"| {model} | {temp} | {question} | {len(ok)}/{len(rs)} "
            f"| {statistics.mean(secs):.1f}({min(secs):.1f}〜{max(secs):.1f}) "
            f"| {ok[0]['input_tokens']} | {mean('output_tokens')} | {mean('thought_tokens')} "
            f"| {mean('total_tokens')} | {chars:.0f} |"
        )
    return "\n".join(lines)


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def main() -> None:
    parser = argparse.ArgumentParser(description="モデル・temperature を変えて同じ質問を繰り返し、記録する")
    parser.add_argument("--models", nargs="+", default=[MODEL])
    parser.add_argument("--questions", nargs="+", default=[DEFAULT_QUESTION])
    parser.add_argument("--temperatures", nargs="+", type=float, default=[None])
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--interval", type=float, default=13.0, help="呼び出しの間に待つ秒数")
    parser.add_argument("--out", type=Path, help="記録を追記する JSONL ファイル")
    parser.add_argument("--summary", type=Path, help="記録済みの JSONL を表にするだけ")
    args = parser.parse_args()

    if args.summary:
        print(summarize(load(args.summary)))
        return

    client = genai.Client(api_key=get_api_key())
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)

    records = []
    plan = [
        (model, question, temperature, i)
        for model in args.models
        for question in args.questions
        for temperature in args.temperatures
        for i in range(1, args.repeat + 1)
    ]
    for n, (model, question, temperature, i) in enumerate(plan, 1):
        if n > 1:
            time.sleep(args.interval)
        started_at = time.strftime("%H:%M:%S")
        record = run_once(client, model, question, temperature)
        record["run"] = i
        record["started_at"] = started_at
        records.append(record)
        status = record.get("message") or f"{record['seconds']}s 入力{record['input_tokens']} 出力{record['output_tokens']} 思考{record['thought_tokens']}"
        print(f"[{n}/{len(plan)}] {model} t={temperature} #{i} {question[:20]} → {status}", flush=True)
        if args.out:
            with args.out.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if record.get("error") == 429:
            time.sleep(RATE_LIMIT_WAIT)

    print()
    print(summarize(records))


if __name__ == "__main__":
    main()
