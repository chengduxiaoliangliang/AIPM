# AIPM 部署说明

## 架构

```
                 ┌──────────────┐
   80/tcp ──────▶│   frontend   │  nginx:1.27-alpine
                 │  (Vue3 dist) │
                 └──────┬───────┘
                        │ /api/ → http://backend:8000
                 ┌──────▼───────┐
                 │   backend    │  python:3.11-slim + uvicorn ×2
                 └──┬────────┬──┘
                    │        │
        ┌───────────▼──┐  ┌──▼──────────┐
        │    mysql     │  │    redis    │
        │  mysql:8.0   │  │ redis:7     │
        └──────────────┘  └─────────────┘
```

全部服务位于 `aipm-net` 自定义桥接网络，仅 `frontend` 对外暴露 80 端口，
MySQL / Redis / backend 均不直接暴露到公网。

## 前置条件

- Docker 20.10+ 与 Docker Compose v2
- 至少 2 GB 可用内存、10 GB 磁盘

## 首次部署

```bash
# 1. 准备环境变量
cp .env.example .env
vi .env                     # 填入 SECRET_KEY / 数据库密码 / DeepSeek Key

# 2. 构建并启动
docker compose up -d --build

# 3. 查看状态
docker compose ps
docker compose logs -f backend
```

首次启动时 backend 入口脚本会等待 MySQL 就绪，然后自动建表并写入种子数据
（幂等：数据库已有用户时会跳过，不会覆盖线上数据）。

访问 `http://<服务器IP>/`。

## 常用运维命令

| 操作 | 命令 |
|---|---|
| 查看日志 | `docker compose logs -f backend` |
| 重启服务 | `docker compose restart backend` |
| 更新代码后重建 | `docker compose up -d --build` |
| 停止 | `docker compose down` |
| 停止并清空数据 | `docker compose down -v` ⚠️ 会删除数据库 |
| 重置种子数据 | `docker compose exec backend python -m app.init_db --force` ⚠️ 会清空业务表 |

## 数据持久化

| 卷 | 内容 |
|---|---|
| `aipm_mysql_data` | MySQL 数据文件 |
| `aipm_redis_data` | Redis AOF |
| `aipm_kb_data` | 知识库上传的原始文件（挂载到 `/app/data`） |

备份 MySQL：

```bash
docker compose exec mysql sh -c \
  'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction aipm_db' \
  > backup-$(date +%F).sql
```

## 知识库（LLM Wiki）

知识库采用 **LLM Wiki** 模式而非 RAG：上传的资料会被解析为全文，再由大模型增量整合进一个持久化的 Markdown 维基，
页面之间通过 `[[双链]]` 关联，并自动维护 `index.md`（目录）与 `log.md`（变更日志）。

- **摄入流程**：上传 → 抽取正文 → 大模型分析 → 创建/更新页面 → 重建双链与索引 → 记录日志
- **体检**：确定性规则（孤岛页、断链、空页、未摄入资料）+ 大模型检查（矛盾、过时、缺失概念）→ 健康分
- **导出**：整库打包为 zip，按页面类型分目录，带 YAML frontmatter，可直接用 Obsidian 打开
- **并发**：同一项目的摄入通过 Redis 锁串行化，避免多个任务争抢同一批页面

相关配置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `KB_STORAGE_DIR` | `data/kb` | 上传文件落盘目录（相对路径基于 backend 目录） |
| `KB_MAX_UPLOAD_MB` | `25` | 单个文件大小上限 |
| `KB_INGEST_WORKERS` | `2` | 摄入队列消费者数量 |
| `KB_LINT_INTERVAL_HOURS` | `24` | 自动体检周期，`0` 关闭 |
| `SMTP_HOST` 等 | 空 | 邮件通知；不填则静默跳过 |
| `KB_NOTIFY_LINT_SCORE_BELOW` | `70` | 健康分低于该值时邮件告警 |

**摄入队列**：任务写入 Redis 列表，由 `KB_INGEST_WORKERS` 个消费者处理。
API 重启时会把未完成的 queued/running 任务重新入队（运行未超过 10 分钟的不动，
避免滚动重启时抢走正在跑的任务）。任务通过 `UPDATE ... WHERE status='queued'`
原子抢占，重复入队不会导致重复处理。

支持格式：PDF、Word(.docx)、Excel(.xlsx)、Markdown、TXT、CSV、JSON、HTML、常见代码文件。

## 默认账号
种子数据内置 5 个账号，密码统一为 `123456`（首次登录后请立即修改）：

| 用户名 | 角色 |
|---|---|
| admin | 超级管理员 |
| zhangsan | 研发工程师 |
| lisi | 项目经理 |
| wangwu | 测试工程师 |
| zhaoliu | 研发工程师 |

## 注意事项

- `.env` 含明文密钥，权限应为 `600`，且不得提交到版本库。
- 修改 `.env` 后需 `docker compose up -d` 让容器重新读取环境变量。
- AI 相关配置也可在「系统管理 → AI 管理」页面在线修改，覆盖项存于 Redis，
  优先级高于 `.env`；点击「恢复默认」可清除。
- nginx 已为 `/api/v1/ai/chat/stream` 关闭代理缓冲，保证 SSE 流式输出不被截断。
