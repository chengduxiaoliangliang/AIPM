<template>
  <div class="header-wrapper">
    <!-- Left Section: Collapse & Breadcrumbs -->
    <div class="header-left">
      <div class="action-btn" @click="appStore.toggleSidebar">
        <el-icon :size="18">
          <Fold v-if="!appStore.isCollapse" />
          <Expand v-else />
        </el-icon>
      </div>

      <el-breadcrumb separator="/" class="breadcrumb">
        <el-breadcrumb-item :to="{ path: '/dashboard' }">首页</el-breadcrumb-item>
        <el-breadcrumb-item v-if="currentTitle !== '统计大盘'">{{ currentTitle }}</el-breadcrumb-item>
      </el-breadcrumb>
    </div>

    <!-- Right Section: Tools, Dark Mode, Profile -->
    <div class="header-right">
      <!-- Dark mode switch -->
      <el-tooltip :content="appStore.isDark ? '切换浅色模式' : '切换深色模式'" placement="bottom">
        <div class="action-btn" @click="appStore.toggleDarkMode">
          <el-icon :size="18">
            <Moon v-if="appStore.isDark" />
            <Sunny v-else />
          </el-icon>
        </div>
      </el-tooltip>

      <!-- Full screen toggle -->
      <el-tooltip content="全屏切换" placement="bottom">
        <div class="action-btn" @click="toggleFullScreen">
          <el-icon :size="18"><FullScreen /></el-icon>
        </div>
      </el-tooltip>

      <!-- User Profile Dropdown -->
      <el-dropdown trigger="click" @command="handleCommand">
        <div class="user-profile-btn">
          <el-avatar :size="30" :src="userStore.userAvatar" />
          <span class="user-name">{{ userStore.username }}</span>
          <el-tag v-if="userStore.userInfo?.is_superuser" size="small" type="danger" effect="plain" class="admin-badge">Admin</el-tag>
          <el-icon :size="12" class="el-icon--right"><ArrowDown /></el-icon>
        </div>

        <template #dropdown>
          <el-dropdown-menu class="glass-dropdown">
            <el-dropdown-item command="profile">
              <el-icon><User /></el-icon> 个人资料
            </el-dropdown-item>
            <el-dropdown-item command="password">
              <el-icon><Key /></el-icon> 修改密码
            </el-dropdown-item>
            <el-dropdown-item divided command="logout">
              <el-icon><SwitchButton /></el-icon> 退出登录
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/store/modules/app'
import { useUserStore } from '@/store/modules/user'
import { ElMessageBox, ElMessage } from 'element-plus'
import {
  Fold,
  Expand,
  Sunny,
  Moon,
  FullScreen,
  ArrowDown,
  User,
  Key,
  SwitchButton
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const appStore = useAppStore()
const userStore = useUserStore()

const currentTitle = computed(() => (route.meta.title as string) || '')

function toggleFullScreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen()
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen()
    }
  }
}

async function handleCommand(cmd: string) {
  if (cmd === 'profile') {
    router.push('/profile')
  } else if (cmd === 'password') {
    router.push('/profile?tab=password')
  } else if (cmd === 'logout') {
    ElMessageBox.confirm('确定要退出当前登录系统吗？', '提示', {
      confirmButtonText: '确定退出',
      cancelButtonText: '取消',
      type: 'warning'
    }).then(async () => {
      await userStore.logout()
      ElMessage.success('已安全退出登录')
      router.push('/login')
    })
  }
}
</script>

<style scoped lang="scss">
.header-wrapper {
  height: var(--header-height);
  background: var(--bg-header);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  z-index: 999;
  flex-shrink: 0;

  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;

    .breadcrumb {
      font-size: 13px;

      :deep(.el-breadcrumb__inner) {
        color: var(--text-muted);
        font-weight: 450;
      }

      :deep(.el-breadcrumb__item:last-child .el-breadcrumb__inner) {
        color: var(--text-main);
        font-weight: 500;
      }

      :deep(.el-breadcrumb__separator) {
        color: var(--text-faint);
      }
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 4px;

    .user-profile-btn {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 10px 4px 5px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      border: 1px solid transparent;
      transition: background-color 0.15s ease, border-color 0.15s ease;

      &:hover {
        background: var(--bg-hover);
        border-color: var(--border-color);
      }

      .user-name {
        font-size: 13px;
        font-weight: 500;
        color: var(--text-main);
      }

      .admin-badge {
        font-size: 10px;
        padding: 0 5px;
        height: 17px;
        line-height: 15px;
        border-radius: 3px;
        font-weight: 600;
      }
    }
  }

  .action-btn {
    width: 34px;
    height: 34px;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-muted);
    cursor: pointer;
    transition: background-color 0.15s ease, color 0.15s ease;

    &:hover {
      background: var(--bg-hover);
      color: var(--text-main);
    }
  }
}
</style>
