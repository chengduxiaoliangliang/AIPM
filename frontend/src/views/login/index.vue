<template>
  <div class="login-page">
    <!-- 背景：极淡点阵 + 单点柔光 -->
    <div class="bg-grid"></div>
    <div class="bg-glow"></div>

    <!-- 顶部状态栏 -->
    <header class="topbar">
      <div class="brand">
        <div class="brand-mark">
          <el-icon :size="17"><Management /></el-icon>
        </div>
        <span class="brand-name">AIPM</span>
        <span class="brand-sep"></span>
        <span class="brand-sub">智能项目管理平台</span>
      </div>
      <div class="topbar-meta">
        <span class="live-dot"></span>
        <span class="live-text">服务运行中</span>
        <span class="build">v2.0</span>
      </div>
    </header>

    <main class="stage">
      <!-- 左：品牌叙事 -->
      <section class="intro">
        <div class="eyebrow">PROJECT INTELLIGENCE PLATFORM</div>

        <h1 class="headline">
          把项目<br />
          从排期管到交付
        </h1>

        <p class="lede">
          需求、任务、工时、知识沉淀在同一条时间线上。<br />
          进度不再靠追问，而是自己浮现。
        </p>

        <!-- 抽象甘特：用发丝线表达"时间线"，纯装饰 -->
        <div class="timeline" aria-hidden="true">
          <div class="timeline-head">
            <span class="tl-label">交付节奏</span>
            <span class="tl-scale"><i v-for="n in 6" :key="n"></i></span>
          </div>
          <div v-for="row in timeline" :key="row.label" class="tl-row">
            <span class="tl-name">{{ row.label }}</span>
            <span class="tl-track">
              <span
                class="tl-bar"
                :class="{ 'is-accent': row.accent }"
                :style="{ left: row.left, width: row.width }"
              ></span>
            </span>
          </div>
        </div>

        <ul class="facts">
          <li v-for="f in facts" :key="f.title">
            <b>{{ f.title }}</b>
            <span>{{ f.desc }}</span>
          </li>
        </ul>
      </section>

      <!-- 右：登录 -->
      <section class="panel">
        <div class="form-box">
          <div class="form-head">
            <h2>登录</h2>
            <p>使用你的工作账号继续</p>
          </div>

          <el-form
            ref="loginFormRef"
            :model="loginForm"
            :rules="loginRules"
            class="login-form"
            label-position="top"
            hide-required-asterisk
            @keyup.enter="handleLogin"
          >
            <el-form-item label="用户名" prop="username">
              <el-input
                v-model="loginForm.username"
                placeholder="请输入用户名"
                size="large"
                :prefix-icon="User"
                autocomplete="username"
                clearable
                class="dark-input"
              />
            </el-form-item>

            <el-form-item label="密码" prop="password">
              <el-input
                v-model="loginForm.password"
                type="password"
                placeholder="请输入密码"
                size="large"
                :prefix-icon="Lock"
                autocomplete="current-password"
                show-password
                class="dark-input"
              />
            </el-form-item>

            <div class="form-row">
              <el-checkbox v-model="rememberMe">保持登录</el-checkbox>
              <el-link class="quiet-link" :underline="false">忘记密码？</el-link>
            </div>

            <el-button class="submit" size="large" :loading="loading" @click="handleLogin">
              进入工作台
            </el-button>
          </el-form>

          <div class="demo">
            <span class="demo-label">没有账号？用演示身份体验</span>
            <el-dropdown trigger="click" @command="fillAccount">
              <button class="demo-trigger" type="button">
                选择角色
                <el-icon :size="12"><ArrowDown /></el-icon>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="admin">管理员 · admin</el-dropdown-item>
                  <el-dropdown-item command="zhangsan">前端工程师 · zhangsan</el-dropdown-item>
                  <el-dropdown-item command="lisi">后端工程师 · lisi</el-dropdown-item>
                  <el-dropdown-item command="wangwu">测试工程师 · wangwu</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
        </div>
      </section>
    </main>

    <footer class="footbar">
      <span>© 2026 AIPM</span>
      <span class="dot">·</span>
      <span>内部系统，仅限授权人员访问</span>
      <span class="foot-right">所有操作均记录审计日志</span>
    </footer>

    <!-- 滑块验证 -->
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
import { User, Lock, Management, ArrowDown } from '@element-plus/icons-vue'
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

/** 抽象甘特：纯装饰，表达"时间线"这个产品内核 */
const timeline = [
  { label: '需求', left: '0%', width: '32%' },
  { label: '设计', left: '24%', width: '24%' },
  { label: '开发', left: '42%', width: '38%', accent: true },
  { label: '测试', left: '68%', width: '22%' },
  { label: '交付', left: '84%', width: '14%' }
]

const facts = [
  { title: '一条时间线', desc: '排期与执行不脱节' },
  { title: '一份工时', desc: '投入产出看得见' },
  { title: '一套知识库', desc: '结论留得住、找得到' }
]

