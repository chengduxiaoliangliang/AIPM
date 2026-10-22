import sys
import os

# Ensure backend root is in pythonpath
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from datetime import datetime, date, timedelta
from sqlalchemy import create_engine
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.models import (
    ImportLog,
    ImportPreset,
    Department, Role, Permission, User,
    Project, ProjectMember, Milestone,
    Task, SubTask, TaskComment,
    WorkLog, Issue, Document, AuditLog
)
from app.core.security import get_password_hash

def create_database_if_not_exists():
    """Create the target MySQL database if it doesn't exist yet.

    In containerised setups the database is created by the MySQL image and the
    application user may not hold CREATE privileges, so failures here are
    non-fatal: we only warn and let the caller proceed.
    """
    print(f"Connecting to MySQL server at {settings.MYSQL_HOST}:{settings.MYSQL_PORT}...")
    try:
        connection = pymysql.connect(
            host=settings.MYSQL_HOST,
            port=settings.MYSQL_PORT,
            user=settings.MYSQL_USER,
            password=settings.MYSQL_PASSWORD,
            charset="utf8mb4",
            connect_timeout=10,
        )
    except Exception as e:
        print(f"WARNING: cannot connect to MySQL server ({e}); assuming `{settings.MYSQL_DB}` already exists.")
        return
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{settings.MYSQL_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            print(f"Database `{settings.MYSQL_DB}` verified/created successfully.")
    except Exception as e:
        print(f"WARNING: could not create database ({e}); assuming it already exists.")
    finally:
        connection.close()


def ensure_columns():
    """Add columns introduced after a table was first created.

    `Base.metadata.create_all` only creates *missing tables* — it never alters an
    existing one. New columns therefore need an explicit, idempotent migration.
    """
    from sqlalchemy import text

    wanted = [
        ("pm_kb_pages", "visibility", "VARCHAR(16) NOT NULL DEFAULT 'project'"),
        ("pm_kb_pages", "allowed_roles", "VARCHAR(255) NULL"),
        # 导入日志后来扩展到里程碑与成员
        ("pm_import_logs", "milestones_created", "INT NOT NULL DEFAULT 0"),
        ("pm_import_logs", "milestones_skipped", "INT NOT NULL DEFAULT 0"),
        ("pm_import_logs", "members_created", "INT NOT NULL DEFAULT 0"),
        ("pm_import_logs", "members_skipped", "INT NOT NULL DEFAULT 0"),
        ("pm_import_logs", "created_ids", "TEXT NULL"),
        ("pm_import_logs", "rolled_back_at", "DATETIME NULL"),
    ]
    with engine.begin() as conn:
        for table, column, ddl in wanted:
            exists = conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = :t AND column_name = :c"
            ), {"t": table, "c": column}).scalar()
            if not exists:
                conn.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{column}` {ddl}"))
                print(f"  + added {table}.{column}")


def ensure_indexes():
    """Drop secondary indexes that duplicate the primary key.

    Every model used to declare `id = Column(..., primary_key=True, index=True)`,
    which makes SQLAlchemy emit both PRIMARY and ix_<table>_id. In InnoDB the
    primary key is already a clustered index, so the second one is pure overhead:
    an extra B-tree to maintain on every insert/update.
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        rows = conn.execute(text(
            "SELECT TABLE_NAME, INDEX_NAME FROM information_schema.STATISTICS "
            "WHERE table_schema = DATABASE() "
            "AND COLUMN_NAME = 'id' "
            "AND NON_UNIQUE = 1 "
            "AND INDEX_NAME LIKE 'ix\\_%' ESCAPE '\\\\' "
            "GROUP BY TABLE_NAME, INDEX_NAME "
            "HAVING COUNT(*) = 1"
        )).fetchall()

        dropped = 0
        for table, index in rows:
            # 确认主键确实建在 id 上，再删
            pk = conn.execute(text(
                "SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE table_schema = DATABASE() AND table_name = :t "
                "AND constraint_name = 'PRIMARY' ORDER BY ORDINAL_POSITION"
            ), {"t": table}).fetchall()
            if [c[0] for c in pk] != ["id"]:
                continue
            conn.execute(text(f"ALTER TABLE `{table}` DROP INDEX `{index}`"))
            dropped += 1
            print(f"  - dropped redundant index {table}.{index}")

    if dropped:
        print(f"  total {dropped} redundant index(es) removed")


def init_db(force: bool = False):
    create_database_if_not_exists()

    print("Creating all database tables...")
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

    ensure_columns()
    ensure_indexes()

    db = SessionLocal()
    try:
        from sqlalchemy import text

        # Idempotency guard: never wipe an existing database unless explicitly forced.
        if not force:
            try:
                existing_users = db.query(User).count()
            except Exception:
                existing_users = 0
            if existing_users > 0:
                print(
                    f"Database already contains {existing_users} user(s) — "
                    "skipping seed. Re-run with --force to reset."
                )
                return

        # Clean any partial records to ensure fresh seeding
        print("Cleaning old records...")
        db.execute(text("SET FOREIGN_KEY_CHECKS = 0;"))
        for table in Base.metadata.sorted_tables:
            try:
                db.execute(text(f"TRUNCATE TABLE `{table.name}`;"))
            except Exception:
                pass
        db.execute(text("SET FOREIGN_KEY_CHECKS = 1;"))
        db.commit()

        print("Seeding initial data...")

        # 1. Departments
        d_root = Department(name="研发中心", code="DEV_CENTER", leader="张总", phone="13800000001", email="dev@aipm.com", order_num=1)
        db.add(d_root)
        db.commit()
        db.refresh(d_root)

        d_arch = Department(name="架构部", code="ARCH_DEPT", parent_id=d_root.id, leader="李工", phone="13800000002", email="arch@aipm.com", order_num=1)
        d_front = Department(name="前端开发组", code="FRONTEND_DEPT", parent_id=d_root.id, leader="张三", phone="13800000003", email="fe@aipm.com", order_num=2)
        d_back = Department(name="后端开发组", code="BACKEND_DEPT", parent_id=d_root.id, leader="李四", phone="13800000004", email="be@aipm.com", order_num=3)
        d_qa = Department(name="测试质量组", code="QA_DEPT", parent_id=d_root.id, leader="王五", phone="13800000005", email="qa@aipm.com", order_num=4)
        db.add_all([d_arch, d_front, d_back, d_qa])
        db.commit()
        db.refresh(d_front)
        db.refresh(d_back)
        db.refresh(d_qa)

        # 2. Permissions
        permissions_data = [
            ("项目查看", "project:view", "menu", 1),
            ("项目创建", "project:add", "button", 2),
            ("项目编辑", "project:edit", "button", 3),
            ("项目删除", "project:delete", "button", 4),
            ("任务管理", "task:manage", "menu", 5),
            ("工时审批", "worklog:approve", "button", 6),
            ("缺陷管理", "issue:manage", "menu", 7),
            ("知识库管理", "doc:manage", "menu", 8),
            ("用户管理", "system:user:view", "menu", 9),
            ("用户新增", "system:user:add", "button", 10),
            ("用户编辑", "system:user:edit", "button", 11),
            ("用户删除", "system:user:delete", "button", 12),
            ("角色管理", "system:role:manage", "menu", 13),
            ("角色新增", "system:role:add", "button", 14),
            ("角色编辑", "system:role:edit", "button", 15),
            ("角色删除", "system:role:delete", "button", 16),
            ("部门管理", "system:dept:manage", "menu", 17),
            ("部门新增", "system:dept:add", "button", 18),
            ("部门编辑", "system:dept:edit", "button", 19),
            ("部门删除", "system:dept:delete", "button", 20),
        ]
        created_perms = []
        for name, code, ptype, order in permissions_data:
            p = Permission(name=name, code=code, type=ptype, order_num=order)
            db.add(p)
            created_perms.append(p)
        db.commit()

        # 3. Roles
        r_admin = Role(name="超级管理员", code="ADMIN", description="系统超级管理员，拥有全部权限", order_num=1)
        r_admin.permissions = created_perms
        r_pm = Role(name="项目经理", code="PM", description="负责项目排期、任务分派与工时审批", order_num=2)
        r_pm.permissions = [p for p in created_perms if not p.code.startswith("system:")]
        r_dev = Role(name="研发工程师", code="DEV", description="负责功能研发、任务流转与工时填报", order_num=3)
        r_qa = Role(name="测试工程师", code="QA", description="负责缺陷提报、用例验证与质量把控", order_num=4)
        
        db.add_all([r_admin, r_pm, r_dev, r_qa])
        db.commit()
        db.refresh(r_admin)
        db.refresh(r_pm)
        db.refresh(r_dev)
        db.refresh(r_qa)

        # 4. Users
        pwd_hash = get_password_hash("123456")
        u_admin = User(
            username="admin",
            nickname="系统管理员",
            email="admin@aipm.com",
            phone="13800000000",
            password_hash=pwd_hash,
            avatar="https://api.dicebear.com/7.x/bottts/svg?seed=admin",
            department_id=d_root.id,
            position="系统总架构师",
            is_superuser=True,
            roles=[r_admin, r_pm]
        )
        u_zhangsan = User(
            username="zhangsan",
            nickname="张三",
            email="zhangsan@aipm.com",
            phone="13800000003",
            password_hash=pwd_hash,
            avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=zhangsan",
            department_id=d_front.id,
            position="高级前端工程师",
            is_superuser=False,
            roles=[r_dev]
        )
        u_lisi = User(
            username="lisi",
            nickname="李四",
            email="lisi@aipm.com",
            phone="13800000004",
            password_hash=pwd_hash,
            avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=lisi",
            department_id=d_back.id,
            position="高级后端工程师",
            is_superuser=False,
            roles=[r_dev]
        )
        u_wangwu = User(
            username="wangwu",
            nickname="王五",
            email="wangwu@aipm.com",
            phone="13800000005",
            password_hash=pwd_hash,
            avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=wangwu",
            department_id=d_qa.id,
            position="资深QA质量专家",
            is_superuser=False,
            roles=[r_qa]
        )
        u_zhaoliu = User(
            username="zhaoliu",
            nickname="赵六",
            email="zhaoliu@aipm.com",
            phone="13800000006",
            password_hash=pwd_hash,
            avatar="https://api.dicebear.com/7.x/avataaars/svg?seed=zhaoliu",
            department_id=d_front.id,
            position="UI/UX 体验设计师",
            is_superuser=False,
            roles=[r_dev]
        )
        db.add_all([u_admin, u_zhangsan, u_lisi, u_wangwu, u_zhaoliu])
        db.commit()
        db.refresh(u_admin)
        db.refresh(u_zhangsan)
        db.refresh(u_lisi)
        db.refresh(u_wangwu)
        db.refresh(u_zhaoliu)

        # 5. Projects
        p1 = Project(
            name="AIPM 智能项目管理系统 2.0",
            code="AIPM-2026",
            description="基于 FastAPI + Vue3 + Element Plus 的下一代现代化项目协作与工时管理平台，支持看板排期、甘特图、缺陷闭环与智能报表。",
            owner_id=u_admin.id,
            status="in_progress",
            priority="high",
            budget=280000.0,
            consumed_budget=145000.0,
            progress=68,
            health="good",
            start_date=date.today() - timedelta(days=45),
            end_date=date.today() + timedelta(days=60),
            cover_image="https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?w=600&auto=format&fit=crop&q=80"
        )
        p2 = Project(
            name="企业级微服务云原生改造",
            code="CLOUD-MIGRATE",
            description="将单体业务系统解耦为基于 Kubernetes、Istio 与 Redis 集群的云原生微服务架构，提升并发性能与可用性。",
            owner_id=u_admin.id,
            status="planning",
            priority="urgent",
            budget=520000.0,
            consumed_budget=80000.0,
            progress=25,
            health="warning",
            start_date=date.today() - timedelta(days=15),
            end_date=date.today() + timedelta(days=120),
            cover_image="https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=600&auto=format&fit=crop&q=80"
        )
        p3 = Project(
            name="移动端多端协同与跨端研发",
            code="MOBILE-CROSS",
            description="支持 iOS、Android 与微信小程序统一代码库跨端渲染，优化离线缓存与即时消息推送体验。",
            owner_id=u_admin.id,
            status="testing",
            priority="medium",
            budget=180000.0,
            consumed_budget=160000.0,
            progress=88,
            health="good",
            start_date=date.today() - timedelta(days=70),
            end_date=date.today() + timedelta(days=20),
            cover_image="https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=600&auto=format&fit=crop&q=80"
        )
        db.add_all([p1, p2, p3])
        db.commit()
        db.refresh(p1)
        db.refresh(p2)
        db.refresh(p3)

        # 6. Project Members
        members = [
            ProjectMember(project_id=p1.id, user_id=u_admin.id, project_role="pm"),
            ProjectMember(project_id=p1.id, user_id=u_zhangsan.id, project_role="developer"),
            ProjectMember(project_id=p1.id, user_id=u_lisi.id, project_role="developer"),
            ProjectMember(project_id=p1.id, user_id=u_wangwu.id, project_role="qa"),
            ProjectMember(project_id=p1.id, user_id=u_zhaoliu.id, project_role="designer"),
            ProjectMember(project_id=p2.id, user_id=u_admin.id, project_role="pm"),
            ProjectMember(project_id=p2.id, user_id=u_lisi.id, project_role="tech_lead"),
            ProjectMember(project_id=p3.id, user_id=u_zhangsan.id, project_role="tech_lead"),
            ProjectMember(project_id=p3.id, user_id=u_wangwu.id, project_role="qa")
        ]
        db.add_all(members)

        # 7. Milestones
        ms1 = Milestone(project_id=p1.id, title="M1: 核心架构与认证鉴权上线", description="完成 FastAPI + Redis + JWT 架构与 RBAC 权限体系搭建", due_date=date.today() - timedelta(days=15), status="reached", reached_at=datetime.utcnow() - timedelta(days=16), order_num=1)
        ms2 = Milestone(project_id=p1.id, title="M2: 看板协作与甘特图排期交付", description="完成拖拽看板、甘特图交互与工时审批闭环", due_date=date.today() + timedelta(days=10), status="in_progress", order_num=2)
        ms3 = Milestone(project_id=p1.id, title="M3: 知识库与数据大盘发布", description="完成 Markdown 文档中心与 ECharts 统计大盘", due_date=date.today() + timedelta(days=35), status="pending", order_num=3)
        db.add_all([ms1, ms2, ms3])
        db.commit()
        db.refresh(ms1)
        db.refresh(ms2)
        db.refresh(ms3)

        # 8. Tasks
        t1 = Task(
            project_id=p1.id, milestone_id=ms2.id, title="实现 Element Plus 高颜值看板拖拽与状态流转",
            description="支持在 To Do、In Progress、In Review、Testing、Done 各泳道间无缝拖拽更新状态，并在后端实时持久化。",
            task_type="feature", status="in_progress", priority="urgent", creator_id=u_admin.id, assignee_id=u_zhangsan.id,
            estimated_hours=16.0, actual_hours=12.0, progress=75, start_date=date.today() - timedelta(days=3), due_date=date.today() + timedelta(days=2), order_num=1, tags="Vue3,ElementPlus,Kanban"
        )
        t2 = Task(
            project_id=p1.id, milestone_id=ms2.id, title="FastAPI 异步工时填报与多级审批接口",
            description="提供工时日历视图接口、PM 批量审批/驳回接口以及工时报表统计接口。",
            task_type="feature", status="in_progress", priority="high", creator_id=u_admin.id, assignee_id=u_lisi.id,
            estimated_hours=12.0, actual_hours=8.0, progress=65, start_date=date.today() - timedelta(days=2), due_date=date.today() + timedelta(days=3), order_num=2, tags="FastAPI,WorkLog,API"
        )
        t3 = Task(
            project_id=p1.id, milestone_id=ms1.id, title="统一 JWT 认证守卫与 Redis 黑名单机制",
            description="实现用户登录凭证签发、登出主动注销黑名单校验，以及全局 Token 自动续期。",
            task_type="task", status="done", priority="high", creator_id=u_admin.id, assignee_id=u_lisi.id,
            estimated_hours=8.0, actual_hours=8.0, progress=100, start_date=date.today() - timedelta(days=15), due_date=date.today() - timedelta(days=13), order_num=1, tags="Security,Redis,JWT"
        )
        t4 = Task(
            project_id=p1.id, milestone_id=ms3.id, title="ECharts 数据大盘仪表盘与趋势燃尽图",
            description="设计指标统计卡片、项目状态占比环形图、月度工时与任务交付趋势折线图以及团队负荷雷达图。",
            task_type="feature", status="todo", priority="medium", creator_id=u_admin.id, assignee_id=u_zhangsan.id,
            estimated_hours=14.0, actual_hours=0.0, progress=0, start_date=date.today() + timedelta(days=5), due_date=date.today() + timedelta(days=12), order_num=1, tags="ECharts,Dashboard,Vue3"
        )
        t5 = Task(
            project_id=p1.id, milestone_id=ms2.id, title="甘特图排期交互与任务依赖连线",
            description="在甘特图上按时间线展现所有任务起止周期与里程碑节点，支持按周/按月缩放与快速跳转。",
            task_type="feature", status="in_review", priority="high", creator_id=u_admin.id, assignee_id=u_zhangsan.id,
            estimated_hours=20.0, actual_hours=18.0, progress=90, start_date=date.today() - timedelta(days=5), due_date=date.today() + timedelta(days=4), order_num=3, tags="Gantt,Schedule,Frontend"
        )
        t6 = Task(
            project_id=p1.id, milestone_id=ms2.id, title="全模块自动化集成测试与边界用例编写",
            description="覆盖权限拦截、数据越权、工时审批流状态机校验及高并发任务流转压力测试。",
            task_type="research", status="testing", priority="medium", creator_id=u_admin.id, assignee_id=u_wangwu.id,
            estimated_hours=16.0, actual_hours=10.0, progress=60, start_date=date.today() - timedelta(days=2), due_date=date.today() + timedelta(days=6), order_num=1, tags="QA,Testing,Automation"
        )
        db.add_all([t1, t2, t3, t4, t5, t6])
        db.commit()
        db.refresh(t1)
        db.refresh(t2)

        # 9. Subtasks & Comments
        subtasks = [
            SubTask(task_id=t1.id, title="完成 SortableJS 看板拖拽事件监听", is_completed=True, assignee_id=u_zhangsan.id),
            SubTask(task_id=t1.id, title="对接后端 /tasks/{id}/status 状态更新接口", is_completed=True, assignee_id=u_zhangsan.id),
            SubTask(task_id=t1.id, title="添加看板列任务计数与动画微动效", is_completed=False, assignee_id=u_zhangsan.id),
            SubTask(task_id=t2.id, title="编写 WorkLog 模型与审批数据结构", is_completed=True, assignee_id=u_lisi.id),
            SubTask(task_id=t2.id, title="实现 PM 审批/驳回接口逻辑", is_completed=True, assignee_id=u_lisi.id),
            SubTask(task_id=t2.id, title="工时统计与成员负荷聚合计算", is_completed=False, assignee_id=u_lisi.id),
        ]
        comments = [
            TaskComment(task_id=t1.id, user_id=u_admin.id, content="看板交互做得很流畅，注意在移动时增加平滑过渡动画！"),
            TaskComment(task_id=t1.id, user_id=u_zhangsan.id, content="收到，已加入 CSS 弹性贝塞尔曲线过渡，体验极佳。"),
            TaskComment(task_id=t2.id, user_id=u_lisi.id, content="已完成工时审批状态机的单元测试，已准备联调。")
        ]
        db.add_all(subtasks)
        db.add_all(comments)

        # 10. WorkLogs
        worklogs = [
            WorkLog(project_id=p1.id, task_id=t1.id, user_id=u_zhangsan.id, log_date=date.today() - timedelta(days=1), hours=6.0, description="完成看板列布局重构与拖拽交互编写", status="approved", approver_id=u_admin.id, approved_at=datetime.utcnow() - timedelta(hours=5)),
            WorkLog(project_id=p1.id, task_id=t1.id, user_id=u_zhangsan.id, log_date=date.today(), hours=6.0, description="对接任务状态变更 API 与局部刷新逻辑", status="pending"),
            WorkLog(project_id=p1.id, task_id=t2.id, user_id=u_lisi.id, log_date=date.today() - timedelta(days=1), hours=8.0, description="编写工时填报与审批 API，集成 Redis 缓存", status="approved", approver_id=u_admin.id, approved_at=datetime.utcnow() - timedelta(hours=3)),
            WorkLog(project_id=p1.id, task_id=t3.id, user_id=u_lisi.id, log_date=date.today() - timedelta(days=3), hours=8.0, description="完成 JWT 认证与密码加密体系", status="approved", approver_id=u_admin.id, approved_at=datetime.utcnow() - timedelta(days=2)),
            WorkLog(project_id=p1.id, task_id=t6.id, user_id=u_wangwu.id, log_date=date.today(), hours=5.5, description="执行项目管理系统第一轮集成冒烟测试", status="pending")
        ]
        db.add_all(worklogs)

        # 11. Issues
        issues = [
            Issue(project_id=p1.id, task_id=t1.id, title="深色模式下看板列边框颜色对比度需微调", description="在深色模式下，灰色文字在深色卡片背景中略显暗淡，建议提高亮度。", severity="low", priority="low", status="resolved", reporter_id=u_wangwu.id, assignee_id=u_zhangsan.id, resolution="已调整 CSS 变量 --el-text-color-regular 达到 WCAG AA 标准。"),
            Issue(project_id=p1.id, task_id=t2.id, title="工时填报时若输入负数应在前端和后端同时校验阻断", description="输入小于或等于0的工时时需提示有效数字范围 0.5 ~ 24 小时。", severity="medium", priority="medium", status="in_progress", reporter_id=u_wangwu.id, assignee_id=u_lisi.id),
            Issue(project_id=p2.id, title="云原生网关超时配置需与后端保持一致", description="Istio Ingress Gateway 默认超时时间 15s，需调整为 60s 应对报表导出请求。", severity="high", priority="high", status="open", reporter_id=u_lisi.id, assignee_id=u_lisi.id)
        ]
        db.add_all(issues)

        # 12. Documents
        docs = [
            Document(
                project_id=p1.id,
                title="AIPM 系统架构设计与数据流转规范",
                category="design",
                version="v1.2",
                author_id=u_admin.id,
                content="""# AIPM 系统架构规范

## 1. 整体架构设计
AIPM 采用现代化前后端分离架构：
- **后端服务**：FastAPI 提供高性能异步 REST API，Pydantic 进行强类型请求响应校验。
- **数据库层**：MySQL 存储核心业务实体（用户、项目、任务、工时、缺陷），SQLAlchemy 2.0 ORM 进行持久化映射。
- **缓存与状态**：Redis 存储 Token 黑名单、分布式锁及高频大盘汇总数据。
- **前端工程**：基于 Vue 3 + Element Plus + Pinia + ECharts，重构自 Vben Admin 架构。

## 2. 权限与安全机制
1. 所有受保护接口均需在 Header 中携带 `Authorization: Bearer <token>`；
2. 服务端实时校验 JWT 签名与过期时间，并查询 Redis 黑名单防范注销后凭证滥用；
3. 基于 RBAC 角色权限模型，通过 `PermissionChecker` 拦截未授权访问。
"""
            ),
            Document(
                project_id=p1.id,
                title="前端组件库与 Vben 布局重构使用指南",
                category="requirement",
                version="v1.0",
                author_id=u_zhangsan.id,
                content="""# 前端组件库与布局指南

- **主布局 Layout**：包含 `Sidebar` 多级菜单导航、`Header` 顶部栏与 `TagsView` 多标签页系统；
- **状态标签 StatusTag**：根据项目状态、优先级自动映射色彩与图标；
- **拖拽看板 KanbanBoard**：基于 SortableJS 实现流畅的泳道拖拽体验；
- **指标卡片 StatCard**：玻璃拟态卡片，支持环比上涨/下跌标签展示。
"""
            )
        ]
        db.add_all(docs)

        # 13. Audit Logs
        logs = [
            AuditLog(user_id=u_admin.id, username="admin", module="认证", action="登录", method="POST", path="/api/v1/auth/login", ip="127.0.0.1", status_code=200, details="管理员成功登录系统"),
            AuditLog(user_id=u_admin.id, username="admin", module="项目管理", action="创建", method="POST", path="/api/v1/projects", ip="127.0.0.1", status_code=200, details="创建了项目 [AIPM-2026] AIPM 智能项目管理系统 2.0"),
            AuditLog(user_id=u_zhangsan.id, username="zhangsan", module="任务协作", action="更新状态", method="PATCH", path="/api/v1/tasks/1/status", ip="127.0.0.1", status_code=200, details="将任务 [实现 Element Plus 高颜值看板拖拽] 状态流转为进行中"),
            AuditLog(user_id=u_lisi.id, username="lisi", module="工时管理", action="填报", method="POST", path="/api/v1/worklogs", ip="127.0.0.1", status_code=200, details="填报了 8.0 小时工时: 编写工时填报与审批 API")
        ]
        db.add_all(logs)

        db.commit()
        print("Database initialized with rich seed data successfully!")

    except Exception as e:
        db.rollback()
        print(f"Error during init_db: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    init_db(force="--force" in sys.argv)
