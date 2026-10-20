#!/usr/bin/env python3
"""Streaming regression check.

The bug this guards against: a ChatOpenAI instance created with
`streaming=False` is reused by a streaming endpoint, so `astream()` yields the
whole answer in a single chunk. The response still looks correct — it just
arrives all at once. The only reliable signal is *timing*: the first token must
land measurably before the end, and there must be many frames.

Checks:
  - POST /ai/chat/stream               (always available)
  - POST /kb/projects/{id}/ask/stream  (needs at least one page)
  - POST /kb/ask/stream                (needs pages across projects)

Usage:
    python scripts/kb_stream_check.py --base-url http://127.0.0.1:8000/api/v1
"""
from __future__ import annotations

import argparse
import sys

try:
    from _kbclient import KBApi
except ImportError:  # imported as a module
    from scripts._kbclient import KBApi


class StreamCheck:
    def __init__(self, api: KBApi, project_id: int, min_frames: int, margin: float):
        self.api = api
        self.project_id = project_id
        self.min_frames = min_frames
        self.margin = margin
        self.failures = []
        self.results = []

    def expect(self, cond: bool, label: str, detail: str = "") -> None:
        mark = "✓" if cond else "✗"
        print(f"  {mark} {label}" + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            self.failures.append(label)

    def check_stream(self, title: str, path: str, payload: dict, need_citations: bool) -> None:
        print(f"\n[{title}]  {path}")
        r = self.api.stream(path, payload)

        if r["status"] != 200:
            self.expect(False, f"{title} 返回 200", f"HTTP {r['status']}")
            return

        first = r["first"]
        total = r["total"]
        frames = r["frames"]

        self.expect(bool(r["text"].strip()), f"{title} 有实际内容")
        self.expect("finished" in r["events"], f"{title} 收到 finished 事件")
        self.expect(
            frames >= self.min_frames,
            f"{title} 分帧数 ≥ {self.min_frames}",
            f"实际 {frames} 帧",
        )

        # The core assertion: incremental delivery, not one big blob.
        if first is None:
            self.expect(False, f"{title} 有首 token 时间")
        else:
            gap = total - first
            self.expect(
                gap >= self.margin,
                f"{title} 首 token 早于结束 ≥ {self.margin}s",
                f"首 token {first:.2f}s / 总耗时 {total:.2f}s（几乎同时到达，疑似未流式）",
            )
            print(f"    首 token {first:.2f}s · 总耗时 {total:.2f}s · {frames} 帧")

        if need_citations:
            self.expect(
                "citations" in r["events"],
                f"{title} 先推送 citations 事件",
            )

        self.results.append({
            "title": title, "first": first, "total": total,
            "frames": frames, "ok": True,
        })

    def run(self) -> int:
        print(f"目标: {self.api.base}")

        # 1) AI assistant — independent of the knowledge base.
        self.check_stream(
            "AI 助手对话", "/ai/chat/stream", {"message": "你好"}, need_citations=False
        )

        # 2) Knowledge base Q&A — only meaningful when pages exist.
        code, body = self.api.get(f"/kb/projects/{self.project_id}/structure")
        pages = body.get("data", {}).get("total_pages", 0) if code == 200 else 0

        if pages == 0:
            print(f"\n[知识库问答] 跳过：项目 {self.project_id} 还没有页面")
            print("  （先上传资料并完成摄入，或运行 kb_acceptance.py 生成数据）")
        else:
            self.check_stream(
                "知识库问答（单项目）",
                f"/kb/projects/{self.project_id}/ask/stream",
                {"question": "这个项目讲了什么？"},
                need_citations=True,
            )

            code, body = self.api.get("/kb/projects")
            multi = len(body.get("data", [])) > 1 if code == 200 else False
            if multi:
                self.check_stream(
                    "知识库问答（跨项目）",
                    "/kb/ask/stream",
                    {"question": "这个项目讲了什么？"},
                    need_citations=True,
                )

        print("\n" + "=" * 56)
        if self.failures:
            print(f"结果: 失败 {len(self.failures)} 项")
            for f in self.failures:
                print(f"  - {f}")
            return 1
        print("结果: 流式输出正常 ✓")
        return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="流式输出回归检查")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    ap.add_argument("--project-id", type=int, default=1)
    ap.add_argument("--password", default="123456")
    ap.add_argument("--min-frames", type=int, default=5,
                    help="最少分帧数，低于此值视为未真正流式")
    ap.add_argument("--margin", type=float, default=0.3,
                    help="首 token 与结束之间的最小时间差（秒）")
    args = ap.parse_args()

    api = KBApi(args.base_url, args.password)
    try:
        sys.exit(StreamCheck(api, args.project_id, args.min_frames, args.margin).run())
    finally:
        api.close()


if __name__ == "__main__":
    main()