const DEMO_PASSWORDS: Record<string, string> = {
  admin: '123456',
  zhangsan: '123456',
  lisi: '123456',
  wangwu: '123456'
}

function fillAccount(username: string) {
  loginForm.username = username
  loginForm.password = DEMO_PASSWORDS[username] || '123456'
  ElMessage.info(`已填入演示账号：${username}`)
}

async function handleLogin() {
  if (!loginFormRef.value) return
  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      // 先过滑块验证，再提交
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
    ElMessage.success('登录成功，欢迎回来')
    const redirect = (route.query.redirect as string) || '/dashboard'
    router.push(redirect)
  } catch (err: any) {
    // 错误由请求拦截器统一提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped lang="scss">
$bg: #070b12;
$line: rgba(255, 255, 255, 0.075);
$line-strong: rgba(255, 255, 255, 0.14);
$text: #e9edf4;
$muted: #7d899b;
$faint: #4d5768;
$accent: #4d6bfe;

.login-page {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: $bg;
  color: $text;
  position: relative;
  overflow: hidden;
  font-variant-numeric: tabular-nums;
}

/* ── 背景 ───────────────────────────────────────────────────────────── */
.bg-grid {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
  background-size: 26px 26px;
  pointer-events: none;
  mask-image: radial-gradient(ellipse 70% 60% at 30% 40%, #000 40%, transparent 100%);
}

.bg-glow {
  position: absolute;
  width: 820px;
  height: 820px;
  left: -260px;
  top: -320px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(77, 107, 254, 0.2) 0%, rgba(77, 107, 254, 0) 62%);
  filter: blur(30px);
  pointer-events: none;
}

/* ── 顶栏 ───────────────────────────────────────────────────────────── */
.topbar {
  position: relative;
  z-index: 2;
  height: 58px;
  flex: 0 0 58px;
  padding: 0 40px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid $line;

  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .brand-mark {
    width: 28px;
    height: 28px;
    border-radius: 6px;
    background: $accent;
    color: #fff;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .brand-name {
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 0.14em;
    text-indent: 0.14em;
  }

  .brand-sep {
    width: 1px;
    height: 12px;
    background: $line-strong;
    margin: 0 4px;
  }

  .brand-sub {
    font-size: 12.5px;
    color: $muted;
  }

  .topbar-meta {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 12px;
    color: $muted;
  }

  .live-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #35c07a;
    box-shadow: 0 0 0 3px rgba(53, 192, 122, 0.14);
  }

  .build {
    margin-left: 10px;
    padding-left: 12px;
    border-left: 1px solid $line;
    color: $faint;
    font-size: 11.5px;
    letter-spacing: 0.06em;
  }
}

/* ── 主体 ───────────────────────────────────────────────────────────── */
.stage {
  position: relative;
  z-index: 2;
  flex: 1;
  display: grid;
  grid-template-columns: 1.06fr 0.94fr;
  min-height: 0;
}

/* 左：品牌叙事 */
.intro {
  padding: 0 64px 0 76px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  max-width: 720px;
}

.eyebrow {
  font-size: 10.5px;
  letter-spacing: 0.2em;
  color: $faint;
  margin-bottom: 22px;
}

.headline {
  font-size: 40px;
  line-height: 1.24;
  font-weight: 600;
  letter-spacing: -0.02em;
  margin: 0 0 20px;
}

.lede {
  font-size: 14px;
  line-height: 1.85;
  color: $muted;
  margin: 0 0 44px;
}

/* 抽象甘特 */
.timeline {
  margin-bottom: 40px;
  user-select: none;
}

.timeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 10px;
  margin-bottom: 14px;
  border-bottom: 1px solid $line;

  .tl-label {
    font-size: 11px;
    letter-spacing: 0.12em;
    color: $faint;
  }

  .tl-scale {
    display: flex;
    gap: 14px;

    i {
      width: 1px;
      height: 7px;
      background: $line-strong;
    }
  }
}

.tl-row {
  display: flex;
  align-items: center;
  gap: 14px;
  height: 26px;

  .tl-name {
    flex: 0 0 34px;
    font-size: 11.5px;
    color: $faint;
  }

  .tl-track {
    position: relative;
    flex: 1;
    height: 100%;
  }

  .tl-bar {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    height: 5px;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.13);

    &.is-accent {
      background: $accent;
      box-shadow: 0 0 12px rgba(77, 107, 254, 0.3);
    }
  }
}

.facts {
  display: flex;
  gap: 36px;
  margin: 0;
  padding: 0;
  list-style: none;

  li {
    display: flex;
    flex-direction: column;
    gap: 4px;
    position: relative;
    padding-left: 12px;

    &::before {
      content: '';
      position: absolute;
      left: 0;
      top: 3px;
      bottom: 3px;
      width: 1px;
      background: $line-strong;
    }
  }

  b {
    font-size: 12.5px;
    font-weight: 600;
    color: #cfd7e3;
  }

  span {
    font-size: 11.5px;
    color: $faint;
  }
}

