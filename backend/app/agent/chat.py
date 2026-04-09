from app.models import ChatSendRequest, ChatSendResponse
from app.agent.runtime import run_turn_runtime
from app.state.runtime_state import create_turn_runtime


async def handle_chat(request: ChatSendRequest) -> ChatSendResponse:
    runtime = create_turn_runtime(request, persist_session=True)
    return await run_turn_runtime(runtime)
