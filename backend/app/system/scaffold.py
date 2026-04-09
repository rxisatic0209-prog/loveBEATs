from app.models import AgentScaffold
from app.system.guardrails import BASE_SYSTEM_PROMPT, RUNTIME_PIPELINE_STEPS, SYSTEM_SAFETY_RULES
from app.tools.registry import get_tool_registry


def build_agent_scaffold() -> AgentScaffold:
    return AgentScaffold(
        base_system_prompt=BASE_SYSTEM_PROMPT,
        safety_rules=SYSTEM_SAFETY_RULES,
        pipeline_steps=RUNTIME_PIPELINE_STEPS,
        tool_registry=get_tool_registry(),
    )
