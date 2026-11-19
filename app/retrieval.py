"""第5回: ページ単位のベクトル検索。"""

import argparse
import json
import math
import re
import sqlite3
from contextlib import contextmanager
from collections import defaultdict, deque
from pathlib import Path

from google import genai
from google.genai import types
from pydantic_ai.exceptions import ModelHTTPError
import sqlite_vec

from app.config import (
    EMBEDDING_DIMENSIONS, EMBEDDING_MAX_TOKENS, EMBEDDING_MODEL,
    RAG_DB, RAG_DOCUMENT_IDS, RAG_SOURCE, RAG_TOP_K, RAG_TREE, get_api_key,
    RAG_GRAPH, GRAPH_START_K, GRAPH_HOPS, GRAPH_MAX_RESULTS,
)


def get_all_materials() -> str:
    """全資料を、講義・章・ページの情報付きで1つの文字列にまとめる。"""
    documents = json.loads(RAG_SOURCE.read_text(encoding="utf-8"))
    return "\n\n".join(
        f"資料: {document['id']} / {document['title']}\n"
        f"章: {section['section']}\n"
        f"ページ: PDF p.{page['page']} / {page['title']}\n{page['content']}"
        for document in documents
        for section in document["content"]
        for page in section["content"]
    )

def load_pages(source: Path = RAG_SOURCE) -> list[dict]:
    """資料→章→ページのJSONを、対象資料のページ一覧に変換する。"""
    documents = json.loads(source.read_text(encoding="utf-8"))
    pages = []
    for document in documents:
        if document["id"] not in RAG_DOCUMENT_IDS:
            continue
        for section in document["content"]:
            for page in section["content"]:
                pages.append({"page_id": page["id"], "document_id": document["id"],
                              "lecture": int(document["id"][3:5]), "document_title": document["title"],
                              "section": section["section"], "title": page["title"],
                              "page": page["page"], "content": page["content"]})
    return pages


def browse_tree(node_id: str | None = None) -> dict:
    """直下のページは先頭文、指定したページ自身は全文を返す。"""
    tree = json.loads(RAG_TREE.read_text(encoding="utf-8"))
    tree["children"] = [node for node in tree["children"] if node["id"] in RAG_DOCUMENT_IDS]
    node_id = node_id or tree["id"]
    pages = {page["page_id"]: page for page in load_pages(RAG_SOURCE)}

    def describe(node, full=False):
        info = {key: node[key] for key in ("id", "kind", "title")}
        if node["kind"] == "page":
            info.update({key: value for key, value in pages[node["id"]].items() if key != "page_id"})
            if not full:
                info["content"] = re.split(r"(?<=[。！？])|\n", info["content"].strip(), maxsplit=1)[0]
        return info

    remaining = [tree]
    while remaining:
        node = remaining.pop()
        if node["id"] == node_id:
            return {
                "node": describe(node, full=True),
                "children": [describe(child) for child in node.get("children", [])],
            }
        remaining.extend(node.get("children", []))
    raise ValueError("対象の目次ノードが見つかりません。")


def read_page(page_id: str) -> dict:
    """第1〜3回の本講義から、指定した1ページの本文と引用情報を返す。"""
    for page in load_pages(RAG_SOURCE):
        if page["page_id"] == page_id:
            return page
    raise ValueError("対象のページが見つかりません。")


def normalized_vector(values: list[float]) -> list[float]:
    """ベクトルの長さを1に揃える。"""
    norm = math.hypot(*values)
    if norm == 0:
        raise ValueError("埋め込みがゼロベクトルです。")
    return [value / norm for value in values]


def embed_text(text: str, task_type: str) -> list[float]:
    """Geminiで文章を埋め込む。入力上限を超えた場合は切り捨てず停止する。"""
    with genai.Client(api_key=get_api_key()) as client:
        count = client.models.count_tokens(model=EMBEDDING_MODEL, contents=text).total_tokens
        if count is None or count > EMBEDDING_MAX_TOKENS:
            raise ValueError(f"埋め込み入力が上限を超えるか計測不能です: {count} tokens。")
        response = client.models.embed_content(
            model=EMBEDDING_MODEL, contents=text,
            config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBEDDING_DIMENSIONS),
        )
    embedding = response.embeddings[0]
    if embedding.statistics and embedding.statistics.truncated:
        raise ValueError("埋め込みAPIが本文を切り捨てました。")
    return normalized_vector(embedding.values)