/* 右：登录面板 */
.panel {
  border-left: 1px solid $line;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 64px;
}

.form-box {
  width: 100%;
  max-width: 348px;
}

.form-head {
  margin-bottom: 28px;

  h2 {
    font-size: 21px;
    font-weight: 600;
    letter-spacing: -0.01em;
    margin: 0 0 6px;
  }

  p {
    font-size: 12.5px;
    color: $muted;
    margin: 0;
  }
}

.login-form {
  :deep(.el-form-item) {
    margin-bottom: 18px;
  }

  :deep(.el-form-item__label) {
    padding-bottom: 6px;
    font-size: 12px;
    color: $muted;
    line-height: 1.4;
  }
}

/* 深色输入框 */
.dark-input {
  :deep(.el-input__wrapper) {
    background: rgba(255, 255, 255, 0.035);
    box-shadow: inset 0 0 0 1px $line;
    border-radius: 7px;
    padding: 3px 12px;
    transition: box-shadow 0.16s ease, background 0.16s ease;

    &:hover {
      background: rgba(255, 255, 255, 0.055);
      box-shadow: inset 0 0 0 1px $line-strong;
    }

    /* 键盘焦点必须可见 */
    &.is-focus {
      background: rgba(255, 255, 255, 0.055);
      box-shadow: inset 0 0 0 1px $accent, 0 0 0 3px rgba(77, 107, 254, 0.18);
    }
  }

  :deep(.el-input__inner) {
    color: $text;
    font-size: 13.5px;
    height: 38px;

    &::placeholder {
      color: $faint;
    }
  }

  :deep(.el-input__prefix),
  :deep(.el-input__suffix) {
    color: $faint;
  }
}

.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 2px 0 22px;

  :deep(.el-checkbox__label) {
    font-size: 12.5px;
    color: $muted;
  }

  :deep(.el-checkbox__inner) {
    background: transparent;
    border-color: $line-strong;
  }

  :deep(.el-checkbox.is-checked .el-checkbox__inner) {
    background: $accent;
    border-color: $accent;
  }

  .quiet-link {
    font-size: 12.5px;
    color: $muted;

    &:hover {
      color: $text;
    }
  }
}

.submit {
  width: 100%;
  height: 44px;
  border: none;
  border-radius: 7px;
  background: $accent;
  color: #fff;
  font-size: 13.5px;
  font-weight: 500;
  letter-spacing: 0.04em;
  transition: background 0.16s ease, transform 0.16s ease;

  &:hover,
  &:focus-visible {
    background: #5b78ff;
    color: #fff;
  }

  &:focus-visible {
    outline: 2px solid rgba(255, 255, 255, 0.6);
    outline-offset: 2px;
  }

  &:active {
    transform: translateY(1px);
  }
}

/* 演示账号：收进下拉，去掉一排彩色标签 */
.demo {
  margin-top: 26px;
  padding-top: 18px;
  border-top: 1px solid $line;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;

  .demo-label {
    font-size: 12px;
    color: $faint;
  }

  .demo-trigger {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 0;
    border: none;
    background: none;
    font-size: 12px;
    font-family: inherit;
    color: $muted;
    cursor: pointer;
    transition: color 0.16s ease;

    &:hover {
      color: $text;
    }

    &:focus-visible {
      outline: 2px solid $accent;
      outline-offset: 3px;
      border-radius: 3px;
    }
  }
}

/* ── 底栏 ───────────────────────────────────────────────────────────── */
.footbar {
  position: relative;
  z-index: 2;
  height: 46px;
  flex: 0 0 46px;
  padding: 0 40px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-top: 1px solid $line;
  font-size: 11.5px;
  color: $faint;

  .dot {
    opacity: 0.5;
  }

  .foot-right {
    margin-left: auto;
  }
}

/* ── 窄屏：隐藏品牌区，表单居中 ─────────────────────────────────────── */
@media (max-width: 1024px) {
  .stage {
    grid-template-columns: 1fr;
  }

  .intro {
    display: none;
  }

  .panel {
    border-left: none;
    padding: 0 28px;
  }
}

@media (max-width: 480px) {
  .topbar {
    padding: 0 20px;

    .brand-sub,
    .brand-sep {
      display: none;
    }
  }

  .footbar {
    padding: 0 20px;

    .foot-right {
      display: none;
    }
  }
}

/* ── 动效降级 ───────────────────────────────────────────────────────── */
@media (prefers-reduced-motion: reduce) {
  .dark-input :deep(.el-input__wrapper),
  .submit,
  .demo .demo-trigger {
    transition: none;
  }

  .submit:active {
    transform: none;
  }
}
</style>
