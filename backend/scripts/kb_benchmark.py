#!/usr/bin/env python3
"""Knowledge-base performance baseline.

Records the latency of the operations that actually matter, so a regression
shows up as a number instead of a vague "感觉变慢了".

Baseline IO is explicit — nothing is written or read unless you ask:

    # 建立/刷新基线
    python scripts/kb_benchmark.py --save perf-baseline.json

    # 与基线对比（不会覆盖基线）
    python scripts/kb_benchmark.py --baseline perf-baseline.json

Model-bound metrics are compared with a much looser threshold than plain API
latency, because LLM provider variance routinely swings 2x between runs.

Notes:
- Cheap endpoints are warmed up and measured 3x (median), so first-call
  connection setup doesn't pollute the numbers.
- Ingest/ask/lint call the real model and take tens of seconds; use
  --skip-llm to benchmark only the fast paths.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

try:
    from _kbclient import KBApi
except ImportError:  # imported as a module
    from scripts._kbclient import KBApi

SAMPLE_DOC = """# 性能基线资料

## 概述
本文档由性能基线脚本生成，用于测量摄入链路耗时。

## 权限
系统采用 RBAC 模型，角色包括 ADMIN、PM、DEV、QA。

## 部署
使用 Docker Compose 编排四个服务，仅前端暴露 80 端口。
"""

LABELS: Dict[str, str] = {
    "health_ms": "健康检查",
    "projects_ms": "项目列表",
    "structure_ms": "知识结构",
    "graph_ms": "图谱数据",
    "page_detail_ms": "页面详情",
    "queue_status_ms": "队列状态",
    "upload_ms": "资料上传",
    "ingest_ms": "摄入总耗时",
    "ask_ms": "问答（非流式）",
    "stream_first_token_ms": "流式首 token",
    "stream_total_ms": "流式总耗时",
    "stream_frames": "流式帧数",
    "lint_ms": "知识体检",
    "export_ms": "整库导出",
    "export_bytes": "导出体积",
}

# Metrics where a *decrease* is suspicious (fewer frames ≈ not streaming).
LOWER_IS_WORSE = {"stream_frames"}
# Informational only, never flagged.
NO_FLAG = {"export_bytes"}
# Latency dominated by the model provider, not by our code. These routinely
# swing 2x run-to-run, so they use a much looser threshold.
LLM_BOUND = {
    "ingest_ms", "ask_ms", "stream_first_token_ms", "stream_total_ms", "lint_ms",
}


def median_ms(fn: Callable[[], Any], repeat: int = 3) -> float:
    samples = []
    for _ in range(repeat):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(samples), 1)


class Benchmark:
    def __init__(self, api: KBApi, project_id: int, skip_llm: bool):
        self.api = api
        self.project_id = project_id
        self.skip_llm = skip_llm
        self.metrics: Dict[str, float] = {}
        self.notes: list = []
        self._source_id: Optional[int] = None
        self._page_id: Optional[int] = None
        self._new_pages: set = set()

    # ── helpers ─────────────────────────────────────────────────────────────
    def record(self, key: str, value: float) -> None:
        self.metrics[key] = value
        print(f"  {LABELS.get(key, key):<14} {value:>10.1f}")

    def page_ids(self) -> set:
        code, body = self.api.get(f"/kb/projects/{self.project_id}/structure")
        if code != 200:
            return set()
        return {p["id"] for g in body["data"]["groups"] for p in g["pages"]}

    def wait_job(self, source_id: int, timeout: float = 300.0) -> Optional[dict]:
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
            time.sleep(1.5)
        return last

    # ── run ─────────────────────────────────────────────────────────────────
    def run(self) -> Dict[str, Any]:
        print(f"目标: {self.api.base} | 项目: {self.project_id}\n")
        baseline_pages = self.page_ids()

        print("预热…")
        for path in (
            "/kb/projects", f"/kb/projects/{self.project_id}/structure",
            f"/kb/projects/{self.project_id}/graph", "/kb/queue/status",
        ):
            self.api.get(path)

        print("\n[接口延迟]（3 次取中位数）")
        self.record("health_ms", median_ms(lambda: self.api.health()))
        self.record("projects_ms", median_ms(lambda: self.api.get("/kb/projects")))
        self.record("structure_ms", median_ms(
            lambda: self.api.get(f"/kb/projects/{self.project_id}/structure")))
        self.record("graph_ms", median_ms(
            lambda: self.api.get(f"/kb/projects/{self.project_id}/graph")))
        self.record("queue_status_ms", median_ms(lambda: self.api.get("/kb/queue/status")))

        if self.skip_llm:
            print("\n[跳过模型相关步骤：--skip-llm]")
            return self.result()

        # ── ingest ──────────────────────────────────────────────────────────
        print("\n[摄入链路]")
        stamp = int(time.time())
        t0 = time.perf_counter()
        code, body = self.api.upload(
            self.project_id, f"perf-{stamp}.md", SAMPLE_DOC
        )
        upload_ms = (time.perf_counter() - t0) * 1000
        if code != 200 or not body.get("data"):
            self.notes.append(f"上传失败 HTTP {code}，跳过摄入与问答基准")
            return self.result()
        self.record("upload_ms", round(upload_ms, 1))

        self._source_id = body["data"][0]["id"]
        t0 = time.perf_counter()
        self.api.post(f"/kb/sources/{self._source_id}/ingest")
        job = self.wait_job(self._source_id)
        ingest_ms = (time.perf_counter() - t0) * 1000
        if job and job["status"] == "succeeded":
            self.record("ingest_ms", round(ingest_ms, 1))
        else:
            self.notes.append(f"摄入未成功：{job.get('message') if job else 'timeout'}")
            return self.result()

        self._new_pages = self.page_ids() - baseline_pages
        if self._new_pages:
            self._page_id = sorted(self._new_pages)[0]
            self.record("page_detail_ms", median_ms(
                lambda: self.api.get(f"/kb/pages/{self._page_id}")))

        # ── ask ─────────────────────────────────────────────────────────────
        print("\n[问答]")
        t0 = time.perf_counter()
        self.api.post(
            f"/kb/projects/{self.project_id}/ask",
            json={"question": "系统的权限模型是怎样的？"},
        )
        self.record("ask_ms", round((time.perf_counter() - t0) * 1000, 1))

        r = self.api.stream(
            f"/kb/projects/{self.project_id}/ask/stream",
            {"question": "系统的部署方式是怎样的？"},
        )
        if r["first"] is not None:
            self.record("stream_first_token_ms", round(r["first"] * 1000, 1))
            self.record("stream_total_ms", round(r["total"] * 1000, 1))
            self.record("stream_frames", float(r["frames"]))
        else:
            self.notes.append("流式问答未返回首 token")

        # ── lint ────────────────────────────────────────────────────────────
        print("\n[体检与导出]")
        t0 = time.perf_counter()
        self.api.post(f"/kb/projects/{self.project_id}/lint")
        self.record("lint_ms", round((time.perf_counter() - t0) * 1000, 1))

        t0 = time.perf_counter()
        code, raw = self.api.download(f"/kb/projects/{self.project_id}/export")
        self.record("export_ms", round((time.perf_counter() - t0) * 1000, 1))
        if code == 200:
            self.record("export_bytes", float(len(raw)))

        return self.result()

    def result(self) -> Dict[str, Any]:
        return {
            "meta": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "base_url": self.api.base,
                "project_id": self.project_id,
                "skip_llm": self.skip_llm,
            },
            "metrics": self.metrics,
            "notes": self.notes,
        }

    def cleanup(self) -> None:
        if self._source_id:
            self.api.delete(f"/kb/sources/{self._source_id}")
        for pid in sorted(self._new_pages):
            self.api.delete(f"/kb/pages/{pid}")
        if self._source_id or self._new_pages:
            print(f"\n已清理：1 份资料 + {len(self._new_pages)} 个页面")


def compare(
    current: Dict[str, Any],
    base: Dict[str, Any],
    threshold: float,
    llm_threshold: float,
) -> int:
    print("\n" + "=" * 68)
    print(f"对比基线：{base['meta']['timestamp']}")
    print(
        f"阈值：接口 {threshold * 100:.0f}% · 模型相关 {llm_threshold * 100:.0f}%"
        f"（带 ~ 的指标受供应商波动影响）"
    )
    print(f"{'指标':<18}{'基线':>12}{'本次':>12}{'变化':>12}")
    print("-" * 68)

    regressions = []
    for key, cur in current["metrics"].items():
        prev = base.get("metrics", {}).get(key)
        if prev is None or prev == 0:
            continue

        delta = (cur - prev) / prev * 100
        is_llm = key in LLM_BOUND
        limit = (llm_threshold if is_llm else threshold) * 100

        bad = delta < -limit if key in LOWER_IS_WORSE else delta > limit
        if key in NO_FLAG:
            bad = False

        label = LABELS.get(key, key) + ("~" if is_llm else "")
        print(f"{label:<18}{prev:>12.1f}{cur:>12.1f}{delta:>+11.1f}%{'  ⚠️' if bad else ''}")
        if bad:
            regressions.append((key, prev, cur, delta))

    print("-" * 68)
    if regressions:
        for key, prev, cur, delta in regressions:
            print(f"  ⚠️ {LABELS.get(key, key)}: {prev:.1f} → {cur:.1f} ({delta:+.1f}%)")
        return 1
    print("无显著回归 ✓")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description="知识库性能基线")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1")
    ap.add_argument("--project-id", type=int, default=1)
    ap.add_argument("--password", default="123456")
    ap.add_argument("--save", default=None, help="把本次结果写入该文件作为基线")
    ap.add_argument("--baseline", default=None, help="与该基线文件对比（不覆盖）")
    ap.add_argument("--threshold", type=float, default=0.5,
                    help="接口类指标的回归阈值（0.5 = 50%%）")
    ap.add_argument("--llm-threshold", type=float, default=1.5,
                    help="模型相关指标的回归阈值（1.5 = 150%%）")
    ap.add_argument("--skip-llm", action="store_true", help="跳过摄入/问答/体检等模型调用")
    ap.add_argument("--keep", action="store_true", help="保留测试数据")
    args = ap.parse_args()

    api = KBApi(args.base_url, args.password, timeout=180.0)
    bench = Benchmark(api, args.project_id, args.skip_llm)
    exit_code = 0

    try:
        result = bench.run()

        if args.baseline:
            path = Path(args.baseline)
            if path.exists():
                try:
                    base = json.loads(path.read_text(encoding="utf-8"))
                    exit_code = compare(result, base, args.threshold, args.llm_threshold)
                except Exception as exc:
                    print(f"\n基线读取失败（{exc}），跳过对比")
            else:
                print(f"\n未找到基线文件：{path}")

        if args.save:
            Path(args.save).write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"\n已写入基线：{args.save}")

        if result["notes"]:
            print("\n备注：")
            for n in result["notes"]:
                print(f"  - {n}")
    finally:
        if not args.keep:
            bench.cleanup()
        api.close()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
