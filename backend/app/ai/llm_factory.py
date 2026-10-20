"""
LLM Factory — Centralized, singleton-friendly LangChain LLM instance management.

Provides:
- A ChatOpenAI-compatible client for DeepSeek (reads runtime config from Redis first)
- Separate cached instances for streaming and non-streaming use
- Token estimation utility
- Connection health check
"""
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Cache keyed by (config hash, streaming flag).
#
# The streaming flag MUST be part of the key: a ChatOpenAI built with
# streaming=False returns its whole answer in a single chunk even when you call
# astream(). Reusing such an instance for a streaming endpoint silently degrades
# it to one big chunk, which is very hard to notice.
_llm_cache: dict = {}


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
    """Simple hash to detect config changes and rebuild LLM instances."""
    return (
        f"{cfg.get('api_key','')}|{cfg.get('base_url','')}|"
        f"{cfg.get('model','')}|{cfg.get('temperature','')}|{cfg.get('max_tokens','')}"
    )


def get_llm(streaming: bool = True):
    """
    Get (or create) the DeepSeek ChatOpenAI instance.

    One instance is cached per (config, streaming) pair. The cache is invalidated
    automatically when the runtime config changes (e.g. admin updates the API key
    or model in the management console).

    Returns None if the API key is not configured.
    """
    cfg = _get_config()
    api_key = cfg.get("api_key", "").strip()

    if not api_key or api_key == "your_deepseek_api_key_here":
        logger.warning("DeepSeek API key not configured — LLM disabled.")
        return None

    cfg_hash = _config_hash(cfg)
    key = (cfg_hash, bool(streaming))
    if key in _llm_cache:
        return _llm_cache[key]

    try:
        from langchain_openai import ChatOpenAI

        instance = ChatOpenAI(
            model=cfg.get("model", settings.DEEPSEEK_MODEL),
            api_key=api_key,
            base_url=cfg.get("base_url", settings.DEEPSEEK_BASE_URL),
            temperature=float(cfg.get("temperature", settings.DEEPSEEK_TEMPERATURE)),
            max_tokens=int(cfg.get("max_tokens", settings.DEEPSEEK_MAX_TOKENS)),
            streaming=streaming,
        )
    except ImportError:
        logger.error("langchain-openai is not installed. Run: pip install langchain-openai")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize LLM: {e}")
        return None

    # Drop instances built from a stale config so old keys/URLs don't linger.
    for stale in [k for k in _llm_cache if k[0] != cfg_hash]:
        _llm_cache.pop(stale, None)

    _llm_cache[key] = instance
    logger.info(
        "LLM initialized: model=%s, streaming=%s, base_url=%s",
        cfg.get("model"), streaming, cfg.get("base_url"),
    )
    return instance


def reset_llm():
    """Force re-creation of the LLM instances on next call."""
    _llm_cache.clear()
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
