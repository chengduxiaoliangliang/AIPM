"""Minimal API client shared by the knowledge-base check scripts.

Zero extra dependencies beyond httpx (already required by the backend).
Import as `from _kbclient import KBApi` when running `python scripts/xxx.py`,
or `from scripts._kbclient import KBApi` when imported as a module.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx


class KBApi:
    def __init__(self, base_url: str, password: str = "123456", timeout: float = 60.0):
        self.base = base_url.rstrip("/")
        self.password = password
        self.client = httpx.Client(timeout=timeout)
        self._tokens: Dict[str, Optional[str]] = {}

    # ── auth ────────────────────────────────────────────────────────────────
    def login(self, username: str) -> Optional[str]:
        if username in self._tokens:
            return self._tokens[username]
        try:
            r = self.client.post(f"{self.base}/auth/login", json={
                "username": username, "password": self.password,
            })
            token = r.json()["data"]["token"] if r.status_code == 200 else None
        except Exception:
            token = None
        self._tokens[username] = token
        return token

    def _headers(self, user: str) -> Dict[str, str]:
        token = self.login(user)
        return {"Authorization": f"Bearer {token}"} if token else {}

    # ── plain requests ──────────────────────────────────────────────────────
    def request(self, method: str, path: str, user: str = "admin", **kwargs) -> Tuple[int, dict]:
        try:
            r = self.client.request(
                method, f"{self.base}{path}", headers=self._headers(user), **kwargs
            )
            try:
                body = r.json()
            except Exception:
                body = {}
            return r.status_code, body
        except Exception as exc:
            return 0, {"message": str(exc)}

    def get(self, path: str, user: str = "admin", **kw) -> Tuple[int, dict]:
        return self.request("GET", path, user, **kw)

    def post(self, path: str, user: str = "admin", **kw) -> Tuple[int, dict]:
        return self.request("POST", path, user, **kw)

    def put(self, path: str, user: str = "admin", **kw) -> Tuple[int, dict]:
        return self.request("PUT", path, user, **kw)

    def delete(self, path: str, user: str = "admin", **kw) -> Tuple[int, dict]:
        return self.request("DELETE", path, user, **kw)

    def upload(self, project_id: int, filename: str, content: str, user: str = "admin") -> Tuple[int, dict]:
        try:
            r = self.client.post(
                f"{self.base}/kb/projects/{project_id}/sources",
                headers=self._headers(user),
                files={"files": (filename, content.encode("utf-8"), "text/markdown")},
            )
            return r.status_code, (r.json() if r.content else {})
        except Exception as exc:
            return 0, {"message": str(exc)}

    def download(self, path: str, user: str = "admin") -> Tuple[int, bytes]:
        try:
            r = self.client.get(f"{self.base}{path}", headers=self._headers(user))
            return r.status_code, r.content
        except Exception as exc:
            return 0, str(exc).encode()

    # ── SSE ─────────────────────────────────────────────────────────────────
    def stream(
        self,
        path: str,
        payload: Dict[str, Any],
        user: str = "admin",
        timeout: float = 180.0,
    ) -> Dict[str, Any]:
        """Consume an SSE endpoint and measure how it actually streamed."""
        start = time.time()
        first_token_at: Optional[float] = None
        frames = 0
        chunks: List[str] = []
        events: List[str] = []
        citations: List[dict] = []
        status_code = 0

        try:
            with self.client.stream(
                "POST", f"{self.base}{path}",
                json=payload, headers=self._headers(user), timeout=timeout,
            ) as resp:
                status_code = resp.status_code
                if status_code != 200:
                    return {
                        "status": status_code, "first": None,
                        "total": time.time() - start, "frames": 0,
                        "text": "", "events": [], "citations": [],
                    }
                for line in resp.iter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    try:
                        data = json.loads(line[6:])
                    except Exception:
                        continue
                    kind = data.get("status")
                    events.append(kind)
                    if kind == "citations":
                        citations = data.get("citations") or []
                    elif kind == "streaming" and data.get("content"):
                        if first_token_at is None:
                            first_token_at = time.time() - start
                        frames += 1
                        chunks.append(data["content"])
        except Exception as exc:
            events.append(f"error:{exc}")

        return {
            "status": status_code,
            "first": first_token_at,
            "total": time.time() - start,
            "frames": frames,
            "text": "".join(chunks),
            "events": events,
            "citations": citations,
        }

    def health(self) -> Tuple[int, dict]:
        """GET /health lives at the app root, not under the API prefix."""
        root = self.base.split("/api/")[0]
        try:
            r = self.client.get(f"{root}/health", timeout=10)
            return r.status_code, (r.json() if r.content else {})
        except Exception as exc:
            return 0, {"message": str(exc)}

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass
