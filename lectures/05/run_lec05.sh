#!/usr/bin/env bash
# 第5回: 演習と宿題（基礎・実装・発展）の実行をまとめて行い，結果を lectures/05/results/ に残す
#   bash lectures/05/run_lec05.sh
set -u
R=lectures/05/results
mkdir -p "$R"
FILTER='Logfire\|OpenTelemetry\|goes away'
Q1='第2回の説明では、LoRAは何を固定し何を学習しますか？ QLoRAは何を加えますか？'
Q2='第3回の例では、コンパクションとセッションをまたぐメモリはどう違いますか。日々のメモはすべて長期メモリに入りますか'
Q3='今回作ったRAGの実測平均応答時間と正答率を教えてください'
Q4='第2回の説明では、Fine-Tuningで知識を足すのが難しいのはなぜですか。知識を足したいときは何を使うとよいとされていますか'

run() {  # run <名前> <agent の引数...>  結果があれば飛ばす．混雑などで失敗したら間を空けて再試行
  name=$1; shift
  for try in 1 2 3 4; do
    grep -q '^\[cost\]' "$R/$name.txt" 2>/dev/null && return 0
    echo; echo "===== $name (try $try)"
    uv run python -m app.agent "$@" < /dev/null 2>&1 | grep -v "$FILTER" > "$R/$name.txt"
    tail -n 4 "$R/$name.txt"
    grep -q '^\[cost\]' "$R/$name.txt" || { echo "$(date +%T) $name try $try failed" >> "$R/retry_log.txt"; sleep 60; }
  done
  sleep 10
}

uv run pytest -q 2>&1 | tail -n 3 | tee "$R/pytest.txt"

# ---- 演習（RAG_TOP_K=5）
run ex_full_q1 --full-context --trace "$Q1"
uv run python -m app.retrieval "LoRA QLoRA 違い" > "$R/ex_retrieval.txt" 2>&1
for q in 1 2 3 4; do
  eval "Q=\$Q$q"
  run ex_vector_q$q --trace "$Q"
  run ex_tree_q$q --tree --trace "$Q"
  run ex_graph_q$q --graph --trace "$Q"
done
run ex_full_q2 --full-context --trace "$Q2"

# ---- 取得されるページの比較（LLM なし，基礎・実装・発展の分も含む）
uv run python -m scripts.inspect_retrieval_lec05 > "$R/retrieval_pages.txt" 2>&1

# ---- 実装: 前後 1 ページの本文も付ける（RAG_TOP_K=5 のまま）
uv run python -m app.retrieval --neighbors 1 "LoRA QLoRA 違い" > "$R/impl_retrieval_neighbors.txt" 2>&1
export AIE_RAG_NEIGHBORS=1
for q in 1 2 4; do
  eval "Q=\$Q$q"
  run impl_neighbors_q$q --trace "$Q"
done
unset AIE_RAG_NEIGHBORS

# ---- 発展: 質問の用語で絞る Graph
export AIE_GRAPH_MODE=focused
for q in 1 2 3 4; do
  eval "Q=\$Q$q"
  run adv_graph_focused_q$q --graph --trace "$Q"
done
unset AIE_GRAPH_MODE

# ---- 基礎: RAG_TOP_K を 5 → 3 に変えて，同じ質問を実行する（変更はそのまま残す）
sed -i 's/^RAG_TOP_K = 5$/RAG_TOP_K = 3/' app/config.py
grep -n '^RAG_TOP_K' app/config.py | tee "$R/basic_config.txt"
for q in 1 2 4; do
  eval "Q=\$Q$q"
  run basic_top3_q$q --trace "$Q"
done

git add lectures/05 app/config.py
git commit -q -m "第5回: 演習・宿題の実行結果" && git push -q
ls "$R"; echo ALL_DONE
