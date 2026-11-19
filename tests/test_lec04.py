"""第4回 宿題（基礎）で足した「判定→理由」の順の採点器のテスト（API キーは使わない）。"""

from app import judge
from app.judge import ALL_CRITERIA, DEFAULT_CASES, DEFAULT_RUBRIC, build_judge, build_test_model, judge_cases, read_jsonl


def test_verdict_first_swaps_only_the_order():
    assert list(judge.CriterionVerdict.model_fields) == ["reason", "verdict"]
    assert list(judge.CriterionVerdictFirst.model_fields) == ["verdict", "reason"]
    # 順序に触れている 1 文が rubric にあること（無いと、順序を入れ替えても指示が食い違う）
    assert judge.REASON_FIRST_RULE in DEFAULT_RUBRIC.read_text(encoding="utf-8")


def test_verdict_first_judge_runs_on_the_same_cases():
    agent = build_judge(build_test_model(), DEFAULT_RUBRIC.read_text(encoding="utf-8"), verdict_first=True)
    verdicts = judge_cases(agent, read_jsonl(DEFAULT_CASES))
    assert len(verdicts) == 10
    assert all(v[key]["verdict"] in ("pass", "fail", "unsure") for v in verdicts.values() for key, _ in ALL_CRITERIA)
