"""第1回: 素のLLMに質問するスクリプト。

使い方:
    uv run python -m app.ask "LoRAとは何ですか？"
    uv run python -m app.ask            # 質問を省略すると、講座に固有の質問をする
    uv run python -m app.ask --chat     # 会話履歴を保ったまま、続けて質問する（第1回 宿題・実装）

ツールを持たない「素の」呼び出し。
講座に固有のことを聞くと、「分からない」と答えるか、一般論でもっともらしく答える
（講座の実際とは違う）ことを確かめよう。
（第3回で、用語集を検索できるエージェントにして改善する）
"""

import argparse

from google import genai
from google.genai import errors, types

from app.config import MODEL, api_error_message, get_api_key

# 講座に固有の質問。正しい答えは data/glossary.json の homework-levels にある
DEFAULT_QUESTION = "AIE2026の講座の宿題にある「3レベル」とは何ですか？"

# 会話モードを終える入力
EXIT_WORDS = ("", "exit", "quit")


def format_usage(usage: types.GenerateContentResponseUsageMetadata | None) -> str:
    """usage_metadata から、入力・出力トークン数の1行を作る。"""
    if usage is None:
        return "[tokens] 取得できませんでした"
    line = f"[tokens] 入力: {usage.prompt_token_count} / 出力: {usage.candidates_token_count}"
    # 思考（thinking）するモデルでは、出力とは別に思考のトークンが数えられる
    if usage.thoughts_token_count:
        line += f" / 思考: {usage.thoughts_token_count}"
    return line + f" / 合計: {usage.total_token_count}"


def ask(question: str) -> str:
    client = genai.Client(api_key=get_api_key())
    response = client.models.generate_content(model=MODEL, contents=question)

    # 第1回 演習: 入力トークン数と出力トークン数を表示する
    print(format_usage(response.usage_metadata))

    return response.text


def chat(first_question: str | None = None) -> None:
    """会話履歴を保ったまま、続けて質問する（第1回 宿題・実装）。

    client.chats.create で作ったチャットは、送受信したメッセージを履歴として持ち、
    次の send_message で履歴ごとモデルに送る。そのため入力トークン数は回を追うごとに増える。
    """
    client = genai.Client(api_key=get_api_key())
    session = client.chats.create(model=MODEL)
    print("会話モード（空行・exit・quit・Ctrl+D で終了）")

    question = first_question
    while True:
        if question is None:
            try:
                question = input("\n[質問] ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
        if question in EXIT_WORDS:
            break
        try:
            response = session.send_message(question)
        except errors.APIError as e:
            # 失敗した質問は履歴に入らないので、待ってから同じ質問をし直せる
            print(api_error_message(e.code, e.message))
        else:
            print(format_usage(response.usage_metadata))
            print(response.text)
        question = None

    print(f"[履歴] {len(session.get_history())} メッセージ")


def main() -> None:
    parser = argparse.ArgumentParser(description="素のLLMに質問する")
    parser.add_argument("question", nargs="?")
    parser.add_argument("--chat", action="store_true", help="会話履歴を保ったまま続けて質問する")
    args = parser.parse_args()

    print(f"[model] {MODEL}")
    if args.chat:
        chat(args.question)
        return

    question = args.question or DEFAULT_QUESTION
    print(f"[質問] {question}\n")
    try:
        print(ask(question))
    except errors.APIError as e:
        print(api_error_message(e.code, e.message))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
