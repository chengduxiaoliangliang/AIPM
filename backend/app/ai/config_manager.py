"""
AI Config Manager — Runtime LLM configuration override via Redis.

Allows admins to update model parameters (API key, base URL, model name,
temperature, max_tokens) at runtime without restarting the server.

Redis key: aipm:ai_runtime_config  (JSON hash)

If no override exists in Redis, falls back to settings from config.py.
"""
import json
import logging
from typing import Optional, Dict, Any
from app.redis_client import redis_client
from app.config import settings

logger = logging.getLogger(__name__)

_RUNTIME_CONFIG_KEY = "aipm:ai_runtime_config"


def _defaults() -> Dict[str, Any]:
    """Default config from settings (config.py / env vars)."""
    return {
        "api_key": settings.DEEPSEEK_API_KEY,
        "base_url": settings.DEEPSEEK_BASE_URL,
        "model": settings.DEEPSEEK_MODEL,
        "max_tokens": settings.DEEPSEEK_MAX_TOKENS,
        "temperature": settings.DEEPSEEK_TEMPERATURE,
        "ai_enabled": settings.AI_ENABLED,
    }


def get_runtime_config() -> Dict[str, Any]:
    """
    Get current effective LLM config.
    Redis override takes priority over settings.py defaults.
    """
    client = redis_client.get_client()
    if client:
        try:
            raw = client.get(_RUNTIME_CONFIG_KEY)
            if raw:
                override = json.loads(raw)
                merged = _defaults()
                merged.update(override)
                return merged
        except Exception as e:
            logger.warning(f"Failed to read runtime AI config from Redis: {e}")
    return _defaults()


def save_runtime_config(updates: Dict[str, Any]) -> bool:
    """
    Persist runtime LLM config override to Redis.
    Only saves the provided fields (partial update supported).
    Returns True on success.
    """
    client = redis_client.get_client()
    if not client:
        logger.warning("Redis unavailable — AI config will not be persisted.")
        return False

    try:
        # Load existing override or empty dict
        raw = client.get(_RUNTIME_CONFIG_KEY)
        existing: Dict[str, Any] = json.loads(raw) if raw else {}

        # Merge new values in
        existing.update(updates)

        # Persist (no TTL — config should be permanent until changed)
        client.set(_RUNTIME_CONFIG_KEY, json.dumps(existing, ensure_ascii=False))
        logger.info(f"AI runtime config updated: {list(updates.keys())}")
        return True
    except Exception as e:
        logger.error(f"Failed to save AI runtime config: {e}")
        return False


def clear_runtime_config() -> bool:
    """Reset all runtime overrides, falling back to settings.py defaults."""
    client = redis_client.get_client()
    if not client:
        return False
    try:
        client.delete(_RUNTIME_CONFIG_KEY)
        logger.info("AI runtime config cleared — using defaults from settings.py")
        return True
    except Exception as e:
        logger.error(f"Failed to clear AI runtime config: {e}")
        return False


def get_masked_api_key(api_key: str) -> str:
    """Return masked API key for display (never expose full key to frontend)."""
    if not api_key or len(api_key) <= 12:
        return "未配置"
    return api_key[:8] + "****" + api_key[-4:]
