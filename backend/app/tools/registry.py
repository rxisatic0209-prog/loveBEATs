from app.models import RuntimePolicy, ToolDefinition


HEART_RATE_TOOL = ToolDefinition(
    name="get_heart_rate",
    description=(
        "读取用户最近一次可用心率，作为亲密互动中的辅助线索，帮助你在调情、靠近、安抚、沉默和关系"
        "张力变化时更自然地理解当下节奏。任何时候都允许调用，但只有当它能帮助你更细腻地判断距离感、"
        "靠近方式和回应分寸时才值得使用，例如调情推进后、用户说了害羞或暧昧的话后、有张力的互动后"
        "长时间沉默、或用户显露脆弱和依赖时。心率只是弱信号，不等于明确情绪结论；你需要把它和当前"
        "语境、用户措辞、对话气氛一起判断，而不是机械套规则。不能把它说成医学、心理学或健康判断，"
        "也不能直接替用户定义感受。没有数据、数据过旧或不可用时，直接忽略它，继续依赖语言本身完成"
        "恋人式陪伴。"
    ),
    parameters={"type": "object", "properties": {}, "additionalProperties": False},
)


def get_tool_registry() -> list[ToolDefinition]:
    return [HEART_RATE_TOOL]


def get_runtime_tools(policy: RuntimePolicy) -> list[ToolDefinition]:
    tools: list[ToolDefinition] = []
    if policy.heart_rate.enabled:
        tools.append(HEART_RATE_TOOL)
    return tools
