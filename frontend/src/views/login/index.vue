<template>
  <div class="login-page">
    <!-- Ambient glowing mesh orbs for glassmorphism refraction -->
    <div class="glow-orb orb-1"></div>
    <div class="glow-orb orb-2"></div>
    <div class="glow-orb orb-3"></div>

    <div class="login-card-container">
      <!-- Left Glass Brand Hero Banner -->
      <div class="login-banner">
        <div class="banner-content">
          <div class="brand-logo">
            <el-icon :size="30" color="#ffffff"><Management /></el-icon>
          </div>
          <h1 class="brand-name">AIPM</h1>
          <p class="brand-desc">智能项目协作 · 极速敏捷排期 · 全闭环管理</p>
          
          <div class="banner-features">
            <div class="feature-item">
              <span class="feat-dot"></span>
              <span>敏捷看板与甘特排期无缝流转</span>
            </div>
            <div class="feature-item">
              <span class="feat-dot"></span>
              <span>细粒度工时填报与自动审批流</span>
            </div>
            <div class="feature-item">
              <span class="feat-dot"></span>
              <span>项目健康度与实时多维数据大盘</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Form Area -->
      <div class="login-form-wrapper">
        <div class="form-header">
          <h2>系统登录</h2>
          <p>欢迎回到 AIPM 智能项目管理平台</p>
        </div>

        <el-form
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          class="login-form"
          @keyup.enter="handleLogin"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              size="large"
              :prefix-icon="User"
              clearable
              class="glass-input"
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              :prefix-icon="Lock"
              show-password
              class="glass-input"
            />
          </el-form-item>

          <div class="form-options">
            <el-checkbox v-model="rememberMe">记住账号</el-checkbox>
            <el-link type="primary" :underline="false">忘记密码?</el-link>
          </div>

          <el-button
            type="primary"
            size="large"
            :loading="loading"
            class="submit-btn"
            @click="handleLogin"
          >
            登 录
          </el-button>

          <!-- Quick Fill Demo Accounts (Flat Badges) -->
          <div class="demo-accounts">
            <div class="demo-title">演示账号快速填入：</div>
            <div class="account-tags">
              <el-tag
                size="small"
                effect="plain"
                class="account-tag tag-admin"
                @click="fillAccount('admin', '123456')"
              >
                管理员 (admin)
              </el-tag>
              <el-tag
                size="small"
                type="success"
                effect="plain"
                class="account-tag tag-dev"
                @click="fillAccount('zhangsan', '123456')"
              >
                前端 (zhangsan)
              </el-tag>
              <el-tag
                size="small"
                type="warning"
                effect="plain"
                class="account-tag tag-be"
                @click="fillAccount('lisi', '123456')"
              >
                后端 (lisi)
              </el-tag>
              <el-tag
                size="small"
                type="danger"
                effect="plain"
                class="account-tag tag-qa"
                @click="fillAccount('wangwu', '123456')"
              >
                测试 (wangwu)
              </el-tag>
            </div>
          </div>
        </el-form>
      </div>
    </div>

    <!-- Sliding Puzzle Captcha Modal -->
    <SliderCaptchaModal
      :visible="captchaVisible"
      @success="onCaptchaSuccess"
      @close="captchaVisible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/store/modules/user'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock, Management } from '@element-plus/icons-vue'
import SliderCaptchaModal from '@/components/SliderCaptchaModal.vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loginFormRef = ref<FormInstance>()
const loading = ref(false)
const rememberMe = ref(true)
const captchaVisible = ref(false)

const loginForm = reactive({
  username: 'admin',
  password: '123456'
})

const loginRules = reactive<FormRules>({
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
})

function fillAccount(u: string, p: string) {
  loginForm.username = u
  loginForm.password = p
  ElMessage.info(`已填入账号: ${u}`)
}

async function handleLogin() {
  if (!loginFormRef.value) return
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      // Trigger Sliding Captcha Verification first
      captchaVisible.value = true
    }
  })
}

