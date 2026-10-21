"""登录失败限流。

滑块验证码只存在于前端：攻击者直接调用 /auth/login 就能完全绕过它
（实测用 curl 一行命令即可拿到 token）。所以服务端必须自己兜底。

策略：按「账号」和「来源 IP」两个维度独立计数，任一维度超过阈值即锁定。
- 只数失败：成功登录会清零，正常用户不会因为手滑几次被长期锁住
- 固定窗口：首次失败时设置 TTL，窗口内持续累计
- Redis 不可用时**放行**：认证是核心链路，不能因为缓存故障把所有人挡在门外

局限：单机 Redis 计数，多实例共享同一 Redis 时依然有效；但如果攻击者
不断更换 IP，IP 维度会失效，账号维度仍然生效。
"""
from __future__ import annotations

import logging
from typing import Optional

from app.config import settings
from app.redis_client import redis_client

logger = logging.getLogger(__name__)


def _user_key(username: str) -> str:
    return f"aipm:auth:fail:user:{(username or '').strip().lower()}"


def _ip_key(ip: str) -> str:
    return f"aipm:auth:fail:ip:{ip or 'unknown'}"


def _client():
    try:
        return redis_client.get_client()
    except Exception:
        return None


def _window() -> int:
    return max(60, int(settings.LOGIN_LOCKOUT_MINUTES) * 60)


def locked_for(username: str, ip: str) -> Optional[int]:
    """Return remaining lockout seconds, or None when not locked."""
    client = _client()
    if client is None:
        return None

    for key in (_user_key(username), _ip_key(ip)):
        try:
            raw = client.get(key)
            if raw is None:
                continue
            if int(raw) >= int(settings.LOGIN_MAX_ATTEMPTS):
                ttl = client.ttl(key)
                return int(ttl) if ttl and ttl > 0 else _window()
        except Exception as exc:
            logger.warning("login throttle check failed: %s", exc)
            return None
    return None


def record_failure(username: str, ip: str) -> None:
    client = _client()
    if client is None:
        return

    window = _window()
    for key in (_user_key(username), _ip_key(ip)):
        try:
            count = client.incr(key)
            # 首次失败开窗；万一 key 丢了 TTL 也补上，避免永久计数
            if count == 1 or client.ttl(key) < 0:
                client.expire(key, window)
        except Exception as exc:
            logger.warning("login throttle record failed: %s", exc)


def reset(username: str, ip: str) -> None:
    client = _client()
    if client is None:
        return
    try:
        client.delete(_user_key(username), _ip_key(ip))
    except Exception as exc:
        logger.warning("login throttle reset failed: %s", exc)
