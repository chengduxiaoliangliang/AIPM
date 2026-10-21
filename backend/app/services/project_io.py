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
import io
import re
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session

from app.models.project import Project, ProjectMember
from app.models.task import Task
from app.models.user import User

MAX_ROWS = 2000
MAX_BYTES = 8 * 1024 * 1024

SHEET_PROJECT = "项目"
SHEET_TASK = "任务"
SHEET_HELP = "填写说明"

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
    """生成导入模板（含示例行与填写说明）。"""
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

    help_ws = wb.create_sheet(SHEET_HELP)
    help_ws.column_dimensions["A"].width = 18
    help_ws.column_dimensions["B"].width = 12
    help_ws.column_dimensions["C"].width = 62

    rows = [("字段", "是否必填", "说明 / 可选值")]
    for f in PROJECT_FIELDS:
        hint = _field_hint(f["key"], "project")
        rows.append((f["label"], "必填" if f["required"] else "选填", hint))
    rows.append(("", "", ""))
    for f in TASK_FIELDS:
        hint = _field_hint(f["key"], "task")
        rows.append((f["label"], "必填" if f["required"] else "选填", hint))
    rows.append(("", "", ""))
    rows.append(("使用说明", "", "1. 列名可以改、顺序可以调，导入时会自动识别并允许手动映射"))
    rows.append(("", "", "2. 任务通过「项目编号」关联到项目，编号需与项目表一致"))
    rows.append(("", "", "3. 负责人填用户名或昵称；留空则默认为当前登录用户"))
    rows.append(("", "", "4. 日期支持 2026-03-01 / 2026/3/1 / Excel 日期格式"))
    rows.append(("", "", "5. 示例行请删除后再导入；单次最多 2000 行"))

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
    ("project_start", ["项目开始日期", "开始日期"]),
    ("project_end", ["项目结束日期", "结束日期"]),
    ("task_title", ["任务标题", "任务名称", "标题", "task"]),
    ("task_status", ["任务状态", "task status"]),
    ("task_priority", ["任务优先级", "task priority"]),
    ("task_type", ["任务类型", "类型细分", "task type"]),
    ("task_estimate", ["预估工时", "工时", "estimate"]),
    ("task_start", ["任务开始日期"]),
    ("task_due", ["任务截止日期", "截止日期", "due"]),
    ("owner", ["负责人", "指派人", "owner", "assignee"]),
    ("tags", ["标签", "tags"]),
    ("description", ["描述", "说明", "description"]),
]

CSV_HEADERS = [
    "类型", "项目编号", "项目名称", "项目状态", "项目优先级", "预算",
    "项目开始日期", "项目结束日期", "任务标题", "任务状态", "任务优先级",
    "任务类型", "预估工时", "任务开始日期", "任务截止日期",
    "负责人", "标签", "描述",
]

