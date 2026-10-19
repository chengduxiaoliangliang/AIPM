<template>
  <div class="profile-page page-container">
    <el-row :gutter="16">
      <!-- User Profile Card -->
      <el-col :xs="24" :sm="8">
        <div class="user-card vben-card">
          <div class="avatar-box">
            <el-avatar :size="80" :src="userStore.userAvatar" />
            <h3>{{ userStore.username }}</h3>
            <p class="user-pos">{{ userStore.userInfo?.position || '研发团队成员' }}</p>
          </div>

          <div class="profile-details">
            <div class="detail-row">
              <span class="lbl">登录账号：</span>
              <span class="val">{{ userStore.userInfo?.username }}</span>
            </div>
            <div class="detail-row">
              <span class="lbl">所属部门：</span>
              <span class="val">{{ userStore.userInfo?.department_name || '技术研发中心' }}</span>
            </div>
            <div class="detail-row">
              <span class="lbl">绑定角色：</span>
              <span class="val">
                <el-tag v-for="r in userStore.roles" :key="r" size="small" style="margin-right: 4px">{{ r }}</el-tag>
              </span>
            </div>
            <div class="detail-row">
              <span class="lbl">联系邮箱：</span>
              <span class="val">{{ userStore.userInfo?.email || 'admin@aipm.com' }}</span>
            </div>
          </div>
        </div>
      </el-col>

      <!-- Password Change & Info Edit Tabs -->
      <el-col :xs="24" :sm="16">
        <div class="settings-card vben-card">
          <el-tabs v-model="activeTab">
            <el-tab-pane label="修改登录密码" name="password">
              <el-form :model="pwdForm" label-position="top" style="max-width: 440px; margin-top: 16px">
                <el-form-item label="当前原密码" required>
                  <el-input v-model="pwdForm.old_password" type="password" show-password placeholder="请输入原密码" />
                </el-form-item>
                <el-form-item label="设置新密码" required>
                  <el-input v-model="pwdForm.new_password" type="password" show-password placeholder="请输入新密码" />
                </el-form-item>
                <el-form-item label="确认新密码" required>
                  <el-input v-model="pwdForm.confirm_password" type="password" show-password placeholder="请再次确认新密码" />
                </el-form-item>
                <el-button type="primary" :loading="pwdLoading" @click="submitChangePassword">确认修改并重新登录</el-button>
              </el-form>
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store/modules/user'
import { changePasswordApi } from '@/api/user'
import { ElMessage } from 'element-plus'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const activeTab = ref('password')
const pwdLoading = ref(false)

const pwdForm = reactive({
  old_password: '',
  new_password: '',
  confirm_password: ''
})

async function submitChangePassword() {
  if (!pwdForm.old_password || !pwdForm.new_password) {
    ElMessage.warning('请填写原密码与新密码')
    return
  }
  if (pwdForm.new_password !== pwdForm.confirm_password) {
    ElMessage.error('两次输入的新密码不一致')
    return
  }

  pwdLoading.value = true
  try {
    await changePasswordApi({
      old_password: pwdForm.old_password,
      new_password: pwdForm.new_password
    })
    ElMessage.success('密码修改成功，请使用新密码重新登录')
    await userStore.logout()
    router.push('/login')
  } finally {
    pwdLoading.value = false
  }
}

onMounted(() => {
  if (route.query.tab) {
    activeTab.value = route.query.tab as string
  }
})
</script>

<style scoped lang="scss">
.profile-page {
  .user-card {
    padding: 24px;
    text-align: center;

    .avatar-box {
      margin-bottom: 20px;
      h3 { font-size: 18px; margin: 12px 0 4px; color: var(--text-main); }
      .user-pos { font-size: 13px; color: var(--text-muted); }
    }

    .profile-details {
      text-align: left;
      border-top: 1px solid var(--border-color);
      padding-top: 16px;
      display: flex;
      flex-direction: column;
      gap: 12px;

      .detail-row {
        display: flex;
        font-size: 13px;
        .lbl { width: 80px; color: var(--text-muted); }
        .val { font-weight: 500; color: var(--text-main); flex: 1; }
      }
    }
  }

  .settings-card {
    padding: 24px;
  }
}
</style>
