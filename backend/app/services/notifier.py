"""Email notifications for knowledge-base changes.

Deliberately dependency-free (stdlib smtplib) and strictly best-effort: a broken
SMTP config must never break ingest or lint, so every send is wrapped and logged
rather than raised.
"""
from __future__ import annotations

import asyncio
import html as _html
import logging
import smtplib
from email.message import EmailMessage
from typing import Iterable, List, Optional, Sequence

from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)


def is_email_configured() -> bool:
    return bool(settings.SMTP_HOST and (settings.SMTP_FROM or settings.SMTP_USER))


def _send_sync(to: Sequence[str], subject: str, html: str, text: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM or settings.SMTP_USER
    msg["To"] = ", ".join(to)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")

    host, port = settings.SMTP_HOST, int(settings.SMTP_PORT)
    if settings.SMTP_SSL:
        server = smtplib.SMTP_SSL(host, port, timeout=20)
    else:
        server = smtplib.SMTP(host, port, timeout=20)
        if settings.SMTP_TLS:
            server.starttls()

    try:
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:
            pass


async def send_email(
    to: Iterable[str],
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> bool:
    """Send one email. Returns True only when it actually went out."""
    if not settings.KB_NOTIFY_ENABLED:
        return False
    if not is_email_configured():
        logger.debug("Email not configured — notification skipped")
        return False

    recipients = sorted({e.strip() for e in (to or []) if e and "@" in e})
    if not recipients:
        logger.info("No recipients for notification: %s", subject)
        return False

    text = text_body or _to_text(html_body)
    try:
        await asyncio.to_thread(_send_sync, recipients, subject, html_body, text)
        logger.info("Notification sent to %s: %s", recipients, subject)
        return True
    except Exception as exc:
        logger.warning("Notification failed (%s): %s", subject, exc)
        return False


def _to_text(html: str) -> str:
    import re
    text = re.sub(r"<br\s*/?>", "\n", html)
    text = re.sub(r"</(p|tr|h\d|div)>", "\n", text)
    text = re.sub(r"<[^>]+>", "", text)
    return _html.unescape(text).strip()


def _wrap(title: str, rows: Sequence[tuple], footer: str = "") -> str:
    body = "".join(
        "<tr>"
        f"<td style='padding:7px 14px;color:#6b7280;white-space:nowrap'>{_html.escape(str(k))}</td>"
        f"<td style='padding:7px 14px;color:#111827'>{_html.escape(str(v))}</td>"
        "</tr>"
        for k, v in rows
    )
    return f"""<div style="font-family:-apple-system,'Segoe UI',Helvetica,Arial,sans-serif;max-width:660px">
  <h2 style="font-size:17px;color:#2b6fd4;margin:0 0 14px">{_html.escape(title)}</h2>
  <table style="border-collapse:collapse;background:#f7f9fc;border-radius:8px;width:100%">{body}</table>
  {footer}
  <p style="color:#9ca3af;font-size:12px;margin-top:22px">
    本邮件由 AIPM 知识库自动发送，请勿直接回复。
  </p>
</div>"""


# ─── recipients ──────────────────────────────────────────────────────────────

def project_recipients(db: Session, project_id: int) -> List[str]:
    """Project members plus system administrators."""
    from app.models.project import ProjectMember
    from app.models.user import Role, User, user_role_table

    emails = set()

    members = (
        db.query(User.email)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .filter(
            ProjectMember.project_id == project_id,
            User.status.is_(True),
            User.email.isnot(None),
        )
        .all()
    )
    emails.update(m[0] for m in members if m[0])

    admins = (
        db.query(User.email)
        .join(user_role_table, user_role_table.c.user_id == User.id)
        .join(Role, Role.id == user_role_table.c.role_id)
        .filter(Role.code == "ADMIN", User.status.is_(True), User.email.isnot(None))
        .all()
    )
    emails.update(a[0] for a in admins if a[0])

    return sorted(emails)


# ─── notification types ──────────────────────────────────────────────────────

async def notify_ingest_result(db: Session, project, source, result: dict) -> bool:
    """Tell project members that a source finished (or failed) ingesting."""
    if not settings.KB_NOTIFY_ON_INGEST:
        return False

    ok = result.get("status") == "succeeded"
    subject = f"[AIPM] 知识库{'更新完成' if ok else '更新失败'}：{source.original_name}"

    rows: list = [
        ("项目", project.name),
        ("资料", source.original_name),
        ("结果", "✅ 成功" if ok else "❌ 失败"),
    ]
    if ok:
        rows += [
            ("新增页面", result.get("pages_created", 0)),
            ("更新页面", result.get("pages_updated", 0)),
            ("新增双链", result.get("links", 0)),
            ("处理方式", "AI 提炼" if result.get("used_llm") else "原文归档（AI 不可用）"),
        ]
        if result.get("chunks", 1) > 1:
            rows.append(("分段数", result.get("chunks")))
        footer = (
            f"<p style='color:#374151;font-size:13px;line-height:1.7;margin-top:16px'>"
            f"{_html.escape((result.get('summary') or '')[:400])}</p>"
        )
    else:
        rows.append(("失败原因", (result.get("error") or "未知错误")[:300]))
        footer = ""

    return await send_email(
        project_recipients(db, project.id),
        subject,
        _wrap(subject, rows, footer),
    )


async def notify_lint_alert(db: Session, project, report, issues: Sequence[dict]) -> bool:
    """Alert when an automatic health check finds the wiki in poor shape."""
    if report.score >= settings.KB_NOTIFY_LINT_SCORE_BELOW:
        return False

    high = [i for i in issues if i.get("severity") == "high"]
    medium = [i for i in issues if i.get("severity") == "medium"]
    subject = f"[AIPM] 知识库体检告警：{project.name}（{report.score} 分）"

    rows: list = [
        ("项目", project.name),
        ("健康分", f"{report.score} / 100"),
        ("问题总数", len(issues)),
        ("高危 / 中危", f"{len(high)} / {len(medium)}"),
    ]

    items = "".join(
        "<li style='margin:6px 0;color:#374151;font-size:13px'>"
        f"<b>[{_html.escape(str(i.get('severity')))}]</b> {_html.escape(str(i.get('detail'))[:160])}"
        f"<span style='color:#9ca3af'> — {_html.escape(str(i.get('page') or '全局'))}</span>"
        "</li>"
        for i in issues[:8]
    )
    footer = f"<ul style='padding-left:18px;margin-top:16px'>{items}</ul>" if items else ""

    return await send_email(
        project_recipients(db, project.id),
        subject,
        _wrap(subject, rows, footer),
    )
