import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.responses import JSONResponse

from app.agent.chat import handle_chat
from app.agent.llm import LLMCallError
from app.config import settings
from app.db import init_db
from app.logging_setup import get_logger, setup_logging
from app.memory.agent_profiles import (
    build_default_agent_profile,
    create_agent_profile,
    delete_agent_profile,
    get_agent_profile,
    list_agent_profiles,
    update_agent_profile,
)
from app.memory.heart_rate_store import (
    append_role_heart_rate,
    get_latest_heart_rate,
    get_latest_role_heart_rate,
    list_app_user_heart_rate_events,
    list_role_heart_rate_events,
    upsert_heart_rate,
)
from app.memory.persona_templates import (
    create_persona_template,
    delete_persona_template,
    get_persona_template,
    list_persona_templates,
    update_persona_template,
)
from app.memory.role_store import create_or_update_role, delete_role, get_role, get_role_history, list_role_messages, list_roles
from app.models import (
    AgentScaffold,
    AgentProfile,
    AgentProfileCreateRequest,
    AgentProfileUpdateRequest,
    ChatMessage,
    ChatSendRequest,
    ChatSendResponse,
    HeartRateUpsertRequest,
    HeartRateReading,
    PersonaCompileRequest,
    PersonaTemplate,
    PersonaTemplateCreateRequest,
    PersonaTemplateUpdateRequest,
    RoleHeartRateAppendRequest,
    RoleCreateRequest,
    RoleHistoryResponse,
    RoleState,
    TurnDebugSnapshot,
    TurnRuntime,
)
from app.state.runtime_state import create_turn_debug_snapshot, create_turn_runtime
from app.system.persona import compile_persona
from app.system.scaffold import build_agent_scaffold
from app.tools.providers import get_heart_rate_provider_info

setup_logging()
logger = get_logger("LoveBeats.api")

app = FastAPI(title=settings.app_name)
CHAT_PAGE_PATH = Path(__file__).resolve().parent / "static" / "chat.html"
LOG_FILE_PATH = (Path(__file__).resolve().parent.parent / settings.log_dir / settings.log_filename).resolve()


@app.on_event("startup")
async def startup() -> None:
    init_db()
    logger.info("startup complete")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    logger.info("request start id=%s method=%s path=%s", request_id, request.method, request.url.path)
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.exception(
            "request failed id=%s method=%s path=%s duration_ms=%s",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "request end id=%s method=%s path=%s status=%s duration_ms=%s",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled exception path=%s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "app": settings.app_name}


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/chat")


@app.get("/chat", include_in_schema=False)
async def chat_page() -> FileResponse:
    return FileResponse(CHAT_PAGE_PATH)


@app.get("/v1/debug/logs")
async def debug_logs(lines: int = 120) -> dict:
    safe_lines = max(10, min(lines, 400))
    if not LOG_FILE_PATH.exists():
        return {
            "path": str(LOG_FILE_PATH),
            "lines": [],
            "line_count": 0,
        }

    content = LOG_FILE_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    return {
        "path": str(LOG_FILE_PATH),
        "lines": content[-safe_lines:],
        "line_count": len(content),
    }


@app.get("/v1/agent/scaffold", response_model=AgentScaffold)
async def agent_scaffold() -> AgentScaffold:
    return build_agent_scaffold()


@app.get("/v1/tools/heart-rate/provider")
async def heart_rate_provider_status() -> dict:
    return get_heart_rate_provider_info().__dict__


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


@app.get("/v1/personas", response_model=list[PersonaTemplate])
async def personas_list() -> list[PersonaTemplate]:
    return list_persona_templates()


@app.post("/v1/personas", response_model=PersonaTemplate)
async def persona_create(request: PersonaTemplateCreateRequest) -> PersonaTemplate:
    return create_persona_template(request)


@app.get("/v1/personas/{persona_id}", response_model=PersonaTemplate)
async def persona_get(persona_id: str) -> PersonaTemplate:
    return get_persona_template(persona_id)


@app.put("/v1/personas/{persona_id}", response_model=PersonaTemplate)
async def persona_update(persona_id: str, request: PersonaTemplateUpdateRequest) -> PersonaTemplate:
    return update_persona_template(persona_id, request)


@app.delete("/v1/personas/{persona_id}")
async def persona_delete(persona_id: str) -> dict:
    delete_persona_template(persona_id)
    return {"ok": True}


@app.get("/v1/agents/default", response_model=AgentProfile)
async def agent_default() -> AgentProfile:
    return build_default_agent_profile()


@app.get("/v1/agents", response_model=list[AgentProfile])
async def agents_list() -> list[AgentProfile]:
    return list_agent_profiles()


@app.post("/v1/agents", response_model=AgentProfile)
async def agent_create(request: AgentProfileCreateRequest) -> AgentProfile:
    return create_agent_profile(request)


@app.get("/v1/agents/{agent_id}", response_model=AgentProfile)
async def agent_get(agent_id: str) -> AgentProfile:
    return get_agent_profile(agent_id)


@app.put("/v1/agents/{agent_id}", response_model=AgentProfile)
async def agent_update(agent_id: str, request: AgentProfileUpdateRequest) -> AgentProfile:
    return update_agent_profile(agent_id, request)


@app.delete("/v1/agents/{agent_id}")
async def agent_delete(agent_id: str) -> dict:
    delete_agent_profile(agent_id)
    return {"ok": True}


@app.post("/v1/roles", response_model=RoleState)
async def role_create(request: RoleCreateRequest) -> RoleState:
    return create_or_update_role(request)


@app.get("/v1/roles", response_model=list[RoleState])
async def roles_list() -> list[RoleState]:
    return list_roles()


@app.get("/v1/roles/{role_id}", response_model=RoleState)
async def role_get(role_id: str) -> RoleState:
    return get_role(role_id)


@app.get("/v1/roles/{role_id}/history", response_model=RoleHistoryResponse)
async def role_history(role_id: str) -> RoleHistoryResponse:
    return get_role_history(role_id)


@app.get("/v1/roles/{role_id}/messages", response_model=list[ChatMessage])
async def role_messages_list(role_id: str) -> list[ChatMessage]:
    return list_role_messages(role_id)


@app.delete("/v1/roles/{role_id}")
async def role_delete(role_id: str) -> dict:
    delete_role(role_id)
    return {"ok": True}


@app.post("/v1/heart-rate/latest")
async def heart_rate_latest(request: HeartRateUpsertRequest) -> dict:
    if request.role_id:
        reading = append_role_heart_rate(
            role_id=request.role_id,
            bpm=request.bpm,
            timestamp=request.timestamp,
        )
        return reading.model_dump(mode="json")
    reading = upsert_heart_rate(
        app_user_id=request.app_user_id or request.profile_id,
        bpm=request.bpm,
        timestamp=request.timestamp,
        source="legacy_upsert_api",
    )
    return reading.model_dump(mode="json")


@app.post("/v1/app-users/{app_user_id}/heart-rate/latest", response_model=HeartRateReading)
async def app_user_heart_rate_latest(app_user_id: str, request: RoleHeartRateAppendRequest) -> HeartRateReading:
    return upsert_heart_rate(app_user_id=app_user_id, bpm=request.bpm, timestamp=request.timestamp, source="app_user_api")


@app.get("/v1/app-users/{app_user_id}/heart-rate/latest", response_model=HeartRateReading)
async def app_user_heart_rate_get(app_user_id: str) -> HeartRateReading:
    return get_latest_heart_rate(app_user_id)


@app.get("/v1/app-users/{app_user_id}/heart-rate/history", response_model=list[HeartRateReading])
async def app_user_heart_rate_history(app_user_id: str) -> list[HeartRateReading]:
    return list_app_user_heart_rate_events(app_user_id)


@app.get("/v1/heart-rate/latest/{profile_id}")
async def heart_rate_get(profile_id: str) -> dict:
    reading = get_latest_heart_rate(profile_id)
    return reading.model_dump(mode="json")


@app.post("/v1/roles/{role_id}/heart-rate", response_model=HeartRateReading)
async def role_heart_rate_append(role_id: str, request: RoleHeartRateAppendRequest) -> HeartRateReading:
    return append_role_heart_rate(role_id=role_id, bpm=request.bpm, timestamp=request.timestamp, source="role_api")


@app.get("/v1/roles/{role_id}/heart-rate/latest", response_model=HeartRateReading)
async def role_heart_rate_latest(role_id: str) -> HeartRateReading:
    return get_latest_role_heart_rate(role_id)


@app.get("/v1/roles/{role_id}/heart-rate/history", response_model=list[HeartRateReading])
async def role_heart_rate_history(role_id: str) -> list[HeartRateReading]:
    return list_role_heart_rate_events(role_id)


@app.post("/v1/chat/send", response_model=ChatSendResponse)
async def chat_send(request: ChatSendRequest) -> ChatSendResponse:
    try:
        return await handle_chat(request)
    except LLMCallError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error
