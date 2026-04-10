from app.models import AgentScaffold
from app.system.guardrails import BASE_SYSTEM_PROMPT
from app.tools.registry import get_tool_registry


def build_agent_scaffold() -> AgentScaffold:
    return AgentScaffold(
        base_system_prompt=BASE_SYSTEM_PROMPT,
        tool_registry=get_tool_registry(),
    )
