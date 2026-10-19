<template>
  <div class="sidebar-wrapper" :class="{ 'is-collapsed': appStore.isCollapse }">
    <!-- Logo & Title -->
    <div class="logo-container" @click="router.push('/dashboard')">
      <div class="logo-icon-box">
        <el-icon :size="22" color="#ffffff"><Management /></el-icon>
      </div>
      <div class="logo-text" v-show="!appStore.isCollapse">
        <span class="brand-title">AIPM</span>
        <span class="brand-sub">智能项目管理</span>
      </div>
    </div>

    <!-- Menus -->
    <el-scrollbar class="menu-scrollbar">
      <el-menu
        :default-active="activeMenu"
        :collapse="appStore.isCollapse"
        :unique-opened="true"
        router
        class="vben-sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <template #title>统计大盘</template>
        </el-menu-item>

        <el-sub-menu index="/project">
          <template #title>
            <el-icon><FolderOpened /></el-icon>
            <span>项目管理</span>
          </template>
          <el-menu-item index="/project/list">
            <el-icon><Tickets /></el-icon>
            <template #title>项目总览</template>
          </el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="/task">
          <template #title>
            <el-icon><Checked /></el-icon>
            <span>任务协作</span>
          </template>
          <el-menu-item index="/task/kanban">
            <el-icon><Grid /></el-icon>
            <template #title>任务看板</template>
          </el-menu-item>
          <el-menu-item index="/task/list">
            <el-icon><List /></el-icon>
            <template #title>任务列表</template>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/gantt">
          <el-icon><Calendar /></el-icon>
          <template #title>甘特排期</template>
        </el-menu-item>

        <el-menu-item index="/worklog">
          <el-icon><Timer /></el-icon>
          <template #title>工时管理</template>
        </el-menu-item>

        <el-menu-item index="/issue">
          <el-icon><WarningFilled /></el-icon>
          <template #title>缺陷跟踪</template>
        </el-menu-item>

        <el-menu-item index="/document">
          <el-icon><Document /></el-icon>
          <template #title>项目知识库</template>
        </el-menu-item>

        <el-sub-menu index="/system">
          <template #title>
            <el-icon><Setting /></el-icon>
            <span>系统管理</span>
          </template>
          <el-menu-item index="/system/user">
            <el-icon><User /></el-icon>
            <template #title>用户管理</template>
          </el-menu-item>
          <el-menu-item index="/system/role">
            <el-icon><Key /></el-icon>
            <template #title>角色权限</template>
          </el-menu-item>
          <el-menu-item index="/system/dept">
            <el-icon><OfficeBuilding /></el-icon>
            <template #title>部门架构</template>
          </el-menu-item>
          <el-menu-item index="/system/log">
            <el-icon><Reading /></el-icon>
            <template #title>审计日志</template>
          </el-menu-item>
          <el-menu-item index="/system/ai">
            <el-icon><Service /></el-icon>
            <template #title>AI 管理</template>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-scrollbar>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/store/modules/app'
import {
  Odometer,
  FolderOpened,
  Tickets,
  Checked,
  Grid,
  List,
  Calendar,
  Timer,
  WarningFilled,
  Document,
  Setting,
  User,
  Key,
  OfficeBuilding,
  Reading,
  Management,
  Service
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()

const activeMenu = computed(() => route.path)
</script>

<style scoped lang="scss">
.sidebar-wrapper {
  width: var(--sidebar-width);
  height: 100vh;
  background-color: var(--bg-sidebar);
  backdrop-filter: blur(20px) saturate(180%);
  -webkit-backdrop-filter: blur(20px) saturate(180%);
  display: flex;
  flex-direction: column;
  transition: width 0.28s cubic-bezier(0.4, 0, 0.2, 1);
  border-right: 1px solid rgba(255, 255, 255, 0.08);
  flex-shrink: 0;
  z-index: 1001;

  &.is-collapsed {
    width: var(--sidebar-collapsed-width);
  }

  .logo-container {
    height: var(--header-height);
    display: flex;
    align-items: center;
    padding: 0 18px;
    gap: 12px;
    cursor: pointer;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    overflow: hidden;

    .logo-icon-box {
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      box-shadow: 0 4px 12px rgba(79, 70, 229, 0.4);
      border: 1px solid rgba(255, 255, 255, 0.2);
    }

    .logo-text {
      display: flex;
      flex-direction: column;
      white-space: nowrap;

      .brand-title {
        font-size: 16px;
        font-weight: 800;
        letter-spacing: 0.5px;
        color: #ffffff;
      }

      .brand-sub {
        font-size: 11px;
        color: rgba(255, 255, 255, 0.5);
      }
    }
  }

  .menu-scrollbar {
    flex: 1;

    :deep(.el-menu) {
      border-right: none;
      background: transparent;

      .el-menu-item,
      .el-sub-menu__title {
        color: rgba(255, 255, 255, 0.7);
        height: 46px;
        line-height: 46px;
        margin: 4px 10px;
        border-radius: var(--radius-sm);
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        font-weight: 500;

        &:hover {
          color: #ffffff;
          background-color: rgba(255, 255, 255, 0.07);
        }

        .el-icon {
          font-size: 18px;
          margin-right: 10px;
        }
      }

      .el-menu-item.is-active {
        color: #ffffff !important;
        background: linear-gradient(90deg, #4f46e5 0%, #6366f1 100%) !important;
        box-shadow: 0 4px 14px rgba(79, 70, 229, 0.35);
        font-weight: 600;
      }

      .el-sub-menu .el-menu-item {
        margin: 2px 10px 2px 20px;
        height: 40px;
        line-height: 40px;
      }
    }
  }
}
</style>
