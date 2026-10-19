import { createRouter, createWebHistory, RouteRecordRaw } from 'vue-router'
import Layout from '@/layout/index.vue'

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/index.vue'),
    meta: { title: '登录', hidden: true }
  },
  {
    path: '/',
    component: Layout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/index.vue'),
        meta: { title: '统计大盘', icon: 'Odometer', affix: true }
      }
    ]
  },
  {
    path: '/project',
    component: Layout,
    redirect: '/project/list',
    meta: { title: '项目管理', icon: 'FolderOpened' },
    children: [
      {
        path: 'list',
        name: 'ProjectList',
        component: () => import('@/views/project/list.vue'),
        meta: { title: '项目列表', icon: 'Tickets' }
      },
      {
        path: 'detail/:id',
        name: 'ProjectDetail',
        component: () => import('@/views/project/detail.vue'),
        meta: { title: '项目详情', hidden: true }
      }
    ]
  },
  {
    path: '/task',
    component: Layout,
    redirect: '/task/kanban',
    meta: { title: '任务协作', icon: 'Checked' },
    children: [
      {
        path: 'kanban',
        name: 'TaskKanban',
        component: () => import('@/views/task/kanban.vue'),
        meta: { title: '任务看板', icon: 'Grid' }
      },
      {
        path: 'list',
        name: 'TaskList',
        component: () => import('@/views/task/list.vue'),
        meta: { title: '任务列表', icon: 'List' }
      }
    ]
  },
  {
    path: '/gantt',
    component: Layout,
    children: [
      {
        path: '',
        name: 'GanttSchedule',
        component: () => import('@/views/gantt/index.vue'),
        meta: { title: '甘特排期', icon: 'Calendar' }
      }
    ]
  },
  {
    path: '/worklog',
    component: Layout,
    children: [
      {
        path: '',
        name: 'WorkLog',
        component: () => import('@/views/worklog/index.vue'),
        meta: { title: '工时管理', icon: 'Timer' }
      }
    ]
  },
  {
    path: '/issue',
    component: Layout,
    children: [
      {
        path: '',
        name: 'IssueTracking',
        component: () => import('@/views/issue/index.vue'),
        meta: { title: '缺陷跟踪', icon: 'WarningFilled' }
      }
    ]
  },
  {
    path: '/document',
    component: Layout,
    children: [
      {
        path: '',
        name: 'DocumentWiki',
        component: () => import('@/views/document/index.vue'),
        meta: { title: '项目知识库', icon: 'Document' }
      }
    ]
  },
  {
    path: '/ai-sprite',
    component: Layout,
    children: [
      {
        path: '',
        name: 'AiSpriteLab',
        component: () => import('@/views/ai-sprite/index.vue'),
        meta: { title: '3D 精灵实验室', icon: 'MagicStick' }
      }
    ]
  },
  {
    path: '/system',
    component: Layout,
    redirect: '/system/user',
    meta: { title: '系统管理', icon: 'Setting', permission: 'system' },
    children: [
      {
        path: 'user',
        name: 'SystemUser',
        component: () => import('@/views/system/user/index.vue'),
        meta: { title: '用户管理', icon: 'User' }
      },
      {
        path: 'role',
        name: 'SystemRole',
        component: () => import('@/views/system/role/index.vue'),
        meta: { title: '角色权限', icon: 'Key' }
      },
      {
        path: 'dept',
        name: 'SystemDept',
        component: () => import('@/views/system/dept/index.vue'),
        meta: { title: '部门架构', icon: 'OfficeBuilding' }
      },
      {
        path: 'log',
        name: 'SystemLog',
        component: () => import('@/views/system/log/index.vue'),
        meta: { title: '审计日志', icon: 'Reading' }
      },
      {
        path: 'ai',
        name: 'SystemAiManage',
        component: () => import('@/views/system/AiManage.vue'),
        meta: { title: 'AI 管理', icon: 'Service' }
      }
    ]
  },
  {
    path: '/profile',
    component: Layout,
    meta: { hidden: true },
    children: [
      {
        path: '',
        name: 'UserProfile',
        component: () => import('@/views/profile/index.vue'),
        meta: { title: '个人中心' }
      }
    ]
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/dashboard',
    meta: { hidden: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

export default router
