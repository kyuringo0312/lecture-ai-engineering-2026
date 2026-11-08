"""第3回 演習・宿題で足したツールのテスト（LLMもAPIキーも使わない）。"""

import json

from pydantic_ai import DeferredToolRequests, DeferredToolResults, ToolDenied
from pydantic_ai.models.test import TestModel

from app import tools
from app.agent import agent


def test_make_quiz_picks_a_term_of_the_lecture():
    quiz = json.loads(tools.make_quiz(2))
    lecture2 = {t["term"]: t["definition"] for t in tools.load_glossary() if t["lecture"] == 2}
    term = quiz["question"].split("「")[1].split("」")[0]
    assert term in lecture2
    assert quiz["answer"] == lecture2[term]


def test_make_quiz_reports_missing_lecture():
    assert "用語集にありません" in tools.make_quiz(0)


def test_save_learning_log_writes_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "LOG_DIR", tmp_path / "learning_log")
    message = tools.save_learning_log("LoRA の復習", "重みは固定し、小さな行列だけを学習する。")
    files = list((tmp_path / "learning_log").glob("*.md"))
    assert len(files) == 1 and "保存しました" in message
    assert files[0].read_text(encoding="utf-8").startswith("# LoRA の復習")


def test_save_learning_log_does_not_repeat_heading(tmp_path, monkeypatch):
    # 実行してみると、モデルは本文の先頭にも「# 題名」を書くことがあった
    monkeypatch.setattr(tools, "LOG_DIR", tmp_path / "learning_log")
    tools.save_learning_log("LoRAとQLoRAの違い", "# LoRAとQLoRAの違い\n\n- LoRA: ...")
    text = next((tmp_path / "learning_log").glob("*.md")).read_text(encoding="utf-8")
    assert text.count("# LoRAとQLoRAの違い") == 1


def _run_until_approval(monkeypatch, tmp_path):
    monkeypatch.setattr(tools, "LOG_DIR", tmp_path / "learning_log")
    model = TestModel(call_tools=["save_learning_log"])
    with agent.override(model=model):
        first = agent.run_sync("今日のまとめを学習記録に保存して")
    return model, first


def test_save_waits_for_approval_and_runs_when_approved(monkeypatch, tmp_path):
    model, first = _run_until_approval(monkeypatch, tmp_path)
    # 承認待ちで止まり、まだ何も書かれていない
    assert isinstance(first.output, DeferredToolRequests)
    assert not (tmp_path / "learning_log").exists()

    approvals = {call.tool_call_id: True for call in first.output.approvals}
    with agent.override(model=model):
        agent.run_sync(message_history=first.all_messages(), deferred_tool_results=DeferredToolResults(approvals=approvals))
    assert len(list((tmp_path / "learning_log").glob("*.md"))) == 1


def test_save_is_skipped_when_denied(monkeypatch, tmp_path):
    model, first = _run_until_approval(monkeypatch, tmp_path)
    denials = {call.tool_call_id: ToolDenied("利用者が実行を断りました。") for call in first.output.approvals}
    with agent.override(model=model):
        agent.run_sync(message_history=first.all_messages(), deferred_tool_results=DeferredToolResults(approvals=denials))
    assert not (tmp_path / "learning_log").exists()
