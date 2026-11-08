#!/usr/bin/env bash
# 第3回 演習・宿題の実行をまとめたスクリプト（Codespaces のリポジトリ直下で実行する）
#   bash lectures/03/run_lec03.sh
# 出力は lectures/03/results/ に保存する。無料枠の毎分の上限を超えないよう、実行の間に待つ。
set -u
R=lectures/03/results
mkdir -p "$R"
WAIT=20

step() { echo; echo "===== $1"; }

step "pytest"
uv run pytest -q 2>&1 | tail -3 | tee "$R/pytest.txt"

step "演習2: 第1回と同じ質問（素の LLM とエージェント）"
uv run python -m app.ask "AIE2026の講座の宿題にある「3レベル」とは何ですか？" > "$R/ex2_ask.txt" 2>&1
sleep $WAIT
uv run python -m app.agent --trace "AIE2026の講座の宿題にある「3レベル」とは何ですか？" > "$R/ex2_agent.txt" 2>&1
tail -4 "$R/ex2_agent.txt"
sleep $WAIT

step "演習3: ツール呼び出しを読む"
uv run python -m app.agent --trace "LoRAとQLoRAの違いは？" > "$R/ex3_trace.txt" 2>&1
tail -6 "$R/ex3_trace.txt"
sleep $WAIT

step "演習5: make_quiz が見え、呼ばれるか"
uv run python -m app.agent --list-tools > "$R/ex5_list_tools.txt" 2>&1
uv run python -m app.agent --trace "第2回の内容から確認問題を1問出して" > "$R/ex5_quiz.txt" 2>&1
tail -6 "$R/ex5_quiz.txt"
sleep $WAIT

step "宿題（実装）: 承認して保存する / 断る"
before=$(ls learning_log 2>/dev/null | wc -l)
printf 'y\n' | uv run python -m app.agent --trace "LoRAとQLoRAの違いを調べて、要点を学習記録に保存して" > "$R/impl_approve.txt" 2>&1
after=$(ls learning_log 2>/dev/null | wc -l)
echo "learning_log のファイル数: $before -> $after" | tee -a "$R/impl_approve.txt"
cat learning_log/*.md > "$R/impl_saved_log.md" 2>/dev/null
sleep $WAIT
before=$after
printf 'n\n' | uv run python -m app.agent --trace "PEFTについて調べて、要点を学習記録に保存して" > "$R/impl_deny.txt" 2>&1
after=$(ls learning_log 2>/dev/null | wc -l)
echo "learning_log のファイル数: $before -> $after" | tee -a "$R/impl_deny.txt"
sleep $WAIT

step "宿題（基礎）: INSTRUCTIONS と説明文を 1 か所ずつ変えて比べる"
rm -f "$R/basic.jsonl"
uv run python scripts/compare_instructions_lec03.py --repeat 2 --out "$R/basic.jsonl" 2>&1 | grep -v "pydantic\|Logfire\|banner\|^ *[/\\|\`]" | tee "$R/basic_log.txt"
sleep $WAIT

step "宿題（発展 a）: ADK で作り直したエージェント"
PYTHONPATH=. uv run --with google-adk adk run --jsonl --replay adk_agent/replay_lec03.json adk_agent/glossary_agent > "$R/adv_adk.jsonl" 2> "$R/adv_adk_stderr.txt"
echo "exit=$? lines=$(wc -l < "$R/adv_adk.jsonl")"
if [ ! -s "$R/adv_adk.jsonl" ]; then
  sleep $WAIT
  PYTHONPATH=. uv run --with google-adk adk run --replay adk_agent/replay_lec03.json adk_agent/glossary_agent > "$R/adv_adk.txt" 2>&1
  echo "fallback exit=$?"
fi
PYTHONPATH=. uv run --with google-adk python -c "import google.adk; print('google-adk', google.adk.__version__)" > "$R/adv_adk_version.txt" 2>&1

step "結果を push する"
git add lectures/03/results
git commit -q -m "第3回: 演習・宿題の実行結果" && git push -q
echo ALL_DONE
