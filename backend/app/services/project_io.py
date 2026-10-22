"""项目与任务的 Excel 导入 / 导出。

设计要点
--------
1. **模板不是死格式**：导入时先解析表头，用「别名匹配」自动建立列映射，
   用户也可以在界面上手动改映射。所以改列名、调顺序、加备注列都不会导致导入失败。
2. **导出即可再导入**：导出用同一套 sheet 与表头，形成闭环（迁移/备份/批量改）。
3. **先预览后执行**：解析与校验不写库，用户确认后才落库，避免脏数据。

文件结构（xlsx）：
    项目  | 项目名称* 项目编号* 负责人 状态 优先级 预算 开始日期 结束日期 描述
    任务  | 项目编号* 任务标题* 负责人 状态 优先级 类型 预估工时 开始日期 截止日期 标签 描述
    填写说明
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.models.project import Milestone, Project, ProjectMember
from app.models.task import Task
from app.models.user import User

MAX_ROWS = 2000
MAX_BYTES = 8 * 1024 * 1024

SHEET_PROJECT = "项目"
SHEET_TASK = "任务"
SHEET_HELP = "填写说明"
SHEET_MILESTONE = "里程碑"
SHEET_MEMBER = "成员"

# ─── 字段定义 ────────────────────────────────────────────────────────────────

PROJECT_FIELDS: List[Dict[str, Any]] = [
    {"key": "name", "label": "项目名称", "required": True,
     "aliases": ["项目名称", "名称", "项目", "name", "project", "project name"]},
    {"key": "code", "label": "项目编号", "required": True,
     "aliases": ["项目编号", "编号", "代号", "项目代号", "code", "project code"]},
    {"key": "owner", "label": "负责人", "required": False,
     "aliases": ["负责人", "项目经理", "负责人账号", "owner", "manager"]},
    {"key": "status", "label": "状态", "required": False,
     "aliases": ["状态", "项目状态", "status"]},
    {"key": "priority", "label": "优先级", "required": False,
     "aliases": ["优先级", "priority"]},
    {"key": "budget", "label": "预算", "required": False,
     "aliases": ["预算", "预算金额", "budget"]},
    {"key": "start_date", "label": "开始日期", "required": False,
     "aliases": ["开始日期", "启动日期", "start", "start date"]},
    {"key": "end_date", "label": "结束日期", "required": False,
     "aliases": ["结束日期", "截止日期", "end", "end date"]},
    {"key": "description", "label": "描述", "required": False,
     "aliases": ["描述", "项目描述", "说明", "description", "desc"]},
]

TASK_FIELDS: List[Dict[str, Any]] = [
    {"key": "project_code", "label": "项目编号", "required": True,
     "aliases": ["项目编号", "编号", "所属项目", "项目代号", "project code", "project"]},
    {"key": "title", "label": "任务标题", "required": True,
     "aliases": ["任务标题", "任务名称", "标题", "title", "task", "task name"]},
    {"key": "assignee", "label": "负责人", "required": False,
     "aliases": ["负责人", "指派给", "执行人", "assignee", "owner"]},
    {"key": "status", "label": "状态", "required": False,
     "aliases": ["状态", "任务状态", "status"]},
    {"key": "priority", "label": "优先级", "required": False,
     "aliases": ["优先级", "priority"]},
    {"key": "task_type", "label": "类型", "required": False,
     "aliases": ["类型", "任务类型", "type", "task type"]},
    {"key": "estimated_hours", "label": "预估工时", "required": False,
     "aliases": ["预估工时", "工时", "预计工时", "estimated hours", "estimate"]},
    {"key": "start_date", "label": "开始日期", "required": False,
     "aliases": ["开始日期", "start", "start date"]},
    {"key": "due_date", "label": "截止日期", "required": False,
     "aliases": ["截止日期", "结束日期", "到期日", "due", "due date"]},
    {"key": "tags", "label": "标签", "required": False,
     "aliases": ["标签", "tags", "tag"]},
    {"key": "description", "label": "描述", "required": False,
     "aliases": ["描述", "任务描述", "说明", "description", "desc"]},
]

MILESTONE_FIELDS: List[Dict[str, Any]] = [
    {"key": "project_code", "label": "项目编号", "required": True,
     "aliases": ["项目编号", "编号", "所属项目", "project code"]},
    {"key": "title", "label": "里程碑名称", "required": True,
     "aliases": ["里程碑名称", "里程碑", "名称", "milestone"]},
    {"key": "due_date", "label": "计划日期", "required": True,
     "aliases": ["计划日期", "日期", "截止日期", "due date", "date"]},
    {"key": "status", "label": "状态", "required": False,
     "aliases": ["状态", "milestone status", "status"]},
    {"key": "description", "label": "描述", "required": False,
     "aliases": ["描述", "说明", "description"]},
]

MEMBER_FIELDS: List[Dict[str, Any]] = [
    {"key": "project_code", "label": "项目编号", "required": True,
     "aliases": ["项目编号", "编号", "所属项目", "project code"]},
    {"key": "username", "label": "成员", "required": True,
     "aliases": ["成员", "姓名", "用户名", "账号", "member", "user"]},
    {"key": "project_role", "label": "项目角色", "required": False,
     "aliases": ["项目角色", "角色", "role"]},
]

PROJECT_STATUS = {
    "规划中": "planning", "规划": "planning", "planning": "planning",
    "进行中": "in_progress", "执行中": "in_progress", "in_progress": "in_progress",
    "测试中": "testing", "testing": "testing",
    "已交付": "completed", "已完成": "completed", "完成": "completed", "completed": "completed",
    "已挂起": "suspended", "挂起": "suspended", "暂停": "suspended", "suspended": "suspended",
}

PRIORITY = {
    "低": "low", "low": "low",
    "中": "medium", "普通": "medium", "medium": "medium",
    "高": "high", "high": "high",
    "紧急": "urgent", "最高": "urgent", "urgent": "urgent",
}

TASK_STATUS = {
    "待办": "todo", "未开始": "todo", "todo": "todo",
    "进行中": "in_progress", "处理中": "in_progress", "in_progress": "in_progress",
    "待评审": "in_review", "评审中": "in_review", "in_review": "in_review",
    "测试中": "testing", "testing": "testing",
    "已完成": "done", "完成": "done", "done": "done",
}

TASK_TYPE = {
    "任务": "task", "task": "task",
    "需求": "feature", "功能": "feature", "feature": "feature",
    "缺陷": "bug", "bug": "bug", "bug修复": "bug",
    "改进": "improvement", "优化": "improvement", "improvement": "improvement",
    "调研": "research", "研究": "research", "research": "research",
}

MILESTONE_STATUS = {
    "待开始": "pending", "未开始": "pending", "pending": "pending",
    "进行中": "in_progress", "in_progress": "in_progress",
    "已达成": "reached", "已完成": "reached", "reached": "reached",
    "已延期": "delayed", "延期": "delayed", "delayed": "delayed",
}

MEMBER_ROLE = {
    "项目经理": "pm", "pm": "pm",
    "技术负责人": "tech_lead", "技术主管": "tech_lead", "tech_lead": "tech_lead",
    "开发": "developer", "developer": "developer",
    "测试": "qa", "qa": "qa",
    "设计": "designer", "designer": "designer",
    "观察者": "viewer", "只读": "viewer", "viewer": "viewer",
}

MILESTONE_STATUS_LABEL = {
    "pending": "待开始", "in_progress": "进行中",
    "reached": "已达成", "delayed": "已延期",
}

MEMBER_ROLE_LABEL = {
    "pm": "项目经理", "tech_lead": "技术负责人", "developer": "开发",
    "qa": "测试", "designer": "设计", "viewer": "观察者",
}

PROJECT_STATUS_LABEL = {
    "planning": "规划中", "in_progress": "进行中", "testing": "测试中",
    "completed": "已交付", "suspended": "已挂起",
}
PRIORITY_LABEL = {"low": "低", "medium": "中", "high": "高", "urgent": "紧急"}
TASK_STATUS_LABEL = {
    "todo": "待办", "in_progress": "进行中", "in_review": "待评审",
    "testing": "测试中", "done": "已完成",
}
TASK_TYPE_LABEL = {
    "task": "任务", "feature": "需求", "bug": "缺陷",
    "improvement": "改进", "research": "调研",
}


# ─── 工具 ────────────────────────────────────────────────────────────────────

def _norm(text: Any) -> str:
    """表头归一化：去空白、去必填星号、转小写。"""
    if text is None:
        return ""
    s = str(text).strip().lower()
    s = s.replace("*", "").replace("＊", "")
    s = re.sub(r"[\s_\-()（）:：]+", "", s)
    return s


def _alias_map(fields: List[Dict[str, Any]]) -> Dict[str, str]:
    """别名 → 字段 key。"""
    table: Dict[str, str] = {}
    for f in fields:
        for alias in [f["label"], *f["aliases"]]:
            table[_norm(alias)] = f["key"]
    return table


def _to_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Excel 序列号（例如 45658）
    if re.fullmatch(r"\d{5}", s):
        try:
            return datetime(1899, 12, 30).date() + timedelta(days=int(s))
        except Exception:
            return None
    return None


def _to_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _enum(value: Any, table: Dict[str, str], default: str) -> Tuple[str, bool]:
    """返回 (内部值, 是否识别成功)。"""
    if value is None or str(value).strip() == "":
        return default, True
    key = str(value).strip().lower()
    if key in table:
        return table[key], True
    # 中文不需要 lower
    raw = str(value).strip()
    if raw in table:
        return table[raw], True
    return default, False


# ─── 模板 ────────────────────────────────────────────────────────────────────

_HEADER_FILL = PatternFill("solid", fgColor="EAF0FF")
_HEADER_FONT = Font(bold=True, color="1F3A8A", size=11)
_THIN = Side(style="thin", color="D6DEEB")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _style_sheet(ws, headers: List[str], widths: List[int], sample: List[List[Any]]):
    ws.append(headers)
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width
    for cell in ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = _BORDER
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 26
    for row in sample:
        ws.append(row)


def build_template() -> bytes:
    """生成导入模板（4 个数据表 + 填写说明）。"""
    wb = Workbook()

    ws = wb.active
    ws.title = SHEET_PROJECT
    _style_sheet(
        ws,
        [f["label"] + ("*" if f["required"] else "") for f in PROJECT_FIELDS],
        [22, 16, 12, 10, 10, 12, 12, 12, 36],
        [[
            "示例：客户门户重构", "DEMO-2026", "admin", "进行中", "高",
            120000, "2026-03-01", "2026-06-30", "示例数据，导入前请删除本行",
        ]],
    )

    ws = wb.create_sheet(SHEET_TASK)
    _style_sheet(
        ws,
        [f["label"] + ("*" if f["required"] else "") for f in TASK_FIELDS],
        [16, 26, 12, 10, 10, 10, 12, 12, 12, 16, 36],
        [[
            "DEMO-2026", "示例：登录页改版", "zhangsan", "进行中", "高",
            "需求", 16, "2026-03-01", "2026-03-15", "前端,UI", "示例数据，导入前请删除本行",
        ]],
    )

    ws = wb.create_sheet(SHEET_MILESTONE)
    _style_sheet(
        ws,
        [f["label"] + ("*" if f["required"] else "") for f in MILESTONE_FIELDS],
        [16, 24, 14, 10, 36],
        [[
            "DEMO-2026", "示例：一期上线", "2026-05-30", "待开始", "示例数据，导入前请删除本行",
        ]],
    )

    ws = wb.create_sheet(SHEET_MEMBER)
    _style_sheet(
        ws,
        [f["label"] + ("*" if f["required"] else "") for f in MEMBER_FIELDS],
        [16, 16, 16],
        [["DEMO-2026", "zhangsan", "开发"]],
    )

    help_ws = wb.create_sheet(SHEET_HELP)
    help_ws.column_dimensions["A"].width = 18
    help_ws.column_dimensions["B"].width = 12
    help_ws.column_dimensions["C"].width = 62

    rows = [("字段", "是否必填", "说明 / 可选值")]
    for label, fields, kind in (
        ("【项目】", PROJECT_FIELDS, "project"),
        ("【任务】", TASK_FIELDS, "task"),
        ("【里程碑】", MILESTONE_FIELDS, "milestone"),
        ("【成员】", MEMBER_FIELDS, "member"),
    ):
        rows.append((label, "", ""))
        for f in fields:
            rows.append((f["label"], "必填" if f["required"] else "选填", _field_hint(f["key"], kind)))
        rows.append(("", "", ""))

    rows.append(("使用说明", "", "1. 列名可以改、顺序可以调，导入时会自动识别并允许手动映射"))
    rows.append(("", "", "2. 任务/里程碑/成员都通过「项目编号」关联到项目"))
    rows.append(("", "", "3. 负责人填用户名或昵称；留空则默认为当前登录用户"))
    rows.append(("", "", "4. 日期支持 2026-03-01 / 2026/3/1 / Excel 日期格式"))
    rows.append(("", "", "5. 只有「项目」表是必需的，其余三张表可以留空或删掉"))
    rows.append(("", "", "6. 示例行请删除后再导入；单次最多 2000 行"))

    for r in rows:
        help_ws.append(list(r))
    for cell in help_ws[1]:
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
    for row in help_ws.iter_rows(min_row=1, max_row=help_ws.max_row, min_col=1, max_col=3):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _field_hint(key: str, kind: str) -> str:
    hints = {
        "name": "项目名称，最长 128 字",
        "code": "项目唯一编号，导入时据此判重（已存在则跳过）",
        "owner": "用户名或昵称；留空 = 当前登录用户",
        "status": "规划中 / 进行中 / 测试中 / 已交付 / 已挂起（默认 进行中）",
        "priority": "低 / 中 / 高 / 紧急（默认 中）",
        "budget": "数字，单位元",
        "start_date": "日期，如 2026-03-01",
        "end_date": "日期，需晚于开始日期",
        "description": "多行文本",
        "project_code": "必须与「项目」表中的项目编号一致",
        "title": "任务标题，最长 255 字",
        "assignee": "用户名或昵称；留空则不指派",
        "task_type": "任务 / 需求 / 缺陷 / 改进 / 调研（默认 任务）",
        "estimated_hours": "数字，单位小时",
        "due_date": "日期，如 2026-03-15",
        "tags": "逗号分隔，如 前端,UI",
    }
    if kind == "task" and key == "status":
        return "待办 / 进行中 / 待评审 / 测试中 / 已完成（默认 待办）"
    if kind == "milestone":
        return {
            "project_code": "必须与「项目」表中的项目编号一致",
            "title": "里程碑名称，最长 128 字",
            "due_date": "计划达成日期，必填",
            "status": "待开始 / 进行中 / 已达成 / 已延期（默认 待开始）",
            "description": "多行文本",
        }.get(key, "")
    if kind == "member":
        return {
            "project_code": "必须与「项目」表中的项目编号一致",
            "username": "用户名或昵称，必须是系统里已有的账号",
            "project_role": "项目经理 / 技术负责人 / 开发 / 测试 / 设计 / 观察者（默认 开发）",
        }.get(key, "")
    return hints.get(key, "")


# ─── CSV ─────────────────────────────────────────────────────────────────────
# CSV 只有一张表，用「类型」列区分项目行与任务行：
#   类型=项目 → 用 项目编号/项目名称/项目状态/项目优先级/预算/项目日期
#   类型=任务 → 用 项目编号/任务标题/任务状态/任务优先级/任务类型/工时/任务日期
# 负责人对项目是 owner，对任务是 assignee，按行类型解释。
# 这样一张表就能表达完整结构，也方便从其他系统（Jira/禅道）直接导出改列名。

CSV_COLUMNS: List[Tuple[str, List[str]]] = [
    ("record_type", ["类型", "记录类型", "type"]),
    ("project_code", ["项目编号", "编号", "项目代号", "project code"]),
    ("project_name", ["项目名称", "project name"]),
    ("project_status", ["项目状态", "project status"]),
    ("project_priority", ["项目优先级", "project priority"]),
    ("project_budget", ["预算", "项目预算", "budget"]),
    ("project_start", ["项目开始日期"]),
    ("project_end", ["项目结束日期"]),
    ("task_title", ["任务标题", "任务名称", "task"]),
    ("task_status", ["任务状态", "task status"]),
    ("task_priority", ["任务优先级", "task priority"]),
    ("task_type", ["任务类型", "task type"]),
    ("task_estimate", ["预估工时", "工时", "estimate"]),
    ("task_start", ["任务开始日期"]),
    ("task_due", ["任务截止日期", "截止日期", "due"]),
    ("milestone_title", ["里程碑名称", "里程碑", "milestone"]),
    ("milestone_due", ["里程碑日期", "计划日期"]),
    ("milestone_status", ["里程碑状态"]),
    ("member_name", ["成员", "姓名", "member"]),
    ("member_role", ["项目角色", "角色", "role"]),
    ("owner", ["负责人", "指派人", "owner", "assignee"]),
    ("tags", ["标签", "tags"]),
    ("description", ["描述", "说明", "description"]),
]

CSV_HEADERS = [
    "类型", "项目编号", "项目名称", "项目状态", "项目优先级", "预算",
    "项目开始日期", "项目结束日期",
    "任务标题", "任务状态", "任务优先级", "任务类型", "预估工时",
    "任务开始日期", "任务截止日期",
    "里程碑名称", "里程碑日期", "里程碑状态",
    "成员", "项目角色",
    "负责人", "标签", "描述",
]

CSV_SAMPLES = [
    ["项目", "DEMO-2026", "示例：客户门户重构", "进行中", "高", 120000,
     "2026-03-01", "2026-06-30",
     "", "", "", "", "", "", "",
     "", "", "",
     "", "",
     "admin", "", "示例项目行，导入前请删除"],
    ["任务", "DEMO-2026", "", "", "", "",
     "", "",
     "示例：登录页改版", "进行中", "高", "需求", 16,
     "2026-03-01", "2026-03-15",
     "", "", "",
     "", "",
     "zhangsan", "前端,UI", "示例任务行，导入前请删除"],
    ["里程碑", "DEMO-2026", "", "", "", "",
     "", "",
     "", "", "", "", "", "", "",
     "示例：一期上线", "2026-05-30", "待开始",
     "", "",
     "", "", "示例里程碑行，导入前请删除"],
    ["成员", "DEMO-2026", "", "", "", "",
     "", "",
     "", "", "", "", "", "", "",
     "", "", "",
     "zhangsan", "开发",
     "", "", ""],
]


def build_csv_template() -> bytes:
    """生成 CSV 模板（UTF-8 BOM，Excel 直接打开不乱码）。"""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADERS)
    for row in CSV_SAMPLES:
        writer.writerow(row)
    # BOM：不加的话 Excel 打开中文会乱码
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _decode_text(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ValueError("无法识别文件编码，请另存为 UTF-8 或 GBK 后重试")


# 记录类型 → 内部 sheet key
_CSV_KIND = {
    "项目": "project", "project": "project", "p": "project",
    "任务": "task", "task": "task", "t": "task",
    "里程碑": "milestone", "milestone": "milestone", "m": "milestone",
    "成员": "member", "member": "member", "u": "member",
}

# 每类记录取哪些列 → 内部字段 key
_CSV_FIELD_MAP = {
    "project": {
        "project_code": "code", "project_name": "name", "owner": "owner",
        "project_status": "status", "project_priority": "priority",
        "project_budget": "budget", "project_start": "start_date",
        "project_end": "end_date", "description": "description",
    },
    "task": {
        "project_code": "project_code", "task_title": "title", "owner": "assignee",
        "task_status": "status", "task_priority": "priority",
        "task_type": "task_type", "task_estimate": "estimated_hours",
        "task_start": "start_date", "task_due": "due_date",
        "tags": "tags", "description": "description",
    },
    "milestone": {
        "project_code": "project_code", "milestone_title": "title",
        "milestone_due": "due_date", "milestone_status": "status",
        "description": "description",
    },
    "member": {
        "project_code": "project_code", "member_name": "username",
        "member_role": "project_role",
    },
}


def _parse_csv(raw: bytes) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Dict[str, Any]]]:
    """把单表 CSV 拆成四类记录，结构与 xlsx 解析结果保持一致。"""
    text = _decode_text(raw)
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip() for h in (reader.fieldnames or [])]
    if not headers:
        raise ValueError("CSV 文件没有表头")

    alias: Dict[str, str] = {}
    for key, names in CSV_COLUMNS:
        for n in names:
            alias[_norm(n)] = key

    col_of: Dict[str, str] = {}
    for h in headers:
        key = alias.get(_norm(h))
        if key and key not in col_of:
            col_of[key] = h

    if "record_type" not in col_of and "task_title" not in col_of:
        raise ValueError("CSV 缺少「类型」列，且找不到「任务标题」列")

    rows: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _CSV_FIELD_MAP}

    for idx, raw_row in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k}
        if not any(row.values()):
            continue

        kind_text = row.get(col_of.get("record_type", ""), "").strip().lower()
        kind = _CSV_KIND.get(kind_text, "task")  # 没写类型时按任务处理
        field_map = _CSV_FIELD_MAP[kind]

        item: Dict[str, Any] = {"_row": idx}
        for csv_key, internal in field_map.items():
            item[internal] = row.get(col_of.get(csv_key, ""), "")
        rows[kind].append(item)

    # 映射信息按「sheet → 列 → 字段」给出，供前端展示
    metas: Dict[str, Dict[str, Any]] = {}
    for kind, field_map in _CSV_FIELD_MAP.items():
        mapping = {}
        for i, h in enumerate(headers):
            internal = alias.get(_norm(h))
            if internal and internal in field_map:
                target = field_map[internal]
                if target not in mapping.values():
                    mapping[str(i)] = target
        metas[kind] = {"headers": headers, "mapping": mapping, "header_row": 1}

    return rows, metas


# ─── 解析与校验 ──────────────────────────────────────────────────────────────

def _read_sheet(
    ws,
    fields: List[Dict[str, Any]],
    override: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """读取一个 sheet：返回 (行列表, 表头信息)。

    表头取前 5 行里第一行非空行；列按别名映射，识别不出的列忽略。
    `override` 形如 {"0": "name", "3": "status"}（列下标 → 字段 key），
    用于用户在界面上手动纠正自动映射。
    """
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return [], {"headers": [], "mapping": {}, "header_row": 0}

    header_idx = 0
    for i, row in enumerate(rows[:5]):
        if any(c is not None and str(c).strip() for c in row):
            header_idx = i
            break

    raw_headers = [("" if c is None else str(c).strip()) for c in rows[header_idx]]
    valid_keys = {f["key"] for f in fields}
    if override:
        mapping = {
            int(col): key for col, key in override.items()
            if key in valid_keys and int(col) < len(raw_headers)
        }
    else:
        alias = _alias_map(fields)
        mapping = {}
        for col, header in enumerate(raw_headers):
            key = alias.get(_norm(header))
            if key and key not in mapping.values():
                mapping[col] = key

    out: List[Dict[str, Any]] = []
    for offset, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not any(c is not None and str(c).strip() for c in row):
            continue
        item: Dict[str, Any] = {"_row": offset}
        for col, key in mapping.items():
            item[key] = row[col] if col < len(row) else None
        out.append(item)

    return out, {
        "headers": raw_headers,
        "mapping": {str(col): key for col, key in mapping.items()},
        "header_row": header_idx + 1,
    }


def parse_import(
    file_bytes: bytes,
    filename: str = "",
    mapping: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """解析上传文件，返回各表内容、列映射与校验问题（不写库）。

    返回里的 `rows` 是完整解析结果，供 execute 使用；对外接口会把它剔除。
    """
    if len(file_bytes) > MAX_BYTES:
        raise ValueError(f"文件过大，最大 {MAX_BYTES // 1024 // 1024}MB")

    name = (filename or "").lower()

    if name.endswith(".csv"):
        rows, metas = _parse_csv(file_bytes)
        for key in rows:
            if len(rows[key]) > MAX_ROWS:
                raise ValueError(f"单次导入最多 {MAX_ROWS} 行")
        return _build_result(rows, metas, "csv")

    if not name.endswith((".xlsx", ".xlsm")):
        raise ValueError("仅支持 .xlsx 或 .csv 格式，请用下载的模板填写")

    try:
        wb = load_workbook(io.BytesIO(file_bytes), data_only=True, read_only=True)
    except Exception as exc:
        raise ValueError(f"无法读取该文件：{exc}")

    def pick(names: List[str]):
        for n in names:
            for actual in wb.sheetnames:
                if _norm(actual) == _norm(n):
                    return wb[actual]
        return None

    specs = [
        ("project", [SHEET_PROJECT, "项目信息", "Projects"], PROJECT_FIELDS),
        ("task", [SHEET_TASK, "任务列表", "Tasks"], TASK_FIELDS),
        ("milestone", [SHEET_MILESTONE, "里程碑计划", "Milestones"], MILESTONE_FIELDS),
        ("member", [SHEET_MEMBER, "项目成员", "Members"], MEMBER_FIELDS),
    ]

    found = {key: pick(names) for key, names, _ in specs}
    if found["project"] is None and found["task"] is None:
        raise ValueError(f"未找到「{SHEET_PROJECT}」或「{SHEET_TASK}」工作表，请使用下载的模板")

    overrides = mapping or {}
    rows: Dict[str, List[Dict[str, Any]]] = {}
    metas: Dict[str, Dict[str, Any]] = {}
    for key, _, fields in specs:
        ws = found[key]
        if ws is None:
            rows[key], metas[key] = [], {"headers": [], "mapping": {}, "header_row": 0}
        else:
            rows[key], metas[key] = _read_sheet(ws, fields, overrides.get(key))

    for key in rows:
        if len(rows[key]) > MAX_ROWS:
            raise ValueError(f"单次导入最多 {MAX_ROWS} 行")

    return _build_result(rows, metas, "xlsx")


def _build_result(
    rows: Dict[str, List[Dict[str, Any]]],
    metas: Dict[str, Dict[str, Any]],
    fmt: str,
) -> Dict[str, Any]:
    """把解析结果整理成对外结构（含必填列检查）。"""
    issues: List[Dict[str, Any]] = []

    field_map = {
        "project": PROJECT_FIELDS,
        "task": TASK_FIELDS,
        "milestone": MILESTONE_FIELDS,
        "member": MEMBER_FIELDS,
    }
    sheet_label = {
        "project": SHEET_PROJECT, "task": SHEET_TASK,
        "milestone": SHEET_MILESTONE, "member": SHEET_MEMBER,
    }

    # 必填列是否被识别（表里一行数据都没有时不算问题）
    for key, fields in field_map.items():
        meta = metas.get(key) or {}
        if not meta.get("headers"):
            continue
        mapped = set((meta.get("mapping") or {}).values())
        for f in fields:
            if f["required"] and f["key"] not in mapped:
                issues.append({
                    "level": "error", "sheet": sheet_label[key],
                    "row": meta.get("header_row", 1),
                    "field": f["label"],
                    "message": f"未找到「{f['label']}」列，请在文件中保留该列或调整映射",
                })

    # 表头指纹：用于判断某个映射预设是否适用于当前文件
    sig_src = "|".join(
        f"{key}:" + ",".join(_norm(h) for h in (metas.get(key, {}).get("headers") or []))
        for key in ("project", "task", "milestone", "member")
    )
    signature = hashlib.sha1(sig_src.encode("utf-8")).hexdigest()[:32]

    return {
        "format": fmt,
        "signature": signature,
        "sheets": {
            key: {
                "rows": rows[key][:5],
                "total": len(rows[key]),
                "headers": metas.get(key, {}).get("headers", []),
                "mapping": metas.get(key, {}).get("mapping", {}),
                "header_row": metas.get(key, {}).get("header_row", 0),
            }
            for key in field_map
        },
        "fields": field_map,
        "issues": issues,
        "rows": rows,
    }


def validate_rows(db: Session, rows: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """校验所有记录，返回问题列表（error 阻断导入，warning 仅提示）。"""
    issues: List[Dict[str, Any]] = []

    def add(level: str, sheet: str, row: int, message: str):
        issues.append({"level": level, "sheet": sheet, "row": row, "message": message})

    existing_codes = {c[0] for c in db.query(Project.code).all()}
    usernames: Dict[str, int] = {}
    for uid, username, nickname in db.query(User.id, User.username, User.nickname).all():
        usernames[_norm(username)] = uid
        if nickname:
            usernames.setdefault(_norm(nickname), uid)

    proj_rows = rows.get("project", [])
    task_rows = rows.get("task", [])
    ms_rows = rows.get("milestone", [])
    member_rows = rows.get("member", [])

    # ── 项目 ──────────────────────────────────────────────────────────
    file_codes = set()
    for r in proj_rows:
        row = r["_row"]
        name = str(r.get("name") or "").strip()
        code = str(r.get("code") or "").strip()
        if not name:
            add("error", SHEET_PROJECT, row, "项目名称不能为空")
        if not code:
            add("error", SHEET_PROJECT, row, "项目编号不能为空")
        elif _norm(code) in file_codes:
            add("error", SHEET_PROJECT, row, f"项目编号「{code}」在文件中重复")
        elif code in existing_codes:
            add("warning", SHEET_PROJECT, row, f"项目编号「{code}」已存在，导入时将跳过该项目")
        else:
            file_codes.add(_norm(code))

        owner = str(r.get("owner") or "").strip()
        if owner and _norm(owner) not in usernames:
            add("warning", SHEET_PROJECT, row, f"负责人「{owner}」不存在，将使用当前登录用户")

        for key, table, label in (
            ("status", PROJECT_STATUS, "状态"),
            ("priority", PRIORITY, "优先级"),
        ):
            if str(r.get(key) or "").strip() and not _enum(r.get(key), table, "")[1]:
                add("warning", SHEET_PROJECT, row, f"「{r.get(key)}」不是有效的{label}，将使用默认值")

        for key in ("start_date", "end_date"):
            if str(r.get(key) or "").strip() and _to_date(r.get(key)) is None:
                add("error", SHEET_PROJECT, row, f"{'开始' if key == 'start_date' else '结束'}日期格式无法识别")

        sd, ed = _to_date(r.get("start_date")), _to_date(r.get("end_date"))
        if sd and ed and ed < sd:
            add("error", SHEET_PROJECT, row, "结束日期早于开始日期")

    def check_project_ref(sheet: str, row: int, code: str) -> bool:
        """项目编号必须在本文件的项目表或数据库中。"""
        if not code:
            add("error", sheet, row, "项目编号不能为空")
            return False
        if _norm(code) in file_codes or code in existing_codes:
            return True
        add("error", sheet, row, f"项目编号「{code}」在「项目」表中不存在")
        return False

    # ── 任务 ──────────────────────────────────────────────────────────
    for r in task_rows:
        row = r["_row"]
        if not str(r.get("title") or "").strip():
            add("error", SHEET_TASK, row, "任务标题不能为空")
        check_project_ref(SHEET_TASK, row, str(r.get("project_code") or "").strip())

        assignee = str(r.get("assignee") or "").strip()
        if assignee and _norm(assignee) not in usernames:
            add("warning", SHEET_TASK, row, f"负责人「{assignee}」不存在，该任务将不指派")

        for key, table, label in (
            ("status", TASK_STATUS, "状态"),
            ("priority", PRIORITY, "优先级"),
            ("task_type", TASK_TYPE, "类型"),
        ):
            if str(r.get(key) or "").strip() and not _enum(r.get(key), table, "")[1]:
                add("warning", SHEET_TASK, row, f"「{r.get(key)}」不是有效的{label}，将使用默认值")

        for key in ("start_date", "due_date"):
            if str(r.get(key) or "").strip() and _to_date(r.get(key)) is None:
                add("error", SHEET_TASK, row, "日期格式无法识别")

    # ── 里程碑 ────────────────────────────────────────────────────────
    seen_ms = set()
    for r in ms_rows:
        row = r["_row"]
        code = str(r.get("project_code") or "").strip()
        title = str(r.get("title") or "").strip()
        check_project_ref(SHEET_MILESTONE, row, code)

        if not title:
            add("error", SHEET_MILESTONE, row, "里程碑名称不能为空")
        elif (_norm(code), _norm(title)) in seen_ms:
            add("warning", SHEET_MILESTONE, row, f"里程碑「{title}」在本文件中重复，仅导入第一个")
        else:
            seen_ms.add((_norm(code), _norm(title)))

        if not str(r.get("due_date") or "").strip():
            add("error", SHEET_MILESTONE, row, "计划日期不能为空")
        elif _to_date(r.get("due_date")) is None:
            add("error", SHEET_MILESTONE, row, "计划日期格式无法识别")

        if str(r.get("status") or "").strip() and not _enum(r.get("status"), MILESTONE_STATUS, "")[1]:
            add("warning", SHEET_MILESTONE, row, f"「{r.get('status')}」不是有效的里程碑状态，将使用默认值")

    # ── 成员 ──────────────────────────────────────────────────────────
    seen_member = set()
    for r in member_rows:
        row = r["_row"]
        code = str(r.get("project_code") or "").strip()
        username = str(r.get("username") or "").strip()
        check_project_ref(SHEET_MEMBER, row, code)

        if not username:
            add("error", SHEET_MEMBER, row, "成员不能为空")
        elif _norm(username) not in usernames:
            add("error", SHEET_MEMBER, row, f"成员「{username}」在系统中不存在")
        elif (_norm(code), _norm(username)) in seen_member:
            add("warning", SHEET_MEMBER, row, f"成员「{username}」在本文件中重复，仅导入一次")
        else:
            seen_member.add((_norm(code), _norm(username)))

        if str(r.get("project_role") or "").strip() and not _enum(r.get("project_role"), MEMBER_ROLE, "")[1]:
            add("warning", SHEET_MEMBER, row, f"「{r.get('project_role')}」不是有效的项目角色，将使用默认值")

    return issues


# ─── 导入执行 ────────────────────────────────────────────────────────────────

def execute_import(
    db: Session,
    rows: Dict[str, List[Dict[str, Any]]],
    current_user: User,
) -> Dict[str, Any]:
    """写入数据库。已存在的项目编号跳过；同项目内同名任务/里程碑跳过。"""
    usernames: Dict[str, int] = {}
    for uid, username, nickname in db.query(User.id, User.username, User.nickname).all():
        usernames[_norm(username)] = uid
        if nickname:
            usernames.setdefault(_norm(nickname), uid)

    existing = {c[0]: c[0] for c in db.query(Project.code).all()}
    created_projects = 0
    skipped_projects = 0
    code_to_id: Dict[str, int] = {}
    created_project_ids: List[int] = []
    # 负责人会被自动加成 pm 成员，这条也属于本批次创建，必须记进 created_ids，
    # 否则回滚时会被误判为"导入后新增的成员"而拒绝。
    member_objs: List[ProjectMember] = []

    # ── 项目 ──────────────────────────────────────────────────────────
    for r in rows.get("project", []):
        code = str(r.get("code") or "").strip()
        name = str(r.get("name") or "").strip()
        if not code or not name:
            continue
        if code in existing:
            skipped_projects += 1
            continue

        owner_name = str(r.get("owner") or "").strip()
        owner_id = usernames.get(_norm(owner_name), current_user.id) if owner_name else current_user.id

        status, _ = _enum(r.get("status"), PROJECT_STATUS, "in_progress")
        priority, _ = _enum(r.get("priority"), PRIORITY, "medium")

        project = Project(
            name=name[:128],
            code=code[:64],
            description=str(r.get("description") or "").strip() or None,
            owner_id=owner_id,
            status=status,
            priority=priority,
            budget=_to_float(r.get("budget")) or 0.0,
            start_date=_to_date(r.get("start_date")),
            end_date=_to_date(r.get("end_date")),
        )
        db.add(project)
        db.flush()
        owner_member = ProjectMember(
            project_id=project.id, user_id=owner_id, project_role="pm"
        )
        db.add(owner_member)
        member_objs.append(owner_member)
        code_to_id[code] = project.id
        created_project_ids.append(project.id)
        existing[code] = code
        created_projects += 1

    # 已存在的项目也允许追加任务/里程碑/成员
    for code in {
        str(r.get("project_code") or "").strip()
        for key in ("task", "milestone", "member")
        for r in rows.get(key, [])
    }:
        if code and code not in code_to_id:
            hit = db.query(Project.id).filter(Project.code == code).first()
            if hit:
                code_to_id[code] = hit[0]

    # ── 任务 ──────────────────────────────────────────────────────────
    existing_titles: Dict[int, set] = {}
    for pid in set(code_to_id.values()):
        existing_titles[pid] = {
            _norm(t[0]) for t in db.query(Task.title).filter(Task.project_id == pid).all()
        }

    created_tasks = 0
    skipped_tasks = 0
    task_objs: List[Task] = []
    for r in rows.get("task", []):
        code = str(r.get("project_code") or "").strip()
        title = str(r.get("title") or "").strip()
        pid = code_to_id.get(code)
        if not pid or not title:
            skipped_tasks += 1
            continue

        seen = existing_titles.setdefault(pid, set())
        if _norm(title) in seen:
            skipped_tasks += 1
            continue
        seen.add(_norm(title))

        assignee_name = str(r.get("assignee") or "").strip()
        assignee_id = usernames.get(_norm(assignee_name)) if assignee_name else None

        status, _ = _enum(r.get("status"), TASK_STATUS, "todo")
        priority, _ = _enum(r.get("priority"), PRIORITY, "medium")
        task_type, _ = _enum(r.get("task_type"), TASK_TYPE, "task")

        task_obj = Task(
            project_id=pid,
            title=title[:255],
            description=str(r.get("description") or "").strip() or None,
            task_type=task_type,
            status=status,
            priority=priority,
            creator_id=current_user.id,
            assignee_id=assignee_id,
            estimated_hours=_to_float(r.get("estimated_hours")) or 0.0,
            start_date=_to_date(r.get("start_date")),
            due_date=_to_date(r.get("due_date")),
            tags=str(r.get("tags") or "").strip() or None,
        )
        db.add(task_obj)
        task_objs.append(task_obj)
        created_tasks += 1

    # ── 里程碑 ────────────────────────────────────────────────────────
    existing_ms: Dict[int, set] = {}
    for pid in set(code_to_id.values()):
        existing_ms[pid] = {
            _norm(t[0]) for t in db.query(Milestone.title).filter(Milestone.project_id == pid).all()
        }

    created_milestones = 0
    skipped_milestones = 0
    milestone_objs: List[Milestone] = []
    order_counter: Dict[int, int] = {}
    for r in rows.get("milestone", []):
        code = str(r.get("project_code") or "").strip()
        title = str(r.get("title") or "").strip()
        due = _to_date(r.get("due_date"))
        pid = code_to_id.get(code)
        if not pid or not title or not due:
            skipped_milestones += 1
            continue

        seen = existing_ms.setdefault(pid, set())
        if _norm(title) in seen:
            skipped_milestones += 1
            continue
        seen.add(_norm(title))

        status, _ = _enum(r.get("status"), MILESTONE_STATUS, "pending")
        order_num = order_counter.get(pid, 0)
        order_counter[pid] = order_num + 1

        ms_obj = Milestone(
            project_id=pid,
            title=title[:128],
            description=str(r.get("description") or "").strip() or None,
            due_date=due,
            status=status,
            order_num=order_num,
        )
        db.add(ms_obj)
        milestone_objs.append(ms_obj)
        created_milestones += 1

    # ── 成员 ──────────────────────────────────────────────────────────
    existing_members: Dict[int, set] = {}
    for pid in set(code_to_id.values()):
        existing_members[pid] = {
            m[0] for m in db.query(ProjectMember.user_id).filter(ProjectMember.project_id == pid).all()
        }

    created_members = 0
    skipped_members = 0
    for r in rows.get("member", []):
        code = str(r.get("project_code") or "").strip()
        username = str(r.get("username") or "").strip()
        pid = code_to_id.get(code)
        uid = usernames.get(_norm(username))
        if not pid or not uid:
            skipped_members += 1
            continue

        seen = existing_members.setdefault(pid, set())
        if uid in seen:
            skipped_members += 1
            continue
        seen.add(uid)

        role, _ = _enum(r.get("project_role"), MEMBER_ROLE, "developer")
        mem_obj = ProjectMember(project_id=pid, user_id=uid, project_role=role)
        db.add(mem_obj)
        member_objs.append(mem_obj)
        created_members += 1

    db.flush()
    created_ids = {
        "project": created_project_ids,
        "task": [t.id for t in task_objs],
        "milestone": [m.id for m in milestone_objs],
        "member": [m.id for m in member_objs],
    }

    db.commit()
    return {
        "created_ids": created_ids,
        "projects_created": created_projects,
        "projects_skipped": skipped_projects,
        "tasks_created": created_tasks,
        "tasks_skipped": skipped_tasks,
        "milestones_created": created_milestones,
        "milestones_skipped": skipped_milestones,
        "members_created": created_members,
        "members_skipped": skipped_members,
    }


# ─── 导出 ────────────────────────────────────────────────────────────────────

def export_projects(db: Session, projects: List[Project]) -> bytes:
    """导出若干项目为一个工作簿：项目表每个项目一行，任务表汇总所有任务。

    表头与导入模板一致，导出的文件可以直接再导入（多项目也能一次导回）。
    """
    wb = Workbook()

    ws = wb.active
    ws.title = SHEET_PROJECT
    _style_sheet(
        ws,
        [f["label"] + ("*" if f["required"] else "") for f in PROJECT_FIELDS],
        [22, 16, 12, 10, 10, 12, 12, 12, 36],
        [],
    )
    for p in projects:
        ws.append([
            p.name,
            p.code,
            p.owner.username if p.owner else "",
            PROJECT_STATUS_LABEL.get(p.status, p.status),
            PRIORITY_LABEL.get(p.priority, p.priority),
            p.budget or 0,
            p.start_date.strftime("%Y-%m-%d") if p.start_date else "",
            p.end_date.strftime("%Y-%m-%d") if p.end_date else "",
            p.description or "",
        ])

    ws = wb.create_sheet(SHEET_TASK)
    _style_sheet(
        ws,
        [f["label"] + ("*" if f["required"] else "") for f in TASK_FIELDS],
        [16, 26, 12, 10, 10, 10, 12, 12, 12, 16, 36],
        [],
    )

    if projects:
        ids = [p.id for p in projects]
        code_by_id = {p.id: p.code for p in projects}
        tasks = (
            db.query(Task).filter(Task.project_id.in_(ids))
            .order_by(Task.project_id.asc(), Task.order_num.asc(), Task.id.asc()).all()
        )
        for t in tasks:
            ws.append([
                code_by_id.get(t.project_id, ""),
                t.title,
                t.assignee.username if t.assignee else "",
                TASK_STATUS_LABEL.get(t.status, t.status),
                PRIORITY_LABEL.get(t.priority, t.priority),
                TASK_TYPE_LABEL.get(t.task_type, t.task_type),
                t.estimated_hours or 0,
                t.start_date.strftime("%Y-%m-%d") if t.start_date else "",
                t.due_date.strftime("%Y-%m-%d") if t.due_date else "",
                t.tags or "",
                t.description or "",
            ])

    # ── 里程碑 ────────────────────────────────────────────────────────
    ws = wb.create_sheet(SHEET_MILESTONE)
    _style_sheet(
        ws,
        [f["label"] + ("*" if f["required"] else "") for f in MILESTONE_FIELDS],
        [16, 24, 14, 10, 36],
        [],
    )
    if projects:
        ms_list = (
            db.query(Milestone).filter(Milestone.project_id.in_(ids))
            .order_by(Milestone.project_id.asc(), Milestone.order_num.asc()).all()
        )
        for m in ms_list:
            ws.append([
                code_by_id.get(m.project_id, ""),
                m.title,
                m.due_date.strftime("%Y-%m-%d") if m.due_date else "",
                MILESTONE_STATUS_LABEL.get(m.status, m.status),
                m.description or "",
            ])

    # ── 成员 ──────────────────────────────────────────────────────────
    ws = wb.create_sheet(SHEET_MEMBER)
    _style_sheet(
        ws,
        [f["label"] + ("*" if f["required"] else "") for f in MEMBER_FIELDS],
        [16, 16, 16],
        [],
    )
    if projects:
        members = (
            db.query(ProjectMember).filter(ProjectMember.project_id.in_(ids))
            .order_by(ProjectMember.project_id.asc()).all()
        )
        for mem in members:
            ws.append([
                code_by_id.get(mem.project_id, ""),
                mem.user.username if mem.user else "",
                MEMBER_ROLE_LABEL.get(mem.project_role, mem.project_role),
            ])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_project(db: Session, project: Project) -> bytes:
    """导出单个项目（项目 1 行 + 其全部任务）。"""
    return export_projects(db, [project])


# ─── 回滚 ────────────────────────────────────────────────────────────────────

class RollbackConflict(Exception):
    """导入创建的项目在之后又有了新内容，整体回滚会误删，必须拒绝。"""


def rollback_import(db: Session, log) -> Dict[str, int]:
    """按导入批次精确回滚：只删本批次创建的记录。

    安全策略：如果本批次创建的项目里，出现了「本批次之外」的任务/里程碑/成员，
    说明用户已经在此基础上继续工作了，整体回滚会误删这些内容，直接拒绝。
    这种情况请手动删除具体记录。
    """
    raw = getattr(log, "created_ids", None)
    if not raw:
        raise ValueError("该批次没有记录创建明细，无法回滚（可能是升级前的历史数据）")

    ids = json.loads(raw)
    project_ids = [int(x) for x in ids.get("project", [])]
    task_ids = [int(x) for x in ids.get("task", [])]
    ms_ids = [int(x) for x in ids.get("milestone", [])]
    member_ids = [int(x) for x in ids.get("member", [])]

    if project_ids:
        checks = (
            ("任务", Task, Task.project_id, task_ids),
            ("里程碑", Milestone, Milestone.project_id, ms_ids),
            ("成员", ProjectMember, ProjectMember.project_id, member_ids),
        )
        for label, model, pid_col, allowed in checks:
            q = db.query(model.id).filter(pid_col.in_(project_ids))
            if allowed:
                q = q.filter(~model.id.in_(allowed))
            extra = q.first()
            if extra:
                raise RollbackConflict(
                    f"本次导入创建的项目中已有新的{label}记录，"
                    f"回滚会一并删除它们。请先手动清理，或只删除具体记录。"
                )

    deleted: Dict[str, int] = {}
    for key, model, id_list in (
        ("member", ProjectMember, member_ids),
        ("milestone", Milestone, ms_ids),
        ("task", Task, task_ids),
        ("project", Project, project_ids),
    ):
        if id_list:
            deleted[key] = db.query(model).filter(model.id.in_(id_list)).delete(
                synchronize_session=False
            )

    db.commit()
    return deleted
