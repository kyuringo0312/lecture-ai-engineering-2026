#!/usr/bin/env bash
# 第4回: 503（モデルの混雑）などで結果が保存されなかった実行だけを、間を空けて再試行する
#   bash lectures/04/run_lec04_retry.sh
set -u
R=lectures/04/results
FILTER='pydantic\|observ\|Logfire\|OpenTelemetry\|goes away\|^ *[/\|`]'
judge() {  # judge <名前> <追加の引数...>  結果の json があれば何もしない
  name=$1; shift
  for try in 1 2 3 4 5; do
    [ -s "$R/$name.json" ] && return 0
    echo; echo "===== $name (try $try)"
    uv run python -m app.judge --wait 5 --out "$R/$name.json" "$@" 2>&1 | grep -v "$FILTER" | tee "$R/$name.txt"
    [ -s "$R/$name.json" ] || { echo "$(date +%T) $name try $try failed" >> "$R/retry_log.txt"; sleep 45; }
  done
}
judge step2_before --rubric "$R/rubric_before.md"; sleep 20
judge step3_after; sleep 20
[ -s "$R/step3_after.json" ] && cp "$R/step3_after.json" lectures/04/judge_result.json
judge basic_reason_first_2; sleep 20
judge basic_verdict_first_1 --verdict-first; sleep 20
judge basic_verdict_first_2 --verdict-first; sleep 20

# 宿題（実装）: 回答が 1 件でも空なら、生成し直す
for try in 1 2 3 4; do
  grep -q '"answer": ""' data/eval/my_cases.jsonl || break
  echo; echo "===== generate my_cases (try $try)"
  uv run python -m app.judge --generate --cases data/eval/my_cases.jsonl --wait 8 2>&1 | grep -v "$FILTER" | tee "$R/my_generate.txt"
  grep -q '"answer": ""' data/eval/my_cases.jsonl && { echo "$(date +%T) generate try $try failed" >> "$R/retry_log.txt"; sleep 45; }
done
ls learning_log 2>/dev/null | wc -l | sed 's/^/learning_log のファイル数: /' | tee -a "$R/my_generate.txt"

git add lectures/04 data/eval/my_cases.jsonl
git commit -q -m "第4回: 再試行した実行結果" && git push -q
ls "$R"/*.json; echo ALL_DONE
