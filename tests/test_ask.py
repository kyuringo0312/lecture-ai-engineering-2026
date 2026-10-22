"""第1回 app.ask のテスト（LLMもAPIキーも使わない）。"""

from google.genai import types

from app import ask


def _usage(prompt: int, output: int, thoughts: int | None = None):
    return types.GenerateContentResponseUsageMetadata(
        prompt_token_count=prompt,
        candidates_token_count=output,
        thoughts_token_count=thoughts,
        total_token_count=prompt + output + (thoughts or 0),
    )


def test_format_usage_shows_input_and_output_tokens():
    assert ask.format_usage(_usage(12, 34)) == "[tokens] 入力: 12 / 出力: 34 / 合計: 46"


def test_format_usage_shows_thought_tokens_when_present():
    assert "思考: 5" in ask.format_usage(_usage(12, 34, thoughts=5))


def test_format_usage_without_metadata():
    assert "取得できませんでした" in ask.format_usage(None)


class FakeResponse:
    def __init__(self, text: str, usage):
        self.text = text
        self.usage_metadata = usage


class FakeChat:
    """送った質問を履歴に積み、履歴の長さに応じた入力トークン数を返す。"""

    def __init__(self):
        self.history: list[str] = []

    def send_message(self, message: str) -> FakeResponse:
        self.history.append(message)
        reply = f"{len(self.history)}回目の回答"
        self.history.append(reply)
        return FakeResponse(reply, _usage(prompt=10 * len(self.history), output=5))

    def get_history(self) -> list[str]:
        return self.history


class FakeClient:
    def __init__(self, api_key: str):
        self.chats = self
        self.session = FakeChat()

    def create(self, model: str) -> FakeChat:
        return self.session


def test_chat_keeps_history_across_questions(monkeypatch, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    clients: list[FakeClient] = []

    def make_client(api_key):
        clients.append(FakeClient(api_key))
        return clients[-1]

    monkeypatch.setattr(ask.genai, "Client", make_client)
    inputs = iter(["私の名前は田中です", "私の名前は？", "exit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(inputs))

    ask.chat()

    # 1つのチャットで2往復し、履歴が4メッセージになる
    assert len(clients) == 1
    assert clients[0].session.history == ["私の名前は田中です", "1回目の回答", "私の名前は？", "2回目の回答"]
    out = capsys.readouterr().out
    assert "2回目の回答" in out
    assert "[履歴] 4 メッセージ" in out


def test_chat_sends_first_question_from_command_line(monkeypatch, capsys):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    monkeypatch.setattr(ask.genai, "Client", FakeClient)
    monkeypatch.setattr("builtins.input", lambda _prompt: "")

    ask.chat("LoRAとは？")

    assert "1回目の回答" in capsys.readouterr().out