@contextmanager
def open_index(path: Path):
    """既存の検索DBを読み取り専用で開き、終了時に閉じる。"""
    if not path.is_file():
        raise FileNotFoundError("検索DBがありません。")
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        db.row_factory = sqlite3.Row
        db.enable_load_extension(True)
        sqlite_vec.load(db)
        db.enable_load_extension(False)
        yield db
    finally:
        db.close()


def search(query: str) -> list[dict]:
    """質問を埋め込み、近いページを最大RAG_TOP_K件返す。"""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("検索語が空です。")
    with open_index(RAG_DB) as db:
        vector = embed_text(query.strip(), "RETRIEVAL_QUERY")
        rows = db.execute("""
            SELECT page_id, document_id, lecture, document_title, section, title, page, content,
                   vec_distance_cosine(embedding, ?) AS distance
            FROM chunks ORDER BY distance, page_id LIMIT ?
        """, (sqlite_vec.serialize_float32(vector), RAG_TOP_K))
        return [dict(row) for row in rows]


def search_graph(query: str) -> dict:
    """ベクトル検索を入口に、前後ページと共通用語で候補を広げる。"""
    pages = {page["page_id"]: page for page in load_pages(RAG_SOURCE)}
    graph = json.loads(RAG_GRAPH.read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in graph["nodes"]
             if node["kind"] == "term" or node["id"] in pages}
    adjacent = defaultdict(set)
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        if edge["relation"] in ("next_page", "mentions") and a in nodes and b in nodes:
            adjacent[a].add(b)
            adjacent[b].add(a)

    seeds = [hit for hit in search(query) if hit["page_id"] in pages][:min(GRAPH_START_K, GRAPH_MAX_RESULTS)]
    seed_ids = {seed["page_id"] for seed in seeds}
    results, candidates = [], {}
    for rank, seed in enumerate(seeds):
        root = seed["page_id"]
        results.append({**pages[root], "distance": seed["distance"], "hops": 0,
                        "path": [{"id": root, "title": pages[root]["title"]}]})
        queue = deque([(root, [root])])
        visited = {root}
        while queue:
            current, path = queue.popleft()
            if len(path) - 1 >= GRAPH_HOPS:
                continue
            # 同じ深さなら、接続先が少ない用語からたどる。
            neighbors = sorted(adjacent[current], key=lambda n: (len(adjacent[n]), n))
            for neighbor in neighbors:
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                route = path + [neighbor]
                queue.append((neighbor, route))
                if neighbor not in pages or neighbor in seed_ids:
                    continue
                frequency = max((len(adjacent[n]) for n in route if nodes[n]["kind"] == "term"), default=0)
                priority = (len(route) - 1, frequency, rank, neighbor)
                candidate = {**pages[neighbor], "hops": len(route) - 1,
                             "path": [{"id": n, "title": nodes[n]["title"]} for n in route]}
                if neighbor not in candidates or priority < candidates[neighbor][0]:
                    candidates[neighbor] = (priority, candidate)
    expanded = [candidate for _, candidate in sorted(candidates.values())]
    return {"seeds": results, "expanded": expanded[:max(0, GRAPH_MAX_RESULTS - len(results))],
            "max_hops": GRAPH_HOPS}


def add_neighbors(hits: list[dict], window: int = 1) -> list[dict]:
    """第5回 宿題（実装）: 検索結果の各ページに、同じ資料の前後 window ページの本文を足す。

    スライドの説明は前後のページに続くことが多いので、検索で当たったページの隣も一緒に渡す。
    同じページは 1 回だけ返し、隣のページには、どの検索結果の隣かを neighbor_of に残す。
    """
    pages = load_pages(RAG_SOURCE)
    position = {page["page_id"]: i for i, page in enumerate(pages)}
    seen = {hit["page_id"] for hit in hits}
    results = []
    for hit in hits:
        results.append({**hit, "role": "hit"})
        i = position.get(hit["page_id"])
        if i is None:
            continue
        for j in range(i - window, i + window + 1):
            if j == i or not 0 <= j < len(pages):
                continue
            page = pages[j]
            if page["document_id"] != hit["document_id"] or page["page_id"] in seen:
                continue
            seen.add(page["page_id"])
            results.append({**page, "role": "neighbor", "neighbor_of": hit["page_id"]})
    return results


