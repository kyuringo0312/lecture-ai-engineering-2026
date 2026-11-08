"""第3回 宿題（発展 a）: 演習と同じ指示とツールで、エージェントを組み立てる部分だけを ADK で書き直したもの。

動かし方（リポジトリの直下で）:
    PYTHONPATH=. uv run --with google-adk adk run adk_agent/glossary_agent
"""

from google.adk.agents import Agent

from app import tools
from app.agent import INSTRUCTIONS
from app.config import MODEL

# Pydantic AI 版（app/agent.py）は Agent を作ってから agent.tool_plain(...) で 1 つずつ登録するが、
# ADK では関数のリストを tools= にまとめて渡す。関数の docstring と型ヒントがツールの説明になる点は同じ
root_agent = Agent(
    model=MODEL,
    name="glossary_agent",
    instruction=INSTRUCTIONS,
    tools=[tools.search_glossary, tools.get_lecture_summary, tools.make_quiz],
)
