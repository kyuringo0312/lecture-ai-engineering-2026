"""第3回: エージェントに持たせるツール。

ここに書いた関数の docstring と型ヒントが、そのままモデルへの「ツールの説明文」になる。
説明文を書き換えると、モデルがツールを使うかどうか・どんな引数で呼ぶかが変わる。
"""

import json
import random
import re
from datetime import datetime
from functools import cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_DIR = Path(__file__).resolve().parent.parent / "learning_log"
MAX_RESULTS = 3


@cache
def load_glossary() -> list[dict]:
    with open(DATA_DIR / "glossary.json", encoding="utf-8") as f:
        return json.load(f)["terms"]


def _normalize(text: str) -> str:
    return text.casefold().replace(" ", "").replace("　", "")


def _names(entry: dict) -> list[str]:
    return [_normalize(entry["term"]), _normalize(entry["id"])] + [
        _normalize(a) for a in entry["aliases"]
    ]


def search_glossary(query: str) -> str:
    """講座の用語集から用語を検索し、定義と、どの回で扱うかを返す。

    AIエンジニアリングの用語や、この講座（AIE2026）に固有の言葉について
    答える前に使うこと。query には調べたい用語を1つだけ入れる（例: "LoRA"）。
    """
    q = _normalize(query)
    if not q:
        return "検索語が空です。調べたい用語を1つ指定してください。"
    glossary = load_glossary()

    exact = [e for e in glossary if q in _names(e)]
    # 「r」のような短い別名が何にでも当たらないよう、名前側が短いものは除く
    partial = [
        e for e in glossary
        if e not in exact and any(q in n or (len(n) >= 3 and n in q) for n in _names(e))
    ]
    in_definition = [
        e for e in glossary
        if e not in exact and e not in partial and q in _normalize(e["definition"])
    ]
    hits = (exact + partial + in_definition)[:MAX_RESULTS]

    if not hits:
        return f"用語集に「{query}」は見つかりませんでした。"
    return json.dumps(
        [
            {
                "term": e["term"],
                "lecture": e["lecture"],
                "definition": e["definition"],
                "related": e["related"],
            }
            for e in hits
        ],
        ensure_ascii=False,
    )


def get_lecture_summary(lecture: int) -> str:
    """指定した回（1始まりの整数）の講義の要点を返す。

    「第3回では何を学ぶ？」のように、回の内容や関係を聞かれたときに使う。
    """
    path = DATA_DIR / "lectures" / f"{lecture:02d}.md"
    if not path.exists():
        available = sorted(p.stem for p in (DATA_DIR / "lectures").glob("*.md"))
        return f"第{lecture}回の要点はまだありません。用意されている回: {', '.join(available)}"
    return path.read_text(encoding="utf-8")


def make_quiz(lecture: int) -> str:
    """指定した回（1始まりの整数）の用語から、確認問題を1問作って返す。

    「第2回の確認問題を出して」「復習のクイズを出して」のように、確認問題や
    クイズを求められたときに使う。返り値の question を出題し、answer は
    利用者が答えたあとの答え合わせに使う（出題と同時に answer を見せない）。
    """
    terms = [t for t in load_glossary() if t["lecture"] == lecture]
    if not terms:
        available = sorted({t["lecture"] for t in load_glossary()})
        return f"第{lecture}回の用語は用語集にありません。用語がある回: {', '.join(map(str, available))}"
    term = random.choice(terms)
    return json.dumps({"question": f"「{term['term']}」の意味は？", "answer": term["definition"]}, ensure_ascii=False)


def save_learning_log(title: str, content: str) -> str:
    """学習の記録（その日に学んだことのまとめ）を learning_log/ フォルダに Markdown で保存する。

    利用者が「学習記録に保存して」「今日のまとめを残して」のように保存を頼んだときだけ使う。
    title には記録の題名を、content には保存する本文を入れる。
    保存を頼まれたら、利用者に聞き返さずにすぐこのツールを呼ぶこと。実行してよいかの
    確認は、システムが利用者に直接行う。
    """
    LOG_DIR.mkdir(exist_ok=True)
    slug = re.sub(r"[^\w\-]+", "_", title).strip("_")[:40] or "log"
    path = LOG_DIR / f"{datetime.now():%Y%m%d-%H%M%S}_{slug}.md"
    path.write_text(f"# {title}\n\n{content.strip()}\n", encoding="utf-8")
    return f"{path.relative_to(LOG_DIR.parent)} に保存しました。"
