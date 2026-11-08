#!/usr/bin/env bash
# 第3回 追加の実行（1 回目の結果を見て足したもの）
#   bash lectures/03/run_lec03b.sh
set -u
R=lectures/03/results
WAIT=20
step() { echo; echo "===== $1"; }

step "pytest"
uv run pytest -q 2>&1 | tail -3 | tee "$R/pytest_b.txt"

step "宿題（実装）2 回目: save_learning_log の説明文を直して再実行（承認する / 断る）"
uv run python -m app.agent --list-tools > "$R/impl2_list_tools.txt" 2>&1
before=$(ls learning_log 2>/dev/null | wc -l)
printf 'y\n' | uv run python -m app.agent --trace "LoRAとQLoRAの違いを調べて、要点を学習記録に保存して" > "$R/impl2_approve.txt" 2>&1
after=$(ls learning_log 2>/dev/null | wc -l)
echo "learning_log のファイル数: $before -> $after" | tee -a "$R/impl2_approve.txt"
cat learning_log/*.md > "$R/impl2_saved_log.md" 2>/dev/null
sleep $WAIT
before=$after
printf 'n\n' | uv run python -m app.agent --trace "PEFTについて調べて、要点を学習記録に保存して" > "$R/impl2_deny.txt" 2>&1
after=$(ls learning_log 2>/dev/null | wc -l)
echo "learning_log のファイル数: $before -> $after" | tee -a "$R/impl2_deny.txt"
sleep $WAIT

step "宿題（基礎）追加の検証: 指示と説明文の両方から「先に検索する」を消す"
rm -f "$R/basic_extra.jsonl"
uv run python scripts/compare_instructions_lec03.py --extra --repeat 2 --out "$R/basic_extra.jsonl" 2>&1 | grep "^\[" | tee "$R/basic_extra_log.txt"
sleep $WAIT

step "宿題（発展 a）2 回目: ADK のログからツール呼び出しを取り出す"
printf 'n\n' | PYTHONPATH=. uv run --with google-adk adk run --replay adk_agent/replay_lec03.json adk_agent/glossary_agent > "$R/adv_adk2.txt" 2>&1
echo "exit=$?"
grep -iE "function_call|functioncall|tool|search_glossary|make_quiz|get_lecture_summary" /tmp/agents_log/agent.latest.log | cut -c1-400 > "$R/adv_adk2_log_tools.txt"
wc -l "$R/adv_adk2_log_tools.txt"

step "結果を push する"
git add lectures/03/results
git commit -q -m "第3回: 追加の実行結果" && git push -q
echo ALL_DONE
