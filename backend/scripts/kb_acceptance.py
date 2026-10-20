#!/usr/bin/env python3
"""Knowledge-base end-to-end acceptance checklist.

Walks the whole feature the way a user would: upload → extract → ingest →
browse → link → version → permission → ask → lint → export, then cleans up.

Every step reports PASS / FAIL / SKIP. Exit code is 0 only when nothing failed
(SKIP is allowed — e.g. AI features when the model is unavailable).

Usage:
    python scripts/kb_acceptance.py --base-url http://127.0.0.1:8000/api/v1
    python scripts/kb_acceptance.py --keep     # keep test data for inspection
"""
from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from typing import Any, Dict, List, Optional, Set

try:
    from _kbclient import KBApi
except ImportError:  # imported as a module
    from scripts._kbclient import KBApi

SAMPLE_DOC = """# 验收测试资料

## 背景
本文档由知识库验收脚本自动生成，用于验证上传、抽取、摄入、检索与导出链路。

## 权限模型
系统采用 RBAC 三级模型：用户、角色、权限。内置 ADMIN、PM、DEV、QA 四类角色。
服务层统一通过 get_user_accessible_project_ids 计算可见项目集合。

## 部署方式
生产环境使用 Docker Compose 编排四个服务，仅前端暴露 80 端口。

## 验收结论
当上述内容被正确整理为知识库页面，说明摄入链路工作正常。
"""


