from app.models import AgentScaffold
from app.prompts import BASE_SYSTEM_PROMPT
from app.services.tool_registry import get_tool_registry


def build_agent_scaffold() -> AgentScaffold:
    return AgentScaffold(
        base_system_prompt=BASE_SYSTEM_PROMPT,
        safety_rules=[
            "不做医学诊断",
            "不频繁使用心率信息解释用户",
            "不制造控制感、羞耻感、内疚感或对现实关系的排斥",
            "心率过旧或不可用时必须忽略它，优先依据当前对话回复",
        ],
        pipeline_steps=[
            "读取会话配置",
            "编译 persona",
            "构造 runtime policy 与 tool availability",
            "拼接 system prompt 与当前窗口消息",
            "调用 LLM",
            "如有 tool call，则执行工具并继续生成回复",
        ],
        tool_registry=get_tool_registry(),
    )
