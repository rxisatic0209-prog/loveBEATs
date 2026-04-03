from app.models import ChatSendRequest, ChatSendResponse
from app.services.turn_runtime import create_turn_runtime, run_turn_runtime


async def handle_chat(request: ChatSendRequest) -> ChatSendResponse:
    runtime = create_turn_runtime(request, persist_session=True)
    return await run_turn_runtime(runtime)
