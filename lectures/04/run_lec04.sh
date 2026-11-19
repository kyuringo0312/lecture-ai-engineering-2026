#!/usr/bin/env bash
# 第4回 演習・宿題（基礎・実装の前半）の実行をまとめたスクリプト（Codespaces のリポジトリ直下で実行する）
#   bash lectures/04/run_lec04.sh
# 無料枠の毎分の上限を超えないよう、採点は 1 件ごとに 5 秒、実行の間に 20 秒待つ。
set -u
R=lectures/04/results
mkdir -p "$R"
judge() {  # judge <名前> <追加の引数...>
  name=$1; shift
  echo; echo "===== $name"
  uv run python -m app.judge --wait 5 --out "$R/$name.json" "$@" 2>&1 | grep -v "pydantic\|observ\|Logfire\|OpenTelemetry\|goes away\|^ *[/\\|\`]" | tee "$R/$name.txt"
  sleep 20
}

echo "===== pytest"; uv run pytest -q 2>&1 | tail -2 | tee "$R/pytest.txt"

# 演習 STEP 2: 直す前の基準（rubric_before.md は main の data/eval/rubric.md と同じ）
judge step2_before --rubric "$R/rubric_before.md"
# 演習 STEP 3: 「根拠」に方針を 1 行書き足した基準（data/eval/rubric.md）
judge step3_after
cp "$R/step3_after.json" lectures/04/judge_result.json

# 宿題（基礎）: 判定の順序だけを変える。揺れを見るため、同じ条件でも 2 回ずつ流す（1 回目の理由→判定は step3_after）
judge basic_reason_first_2
judge basic_verdict_first_1 --verdict-first
judge basic_verdict_first_2 --verdict-first

# 宿題（実装）: 自作の 10 問に、第3回で作った自分のエージェントで回答を生成する
echo; echo "===== generate my_cases"
uv run python -m app.judge --generate --cases data/eval/my_cases.jsonl --wait 8 2>&1 | grep -v "pydantic\|observ\|Logfire\|OpenTelemetry\|goes away\|^ *[/\\|\`]" | tee "$R/my_generate.txt"
ls learning_log 2>/dev/null | wc -l | sed 's/^/learning_log のファイル数: /' | tee -a "$R/my_generate.txt"

git add lectures/04 data/eval/my_cases.jsonl
git commit -q -m "第4回: 採点と回答生成の実行結果" && git push -q
echo ALL_DONE
