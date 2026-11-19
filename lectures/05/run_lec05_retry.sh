#!/usr/bin/env bash
# 第5回: 503 で 4 回とも失敗した実行だけをやり直す（結果があるものは飛ばす）
#   bash lectures/05/run_lec05_retry.sh
set -u
R=lectures/05/results
FILTER='Logfire\|OpenTelemetry\|goes away'
Q2='第3回の例では、コンパクションとセッションをまたぐメモリはどう違いますか。日々のメモはすべて長期メモリに入りますか'
Q3='今回作ったRAGの実測平均応答時間と正答率を教えてください'
Q4='第2回の説明では、Fine-Tuningで知識を足すのが難しいのはなぜですか。知識を足したいときは何を使うとよいとされていますか'
run() {
  name=$1; shift
  for try in 1 2 3 4 5 6; do
    grep -q '^\[cost\]' "$R/$name.txt" 2>/dev/null && return 0
    echo; echo "===== $name (retry $try)"
    uv run python -m app.agent "$@" < /dev/null 2>&1 | grep -v "$FILTER" > "$R/$name.txt"
    tail -n 4 "$R/$name.txt"
    grep -q '^\[cost\]' "$R/$name.txt" || { echo "$(date +%T) $name retry $try failed" >> "$R/retry_log.txt"; sleep 90; }
  done
  sleep 10
}
run ex_tree_q3 --tree --trace "$Q3"
run ex_tree_q4 --tree --trace "$Q4"
# 実装の比較は演習と同じ RAG_TOP_K=5 で行うので，この実行の間だけ 5 に戻す
sed -i 's/^RAG_TOP_K = 3$/RAG_TOP_K = 5/' app/config.py
export AIE_RAG_NEIGHBORS=1; run impl_neighbors_q2 --trace "$Q2"
unset AIE_RAG_NEIGHBORS
sed -i 's/^RAG_TOP_K = 5$/RAG_TOP_K = 3/' app/config.py
grep -n '^RAG_TOP_K' app/config.py
git add lectures/05 app/config.py
git commit -q -m "第5回: 503 で失敗した実行をやり直した結果" && git push -q
echo ALL_DONE
