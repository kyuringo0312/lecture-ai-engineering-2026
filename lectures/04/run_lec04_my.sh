#!/usr/bin/env bash
# 第4回 宿題（実装）: 自作の評価セットを LLM に採点させ，自分のラベルと比べる
#   bash lectures/04/run_lec04_my.sh
set -u
R=lectures/04/results
FILTER='Logfire\|OpenTelemetry\|goes away'
for try in 1 2 3 4 5; do
  [ -s lectures/04/my_judge_result.json ] && break
  echo "===== my_judge (try $try)"
  uv run python -m app.judge --cases data/eval/my_cases.jsonl --labels lectures/04/my_labels.jsonl \
    --out lectures/04/my_judge_result.json --wait 5 2>&1 | grep -v "$FILTER" | tee "$R/my_judge.txt"
  [ -s lectures/04/my_judge_result.json ] || sleep 60
done
git add lectures/04
git commit -q -m "第4回: 自作の評価セットの採点結果" && git push -q
echo LEC04_DONE
