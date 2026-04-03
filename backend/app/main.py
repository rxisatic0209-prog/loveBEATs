from fastapi import FastAPI

from app.config import settings
from app.db import init_db
from app.models import (
    AgentScaffold,
    ChatMessage,
    ChatSendRequest,
    ChatSendResponse,
    HeartRateUpsertRequest,
    PersonaCompileRequest,
    SessionCreateRequest,
    SessionHistoryResponse,
    SessionState,
    TurnDebugSnapshot,
    TurnRuntime,
)
from app.services.agent_scaffold import build_agent_scaffold
from app.services.chat_runtime import handle_chat
from app.services.heart_rate import get_latest_heart_rate, upsert_heart_rate
from app.services.persona import compile_persona
from app.services.session import create_or_update_session, get_history, get_session, list_messages
from app.services.turn_runtime import create_turn_debug_snapshot, create_turn_runtime

app = FastAPI(title=settings.app_name)


@app.on_event("startup")
async def startup() -> None:
    init_db()


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "app": settings.app_name}


@app.get("/v1/agent/scaffold", response_model=AgentScaffold)
async def agent_scaffold() -> AgentScaffold:
    return build_agent_scaffold()


@app.post("/v1/turns/preview", response_model=TurnRuntime)
async def turn_preview(request: ChatSendRequest) -> TurnRuntime:
    return create_turn_runtime(request, persist_session=False)


@app.post("/v1/turns/debug", response_model=TurnDebugSnapshot)
async def turn_debug(request: ChatSendRequest) -> TurnDebugSnapshot:
    return create_turn_debug_snapshot(request, persist_session=False)


@app.post("/v1/persona/compile")
async def persona_compile(request: PersonaCompileRequest) -> dict:
    persona = compile_persona(request.persona_text, request.persona_profile)
    return persona.model_dump(mode="json")


@app.post("/v1/sessions", response_model=SessionState)
async def session_create(request: SessionCreateRequest) -> SessionState:
    return create_or_update_session(request)


@app.get("/v1/sessions/{session_id}", response_model=SessionState)
async def session_get(session_id: str) -> SessionState:
    return get_session(session_id)


@app.get("/v1/sessions/{session_id}/history", response_model=SessionHistoryResponse)
async def session_history(session_id: str) -> SessionHistoryResponse:
    return get_history(session_id)


@app.get("/v1/sessions/{session_id}/messages", response_model=list[ChatMessage])
async def session_messages_list(session_id: str) -> list[ChatMessage]:
    return list_messages(session_id)


@app.post("/v1/heart-rate/latest")
async def heart_rate_latest(request: HeartRateUpsertRequest) -> dict:
    reading = upsert_heart_rate(
        profile_id=request.profile_id,
        bpm=request.bpm,
        timestamp=request.timestamp,
    )
    return reading.model_dump(mode="json")


@app.get("/v1/heart-rate/latest/{profile_id}")
async def heart_rate_get(profile_id: str) -> dict:
    reading = get_latest_heart_rate(profile_id)
    return reading.model_dump(mode="json")


@app.post("/v1/chat/send", response_model=ChatSendResponse)
async def chat_send(request: ChatSendRequest) -> ChatSendResponse:
    return await handle_chat(request)
