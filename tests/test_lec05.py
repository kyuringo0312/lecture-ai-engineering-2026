"""第5回 宿題（実装・発展）で足した取得処理のテスト。埋め込みAPIは呼ばない。"""

import json
import sqlite3
import struct

from app import config, retrieval, tools


def _stored_embedding(page_id: str) -> list[float]:
    """同梱の検索DBから、そのページの埋め込みを読み出す（質問の埋め込みの代わりに使う）。"""
    db = sqlite3.connect(retrieval.RAG_DB)
    blob = db.execute("SELECT embedding FROM chunks WHERE page_id = ?", (page_id,)).fetchone()[0]
    db.close()
    return list(struct.unpack(f"{len(blob) // 4}f", blob))


def test_neighbors_are_added_once_and_stay_in_the_same_document():
    hits = [retrieval.read_page("lec02-main-p052"), retrieval.read_page("lec02-main-p053"),
            retrieval.read_page("lec03-main-p001")]
    results = retrieval.add_neighbors(hits, window=1)
    ids = [r["page_id"] for r in results]
    assert len(ids) == len(set(ids))  # 同じページは 1 回だけ
    assert ids[:2] == ["lec02-main-p052", "lec02-main-p051"]
    assert "lec02-main-p054" in ids
    assert "lec02-main-p070" not in ids  # 第3回 p.1 の前は、別の資料（第2回）なので足さない
    neighbor = next(r for r in results if r["page_id"] == "lec02-main-p051")
    assert neighbor["role"] == "neighbor" and neighbor["neighbor_of"] == "lec02-main-p052"


def test_search_materials_adds_neighbors_only_when_enabled(monkeypatch):
    hit = {**retrieval.read_page("lec02-main-p052"), "distance": 0.1}
    monkeypatch.setattr("app.retrieval.search", lambda *args, **kwargs: [hit])
    monkeypatch.setattr(config, "RAG_NEIGHBOR_WINDOW", 0)
    assert len(json.loads(tools.search_materials("LoRA"))["results"]) == 1
    monkeypatch.setattr(config, "RAG_NEIGHBOR_WINDOW", 1)
    ids = [r["page_id"] for r in json.loads(tools.search_materials("LoRA"))["results"]]
    assert ids == ["lec02-main-p052", "lec02-main-p051", "lec02-main-p053"]


def test_focused_graph_follows_only_terms_in_the_question(monkeypatch):
    monkeypatch.setattr(retrieval, "embed_text", lambda *_: _stored_embedding("lec03-main-p039"))
    result = retrieval.search_graph_focused("セッションをまたぐメモリとは？")
    assert result["matched_terms"] == ["メモリ"]
    assert result["seeds"][0]["page_id"] == "lec03-main-p039"
    ids = [p["page_id"] for p in result["seeds"] + result["expanded"]]
    assert len(ids) == len(set(ids)) <= config.GRAPH_MAX_RESULTS
    assert "lec03-main-p013" in ids  # 前後ページではないが、用語「メモリ」でたどれる
    distances = [p["distance"] for p in result["expanded"]]
    assert distances == sorted(distances)
