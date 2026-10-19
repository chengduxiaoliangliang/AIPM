"""
AIPM Agent Service — Intelligent LangChain & DeepSeek conversational engine.

Integrates:
- LLM Factory (singleton ChatOpenAI instance)
- AI Session Manager (Redis-backed conversation history)
- RBAC-scoped Tools (PermissionScopedTools)
- Graceful fallback when LLM is unavailable
"""
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator, Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.config import settings
from app.models.user import User
from app.ai.tools import PermissionScopedTools
from app.ai.llm_factory import get_llm, is_llm_configured
from app.ai.session_manager import AISessionManager

logger = logging.getLogger(__name__)

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None

_WEEKDAY_CN = ["一", "二", "三", "四", "五", "六", "日"]

# Phrases that mean "tell me the current date / time".
_DATETIME_KEYWORDS = (
    "几号", "几点", "星期几", "周几", "日期", "当前时间", "现在时间",
    "今天是什么", "今天是", "现在是什么", "current date", "what day", "what time",
)


def _now() -> datetime:
    """Current time in the configured timezone (falls back to UTC+8)."""
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(settings.APP_TIMEZONE))
        except Exception:
            logger.debug("ZoneInfo unavailable for %s, falling back to UTC+8", settings.APP_TIMEZONE)
    return datetime.now(timezone(timedelta(hours=8)))


def format_now() -> str:
    """Human-readable current date/time, e.g. 2026年10月19日（星期一）22:31."""
    n = _now()
    return f"{n.strftime('%Y年%m月%d日')}（星期{_WEEKDAY_CN[n.weekday()]}）{n.strftime('%H:%M')}"


def is_datetime_query(message: str) -> bool:
    msg = message.lower()
    return any(k in msg for k in _DATETIME_KEYWORDS)



