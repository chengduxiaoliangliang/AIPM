"""
LLM Factory — Centralized, singleton-friendly LangChain LLM instance management.

Provides:
- A ChatOpenAI-compatible client for DeepSeek (reads runtime config from Redis first)
- Token estimation utility
- Connection health check
"""
import logging
import time
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

# Module-level singleton
_llm_instance = None
_llm_config_hash: str = ""  # Track config hash to detect changes


def _get_config() -> dict:
    """Get effective config (Redis override > settings.py)."""
    try:
        from app.ai.config_manager import get_runtime_config
        return get_runtime_config()
    except Exception:
        return {
            "api_key": settings.DEEPSEEK_API_KEY,
            "base_url": settings.DEEPSEEK_BASE_URL,
            "model": settings.DEEPSEEK_MODEL,
            "max_tokens": settings.DEEPSEEK_MAX_TOKENS,
            "temperature": settings.DEEPSEEK_TEMPERATURE,
            "ai_enabled": settings.AI_ENABLED,
        }


def _config_hash(cfg: dict) -> str:
    """Simple hash to detect config changes and rebuild LLM instance."""
    return f"{cfg.get('api_key','')}|{cfg.get('base_url','')}|{cfg.get('model','')}|{cfg.get('temperature','')}|{cfg.get('max_tokens','')}"


def get_llm(streaming: bool = True):
    """
    Get (or create) the DeepSeek ChatOpenAI instance.
    Automatically rebuilds if runtime config has changed (e.g., admin updated API key).
    Returns None if API key is not configured.
    """
    global _llm_instance, _llm_config_hash

    cfg = _get_config()
    api_key = cfg.get("api_key", "").strip()

    if not api_key or api_key == "your_deepseek_api_key_here":
        logger.warning("DeepSeek API key not configured — LLM disabled.")
        return None

    current_hash = _config_hash(cfg)
    if _llm_instance is not None and current_hash == _llm_config_hash:
        # Config unchanged, reuse existing instance
        return _llm_instance

    # Build or rebuild LLM instance
    try:
        from langchain_openai import ChatOpenAI
        _llm_instance = ChatOpenAI(
            model=cfg.get("model", settings.DEEPSEEK_MODEL),
            api_key=api_key,
            base_url=cfg.get("base_url", settings.DEEPSEEK_BASE_URL),
            temperature=float(cfg.get("temperature", settings.DEEPSEEK_TEMPERATURE)),
            max_tokens=int(cfg.get("max_tokens", settings.DEEPSEEK_MAX_TOKENS)),
            streaming=streaming,
        )
        _llm_config_hash = current_hash
        logger.info(
            f"LLM factory {'rebuilt' if _llm_config_hash else 'initialized'}: "
            f"model={cfg.get('model')}, base_url={cfg.get('base_url')}"
        )
    except ImportError:
        logger.error("langchain-openai is not installed. Run: pip install langchain-openai")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        return None

    return _llm_instance


def reset_llm():
    """Force re-creation of the LLM instance on next call."""
    global _llm_instance, _llm_config_hash
    _llm_instance = None
    _llm_config_hash = ""
    logger.info("LLM instance reset.")


def is_llm_configured() -> bool:
    """Quick check: is a valid API key present (runtime config or settings)?"""
    cfg = _get_config()
    key = cfg.get("api_key", "").strip()
    return bool(key and key != "your_deepseek_api_key_here")


def get_model_info() -> dict:
    """Return current effective LLM configuration for display in admin panels."""
    cfg = _get_config()
    api_key = cfg.get("api_key", "")
    from app.ai.config_manager import get_masked_api_key
    return {
        "provider": "DeepSeek",
        "model": cfg.get("model", settings.DEEPSEEK_MODEL),
        "base_url": cfg.get("base_url", settings.DEEPSEEK_BASE_URL),
        "max_tokens": int(cfg.get("max_tokens", settings.DEEPSEEK_MAX_TOKENS)),
        "temperature": float(cfg.get("temperature", settings.DEEPSEEK_TEMPERATURE)),
        "is_configured": is_llm_configured(),
        "api_key_preview": get_masked_api_key(api_key),
    }


def estimate_tokens(text: str) -> int:
    """
    Rough token count estimate (1 token ≈ 1.5 Chinese chars or 4 English chars).
    """
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    other_chars = len(text) - chinese_chars
    return int(chinese_chars / 1.5 + other_chars / 4) + 1
