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
  background: linear-gradient(180deg, #0f1829 0%, #0b1220 100%);
  display: flex;
  flex-direction: column;
  transition: width 0.24s cubic-bezier(0.4, 0, 0.2, 1);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  flex-shrink: 0;
  z-index: 1001;

  &.is-collapsed {
    width: var(--sidebar-collapsed-width);
  }

  .logo-container {
    height: var(--header-height);
    display: flex;
    align-items: center;
    padding: 0 16px;
    gap: 11px;
    cursor: pointer;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    overflow: hidden;
    flex-shrink: 0;

    .logo-icon-box {
      width: 30px;
      height: 30px;
      border-radius: 7px;
      background: var(--primary-color);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22),
        0 2px 6px rgba(47, 84, 232, 0.35);
    }

    .logo-text {
      display: flex;
      flex-direction: column;
      white-space: nowrap;
      line-height: 1.25;

      .brand-title {
        font-size: 15px;
        font-weight: 700;
        letter-spacing: 0.07em;
        color: #ffffff;
      }

      .brand-sub {
        font-size: 10.5px;
        color: rgba(255, 255, 255, 0.42);
        letter-spacing: 0.02em;
      }
    }
  }

  .menu-scrollbar {
    flex: 1;
    padding-top: 8px;

    :deep(.el-menu) {
      border-right: none;
      background: transparent;

      .el-menu-item,
      .el-sub-menu__title {
        position: relative;
        color: rgba(255, 255, 255, 0.72);
        height: 42px;
        line-height: 42px;
        margin: 2px 8px;
        border-radius: var(--radius-sm);
        transition: background-color 0.15s ease, color 0.15s ease;
        font-weight: 450;
        font-size: 13.5px;

        &:hover {
          color: #ffffff;
          background-color: rgba(255, 255, 255, 0.05);
        }

        .el-icon {
          font-size: 16px;
          margin-right: 9px;
          color: rgba(255, 255, 255, 0.58);
          transition: color 0.15s ease;
        }
      }

      .el-sub-menu.is-active > .el-sub-menu__title {
        color: #ffffff;

        .el-icon {
          color: #8fa6ff;
        }
      }

      .el-menu-item.is-active {
        color: #ffffff !important;
        background: rgba(47, 84, 232, 0.16) !important;
        font-weight: 500;

        .el-icon {
          color: #8fa6ff;
        }

        /* 左缘强调条：像仪表的当前刻度 */
        &::before {
          content: '';
          position: absolute;
          left: -8px;
          top: 50%;
          transform: translateY(-50%);
          width: 2px;
          height: 16px;
          border-radius: 0 2px 2px 0;
          background: var(--primary-color);
        }
      }

      .el-sub-menu .el-menu-item {
        margin: 2px 8px 2px 16px;
        height: 38px;
        line-height: 38px;
        font-size: 13px;

        &.is-active::before {
          left: -16px;
        }
      }
    }
  }
}
</style>
