"""
AI Session Manager — Redis-backed multi-user conversation session management.

Key scheme:
  aipm:ai_sessions:{user_id}            → sorted set of session_ids (score=created_at timestamp)
  aipm:ai_session:{user_id}:{session_id} → JSON list of {role, content, timestamp} messages
"""
import uuid
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from app.redis_client import redis_client
from app.config import settings

logger = logging.getLogger(__name__)

# Redis key prefixes
_SESSION_LIST_KEY = "aipm:ai_sessions:{user_id}"
_SESSION_DATA_KEY = "aipm:ai_session:{user_id}:{session_id}"
_SESSION_META_KEY = "aipm:ai_session_meta:{user_id}:{session_id}"


class AISessionManager:
    """
    Manages AI conversation sessions per user via Redis.
    Each session stores ordered message history with role/content/timestamp.
    """

    # ─── Session Lifecycle ────────────────────────────────────────────────

    @staticmethod
    def create_session(user_id: int, title: str = "") -> Dict[str, Any]:
        """
        Create a new AI conversation session for a user.
        Enforces max session limit per user (oldest pruned automatically).
        Returns session metadata dict.
        """
        session_id = str(uuid.uuid4())
        now_ts = datetime.now().timestamp()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        meta = {
            "session_id": session_id,
            "user_id": user_id,
            "title": title or f"对话 {now_str}",
            "created_at": now_str,
            "updated_at": now_str,
            "message_count": 0,
        }

        list_key = _SESSION_LIST_KEY.format(user_id=user_id)
        meta_key = _SESSION_META_KEY.format(user_id=user_id, session_id=session_id)
        data_key = _SESSION_DATA_KEY.format(user_id=user_id, session_id=session_id)

        client = redis_client.get_client()
        if client:
            try:
                # Store session metadata
                client.setex(meta_key, settings.AI_SESSION_TTL, json.dumps(meta, ensure_ascii=False))
                # Store empty message list
                client.setex(data_key, settings.AI_SESSION_TTL, json.dumps([], ensure_ascii=False))
                # Add to user session sorted set (score = created_at timestamp)
                client.zadd(list_key, {session_id: now_ts})
                client.expire(list_key, settings.AI_SESSION_TTL)

                # Prune oldest sessions if over limit
                count = client.zcard(list_key)
                if count > settings.AI_MAX_SESSIONS_PER_USER:
                    oldest = client.zrange(list_key, 0, count - settings.AI_MAX_SESSIONS_PER_USER - 1)
                    for old_sid in oldest:
                        AISessionManager._delete_session_keys(client, user_id, old_sid)
                    client.zremrangebyrank(list_key, 0, count - settings.AI_MAX_SESSIONS_PER_USER - 1)

            except Exception as e:
                logger.warning(f"Failed to create AI session in Redis: {e}")

        return meta

    @staticmethod
    def get_session_list(user_id: int) -> List[Dict[str, Any]]:
        """
        Get all sessions for a user, sorted newest-first.
        Returns list of session metadata dicts.
        """
        list_key = _SESSION_LIST_KEY.format(user_id=user_id)
        client = redis_client.get_client()
        if not client:
            return []
        try:
            # Get all session_ids sorted by score desc (newest first)
            session_ids = client.zrange(list_key, 0, -1, rev=True)
            sessions = []
            for sid in session_ids:
                meta_key = _SESSION_META_KEY.format(user_id=user_id, session_id=sid)
                raw = client.get(meta_key)
                if raw:
                    try:
                        meta = json.loads(raw)
                        sessions.append(meta)
                    except Exception:
                        pass
            return sessions
        except Exception as e:
            logger.warning(f"Failed to get AI session list for user {user_id}: {e}")
            return []

    @staticmethod
    def delete_session(user_id: int, session_id: str) -> bool:
        """Delete a specific AI session and all its messages."""
        list_key = _SESSION_LIST_KEY.format(user_id=user_id)
        client = redis_client.get_client()
        if not client:
            return False
        try:
            AISessionManager._delete_session_keys(client, user_id, session_id)
            client.zrem(list_key, session_id)
            return True
        except Exception as e:
            logger.warning(f"Failed to delete AI session {session_id}: {e}")
            return False

    @staticmethod
    def _delete_session_keys(client, user_id: int, session_id: str):
        """Internal: remove meta + data keys for a session."""
        meta_key = _SESSION_META_KEY.format(user_id=user_id, session_id=session_id)
        data_key = _SESSION_DATA_KEY.format(user_id=user_id, session_id=session_id)
        client.delete(meta_key, data_key)

    # ─── Message History ──────────────────────────────────────────────────

    @staticmethod
    def get_history(user_id: int, session_id: str) -> List[Dict[str, str]]:
        """
        Retrieve conversation history for a session.
        Returns list of {role, content} dicts (last AI_MAX_HISTORY_TURNS pairs).
        """
        data_key = _SESSION_DATA_KEY.format(user_id=user_id, session_id=session_id)
        client = redis_client.get_client()
        if not client:
            return []
        try:
            raw = client.get(data_key)
            if not raw:
                return []
            messages: List[Dict] = json.loads(raw)
            # Return only last N*2 messages (N turns = N user + N assistant)
            max_msgs = settings.AI_MAX_HISTORY_TURNS * 2
            return [{"role": m["role"], "content": m["content"]} for m in messages[-max_msgs:]]
        except Exception as e:
            logger.warning(f"Failed to get AI session history {session_id}: {e}")
            return []

    @staticmethod
    def append_messages(user_id: int, session_id: str, messages: List[Dict[str, str]], first_user_msg: str = "") -> bool:
        """
        Append new messages to session history and refresh TTL.
        Also updates session metadata (updated_at, message_count, title if first msg).
        """
        data_key = _SESSION_DATA_KEY.format(user_id=user_id, session_id=session_id)
        meta_key = _SESSION_META_KEY.format(user_id=user_id, session_id=session_id)
        client = redis_client.get_client()
        if not client:
            return False
        try:
            # Load existing messages
            raw = client.get(data_key)
            existing: List[Dict] = json.loads(raw) if raw else []

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for msg in messages:
                existing.append({
                    "role": msg["role"],
                    "content": msg["content"],
                    "timestamp": now_str,
                })

            # Trim to max capacity
            max_msgs = settings.AI_MAX_HISTORY_TURNS * 2
            if len(existing) > max_msgs:
                existing = existing[-max_msgs:]

            client.setex(data_key, settings.AI_SESSION_TTL, json.dumps(existing, ensure_ascii=False))

            # Update metadata
            raw_meta = client.get(meta_key)
            if raw_meta:
                meta = json.loads(raw_meta)
                meta["updated_at"] = now_str
                meta["message_count"] = len(existing)
                # Auto-title from first user message (truncated to 20 chars)
                if first_user_msg and meta.get("title", "").startswith("对话 "):
                    meta["title"] = first_user_msg[:20] + ("..." if len(first_user_msg) > 20 else "")
                client.setex(meta_key, settings.AI_SESSION_TTL, json.dumps(meta, ensure_ascii=False))

            return True
        except Exception as e:
            logger.warning(f"Failed to append messages to session {session_id}: {e}")
            return False

    # ─── Utility ──────────────────────────────────────────────────────────

    @staticmethod
    def get_or_create_default_session(user_id: int) -> str:
        """
        Get the most recent session for a user or create one if none exists.
        Returns session_id string.
        """
        sessions = AISessionManager.get_session_list(user_id)
        if sessions:
            return sessions[0]["session_id"]
        meta = AISessionManager.create_session(user_id)
        return meta["session_id"]

    @staticmethod
    def get_total_session_count(user_id: int) -> int:
        """Get total session count for a user."""
        list_key = _SESSION_LIST_KEY.format(user_id=user_id)
        client = redis_client.get_client()
        if not client:
            return 0
        try:
            return client.zcard(list_key)
        except Exception:
            return 0
