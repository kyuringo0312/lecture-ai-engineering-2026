"""第5回: 取得方法ごとに、どのページが返るか（根拠ページを含むか・本文が何文字か）を並べる。

LLM は呼ばず、質問の埋め込みだけを使う。
    uv run python -m scripts.inspect_retrieval_lec05
"""

from app import retrieval

QUESTIONS = {
    "Q1": ("第2回の説明では、LoRAは何を固定し何を学習しますか？ QLoRAは何を加えますか？",
           {"lec02-main-p052"}),
    "Q2": ("第3回の例では、コンパクションとセッションをまたぐメモリはどう違いますか。日々のメモはすべて長期メモリに入りますか",
           {"lec03-main-p013", "lec03-main-p039", "lec03-main-p040"}),
    "Q4": ("第2回の説明では、Fine-Tuningで知識を足すのが難しいのはなぜですか。知識を足したいときは何を使うとよいとされていますか",
           {"lec02-main-p046", "lec02-main-p047", "lec02-main-p053"}),
}


def vector(query, k):
    retrieval.RAG_TOP_K = k
    return retrieval.search(query)


METHODS = {
    "ベクトル top5": lambda q: vector(q, 5),
    "ベクトル top3": lambda q: vector(q, 3),
    "top5＋前後1ページ": lambda q: retrieval.add_neighbors(vector(q, 5), 1),
    "top3＋前後1ページ": lambda q: retrieval.add_neighbors(vector(q, 3), 1),
    "Graph（元）": lambda q: (lambda r: r["seeds"] + r["expanded"])(retrieval.search_graph(q)),
    "Graph（用語で絞る）": lambda q: (lambda r: r["seeds"] + r["expanded"])(retrieval.search_graph_focused(q)),
}


def short(page_id: str) -> str:
    doc, page = page_id.rsplit("-p", 1)
    return f"{doc[:5]}p{int(page)}"


def main() -> None:
    for key, (question, evidence) in QUESTIONS.items():
        print(f"\n## {key} {question}\n根拠ページ: {', '.join(sorted(short(p) for p in evidence))}")
        for name, method in METHODS.items():
            pages = method(question)
            ids = [p["page_id"] for p in pages]
            found = sorted(short(p) for p in evidence if p in ids)
            chars = sum(len(p["content"]) for p in pages)
            marked = " ".join(f"*{short(p)}" if p in evidence else short(p) for p in ids)
            print(f"- {name}: {len(ids)}ページ / 本文{chars:,}字 / 根拠 {len(found)}/{len(evidence)}  [{marked}]")
        focused = retrieval.search_graph_focused(question)
        print(f"  （用語で絞る Graph: 質問から拾った用語 {focused['matched_terms']}，候補 {focused['candidates']} ページ）")


if __name__ == "__main__":
    main()