class AIPMAgentService:
    """
    Intelligent LangChain & DeepSeek Agent Engine for AIPM.
    Equipped with RBAC permission boundaries, Redis session history,
    and zero-downtime hybrid fallback.
    """

    @classmethod
    def get_system_prompt(cls, user: User) -> str:
        role_names = [r.name for r in user.roles] or ["普通员工"]
        return f"""你是由 DeepSeek 大模型驱动的 AIPM 项目管理系统【智能小精灵助手】。
你正在与用户【{user.nickname}（用户名: {user.username}，角色: {', '.join(role_names)}）】对话。

【当前系统时间】{format_now()}
这是服务器提供的真实时间。当用户询问今天是几号、星期几、现在几点、本月/本季度是哪一段时，
必须直接使用上述时间作答，绝不可声称"无法获取实时时间"或要求用户自己查看。

【严格执行的权限与安全规则】:
1. 你必须严格遵循该用户的企业权限边界，绝不向该用户透露其未参与的保密项目、他人的私人薪资或系统超级管理数据。
2. 你的回答应当专业、富有条理、亲切温暖，使用 Markdown 格式（加粗、列表、表格、代码块）进行排版。
3. 当用户询问项目进度、任务待办、缺陷、工时或创建任务时，以精准的数据指标结合建议给出答复。
4. 如果用户请求执行超出其权限的操作，委婉告知权限不足并提示联系系统管理员。
5. 遇到与项目管理无关的日常小问题（日期时间、简单计算、常识问答），也应当正常、简洁地回答。
"""

    @classmethod
    async def stream_chat(
        cls,
        message: str,
        user: User,
        db: Session,
        session_id: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream conversational responses as Server-Sent Events (SSE).
        If session_id is provided, history is loaded from Redis (ignoring client-supplied history).
        New messages are appended to the session after completion.
        """
        # ── Resolve session & load history from Redis ──────────────────────
        if session_id:
            redis_history = AISessionManager.get_history(user.id, session_id)
        else:
            # Fallback to client-supplied history (legacy compatibility)
            redis_history = history or []

        # ── Step 1: Execute permission-scoped tool if query is project-related ──
        tool_output = cls._try_execute_tools(message, user, db)

        # ── Step 2: Stream via DeepSeek LLM ──────────────────────────────────
        if is_llm_configured() and settings.AI_ENABLED:
            try:
                from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

                llm = get_llm(streaming=True)
                if llm is None:
                    raise RuntimeError("LLM instance unavailable")

                messages = [SystemMessage(content=cls.get_system_prompt(user))]
                if tool_output:
                    messages.append(SystemMessage(content=f"【系统数据库实时检索上下文】:\n{tool_output}"))

                # Inject Redis-persisted history (last N turns)
                for h in redis_history:
                    if h.get("role") == "user":
                        messages.append(HumanMessage(content=h.get("content", "")))
                    elif h.get("role") == "assistant":
                        messages.append(AIMessage(content=h.get("content", "")))

                messages.append(HumanMessage(content=message))

                # Collect full assistant response for session persistence
                full_reply = ""

                async for chunk in llm.astream(messages):
                    content = chunk.content if hasattr(chunk, "content") else str(chunk)
                    if content:
                        full_reply += content
                        data = json.dumps({"content": content, "status": "streaming"}, ensure_ascii=False)
                        yield f"data: {data}\n\n"
                        await asyncio.sleep(0.01)

                # ── Persist conversation to Redis session ──
                if session_id and full_reply:
                    AISessionManager.append_messages(
                        user.id, session_id,
                        [
                            {"role": "user", "content": message},
                            {"role": "assistant", "content": full_reply},
                        ],
                        first_user_msg=message,
                    )

                done_data = json.dumps({"content": "", "status": "finished"}, ensure_ascii=False)
                yield f"data: {done_data}\n\n"
                return

            except Exception as e:
                logger.warning(f"DeepSeek API stream failed, switching to local fallback: {e}")

        # ── Step 3: Local Intelligent Reasoning Fallback Engine ────────────
        fallback_text = cls._generate_intelligent_fallback_reply(message, user, db, tool_output)

        # Persist fallback reply to session as well
        if session_id:
            AISessionManager.append_messages(
                user.id, session_id,
                [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": fallback_text},
                ],
                first_user_msg=message,
            )

        words = fallback_text.split(" ")
        for i, word in enumerate(words):
            chunk = word + (" " if i < len(words) - 1 else "")
            data = json.dumps({"content": chunk, "status": "streaming"}, ensure_ascii=False)
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.02)

        done_data = json.dumps({"content": "", "status": "finished"}, ensure_ascii=False)
        yield f"data: {done_data}\n\n"

    @classmethod
    def _try_execute_tools(cls, message: str, user: User, db: Session) -> str:
        """
        Execute matched tool based on natural language intent with RBAC filtering.
        Returns tool output string, or empty string if no tool matched.
        """
        msg = message.lower()
        try:
            # Authoritative clock — the LLM cannot know what "today" is on its own.
            if is_datetime_query(message):
                return f"【系统实时时间】{format_now()}"

            if any(k in msg for k in ["创建任务", "新建任务", "建一个任务", "加个任务"]):
                title = (
                    message
                    .replace("帮我创建任务", "").replace("创建任务", "").replace("新建任务", "")
                    .strip("：: ，,") or "新任务"
                )
                return PermissionScopedTools.create_task_by_ai(user, db, title=title)

            if any(k in msg for k in ["风险", "健康度", "延期", "瓶颈", "诊断"]):
                return PermissionScopedTools.analyze_project_risks(user, db)

            if any(k in msg for k in ["待办", "任务", "我的任务", "未完成", "优先级"]):
                return PermissionScopedTools.query_tasks(user, db, my_tasks_only=True)

            if any(k in msg for k in ["项目", "进度", "预算", "项目列表"]):
                return PermissionScopedTools.query_projects(user, db)

            if any(k in msg for k in ["工时", "填报", "工时记录", "工时统计"]):
                return PermissionScopedTools.query_worklogs(user, db)

            if any(k in msg for k in ["缺陷", "bug", "问题", "严重"]):
                return PermissionScopedTools.query_issues(user, db)

            if any(k in msg for k in ["文档", "wiki", "知识库", "规范", "架构"]):
                return PermissionScopedTools.query_wiki_docs(user, db)

        except Exception as e:
            logger.warning(f"Tool execution failed for message '{message[:30]}': {e}")
            return ""

        return ""

    @classmethod
    def _generate_intelligent_fallback_reply(cls, message: str, user: User, db: Session, tool_output: str) -> str:
        """
        Generate a contextual Markdown response when LLM is unavailable.
        Uses tool output if available, otherwise provides a capability overview.
        """
        if is_datetime_query(message):
            return (
                f"🕐 **现在是 {format_now()}**\n\n"
                f"> 当前处于本地降级模式（大模型暂不可用），时间由服务器实时提供。"
            )

        if tool_output:
            return (
                f"✨ **你好，{user.nickname}！我是您的 AIPM 智能小精灵** 🧚\n\n"
                f"已根据您的身份权限（`{user.roles[0].name if user.roles else '员工'}`）为您实时调取系统数据：\n\n"
                f"{tool_output}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 *您还可以继续向我提问：例如「帮我创建前端优化任务」、「分析项目风险」或「查询本周缺陷列表」！*"
            )

        return (
            f"👋 **你好，{user.nickname}！** 我是 AIPM 智能项目管理小精灵（由 LangChain + DeepSeek 驱动）。\n\n"
            f"我已载入您的专属权限范围（**部门**: {user.department.name if user.department else '研发中心'} | "
            f"**角色**: {user.roles[0].name if user.roles else '普通成员'}）。\n\n"
            f"我可以协助您完成以下工作：\n"
            f"1. 📊 **项目全局洞察**：分析项目进度、预算消耗与延期风险；\n"
            f"2. ⚡ **个人任务管理**：查询指派给您的待办清单，智能创建新任务；\n"
            f"3. ⏱️ **工时统计追踪**：汇总本人本周已填报工时；\n"
            f"4. 🐞 **缺陷风险排查**：检索高危 Bug 与阻塞问题；\n"
            f"5. 📚 **知识库与文档**：快速检索企业规范与架构文档。\n\n"
            f"请问今天有什么可以帮您的吗？"
        )