async function onCaptchaSuccess(captchaToken: string) {
  captchaVisible.value = false
  loading.value = true
  try {
    await userStore.login({
      username: loginForm.username,
      password: loginForm.password,
      captcha_token: captchaToken
    })
    ElMessage.success('登录成功，欢迎回来！')
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (err: any) {
    // Error handled in request interceptor
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
.login-page {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #0f172a;
  position: relative;
  overflow: hidden;

  /* Ambient glowing orbs */
  .glow-orb {
    position: absolute;
    border-radius: 50%;
    filter: blur(80px);
    opacity: 0.6;
    pointer-events: none;
    z-index: 1;

    &.orb-1 {
      width: 480px;
      height: 480px;
      background: radial-gradient(circle, #4f46e5 0%, rgba(79, 70, 229, 0) 70%);
      top: -100px;
      left: -100px;
    }

    &.orb-2 {
      width: 520px;
      height: 520px;
      background: radial-gradient(circle, #8b5cf6 0%, rgba(139, 92, 246, 0) 70%);
      bottom: -120px;
      right: -100px;
    }

    &.orb-3 {
      width: 360px;
      height: 360px;
      background: radial-gradient(circle, #06b6d4 0%, rgba(6, 182, 212, 0) 70%);
      top: 40%;
      left: 50%;
      transform: translate(-50%, -50%);
      opacity: 0.35;
    }
  }

  .login-card-container {
    width: 880px;
    height: 520px;
    background: rgba(255, 255, 255, 0.82);
    backdrop-filter: blur(28px) saturate(200%);
    -webkit-backdrop-filter: blur(28px) saturate(200%);
    border: 1px solid rgba(255, 255, 255, 0.5);
    border-radius: var(--radius-xl);
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.45);
    display: flex;
    overflow: hidden;
    z-index: 10;

    .login-banner {
      width: 42%;
      background: linear-gradient(135deg, rgba(79, 70, 229, 0.95) 0%, rgba(124, 58, 237, 0.95) 100%);
      padding: 40px 32px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      color: #ffffff;
      position: relative;
      border-right: 1px solid rgba(255, 255, 255, 0.15);

      .brand-logo {
        width: 48px;
        height: 48px;
        background: rgba(255, 255, 255, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: var(--radius-md);
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 20px;
        box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
      }

      .brand-name {
        font-size: 32px;
        font-weight: 800;
        letter-spacing: 0.5px;
        margin-bottom: 8px;
      }

      .brand-desc {
        font-size: 13px;
        color: rgba(255, 255, 255, 0.85);
        margin-bottom: 32px;
        line-height: 1.5;
      }

      .banner-features {
        display: flex;
        flex-direction: column;
        gap: 14px;

        .feature-item {
          font-size: 13px;
          display: flex;
          align-items: center;
          gap: 10px;
          color: rgba(255, 255, 255, 0.92);

          .feat-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background-color: #38bdf8;
            box-shadow: 0 0 8px #38bdf8;
          }
        }
      }
    }

    .login-form-wrapper {
      flex: 1;
      padding: 40px 44px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      background-color: rgba(255, 255, 255, 0.6);

      .form-header {
        margin-bottom: 24px;

        h2 {
          font-size: 22px;
          font-weight: 700;
          color: var(--text-main);
          letter-spacing: -0.5px;
          margin-bottom: 6px;
        }

        p {
          font-size: 13px;
          color: var(--text-muted);
        }
      }

      .form-options {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 18px;
        font-size: 13px;
      }

      .submit-btn {
        width: 100%;
        font-weight: 700;
        letter-spacing: 2px;
        background: var(--primary-color);
        border: none;
        height: 44px;
        border-radius: var(--radius-sm);
        box-shadow: 0 4px 14px rgba(79, 70, 229, 0.4);

        &:hover {
          background: var(--primary-hover);
        }
      }

      .demo-accounts {
        margin-top: 20px;
        padding-top: 14px;
        border-top: 1px dashed rgba(203, 213, 225, 0.8);

        .demo-title {
          font-size: 12px;
          color: var(--text-muted);
          margin-bottom: 8px;
          font-weight: 500;
        }

        .account-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;

          .account-tag {
            cursor: pointer;
            font-weight: 600;
            border-radius: var(--radius-xs);
            transition: all 0.18s cubic-bezier(0.4, 0, 0.2, 1);

            &:hover {
              transform: translateY(-2px);
              box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
            }
          }
        }
      }
    }
  }
}
</style>