class Acceptance:
    def __init__(self, api: KBApi, project_id: int, keep: bool, dev_user: str):
        self.api = api
        self.project_id = project_id
        self.keep = keep
        self.dev_user = dev_user

        self.rows: List[Dict[str, Any]] = []
        self.created_pages: Set[int] = set()
        self.source_id: Optional[int] = None
        self.page_id: Optional[int] = None

    # ── reporting ───────────────────────────────────────────────────────────
    def step(self, name: str, status: str, detail: str = "") -> None:
        self.rows.append({"name": name, "status": status, "detail": detail})
        icon = {"PASS": "✓", "FAIL": "✗", "SKIP": "–"}.get(status, "?")
        line = f"  {icon} [{len(self.rows):02d}] {name}"
        if detail and status != "PASS":
            line += f"  ({detail})"
        print(line)

    def ok(self, name: str, cond: bool, detail: str = "") -> bool:
        self.step(name, "PASS" if cond else "FAIL", "" if cond else detail)
        return cond

    def skip(self, name: str, reason: str) -> None:
        self.step(name, "SKIP", reason)

    # ── helpers ─────────────────────────────────────────────────────────────
    def page_ids(self) -> Set[int]:
        code, body = self.api.get(f"/kb/projects/{self.project_id}/structure")
        if code != 200:
            return set()
        return {p["id"] for g in body["data"]["groups"] for p in g["pages"]}

    def wait_job(self, source_id: int, timeout: float = 240.0) -> Optional[dict]:
        deadline = time.time() + timeout
        last = None
        while time.time() < deadline:
            code, body = self.api.get(
                f"/kb/projects/{self.project_id}/jobs", params={"source_id": source_id}
            )
            if code == 200 and body.get("data"):
                last = body["data"][0]
                if last["status"] in ("succeeded", "failed"):
                    return last
            time.sleep(3)
        return last

    # ── steps ───────────────────────────────────────────────────────────────
    def run(self) -> int:
        print(f"目标: {self.api.base} | 项目: {self.project_id}\n")

        baseline = self.page_ids()

        # 1. platform health (root path, not under /api/v1)
        code, body = self.api.health()
        self.ok("服务健康检查", code == 200 and body.get("status") == "ok", f"HTTP {code}")

        # 2. project visibility
        code, body = self.api.get("/kb/projects")
        ids = [p["project_id"] for p in body.get("data", [])] if code == 200 else []
        if not self.ok("知识库项目列表", self.project_id in ids, f"项目不在可见列表: {ids}"):
            return self.finish()

        # 3. upload
        stamp = int(time.time())
        code, body = self.api.upload(
            self.project_id, f"acceptance-{stamp}.md", SAMPLE_DOC
        )
        if not self.ok("上传资料", code == 200 and body.get("data"), f"HTTP {code} {body.get('message')}"):
            return self.finish()
        src = body["data"][0]
        self.source_id = src["id"]

        # 4. text extraction
        self.ok("文本抽取", src["char_count"] > 0, f"char_count={src['char_count']}")

        # 5. enqueue
        code, body = self.api.post(f"/kb/sources/{self.source_id}/ingest")
        self.ok("摄入入队", code == 200, f"HTTP {code} {body.get('message')}")

        # 6. ingest completes
        job = self.wait_job(self.source_id)
        if job is None:
            self.step("摄入完成", "FAIL", "超时未拿到任务状态")
            return self.finish()
        ingested = job["status"] == "succeeded"
        self.ok("摄入完成", ingested, job.get("message", "")[:80])
        if not ingested:
            return self.finish()

        # 7. pages produced
        self.created_pages = self.page_ids() - baseline
        self.ok("生成知识页面", len(self.created_pages) > 0, f"新增 {len(self.created_pages)} 页")

        # 8. index page
        code, body = self.api.get(f"/kb/projects/{self.project_id}/structure")
        special = body.get("data", {}).get("special", {}) if code == 200 else {}
        self.ok("自动生成索引页", "index" in special, "未找到 index 页")
        self.ok("自动生成变更日志", "log" in special, "未找到 log 页")

        # 9. page content
        if self.created_pages:
            self.page_id = sorted(self.created_pages)[0]
            code, body = self.api.get(f"/kb/pages/{self.page_id}")
            content = body.get("data", {}).get("content") or ""
            self.ok("页面正文非空", len(content) > 20, f"长度 {len(content)}")

        # 10. links
        code, body = self.api.get(f"/kb/projects/{self.project_id}/graph")
        graph = body.get("data", {}) if code == 200 else {}
        self.ok("双链解析", len(graph.get("edges", [])) > 0,
                f"边数 {len(graph.get('edges', []))}")

        # 11. communities
        self.ok("社区发现", len(graph.get("communities", [])) >= 1,
                "未返回 communities")

        # 12. version history
        if self.page_id:
            code, body = self.api.get(f"/kb/pages/{self.page_id}/versions")
            versions = body.get("data", []) if code == 200 else []
            self.ok("版本快照", len(versions) >= 1, f"版本数 {len(versions)}")

            # 13. manual edit → new version
            code, detail = self.api.get(f"/kb/pages/{self.page_id}")
            page = detail.get("data", {})
            self.api.put(f"/kb/pages/{self.page_id}", json={
                "title": page.get("title", "验收页面"),
                "page_type": page.get("page_type", "topic"),
                "summary": "验收脚本手动编辑",
                "content": (page.get("content") or "") + "\n\n<!-- acceptance edit -->\n",
                "visibility": page.get("visibility", "project"),
                "allowed_roles": page.get("allowed_roles"),
            })
            code, body = self.api.get(f"/kb/pages/{self.page_id}/versions")
            versions2 = body.get("data", []) if code == 200 else []
            self.ok("编辑产生新版本", len(versions2) > len(versions),
                    f"{len(versions)} → {len(versions2)}")

            # 14. rollback
            if versions:
                v1 = [v for v in versions if v["version_no"] == 1]
                if v1:
                    code, _ = self.api.post(f"/kb/versions/{v1[0]['id']}/restore")
                    self.ok("版本回滚", code == 200, f"HTTP {code}")

        # 15. page-level permission
        code, body = self.api.post(f"/kb/projects/{self.project_id}/pages", json={
            "title": f"验收私有页·{stamp}", "page_type": "topic",
            "summary": "权限验收", "content": "仅创建者可见", "visibility": "private",
        })
        if code == 200:
            priv_id = body["data"]["id"]
            self.created_pages.add(priv_id)
            code_dev, _ = self.api.get(f"/kb/pages/{priv_id}", user=self.dev_user)
            code_admin, _ = self.api.get(f"/kb/pages/{priv_id}", user="admin")
            self.ok("页面级权限生效",
                    code_admin == 200 and code_dev == 403,
                    f"admin={code_admin}, {self.dev_user}={code_dev}")
        else:
            self.step("页面级权限生效", "FAIL", f"创建私有页失败 HTTP {code}")

        # 16. non-streaming answer
        code, body = self.api.post(
            f"/kb/projects/{self.project_id}/ask",
            json={"question": "系统的权限模型是怎样的？"},
        )
        if code == 200:
            data = body.get("data", {})
            self.ok("知识库问答", bool(data.get("answer")), "回答为空")
            self.ok("问答引用来源", len(data.get("citations", [])) > 0, "无引用")
        else:
            self.step("知识库问答", "FAIL", f"HTTP {code}")

        # 17. streaming
        r = self.api.stream(
            f"/kb/projects/{self.project_id}/ask/stream",
            {"question": "系统的部署方式是怎样的？"},
        )
        streamed = (
            r["status"] == 200
            and r["frames"] >= 5
            and r["first"] is not None
            and (r["total"] - r["first"]) >= 0.3
        )
        self.ok("流式输出", streamed,
                f"帧数 {r['frames']}, 首token {r['first']}, 总耗时 {r['total']:.2f}s")

        # 18. lint
        code, body = self.api.post(f"/kb/projects/{self.project_id}/lint")
        if code == 200:
            report = body.get("data", {})
            self.ok("知识库体检", 0 <= report.get("score", -1) <= 100,
                    f"score={report.get('score')}")
        else:
            self.step("知识库体检", "FAIL", f"HTTP {code}")

        # 19. export
        code, raw = self.api.download(f"/kb/projects/{self.project_id}/export")
        has_md = False
        if code == 200 and raw:
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    has_md = any(n.endswith(".md") for n in zf.namelist())
            except Exception:
                has_md = False
        self.ok("整库导出", code == 200 and has_md, f"HTTP {code}, {len(raw)} bytes")

        # 20. queue status
        code, body = self.api.get("/kb/queue/status")
        self.ok("摄入队列状态", code == 200 and isinstance(body.get("data", {}).get("depth"), int),
                f"HTTP {code}")

        return self.finish()

    # ── cleanup + summary ───────────────────────────────────────────────────
    def finish(self) -> int:
        if not self.keep:
            print("\n清理测试数据…")
            if self.source_id:
                code, _ = self.api.delete(f"/kb/sources/{self.source_id}")
                print(f"  {'✓' if code == 200 else '✗'} 删除资料 (HTTP {code})")
            for pid in sorted(self.created_pages):
                code, _ = self.api.delete(f"/kb/pages/{pid}")
                if code != 200:
                    print(f"  ✗ 删除页面 {pid} (HTTP {code})")
            print(f"  已清理 {len(self.created_pages)} 个页面")
        else:
            print("\n--keep 已指定，保留测试数据")

        passed = sum(1 for r in self.rows if r["status"] == "PASS")
        failed = [r for r in self.rows if r["status"] == "FAIL"]
        skipped = sum(1 for r in self.rows if r["status"] == "SKIP")

        print("\n" + "=" * 56)
        print(f"通过 {passed} · 失败 {len(failed)} · 跳过 {skipped}")
        if failed:
            for r in failed:
                print(f"  ✗ {r['name']} — {r['detail']}")
            return 1
        print("知识库整体验收通过 ✓")
        return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="知识库整体验收清单")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    ap.add_argument("--project-id", type=int, default=1)
    ap.add_argument("--password", default="123456")
    ap.add_argument("--dev-user", default="zhangsan", help="用于验证页面权限的普通成员")
    ap.add_argument("--keep", action="store_true", help="保留测试数据")
    args = ap.parse_args()

    api = KBApi(args.base_url, args.password, timeout=120.0)
    try:
        sys.exit(Acceptance(api, args.project_id, args.keep, args.dev_user).run())
    finally:
        api.close()


if __name__ == "__main__":
    main()
