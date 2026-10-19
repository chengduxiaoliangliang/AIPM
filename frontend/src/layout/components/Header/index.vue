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
  background-color: var(--bg-header);
  backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
  border-bottom: 1px solid var(--border-glass);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.03);
  z-index: 999;

  .header-left {
    display: flex;
    align-items: center;
    gap: 14px;

    .breadcrumb {
      font-size: 13px;
      font-weight: 500;
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 8px;

    .user-profile-btn {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 4px 10px;
      border-radius: var(--radius-sm);
      cursor: pointer;
      background: rgba(255, 255, 255, 0.2);
      border: 1px solid var(--border-glass-subtle);
      transition: all 0.2s ease;

      &:hover {
        background-color: var(--bg-hover);
        border-color: var(--primary-light);
      }

      .user-name {
        font-size: 13px;
        font-weight: 600;
        color: var(--text-main);
      }

      .admin-badge {
        font-size: 10px;
        padding: 0 5px;
        height: 18px;
        line-height: 16px;
        border-radius: 4px;
        font-weight: 600;
      }
    }
  }

  .action-btn {
    width: 36px;
    height: 36px;
    border-radius: var(--radius-sm);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-regular);
    cursor: pointer;
    background: transparent;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);

    &:hover {
      background-color: var(--bg-hover);
      color: var(--primary-color);
      transform: translateY(-1px);
    }
  }
}
</style>
