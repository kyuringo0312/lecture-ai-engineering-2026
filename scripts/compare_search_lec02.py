"""第2回 宿題（発展）: 学習モデルと同じ評価用の質問で、用語集の検索（app/tools.py）を採点する。

使い方:
    uv run python scripts/compare_search_lec02.py > lectures/02/results/adv_search.json

検索語の渡し方を 2 通り試す。
- question: 質問文をそのまま渡す
- keyword: エージェントが語を抜き出して渡す場合を想定し、人が選んだ語を渡す
"""

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.tools import search_glossary  # noqa: E402

# 質問ごとに、エージェントが抜き出しそうな語
KEYWORDS = {
    "LoRA はどんな手法か簡単に教えてください": "LoRA",
    "宿題の3レベルにはどんな段階がありますか": "3レベル",
    "この講座で標準に使う既定モデルは何ですか": "既定モデル",
    "answer.md はどこにあるファイルですか": "answer.md",
    "過学習に気づくにはどうすればいいですか": "過学習",
    "事前学習済みの重みを固定して小さな行列だけを学習する手法は何と呼びますか": "小さな行列",
    "重みを少ないビット数で表してメモリを減らす技術は何と呼びますか": "ビット数",
    "LLM が事実と異なる内容をもっともらしく生成する現象は何と呼びますか": "もっともらしく",
    "1 回の更新でパラメータをどれだけ動かすかを決める値は何と呼びますか": "パラメータをどれだけ動かす",
    "この講座で演習の開始時点のコードに付けている Git タグは何と呼びますか": "開始時点",
}


def load_eval() -> list:
    nb = json.loads((ROOT / "notebooks" / "lec02_3_adv_glossary.ipynb").read_text(encoding="utf-8"))
    src = next("".join(c["source"]) for c in nb["cells"] if "".join(c["source"]).startswith("# 評価用の質問"))
    tree = ast.parse(src)
    return ast.literal_eval(next(n.value for n in tree.body if isinstance(n, ast.Assign) and n.targets[0].id == "EVAL"))


def keyword_for(question: str) -> str:
    if question in KEYWORDS:
        return KEYWORDS[question]
    # 「X」とは何ですか？ の形は X を渡す
    return question.split("「")[1].split("」")[0]


def score(result: str, must: list[str]) -> dict:
    found = not result.startswith("用語集に")
    return {"found": found, "ok": all(w in result for w in must) if must else None}


def main() -> None:
    rows = []
    for group, question, must in load_eval():
        keyword = keyword_for(question)
        by_question = search_glossary(question)
        by_keyword = search_glossary(keyword)
        rows.append({
            "group": group, "question": question, "keyword": keyword, "must_include": must,
            "by_question": score(by_question, must), "by_keyword": score(by_keyword, must),
            "keyword_terms": [h["term"] for h in json.loads(by_keyword)] if by_keyword.startswith("[") else [],
        })

    summary = {}
    for mode in ["by_question", "by_keyword"]:
        summary[mode] = {}
        for g in ["known", "paraphrase", "reverse"]:
            rs = [r for r in rows if r["group"] == g]
            summary[mode][g] = f'{sum(r[mode]["ok"] for r in rs)}/{len(rs)}'
        for g in ["unknown_real", "unknown_fake"]:
            rs = [r for r in rows if r["group"] == g]
            summary[mode][g + "_not_found"] = f'{sum(not r[mode]["found"] for r in rs)}/{len(rs)}'
    print(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