def matched_terms(query: str, terms: list[dict]) -> list[dict]:
    """質問の文字列に、名前か別名がそのまま出てくる用語を返す（2文字未満の別名は使わない）。"""
    q = query.casefold()
    return [term for term in terms
            if any(len(name) >= 2 and name.casefold() in q for name in [term["title"], *term.get("aliases", [])])]


def search_graph_focused(query: str) -> dict:
    """第5回 宿題（発展）: 質問に出てくる用語と前後ページだけをたどり、質問との近さで候補を選ぶ。

    元の search_graph は、入口から 2 hop 以内のページを「hop 数 → 用語の珍しさ」の順に選ぶので、
    質問と関係の薄い用語を経由したページも入る。ここでは、
    1. 入口：ベクトル検索の上位 GRAPH_START_K ページ（元と同じ）
    2. 候補：入口の前後ページ（next_page）と、質問に出てくる用語に言及するページ（mentions）
    3. 選択：候補を質問との距離が近い順に並べ、入口と合わせて最大 GRAPH_MAX_RESULTS ページ
    とする。グラフは「どこを候補にするか」を絞るために使い、順位は質問との近さで決める。
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("検索語が空です。")
    pages = {page["page_id"]: page for page in load_pages(RAG_SOURCE)}
    graph = json.loads(RAG_GRAPH.read_text(encoding="utf-8"))
    terms = matched_terms(query, [node for node in graph["nodes"] if node["kind"] == "term"])
    mentioned_by, next_pages = defaultdict(set), defaultdict(set)
    for edge in graph["edges"]:
        a, b = edge["source"], edge["target"]
        if edge["relation"] == "mentions":
            page, term = (a, b) if b.startswith("term:") else (b, a)
            mentioned_by[term].add(page)
        elif edge["relation"] == "next_page":
            next_pages[a].add(b)
            next_pages[b].add(a)

    with open_index(RAG_DB) as db:
        vector = embed_text(query.strip(), "RETRIEVAL_QUERY")
        rows = db.execute("SELECT page_id, vec_distance_cosine(embedding, ?) AS distance FROM chunks",
                          (sqlite_vec.serialize_float32(vector),))
        distance = {row["page_id"]: row["distance"] for row in rows if row["page_id"] in pages}

    seeds = sorted(distance, key=lambda p: (distance[p], p))[:min(GRAPH_START_K, GRAPH_MAX_RESULTS)]
    via = {}
    for seed in seeds:
        for page_id in sorted(next_pages[seed]):
            if page_id in distance:
                via.setdefault(page_id, f"前後ページ（{pages[seed]['title']}）")
    for term in terms:
        for page_id in sorted(mentioned_by[term["id"]]):
            if page_id in distance:
                via.setdefault(page_id, f"用語「{term['title']}」")
    for seed in seeds:
        via.pop(seed, None)
    chosen = sorted(via, key=lambda p: (distance[p], p))[:max(0, GRAPH_MAX_RESULTS - len(seeds))]
    return {
        "seeds": [{**pages[p], "distance": distance[p]} for p in seeds],
        "expanded": [{**pages[p], "distance": distance[p], "via": via[p]} for p in chosen],
        "matched_terms": [term["title"] for term in terms],
        "candidates": len(via),
    }



def run_full_context(agent, question: str, model, instructions: str, prompt_template: str):
    """全資料を一括投入し、検索ツールを使わずに回答する。"""
    prompt = prompt_template.format(materials=get_all_materials(), question=question)
    print(f"[full-context] 入力{len(prompt):,}文字")
    try:
        with agent.override(tools=[], instructions=instructions):
            return agent.run_sync(prompt, model=model)
    except ModelHTTPError as e:
        print(f"[full-context] APIエラー HTTP {e.status_code}: {e.body}")
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="エージェントを使わず、講義資料の検索だけを実行する")
    parser.add_argument("query", help="調べたい内容")
    parser.add_argument("--neighbors", type=int, default=0, help="第5回 宿題（実装）: 前後 N ページの本文も付ける")
    args = parser.parse_args()
    results = search(args.query)
    if args.neighbors:
        results = add_neighbors(results, args.neighbors)
    for i, result in enumerate(results, 1):
        role = f"（{result['neighbor_of']} の隣）" if result.get("role") == "neighbor" else ""
        print(f"\n{'=' * 60}\n検索結果 {i}{role}\n{'=' * 60}")
        print(f"講義: {result['document_title']}")
        print(f"章: {result['section']}")
        print(f"タイトル: {result['title']}")
        print(f"ページ: {result['page']}")
        print(f"\n{result['content']}")
