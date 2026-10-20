#!/usr/bin/env python3
"""Knowledge-base permission regression check.

Creates three pages with different visibility levels, then verifies what each
seeded role can actually see — the exact class of bug that let a broken
`get_user_accessible_project_ids` go unnoticed for so long.

Usage:
    python scripts/kb_permission_check.py --base-url http://127.0.0.1/api/v1
    python scripts/kb_permission_check.py --base-url http://127.0.0.1/api/v1 -v

Exit code is 0 only when every expectation holds.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Dict, List, Optional, Tuple

import httpx

# Expected visibility per seeded user. "restricted" pages allow DEV and PM.
MATRIX: Dict[str, Dict[str, bool]] = {
    "admin":    {"project": True,  "restricted": True,  "private": True},
    "zhangsan": {"project": True,  "restricted": True,  "private": False},
    "lisi":     {"project": True,  "restricted": True,  "private": False},
    "wangwu":   {"project": True,  "restricted": False, "private": False},
}

VIS_LABEL = {"project": "项目可见", "restricted": "指定角色", "private": "仅自己"}


class Checker:
    def __init__(self, base_url: str, password: str, project_id: int, verbose: bool = False):
        self.base = base_url.rstrip("/")
        self.password = password
        self.project_id = project_id
        self.verbose = verbose
        self.client = httpx.Client(timeout=30.0)
        self.failures: List[str] = []

    # ── plumbing ────────────────────────────────────────────────────────────
    def login(self, username: str) -> Optional[str]:
        r = self.client.post(f"{self.base}/auth/login", json={
            "username": username, "password": self.password,
        })
        if r.status_code != 200:
            return None
        try:
            return r.json()["data"]["token"]
        except Exception:
            return None

    def call(self, method: str, path: str, token: str, **kwargs) -> Tuple[int, dict]:
        r = self.client.request(
            method, f"{self.base}{path}",
            headers={"Authorization": f"Bearer {token}"},
            **kwargs,
        )
        try:
            body = r.json()
        except Exception:
            body = {}
        return r.status_code, body

    def note(self, msg: str) -> None:
        if self.verbose:
            print(f"      {msg}")

    # ── fixture setup ───────────────────────────────────────────────────────
    def create_page(self, token: str, suffix: str, visibility: str, roles: str = "") -> Optional[int]:
        payload = {
            "title": f"权限回归测试·{suffix}·{int(time.time())}",
            "page_type": "topic",
            "summary": "自动化权限回归测试创建的页面",
            "content": f"# 权限回归测试\n\nvisibility={visibility}\n",
            "visibility": visibility,
            "allowed_roles": roles or None,
        }
        code, body = self.call("POST", f"/kb/projects/{self.project_id}/pages", token, json=payload)
        if code != 200:
            print(f"  ✗ 创建页面失败({visibility}): HTTP {code} {body.get('message')}")
            return None
        return body["data"]["id"]

    # ── assertions ──────────────────────────────────────────────────────────
    def expect(self, cond: bool, label: str, detail: str = "") -> None:
        if cond:
            print(f"  ✓ {label}")
        else:
            print(f"  ✗ {label}" + (f" — {detail}" if detail else ""))
            self.failures.append(label)

    def check_user(self, username: str, pages: Dict[str, int]) -> None:
        expected = MATRIX[username]
        token = self.login(username)
        if not token:
            print(f"\n[{username}] 跳过：登录失败")
            return

        code, body = self.call("GET", "/kb/projects", token)
        accessible = [p["project_id"] for p in body.get("data", [])] if code == 200 else []
        if self.project_id not in accessible:
            print(f"\n[{username}] 跳过：不是项目 {self.project_id} 的成员")
            return

        print(f"\n[{username}]")

        code, body = self.call("GET", f"/kb/projects/{self.project_id}/structure", token)
        if code != 200:
            self.expect(False, f"{username} 可读取项目结构", f"HTTP {code}")
            return
        titles = [p["title"] for g in body["data"]["groups"] for p in g["pages"]]

        for vis, page_id in pages.items():
            want = expected[vis]
            # Structure listing
            listed = any(t.startswith(f"权限回归测试·{vis}·") for t in titles)
            self.expect(
                listed == want,
                f"{username} 结构树{'可见' if want else '不可见'} {VIS_LABEL[vis]} 页面",
                f"实际 {'可见' if listed else '不可见'}",
            )
            # Direct detail access
            code, _ = self.call("GET", f"/kb/pages/{page_id}", token)
            got = code == 200
            self.expect(
                got == want,
                f"{username} 详情接口{'可访问' if want else '拒绝'} {VIS_LABEL[vis]} 页面",
                f"HTTP {code}",
            )

    def run(self) -> int:
        admin = self.login("admin")
        if not admin:
            print("✗ admin 登录失败，无法执行检查")
            return 2

        print(f"目标: {self.base} | 项目: {self.project_id}")
        print("\n创建测试页面…")
        pages = {
            "project": self.create_page(admin, "project", "project"),
            "restricted": self.create_page(admin, "restricted", "restricted", "DEV,PM"),
            "private": self.create_page(admin, "private", "private"),
        }
        if any(v is None for v in pages.values()):
            print("✗ 测试页面创建失败，中止")
            return 2
        print(f"  已创建: {pages}")

        try:
            for username in MATRIX:
                self.check_user(username, pages)  # type: ignore[arg-type]
        finally:
            print("\n清理测试页面…")
            for vis, pid in pages.items():
                code, _ = self.call("DELETE", f"/kb/pages/{pid}", admin)
                print(f"  {'✓' if code == 200 else '✗'} 删除 {VIS_LABEL[vis]} 页面 (HTTP {code})")

        print("\n" + "=" * 52)
        if self.failures:
            print(f"结果: 失败 {len(self.failures)} 项")
            for f in self.failures:
                print(f"  - {f}")
            return 1
        print("结果: 全部通过 ✓")
        return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="知识库页面权限回归检查")
    ap.add_argument("--base-url", default="http://127.0.0.1/api/v1")
    ap.add_argument("--password", default="123456", help="所有测试账号的统一密码")
    ap.add_argument("--project-id", type=int, default=1)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    sys.exit(Checker(args.base_url, args.password, args.project_id, args.verbose).run())


if __name__ == "__main__":
    main()
