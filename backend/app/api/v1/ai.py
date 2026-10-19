"""
AI Module API Routes — v1

Endpoints:
  POST   /ai/chat/stream               — Stream AI response (SSE), supports session_id
  GET    /ai/capabilities              — User AI capabilities & prompt chips
  GET    /ai/status                    — AI module health status (admin only for full info)
  POST   /ai/sessions                  — Create new conversation session
  GET    /ai/sessions                  — List current user's sessions
  DELETE /ai/sessions/{session_id}     — Delete a session
  GET    /ai/sessions/{session_id}/history — Get session message history
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ResponseModel
from app.ai.agent import AIPMAgentService
from app.ai.tools import PermissionScopedTools
from app.ai.session_manager import AISessionManager
from app.ai.llm_factory import get_model_info, is_llm_configured, reset_llm
from app.ai.config_manager import get_runtime_config, save_runtime_config, clear_runtime_config, get_masked_api_key
from app.redis_client import redis_client
from app.config import settings

router = APIRouter()


# ─── Schemas ─────────────────────────────────────────────────────────────────

class ChatStreamRequest(BaseModel):
    message: str
    session_id: Optional[str] = None          # If provided, history loaded from Redis
    history: Optional[List[Dict[str, str]]] = []  # Legacy fallback if no session_id


class CreateSessionRequest(BaseModel):
    title: Optional[str] = ""


class SessionInfo(BaseModel):
    session_id: str
    user_id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int


class HistoryMessage(BaseModel):
    role: str
    content: str


class CapabilitiesResponse(BaseModel):
    user_id: int
    nickname: str
    roles: List[str]
    accessible_projects_count: int
    prompt_chips: List[str]
    is_deepseek_configured: bool
    current_session_id: Optional[str] = None
    # Effective model actually used for chat, so the UI never has to hardcode it.
    model_name: str = ""
    provider: str = "DeepSeek"


class AIStatusResponse(BaseModel):
    ai_enabled: bool
    is_llm_configured: bool
    redis_connected: bool
    model_info: Dict[str, Any]
    session_config: Dict[str, Any]


class AIConfigResponse(BaseModel):
    api_key_preview: str          # Masked, never expose full key
    base_url: str
    model: str
    max_tokens: int
    temperature: float
    ai_enabled: bool
    is_runtime_override: bool     # True if config comes from Redis, False if defaults


class AIConfigUpdateRequest(BaseModel):
    api_key: Optional[str] = Field(None, description="DeepSeek API Key (leave empty to keep current)")
    base_url: Optional[str] = Field(None, description="API Base URL")
    model: Optional[str] = Field(None, description="Model name, e.g. deepseek-chat / deepseek-coder")
    max_tokens: Optional[int] = Field(None, ge=256, le=32768, description="Max output tokens")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Sampling temperature")
    ai_enabled: Optional[bool] = Field(None, description="Enable or disable AI module")



# ─── Chat Streaming ───────────────────────────────────────────────────────────

@router.post("/chat/stream")
async def chat_stream(
    chat_req: ChatStreamRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Stream AI responses as Server-Sent Events (SSE).
    - If `session_id` is given, history is loaded from Redis and new messages are persisted.
    - Falls back to client-supplied `history` list when no session_id.
    """
    if not chat_req.message.strip():
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    return StreamingResponse(
        AIPMAgentService.stream_chat(
            message=chat_req.message,
            user=current_user,
            db=db,
            session_id=chat_req.session_id,
            history=chat_req.history,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# ─── AI Capabilities ──────────────────────────────────────────────────────────

@router.get("/capabilities", response_model=ResponseModel[CapabilitiesResponse])
def get_ai_capabilities(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get AI Assistant configuration and contextual prompt chips tailored to current user.
    Also returns the most recent session_id to restore conversation continuity.
    """
    accessible_pids = PermissionScopedTools.get_user_accessible_project_ids(current_user, db)
    roles = [r.name for r in current_user.roles]
    is_admin = current_user.is_superuser or any(r.code in ["ADMIN", "PM"] for r in current_user.roles)

    chips = [
        "📊 分析项目整体进度与延期风险",
        "⚡ 查询我未完成的高优待办任务",
        "⏱️ 统计我最近填报的工时记录",
        "🐞 查询待处理的缺陷与Bug",
    ]
    if is_admin:
        chips.insert(1, "📋 汇总各项目预算消耗与工时投入")
    else:
        chips.append("📝 帮我快速创建一条新的开发任务")

    # Get most recent session for continuity
    sessions = AISessionManager.get_session_list(current_user.id)
    current_session_id = sessions[0]["session_id"] if sessions else None

    model_info = get_model_info()

    return ResponseModel(
        code=200,
        message="success",
        data=CapabilitiesResponse(
            user_id=current_user.id,
            nickname=current_user.nickname,
            roles=roles,
            accessible_projects_count=len(accessible_pids),
            prompt_chips=chips,
            is_deepseek_configured=is_llm_configured(),
            current_session_id=current_session_id,
            model_name=model_info.get("model", ""),
            provider=model_info.get("provider", "DeepSeek"),
        )
    )


# ─── AI Status (Admin) ────────────────────────────────────────────────────────

@router.get("/status", response_model=ResponseModel[AIStatusResponse])
def get_ai_status(
    current_user: User = Depends(get_current_user),
):
    """
    Get AI module health status.
    Requires admin role for full details (model info, session config).
    """
    is_admin = current_user.is_superuser or any(r.code in ["ADMIN", "PM"] for r in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    model_info = get_model_info()
    redis_ok = redis_client.is_connected()

    return ResponseModel(
        code=200,
        message="success",
        data=AIStatusResponse(
            ai_enabled=settings.AI_ENABLED,
            is_llm_configured=is_llm_configured(),
            redis_connected=redis_ok,
            model_info=model_info,
            session_config={
                "session_ttl_days": settings.AI_SESSION_TTL // 86400,
                "max_history_turns": settings.AI_MAX_HISTORY_TURNS,
                "max_sessions_per_user": settings.AI_MAX_SESSIONS_PER_USER,
            }
        )
    )


# ─── Session Management ───────────────────────────────────────────────────────

@router.post("/sessions", response_model=ResponseModel[SessionInfo])
def create_session(
    req: CreateSessionRequest,
    current_user: User = Depends(get_current_user),
):
    """Create a new AI conversation session for the current user."""
    meta = AISessionManager.create_session(current_user.id, title=req.title or "")
    return ResponseModel(
        code=200,
        message="会话创建成功",
        data=SessionInfo(**meta)
    )


@router.get("/sessions", response_model=ResponseModel[List[SessionInfo]])
def list_sessions(
    current_user: User = Depends(get_current_user),
):
    """List all AI conversation sessions for the current user (newest first)."""
    sessions = AISessionManager.get_session_list(current_user.id)
    return ResponseModel(
        code=200,
        message="success",
        data=[SessionInfo(**s) for s in sessions]
    )


@router.delete("/sessions/{session_id}", response_model=ResponseModel)
def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Delete an AI conversation session (user can only delete their own)."""
    ok = AISessionManager.delete_session(current_user.id, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在或已被删除")
    return ResponseModel(code=200, message="会话已删除", data=None)


@router.get("/sessions/{session_id}/history", response_model=ResponseModel[List[HistoryMessage]])
def get_session_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    """Retrieve conversation history for a specific session."""
    history = AISessionManager.get_history(current_user.id, session_id)
    return ResponseModel(
        code=200,
        message="success",
        data=[HistoryMessage(**m) for m in history]
    )


# ─── LLM Config Management (Admin Only) ──────────────────────────────────────

@router.get("/config", response_model=ResponseModel[AIConfigResponse])
def get_ai_config(
    current_user: User = Depends(get_current_user),
):
    """
    Get current effective LLM configuration.
    Admin only. API key is masked in response.
    """
    is_admin = current_user.is_superuser or any(r.code in ["ADMIN", "PM"] for r in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    cfg = get_runtime_config()
    # Detect whether Redis override is active
    from app.redis_client import redis_client as rc
    client = rc.get_client()
    has_override = False
    if client:
        try:
            has_override = bool(client.get("aipm:ai_runtime_config"))
        except Exception:
            pass

    return ResponseModel(
        code=200,
        message="success",
        data=AIConfigResponse(
            api_key_preview=get_masked_api_key(cfg.get("api_key", "")),
            base_url=cfg.get("base_url", settings.DEEPSEEK_BASE_URL),
            model=cfg.get("model", settings.DEEPSEEK_MODEL),
            max_tokens=int(cfg.get("max_tokens", settings.DEEPSEEK_MAX_TOKENS)),
            temperature=float(cfg.get("temperature", settings.DEEPSEEK_TEMPERATURE)),
            ai_enabled=bool(cfg.get("ai_enabled", settings.AI_ENABLED)),
            is_runtime_override=has_override,
        )
    )


@router.put("/config", response_model=ResponseModel[AIConfigResponse])
def update_ai_config(
    req: AIConfigUpdateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Update LLM runtime configuration (persisted to Redis, takes effect immediately).
    Admin only. Triggers LLM instance rebuild on next chat request.
    """
    is_admin = current_user.is_superuser or any(r.code in ["ADMIN", "PM"] for r in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    updates: dict = {}
    if req.api_key is not None and req.api_key.strip():
        updates["api_key"] = req.api_key.strip()
    if req.base_url is not None and req.base_url.strip():
        updates["base_url"] = req.base_url.strip()
    if req.model is not None and req.model.strip():
        updates["model"] = req.model.strip()
    if req.max_tokens is not None:
        updates["max_tokens"] = req.max_tokens
    if req.temperature is not None:
        updates["temperature"] = req.temperature
    if req.ai_enabled is not None:
        updates["ai_enabled"] = req.ai_enabled

    if not updates:
        raise HTTPException(status_code=400, detail="未提供任何有效的配置字段")

    ok = save_runtime_config(updates)
    if not ok:
        raise HTTPException(status_code=500, detail="配置保存失败，请检查 Redis 连接")

    # Force LLM instance rebuild on next request
    reset_llm()

    # Return updated config
    cfg = get_runtime_config()
    return ResponseModel(
        code=200,
        message="配置已更新，大模型将在下次对话时使用新配置",
        data=AIConfigResponse(
            api_key_preview=get_masked_api_key(cfg.get("api_key", "")),
            base_url=cfg.get("base_url", ""),
            model=cfg.get("model", ""),
            max_tokens=int(cfg.get("max_tokens", 4096)),
            temperature=float(cfg.get("temperature", 0.7)),
            ai_enabled=bool(cfg.get("ai_enabled", True)),
            is_runtime_override=True,
        )
    )


@router.delete("/config/reset", response_model=ResponseModel)
def reset_ai_config(
    current_user: User = Depends(get_current_user),
):
    """
    Reset all runtime config overrides, falling back to settings.py / env defaults.
    Admin only.
    """
    is_admin = current_user.is_superuser or any(r.code in ["ADMIN", "PM"] for r in current_user.roles)
    if not is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")

    clear_runtime_config()
    reset_llm()
    return ResponseModel(code=200, message="已恢复默认配置（来自环境变量/config.py）", data=None)
