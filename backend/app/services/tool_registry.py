from app.models import RuntimePolicy, ToolDefinition


HEART_RATE_TOOL = ToolDefinition(
    name="get_heart_rate",
    description="获取用户最近一次可用心率，用于辅助理解当前对话氛围。",
    parameters={"type": "object", "properties": {}, "additionalProperties": False},
)


def get_tool_registry() -> list[ToolDefinition]:
    return [HEART_RATE_TOOL]


def get_runtime_tools(policy: RuntimePolicy) -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []
    if policy.heart_rate.enabled:
        tools.append(HEART_RATE_TOOL)
    return tools