CSV_SAMPLES = [
    ["项目", "DEMO-2026", "示例：客户门户重构", "进行中", "高", 120000,
     "2026-03-01", "2026-06-30", "", "", "", "", "", "", "", "admin", "", "示例项目行，导入前请删除"],
    ["任务", "DEMO-2026", "", "", "", "",
     "", "", "示例：登录页改版", "进行中", "高",
     "需求", 16, "2026-03-01", "2026-03-15", "zhangsan", "前端,UI", "示例任务行，导入前请删除"],
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


def _parse_csv(raw: bytes) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """把单表 CSV 拆成 项目行 / 任务行，结构与 xlsx 解析结果保持一致。"""
    text = _decode_text(raw)
    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip() for h in (reader.fieldnames or [])]
    if not headers:
        raise ValueError("CSV 文件没有表头")

    # 表头 → 内部列 key
    alias: Dict[str, str] = {}
    for key, names in CSV_COLUMNS:
        for n in names:
            alias[_norm(n)] = key

    col_of: Dict[str, str] = {}
    for h in headers:
        key = alias.get(_norm(h))
        if key and key not in col_of:
            col_of[key] = h

    if "record_type" not in col_of:
        # 没有类型列时按任务处理，但要求有任务标题
        if "task_title" not in col_of:
            raise ValueError("CSV 缺少「类型」列，且找不到「任务标题」列")

    proj_rows: List[Dict[str, Any]] = []
    task_rows: List[Dict[str, Any]] = []

    for idx, raw_row in enumerate(reader, start=2):
        row = {(k or "").strip(): (v or "").strip() for k, v in raw_row.items() if k}
        if not any(row.values()):
            continue

        kind = row.get(col_of.get("record_type", ""), "").strip().lower()
        is_project = kind in ("项目", "project", "p")

        if is_project:
            proj_rows.append({
                "_row": idx,
                "code": row.get(col_of.get("project_code", ""), ""),
                "name": row.get(col_of.get("project_name", ""), ""),
                "owner": row.get(col_of.get("owner", ""), ""),
                "status": row.get(col_of.get("project_status", ""), ""),
                "priority": row.get(col_of.get("project_priority", ""), ""),
                "budget": row.get(col_of.get("project_budget", ""), ""),
                "start_date": row.get(col_of.get("project_start", ""), ""),
                "end_date": row.get(col_of.get("project_end", ""), ""),
                "description": row.get(col_of.get("description", ""), ""),
            })
        else:
            task_rows.append({
                "_row": idx,
                "project_code": row.get(col_of.get("project_code", ""), ""),
                "title": row.get(col_of.get("task_title", ""), ""),
                "assignee": row.get(col_of.get("owner", ""), ""),
                "status": row.get(col_of.get("task_status", ""), ""),
                "priority": row.get(col_of.get("task_priority", ""), ""),
                "task_type": row.get(col_of.get("task_type", ""), ""),
                "estimated_hours": row.get(col_of.get("task_estimate", ""), ""),
                "start_date": row.get(col_of.get("task_start", ""), ""),
                "due_date": row.get(col_of.get("task_due", ""), ""),
                "tags": row.get(col_of.get("tags", ""), ""),
                "description": row.get(col_of.get("description", ""), ""),
            })

    # CSV 是一张表，但校验按「项目表 / 任务表」两套字段分别做，
    # 所以映射也要按两套字段 key 输出，否则必填列检查会失效。
    PROJ_KEY = {
        "project_name": "name", "project_code": "code", "owner": "owner",
        "project_status": "status", "project_priority": "priority",
        "project_budget": "budget", "project_start": "start_date",
        "project_end": "end_date", "description": "description",
    }
    TASK_KEY = {
        "project_code": "project_code", "task_title": "title", "owner": "assignee",
        "task_status": "status", "task_priority": "priority",
        "task_type": "task_type", "task_estimate": "estimated_hours",
        "task_start": "start_date", "task_due": "due_date",
        "tags": "tags", "description": "description",
    }

    def build_meta(key_map):
        mapping = {}
        for i, h in enumerate(headers):
            internal = alias.get(_norm(h))
            if internal and internal in key_map and key_map[internal] not in mapping.values():
                mapping[str(i)] = key_map[internal]
        return {"headers": headers, "mapping": mapping, "header_row": 1}

    return proj_rows, task_rows, build_meta(PROJ_KEY), build_meta(TASK_KEY)


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
    """解析上传文件，返回 sheet 内容、列映射与校验问题（不写库）。

    返回里的 `rows` 是完整解析结果，供 execute 使用；对外接口会把它剔除。
    """
    if len(file_bytes) > MAX_BYTES:
        raise ValueError(f"文件过大，最大 {MAX_BYTES // 1024 // 1024}MB")

    name = (filename or "").lower()

    if name.endswith(".csv"):
        proj_rows, task_rows, proj_meta, task_meta = _parse_csv(file_bytes)
        if len(proj_rows) > MAX_ROWS or len(task_rows) > MAX_ROWS:
            raise ValueError(f"单次导入最多 {MAX_ROWS} 行")
        return _build_result(proj_rows, task_rows, proj_meta, task_meta, "csv")

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

    proj_ws = pick([SHEET_PROJECT, "项目信息", "Projects"])
    task_ws = pick([SHEET_TASK, "任务列表", "Tasks"])
    if proj_ws is None and task_ws is None:
        raise ValueError(f"未找到「{SHEET_PROJECT}」或「{SHEET_TASK}」工作表，请使用下载的模板")

    mapping = mapping or {}
    proj_rows, proj_meta = (
        _read_sheet(proj_ws, PROJECT_FIELDS, mapping.get("project"))
        if proj_ws else ([], {"headers": [], "mapping": {}, "header_row": 0})
    )
    task_rows, task_meta = (
        _read_sheet(task_ws, TASK_FIELDS, mapping.get("task"))
        if task_ws else ([], {"headers": [], "mapping": {}, "header_row": 0})
    )

    if len(proj_rows) > MAX_ROWS or len(task_rows) > MAX_ROWS:
        raise ValueError(f"单次导入最多 {MAX_ROWS} 行")

    return _build_result(proj_rows, task_rows, proj_meta, task_meta, "xlsx")


