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

备份 MySQL：

```bash
docker compose exec mysql sh -c \
  'exec mysqldump -uroot -p"$MYSQL_ROOT_PASSWORD" --single-transaction aipm_db' \
  > backup-$(date +%F).sql
```

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
