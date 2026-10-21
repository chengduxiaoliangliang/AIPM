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
  background-color: #0b1220;
  position: relative;
  overflow: hidden;

  /* 一层极淡的点阵 + 单点柔光，替代原来的三色光球 */
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image: radial-gradient(circle, rgba(255, 255, 255, 0.055) 1px, transparent 1px);
    background-size: 24px 24px;
    pointer-events: none;
  }

  &::after {
    content: '';
    position: absolute;
    width: 760px;
    height: 760px;
    left: -220px;
    top: -260px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(47, 84, 232, 0.28) 0%, rgba(47, 84, 232, 0) 62%);
    filter: blur(40px);
    pointer-events: none;
  }

  .glow-orb {
    display: none;
  }

  .login-card-container {
    width: 880px;
    height: 520px;
    background: #ffffff;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: var(--radius-xl);
    box-shadow: 0 24px 64px -16px rgba(0, 0, 0, 0.55);
    display: flex;
    overflow: hidden;
    z-index: 10;

    /* ── 左侧：深色技术面板 ───────────────────────────────── */
    .login-banner {
      width: 44%;
      background-color: #0e1729;
      background-image:
        linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.035) 1px, transparent 1px);
      background-size: 26px 26px;
      padding: 44px 36px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      position: relative;
      border-right: 1px solid rgba(255, 255, 255, 0.07);

      .banner-content {
        position: relative;
        z-index: 1;
      }

      .brand-logo {
        width: 40px;
        height: 40px;
        background: var(--primary-color);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 18px;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22);
      }

      .brand-name {
        font-size: 28px;
        font-weight: 700;
        letter-spacing: 0.08em;
        margin-bottom: 6px;
        color: #ffffff;
      }

      .brand-desc {
        font-size: 12.5px;
        color: rgba(255, 255, 255, 0.5);
        margin-bottom: 30px;
        line-height: 1.6;
        letter-spacing: 0.01em;
      }

      .banner-features {
        display: flex;
        flex-direction: column;
        gap: 13px;
        padding-top: 22px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);

        .feature-item {
          font-size: 12.5px;
          display: flex;
          align-items: center;
          gap: 11px;
          color: rgba(255, 255, 255, 0.72);

          .feat-dot {
            width: 14px;
            height: 1px;
            background: rgba(143, 166, 255, 0.75);
            flex-shrink: 0;
          }
        }
      }
    }

    /* ── 右侧：表单 ───────────────────────────────────────── */
    .login-form-wrapper {
      flex: 1;
      padding: 44px 46px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      background: #ffffff;

      .form-header {
        margin-bottom: 26px;

        h2 {
          font-size: 20px;
          font-weight: 600;
          color: var(--text-main);
          letter-spacing: -0.02em;
          margin-bottom: 6px;
        }

        p {
          font-size: 12.5px;
          color: var(--text-muted);
        }
      }

      .form-options {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 18px;
        font-size: 12.5px;
      }

      .submit-btn {
        width: 100%;
        height: 42px;
        font-weight: 500;
        font-size: 14px;
        letter-spacing: 0.06em;
        background: var(--primary-color);
        border: none;
        border-radius: var(--radius-sm);
        box-shadow: 0 1px 2px rgba(47, 84, 232, 0.2);
        transition: background-color 0.15s ease, box-shadow 0.15s ease;

        &:hover {
          background: var(--primary-hover);
          box-shadow: 0 2px 8px rgba(47, 84, 232, 0.28);
        }
      }

      .demo-accounts {
        margin-top: 22px;
        padding-top: 14px;
        border-top: 1px solid var(--border-color);

        .demo-title {
          font-size: 11.5px;
          color: var(--text-faint);
          margin-bottom: 8px;
          letter-spacing: 0.02em;
        }

        .account-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;

          .account-tag {
            cursor: pointer;
            font-weight: 500;
            border-radius: var(--radius-xs);
            transition: border-color 0.15s ease, background-color 0.15s ease;

            &:hover {
              border-color: var(--primary-color);
              background: var(--primary-light);
            }
          }
        }
      }
    }
  }
}
</style>
