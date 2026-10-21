# AIPM · 智能项目管理系统

> 一个把 **大模型真正嵌进项目管理流程** 的系统：AI 助手能按权限查询真实业务数据，
> 项目知识库用 **LLM Wiki** 模式持续沉淀，而不是每次提问都从零检索。

<p>
  <img alt="backend" src="https://img.shields.io/badge/backend-FastAPI-009688">
  <img alt="frontend" src="https://img.shields.io/badge/frontend-Vue%203-42b883">
  <img alt="db" src="https://img.shields.io/badge/database-MySQL%208-4479A1">
  <img alt="cache" src="https://img.shields.io/badge/cache-Redis%207-DC382D">
  <img alt="llm" src="https://img.shields.io/badge/LLM-DeepSeek-4B6BFB">
  <img alt="deploy" src="https://img.shields.io/badge/deploy-Docker%20Compose-2496ED">
</p>

---

## 目录

- [核心特性](#核心特性)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [本地开发](#本地开发)
- [知识库：为什么不是 RAG](#知识库为什么不是-rag)
- [AI 助手](#ai-助手)
- [权限模型](#权限模型)
- [目录结构](#目录结构)
- [配置项](#配置项)
- [常见问题](#常见问题)

---

## 核心特性

### 项目管理
- **项目 / 任务 / 工时 / 缺陷** 全链路管理，支持看板、甘特图、迭代视图
- **工时审批流**：工程师填报 → 项目经理按周批量审批 → 驳回重提
- **数据看板**：项目进度、预算消耗、人力投入、缺陷趋势

### AI 能力
- **流式对话**（SSE），逐字输出不卡顿
- **RBAC 权限隔离**：AI 调用工具时继承调用者权限，绝不可能越权查到别人的项目
- **多会话管理**：上下文存 Redis，支持多轮追问与历史回溯
- **运行时热配置**：模型、Key、温度等参数在管理后台改完即生效，无需重启

### 知识库（LLM Wiki）
- 上传 **PDF / Word / Excel / Markdown / TXT / 代码** 自动抽取全文
- 大模型把资料**增量整合**进一个持久化的 Markdown 维基，页面之间自动建立 `[[双链]]`
- 自动维护 `index.md`（目录）与 `log.md`（变更日志）
- **知识体检**：规则检查 + 大模型检查，输出健康分与问题清单
- 按项目查看知识结构，支持整库导出 zip（可直接用 Obsidian 打开）

### 工程化
- Docker Compose 一键部署，四服务编排
- 密码 bcrypt 哈希，兼容旧 SHA256 并自动升级
- 多页签多账号隔离（凭据存 sessionStorage）
- 前端按需分包，nginx 长缓存 + gzip + SSE 专用代理

---

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3 · Vite 5 · TypeScript · Element Plus · Pinia · ECharts · Three.js |
| 后端 | FastAPI · SQLAlchemy 2.0 · Pydantic v2 · Uvicorn |
| AI | LangChain · DeepSeek · SSE 流式输出 |
| 存储 | MySQL 8（业务数据）· Redis 7（会话/缓存/分布式锁） |
| 部署 | Docker Compose · nginx |

---

## 系统架构

```
                         ┌──────────────────────┐
        80/tcp  ────────▶│      frontend        │  nginx + Vue 3 dist
                         │  静态资源 / 反向代理   │
                         └──────────┬───────────┘
                                    │ /api/  →  http://backend:8000
                         ┌──────────▼───────────┐
                         │      backend         │  FastAPI + uvicorn ×2
                         │  ┌────────────────┐  │
                         │  │  AI Agent      │──┼──▶ DeepSeek API
                         │  │  RBAC 工具隔离  │  │
                         │  ├────────────────┤  │
                         │  │  KB Engine     │  │  抽取 → 摄入 → 体检
                         │  └────────────────┘  │
                         └───┬──────────────┬───┘
                             │              │
                 ┌───────────▼──┐    ┌──────▼────────┐
                 │    mysql     │    │     redis     │
                 │  业务数据     │    │ 会话/锁/缓存   │
                 └──────────────┘    └───────────────┘

  仅 frontend 暴露 80 端口，其余服务位于内部网络 aipm-net
```

---

## 快速开始

### 前置条件
- Docker 20.10+ 与 Docker Compose v2
- 至少 2 GB 可用内存、10 GB 磁盘

### 启动

```bash
git clone https://github.com/chengduxiaoliangliang/AIPM.git
cd AIPM

cp .env.example .env
# 编辑 .env，至少填写 SECRET_KEY、MYSQL_PASSWORD、DEEPSEEK_API_KEY

docker compose up -d --build
docker compose ps          # 等待四个服务都变成 healthy
```

浏览器打开 `http://<服务器IP>/`。

首次启动会自动建表并写入演示数据（幂等：已有用户则跳过，不会覆盖线上数据）。

### 默认账号

| 用户名 | 角色 | 密码 |
|---|---|---|
| `admin` | 超级管理员 | `123456` |
| `lisi` | 项目经理 | `123456` |
| `zhangsan` / `zhaoliu` | 研发工程师 | `123456` |
| `wangwu` | 测试工程师 | `123456` |

> ⚠️ 上线前请立即修改默认密码。

---

## 本地开发

```bash
# 后端（需要本机有 MySQL 与 Redis）
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.init_db          # 建表 + 种子数据
uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
pnpm install
pnpm dev                       # http://localhost:5173，已配置 /api 代理
```

---

## 项目导入 / 导出

支持用模板批量导入项目与任务，也可以把项目导出成同样的格式再导回。

**模板是"可自定义"的**：列名可以改、顺序可以调、多余的列会被忽略。
导入时按别名自动识别，识别不出来还能在界面上手动指定列映射。

两种格式：

| 格式 | 结构 | 适用场景 |
|---|---|---|
| Excel (.xlsx) | 「项目」「任务」两个工作表 + 填写说明 | 首次建库、批量录入 |
| CSV (.csv) | 单表，用「类型」列区分项目行 / 任务行 | 从其他系统导出后直接改 |

导入分三步，**解析与校验不写库**：

```
下载模板 → 上传预览（列映射 + 校验问题 + 样例） → 确认导入
```

幂等规则：项目编号已存在则跳过该项目，同项目内同名任务跳过。
所以导出文件可以安全地再导入一次，不会产生重复数据。

导出支持单项目、多选、以及全部项目，导出的文件与模板同构，可直接再导入。

> CSV 使用 UTF-8 BOM，Excel 打开中文不会乱码；也兼容 GBK 编码的旧文件。

---

## 测试与验收

知识库是系统里链路最长、最容易"结果对但行为错"的模块，因此配了四个可重复执行的检查脚本
（零额外依赖，全部在容器内运行）：

```bash
# 权限矩阵：24 项断言
docker exec aipm-backend python scripts/kb_permission_check.py \
  --base-url http://127.0.0.1:8000/api/v1

# 流式行为：3 个端点 × 5 项断言
docker exec aipm-backend python scripts/kb_stream_check.py \
  --base-url http://127.0.0.1:8000/api/v1

# 端到端验收：22 步
docker exec aipm-backend python scripts/kb_acceptance.py \
  --base-url http://127.0.0.1:8000/api/v1

# 性能基线：建立基线
docker exec aipm-backend python scripts/kb_benchmark.py \
  --base-url http://127.0.0.1:8000/api/v1 --save /app/data/perf-baseline.json

# 之后与基线对比（不会覆盖基线）
docker exec aipm-backend python scripts/kb_benchmark.py \
  --base-url http://127.0.0.1:8000/api/v1 --baseline /app/data/perf-baseline.json
```

| 脚本 | 关注点 | 说明 |
|---|---|---|
| `kb_permission_check.py` | 权限矩阵 | 三种可见范围 × 四类角色，结构树与详情接口双重断言 |
| `kb_stream_check.py` | 流式真实性 | **靠计时判断**：首 token 必须明显早于结束 |
| `kb_acceptance.py` | 全链路 | 上传→摄入→浏览→双链→版本→权限→问答→体检→导出 |
| `kb_benchmark.py` | 性能趋势 | 记录各接口耗时，与基线对比并标记回归 |

### 验收清单（22 步）

| # | 检查项 | # | 检查项 |
|---|---|---|---|
| 01 | 服务健康检查 | 12 | 社区发现 |
| 02 | 知识库项目列表 | 13 | 版本快照 |
| 03 | 上传资料 | 14 | 编辑产生新版本 |
| 04 | 文本抽取 | 15 | 版本回滚 |
| 05 | 摄入入队 | 16 | 页面级权限生效 |
| 06 | 摄入完成 | 17 | 知识库问答 |
| 07 | 生成知识页面 | 18 | 问答引用来源 |
| 08 | 自动生成索引页 | 19 | 流式输出 |
| 09 | 自动生成变更日志 | 20 | 知识库体检 |
| 10 | 页面正文非空 | 21 | 整库导出 |
| 11 | 双链解析 | 22 | 摄入队列状态 |

每步输出 PASS / FAIL / SKIP，退出码可直接接入 CI。脚本会记录基线页面集合，
**只清理本次新增的数据**，不会误删已有知识库。

> **为什么流式要单独测？**
> 如果 LLM 客户端被错误地以 `streaming=False` 复用，接口仍会正常返回内容，
> 只是把整段一次性吐出。结果层面完全正确，只有测量「首 token 时间 vs 总耗时」
> 才能发现。这个 Bug 真实发生过一次。

---

## 知识库：为什么不是 RAG

传统 RAG 的流程是「提问 → 检索相关片段 → 拼进提示词 → 生成答案」。
问题在于：**每次提问，模型都在从零重新理解你的资料**。跨五份文档的综合性问题，每次都要重新拼。

本项目采用 **LLM Wiki** 模式：

```
上传资料 ──▶ 抽取全文 ──▶ 大模型分析 ──▶ 创建/更新 wiki 页面
                                              │
                                    ┌─────────┴─────────┐
                                    ▼                   ▼
                              重建 [[双链]]        更新 index.md
                                    │                   │
                                    └─────────┬─────────┘
                                              ▼
                                        追加 log.md
```

**关键差异**：知识被**编译一次，之后持续维护**。新资料进来时，模型不是"再索引一份"，
而是把它**合并进已有的页面**——修订主题总结、补充实体信息、标注与旧结论的冲突。

实测效果：上传第二份文档时，系统没有新建重复页面，而是更新了已有的「RBAC 三级权限模型」页，
把工时场景的权限约束合并了进去。

### 三层结构

| 层 | 表 | 说明 |
|---|---|---|
| 原始资料 | `pm_kb_sources` | 上传的文件 + 抽取的全文，**只读不改** |
| 维基 | `pm_kb_pages` | 大模型维护的 Markdown 页面 |
| 双链 | `pm_kb_links` | 解析 `[[标题]]` 生成的反向引用 |

### 页面类型

`overview` 综述 · `topic` 主题 · `entity` 实体 · `comparison` 对比 · `decision` 决策 · `source` 资料摘要

### 体检（Lint）

| 类型 | 检查方式 |
|---|---|
| 孤岛页、断链、内容过薄、未摄入资料、解析失败、缺综述 | 确定性规则 |
| 页面矛盾、结论过时、缺失概念、信息缺口 | 大模型通读 |

输出 0-100 健康分 + 分级问题清单，每次结果落库并记入 `log.md`。

---

## AI 助手

```
用户提问
   │
   ├─▶ 意图识别（关键词路由）
   │      ├─ 日期时间  → 服务器权威时间
   │      ├─ 项目/任务/工时/缺陷 → RBAC 过滤后的真实数据
   │      └─ 创建任务 → 写操作（校验权限）
   │
   ├─▶ 组装系统提示词（角色 + 权限边界 + 当前时间 + 工具结果）
   │
   └─▶ DeepSeek 流式生成 ──▶ SSE 逐字推送前端
```

- **权限继承**：工具查询时按 `get_user_accessible_project_ids()` 过滤，模型拿不到越权数据
- **降级兜底**：大模型不可用时自动切换本地规则引擎，不白屏
- **时间感知**：系统提示词注入服务器当前时间，解决"今天是几号"这类问题

---

## 权限模型

```
用户 ──(多对多)── 角色 ──(多对多)── 权限
  │
  └── 部门（树形）
```

- 内置角色：`ADMIN` 超级管理员 · `PM` 项目经理 · `DEV` 研发工程师 · `QA` 测试工程师
- 数据范围：普通成员只能看到自己参与的项目；`PM` / `ADMIN` 可见全部
- 鉴权：JWT（`Authorization: Bearer`），登出时 token 进入 Redis 黑名单

---

## 目录结构

```
AIPM/
├── backend/
│   ├── app/
│   │   ├── ai/                 # Agent、工具、LLM 工厂、会话管理
│   │   ├── api/v1/             # 13 个路由模块（含 kb.py）
│   │   ├── core/               # 安全、验证码、异常
│   │   ├── models/             # SQLAlchemy 模型（含 kb.py 五张表）
│   │   ├── schemas/            # Pydantic 模型
│   │   ├── services/           # kb_extract（抽取）、kb_wiki（Wiki 引擎）
│   │   ├── config.py           # 全部配置走环境变量
│   │   ├── init_db.py          # 建表 + 幂等种子数据
│   │   └── main.py
│   ├── Dockerfile
│   ├── docker-entrypoint.sh    # 等待 MySQL → 初始化 → 启动
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/                # axios 封装（含 kb.ts）
│   │   ├── components/         # 含 3D AI 精灵
│   │   ├── views/              # 页面（document/ 即知识库）
│   │   ├── utils/auth.ts       # 凭据按页签隔离
│   │   └── router/ store/
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml
├── DEPLOY.md                   # 部署与运维手册
└── .env.example
```

---

## 配置项

全部通过环境变量注入，详见 `.env.example`。关键项：

| 变量 | 说明 |
|---|---|
| `SECRET_KEY` | JWT 签名密钥，**生产环境必填**，长度 ≥16 |
| `MYSQL_*` / `REDIS_*` | 数据库与缓存连接信息 |
| `DEEPSEEK_API_KEY` | 大模型密钥（也可在管理后台配置） |
| `DEEPSEEK_MODEL` | 模型名，如 `deepseek-v4-flash` |
| `APP_TIMEZONE` | 告知模型的时区，默认 `Asia/Shanghai` |
| `KB_STORAGE_DIR` | 知识库上传目录，默认 `data/kb` |
| `KB_MAX_UPLOAD_MB` | 单文件大小上限，默认 25 |

> 生产环境若使用默认 `SECRET_KEY`，应用会**拒绝启动**。

---

## 常见问题

**Q：新开浏览器页签要重新登录？**
A：这是刻意设计。凭据存在 `sessionStorage`（按页签隔离），支持同一浏览器同时登录多个账号互不干扰。若存在 `localStorage` 会被所有页签共享，导致后登录的账号覆盖前一个。

**Q：上传的 PDF 解析不出文字？**
A：扫描版 PDF 没有文本层，需要 OCR。系统会在资料列表中标记「解析失败」并给出原因。

**Q：AI 回答"我无法获取实时时间"？**
A：已修复——系统提示词会注入服务器当前时间。若仍出现，检查 `APP_TIMEZONE` 是否正确。

**Q：知识库摄入很慢？**
A：每份资料都要经过一次大模型分析（10-30 秒）。多个文件会**排队串行**处理（Redis 项目级锁），避免并发写坏同一批页面。

---

## License

MIT