def _build_result(
    proj_rows: List[Dict[str, Any]],
    task_rows: List[Dict[str, Any]],
    proj_meta: Dict[str, Any],
    task_meta: Dict[str, Any],
    fmt: str,
) -> Dict[str, Any]:
    """把解析结果整理成对外结构（含必填列检查）。"""
    issues: List[Dict[str, Any]] = []

    # 必填列是否被识别
    for kind, meta, fields, label in (
        ("project", proj_meta, PROJECT_FIELDS, SHEET_PROJECT),
        ("task", task_meta, TASK_FIELDS, SHEET_TASK),
    ):
        mapped = set(meta["mapping"].values())
        for f in fields:
            if f["required"] and f["key"] not in mapped:
                issues.append({
                    "level": "error", "sheet": label, "row": meta["header_row"],
                    "field": f["label"],
                    "message": f"未找到「{f['label']}」列，请在文件中保留该列或调整映射",
                })

    return {
        "format": fmt,
        "sheets": {
            "project": {"rows": proj_rows[:5], "total": len(proj_rows), **proj_meta},
            "task": {"rows": task_rows[:5], "total": len(task_rows), **task_meta},
        },
        "fields": {"project": PROJECT_FIELDS, "task": TASK_FIELDS},
        "issues": issues,
        "rows": {"project": proj_rows, "task": task_rows},
    }


def validate_rows(
    db: Session,
    proj_rows: List[Dict[str, Any]],
    task_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """校验数据行，返回问题列表（error 阻断导入，warning 仅提示）。"""
    issues: List[Dict[str, Any]] = []

    def add(level: str, sheet: str, row: int, message: str):
        issues.append({"level": level, "sheet": sheet, "row": row, "message": message})

    existing_codes = {c[0] for c in db.query(Project.code).all()}
    usernames = {}
    for uid, username, nickname in db.query(User.id, User.username, User.nickname).all():
        usernames[_norm(username)] = uid
        if nickname:
            usernames.setdefault(_norm(nickname), uid)

    seen_codes = set()
    valid_projects = 0

    for r in proj_rows:
        row = r["_row"]
        name = str(r.get("name") or "").strip()
        code = str(r.get("code") or "").strip()
        if not name:
            add("error", SHEET_PROJECT, row, "项目名称不能为空")
        if not code:
            add("error", SHEET_PROJECT, row, "项目编号不能为空")
        elif _norm(code) in seen_codes:
            add("error", SHEET_PROJECT, row, f"项目编号「{code}」在文件中重复")
        elif code in existing_codes:
            add("warning", SHEET_PROJECT, row, f"项目编号「{code}」已存在，导入时将跳过该项目及其任务")
        else:
            seen_codes.add(_norm(code))
            valid_projects += 1

        owner = str(r.get("owner") or "").strip()
        if owner and _norm(owner) not in usernames:
            add("warning", SHEET_PROJECT, row, f"负责人「{owner}」不存在，将使用当前登录用户")

        for key in ("status", "priority"):
            if str(r.get(key) or "").strip():
                table = PROJECT_STATUS if key == "status" else PRIORITY
                _, ok = _enum(r.get(key), table, "")
                if not ok:
                    add("warning", SHEET_PROJECT, row, f"「{r.get(key)}」不是有效的{'状态' if key == 'status' else '优先级'}，将使用默认值")

        for key in ("start_date", "end_date"):
            if str(r.get(key) or "").strip() and _to_date(r.get(key)) is None:
                add("error", SHEET_PROJECT, row, f"{'开始' if key == 'start_date' else '结束'}日期格式无法识别")

        s, e = _to_date(r.get("start_date")), _to_date(r.get("end_date"))
        if s and e and e < s:
            add("error", SHEET_PROJECT, row, "结束日期早于开始日期")

    # 任务：项目编号必须在文件或库中存在
    for r in task_rows:
        row = r["_row"]
        code = str(r.get("project_code") or "").strip()
        title = str(r.get("title") or "").strip()
        if not title:
            add("error", SHEET_TASK, row, "任务标题不能为空")
        if not code:
            add("error", SHEET_TASK, row, "项目编号不能为空")
        elif _norm(code) not in seen_codes and code not in existing_codes:
            add("error", SHEET_TASK, row, f"项目编号「{code}」在「项目」表中不存在")

        assignee = str(r.get("assignee") or "").strip()
        if assignee and _norm(assignee) not in usernames:
            add("warning", SHEET_TASK, row, f"负责人「{assignee}」不存在，该任务将不指派")

        for key, table, label in (
            ("status", TASK_STATUS, "状态"),
            ("priority", PRIORITY, "优先级"),
            ("task_type", TASK_TYPE, "类型"),
        ):
            if str(r.get(key) or "").strip():
                _, ok = _enum(r.get(key), table, "")
                if not ok:
                    add("warning", SHEET_TASK, row, f"「{r.get(key)}」不是有效的{label}，将使用默认值")

        for key in ("start_date", "due_date"):
            if str(r.get(key) or "").strip() and _to_date(r.get(key)) is None:
                add("error", SHEET_TASK, row, "日期格式无法识别")

    return issues


# ─── 导入执行 ────────────────────────────────────────────────────────────────

def execute_import(
    db: Session,
    proj_rows: List[Dict[str, Any]],
    task_rows: List[Dict[str, Any]],
    current_user: User,
) -> Dict[str, Any]:
    """写入数据库。已存在的项目编号跳过（连同其任务）。"""
    usernames: Dict[str, int] = {}
    for uid, username, nickname in db.query(User.id, User.username, User.nickname).all():
        usernames[_norm(username)] = uid
        if nickname:
            usernames.setdefault(_norm(nickname), uid)

    existing = {c[0]: c[0] for c in db.query(Project.code).all()}
    created_projects = 0
    skipped_projects = 0
    code_to_id: Dict[str, int] = {}

    for r in proj_rows:
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
        db.add(ProjectMember(project_id=project.id, user_id=owner_id, project_role="pm"))
        code_to_id[code] = project.id
        existing[code] = code
        created_projects += 1

    # 已存在的项目也允许追加任务
    for code in {str(r.get("project_code") or "").strip() for r in task_rows}:
        if code and code not in code_to_id:
            row = db.query(Project.id).filter(Project.code == code).first()
            if row:
                code_to_id[code] = row[0]

    # 已存在的任务标题（按项目）：让「导出 → 再导入」保持幂等，
    # 同时仍允许向已有项目补充新任务。
    existing_titles: Dict[int, set] = {}
    for pid in set(code_to_id.values()):
        existing_titles[pid] = {
            _norm(t[0]) for t in db.query(Task.title).filter(Task.project_id == pid).all()
        }

    created_tasks = 0
    skipped_tasks = 0
    for r in task_rows:
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

        db.add(Task(
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
        ))
        created_tasks += 1

    db.commit()
    return {
        "projects_created": created_projects,
        "projects_skipped": skipped_projects,
        "tasks_created": created_tasks,
        "tasks_skipped": skipped_tasks,
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

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_project(db: Session, project: Project) -> bytes:
    """导出单个项目（项目 1 行 + 其全部任务）。"""
    return export_projects(db, [project])
