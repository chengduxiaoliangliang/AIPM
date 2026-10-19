<template>
  <div class="ai-manage-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="header-left">
        <div class="header-icon">
          <el-icon :size="22" color="#fff"><Service /></el-icon>
        </div>
        <div>
          <h1 class="page-title">AI 模块管理</h1>
          <p class="page-sub">DeepSeek 大模型接入 · 运行时配置 · 会话管理</p>
        </div>
      </div>
      <el-button type="primary" :loading="loading" @click="loadAll" id="btn-refresh-ai-status">
        <el-icon><Refresh /></el-icon>
        刷新状态
      </el-button>
    </div>

    <!-- Status Cards Row -->
    <el-row :gutter="18" class="status-row" v-loading="loading">
      <el-col :span="8">
        <div class="stat-card" :class="status?.is_llm_configured ? 'card-success' : 'card-warning'">
          <div class="card-icon-box card-icon-ai">🤖</div>
          <div class="card-content">
            <div class="card-value">
              <el-tag :type="status?.is_llm_configured ? 'success' : 'warning'" effect="dark" size="large">
                {{ status?.is_llm_configured ? '✅ 已接入' : '⚠️ 未配置' }}
              </el-tag>
            </div>
            <div class="card-label">DeepSeek 大模型</div>
            <div class="card-detail">{{ status?.model_info?.api_key_preview || '—' }}</div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card" :class="status?.redis_connected ? 'card-success' : 'card-danger'">
          <div class="card-icon-box card-icon-redis">💾</div>
          <div class="card-content">
            <div class="card-value">
              <el-tag :type="status?.redis_connected ? 'success' : 'danger'" effect="dark" size="large">
                {{ status?.redis_connected ? '✅ 已连接' : '❌ 断开' }}
              </el-tag>
            </div>
            <div class="card-label">Redis 会话存储</div>
            <div class="card-detail">TTL: {{ status?.session_config?.session_ttl_days ?? '—' }} 天</div>
          </div>
        </div>
      </el-col>
      <el-col :span="8">
        <div class="stat-card" :class="status?.ai_enabled ? 'card-info' : 'card-muted'">
          <div class="card-icon-box card-icon-switch">⚡</div>
          <div class="card-content">
            <div class="card-value">
              <el-tag :type="status?.ai_enabled ? 'primary' : 'info'" effect="dark" size="large">
                {{ status?.ai_enabled ? '✅ 已启用' : '⏸ 已禁用' }}
              </el-tag>
            </div>
            <div class="card-label">AI 功能状态</div>
            <div class="card-detail">最大 {{ status?.session_config?.max_history_turns ?? '—' }} 轮上下文</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- LLM Config Editor -->
    <div class="config-card vben-card">
      <div class="section-header flex-between">
        <div class="section-title">
          <el-icon><Setting /></el-icon>
          大模型配置
          <el-tag
            v-if="aiConfig?.is_runtime_override"
            type="warning"
            size="small"
            effect="plain"
            class="override-tag"
          >
            运行时覆盖 (Redis)
          </el-tag>
          <el-tag v-else type="info" size="small" effect="plain" class="override-tag">
            默认配置 (系统)
          </el-tag>
        </div>
        <el-button
          v-if="aiConfig?.is_runtime_override"
          size="small"
          type="danger"
          plain
          :loading="resetting"
          @click="handleReset"
          id="btn-reset-ai-config"
        >
          <el-icon><RefreshLeft /></el-icon>
          恢复默认
        </el-button>
      </div>

      <el-form
        ref="configFormRef"
        :model="configForm"
        :rules="configRules"
        label-width="120px"
        label-position="left"
        class="config-form"
        v-loading="configLoading"
      >
        <!-- API Key -->
        <el-form-item label="API Key" prop="api_key">
          <div class="api-key-row">
            <el-input
              v-model="configForm.api_key"
              :type="showApiKey ? 'text' : 'password'"
              placeholder="留空则保持当前 Key 不变"
              class="api-key-input"
              id="input-api-key"
            >
              <template #prefix>
                <el-icon><Key /></el-icon>
              </template>
            </el-input>
            <el-button text :icon="showApiKey ? Hide : View" @click="showApiKey = !showApiKey" />
          </div>
          <div class="field-hint">
            当前: <code>{{ aiConfig?.api_key_preview || '未配置' }}</code>
          </div>
        </el-form-item>

        <!-- Base URL -->
        <el-form-item label="API Base URL" prop="base_url">
          <el-input
            v-model="configForm.base_url"
            placeholder="https://api.deepseek.com"
            id="input-base-url"
          >
            <template #prefix>
              <el-icon><Link /></el-icon>
            </template>
          </el-input>
          <div class="field-hint">OpenAI-compatible API 地址，支持 DeepSeek / 本地 Ollama / Azure 等</div>
        </el-form-item>

        <!-- Model Name -->
        <el-form-item label="模型名称" prop="model">
          <el-select
            v-model="configForm.model"
            allow-create
            filterable
            placeholder="选择或输入模型名"
            style="width: 100%"
            id="select-model"
          >
            <el-option-group label="DeepSeek 官方">
              <el-option label="deepseek-v4-flash (快速响应)" value="deepseek-v4-flash" />
              <el-option label="deepseek-v4-pro (旗舰高性能)" value="deepseek-v4-pro" />
            </el-option-group>
            <el-option-group label="兼容模型">
              <el-option label="gpt-4o" value="gpt-4o" />
              <el-option label="gpt-3.5-turbo" value="gpt-3.5-turbo" />
              <el-option label="qwen-plus (通义千问)" value="qwen-plus" />
              <el-option label="glm-4 (智谱 GLM)" value="glm-4" />
            </el-option-group>
          </el-select>
        </el-form-item>

        <el-row :gutter="24">
          <!-- Temperature -->
          <el-col :span="12">
            <el-form-item label="温度 (Temperature)" prop="temperature">
              <div class="slider-row">
                <el-slider
                  v-model="configForm.temperature"
                  :min="0"
                  :max="2"
                  :step="0.1"
                  show-input
                  :show-input-controls="false"
                  size="small"
                  class="config-slider"
                />
              </div>
              <div class="field-hint">越高越有创意 (0=确定性, 1=平衡, 2=最大随机)</div>
            </el-form-item>
          </el-col>

          <!-- Max Tokens -->
          <el-col :span="12">
            <el-form-item label="最大 Token" prop="max_tokens">
              <el-input-number
                v-model="configForm.max_tokens"
                :min="256"
                :max="32768"
                :step="256"
                controls-position="right"
                style="width: 100%"
                id="input-max-tokens"
              />
              <div class="field-hint">单次响应最大 Token 数 (256–32768)</div>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- AI Enabled -->
        <el-form-item label="AI 功能开关">
          <el-switch
            v-model="configForm.ai_enabled"
            active-text="启用"
            inactive-text="停用"
            id="switch-ai-enabled"
          />
          <span class="field-hint" style="margin-left: 12px;">停用后所有 AI 对话将回退到本地模式</span>
        </el-form-item>

        <!-- Actions -->
        <el-form-item>
          <div class="form-actions">
            <el-button
              type="primary"
              :loading="saving"
              @click="handleSave"
              id="btn-save-ai-config"
            >
              <el-icon><Check /></el-icon>
              保存配置
            </el-button>
            <el-button plain @click="loadConfig">
              <el-icon><RefreshLeft /></el-icon>
              取消
            </el-button>
          </div>
        </el-form-item>
      </el-form>
    </div>

    <!-- Session Management -->
    <div class="sessions-card vben-card">
      <div class="section-header flex-between">
        <div class="section-title">
          <el-icon><ChatDotRound /></el-icon>
          我的对话会话
        </div>
        <div class="flex-center" style="gap: 10px;">
          <el-button size="small" type="primary" plain @click="createNewSession" id="btn-create-session">
            <el-icon><Plus /></el-icon> 新建会话
          </el-button>
          <el-button size="small" plain @click="loadSessions" id="btn-refresh-sessions">
            <el-icon><Refresh /></el-icon>
          </el-button>
        </div>
      </div>

      <el-table
        :data="sessions"
        v-loading="sessionsLoading"
        stripe
        class="sessions-table"
        empty-text="暂无会话记录"
      >
        <el-table-column prop="session_id" label="会话 ID" width="290">
          <template #default="{ row }">
            <span class="session-id-text">{{ row.session_id }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="会话标题" min-width="200">
          <template #default="{ row }">
            <span class="session-title">{{ row.title || '(无标题)' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="message_count" label="消息数" width="90" align="center">
          <template #default="{ row }">
            <el-badge :value="row.message_count" :max="99" type="primary" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column prop="updated_at" label="最后活跃" width="180" />
        <el-table-column label="操作" width="140" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="info" plain @click="viewHistory(row)">
              <el-icon><View /></el-icon>
            </el-button>
            <el-popconfirm
              title="确认删除此会话及所有历史消息？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="deleteSession(row.session_id)"
            >
              <template #reference>
                <el-button size="small" type="danger" plain>
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- History Dialog -->
    <el-dialog
      v-model="historyDialogVisible"
      :title="`会话历史 — ${selectedSession?.title || ''}`"
      width="620px"
      class="history-dialog"
    >
      <div class="history-list" v-loading="historyLoading">
        <div
          v-for="(msg, idx) in historyMessages"
          :key="idx"
          class="history-msg"
          :class="msg.role"
        >
          <el-tag size="small" :type="msg.role === 'user' ? 'primary' : 'info'" class="role-tag">
            {{ msg.role === 'user' ? '👤 用户' : '🤖 AI' }}
          </el-tag>
          <div class="msg-content" v-html="renderMd(msg.content)"></div>
        </div>
        <el-empty v-if="!historyLoading && historyMessages.length === 0" description="暂无历史消息" />
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Service, Refresh, Setting, RefreshLeft, Key, Link, ChatDotRound,
  Plus, View, Delete, Check, Hide
} from '@element-plus/icons-vue'
import {
  getAIStatusApi, getAIConfigApi, updateAIConfigApi, resetAIConfigApi,
  listSessionsApi, createSessionApi, deleteSessionApi, getSessionHistoryApi,
  type AISession, type AIStatusResponse, type AIConfig, type HistoryMessage
} from '@/api/ai'
import MarkdownIt from 'markdown-it'
import type { FormInstance } from 'element-plus'

const md = new MarkdownIt({ html: false, breaks: true, linkify: true })
function renderMd(text: string) { return md.render(text || '') }

// ─── State ────────────────────────────────────────────────────────────────────
const loading = ref(false)
const configLoading = ref(false)
const sessionsLoading = ref(false)
const saving = ref(false)
const resetting = ref(false)
const showApiKey = ref(false)

const status = ref<AIStatusResponse | null>(null)
const aiConfig = ref<AIConfig | null>(null)
const sessions = ref<AISession[]>([])

const configFormRef = ref<FormInstance>()
const configForm = reactive({
  api_key: '',
  base_url: '',
  model: '',
  temperature: 0.7,
  max_tokens: 4096,
  ai_enabled: true,
})

const configRules = {
  base_url: [{ required: true, message: '请输入 API Base URL', trigger: 'blur' }],
  model: [{ required: true, message: '请选择或输入模型名称', trigger: 'blur' }],
}

const historyDialogVisible = ref(false)
const historyLoading = ref(false)
const historyMessages = ref<HistoryMessage[]>([])
const selectedSession = ref<AISession | null>(null)

// ─── Loaders ──────────────────────────────────────────────────────────────────
async function loadAll() {
  loading.value = true
  await Promise.all([loadStatus(), loadConfig(), loadSessions()])
  loading.value = false
}

async function loadStatus() {
  try {
    const res = await getAIStatusApi()
    status.value = res.data
  } catch (e: any) {
    ElMessage.error('获取 AI 状态失败')
  }
}

async function loadConfig() {
  configLoading.value = true
  try {
    const res = await getAIConfigApi()
    aiConfig.value = res.data
    // Fill form with current effective config
    configForm.api_key = ''  // Never prefill key for security
    configForm.base_url = res.data.base_url
    configForm.model = res.data.model
    configForm.temperature = res.data.temperature
    configForm.max_tokens = res.data.max_tokens
    configForm.ai_enabled = res.data.ai_enabled
  } catch (e) {
    // may fail if not admin
  } finally {
    configLoading.value = false
  }
}

async function loadSessions() {
  sessionsLoading.value = true
  try {
    const res = await listSessionsApi()
    sessions.value = res.data
  } catch (e) {
    // ignore
  } finally {
    sessionsLoading.value = false
  }
}

// ─── Config Actions ───────────────────────────────────────────────────────────
async function handleSave() {
  if (!configFormRef.value) return
  await configFormRef.value.validate(async (valid) => {
    if (!valid) return
    saving.value = true
    try {
      const payload: any = {
        base_url: configForm.base_url,
        model: configForm.model,
        temperature: configForm.temperature,
        max_tokens: configForm.max_tokens,
        ai_enabled: configForm.ai_enabled,
      }
      // Only include api_key if user typed a new one
      if (configForm.api_key.trim()) {
        payload.api_key = configForm.api_key.trim()
      }
      const res = await updateAIConfigApi(payload)
      aiConfig.value = res.data
      configForm.api_key = ''  // Clear after save
      ElMessage.success('✅ 大模型配置已更新，下次对话将使用新配置')
      await loadStatus()
    } catch (e: any) {
      ElMessage.error('保存失败: ' + (e?.response?.data?.detail || e?.message || '请求异常'))
    } finally {
      saving.value = false
    }
  })
}

async function handleReset() {
  try {
    await ElMessageBox.confirm(
      '确认恢复为系统默认配置？所有运行时覆盖将被清除。',
      '恢复默认配置',
      { confirmButtonText: '确认恢复', cancelButtonText: '取消', type: 'warning' }
    )
    resetting.value = true
    await resetAIConfigApi()
    ElMessage.success('已恢复默认配置')
    await loadConfig()
    await loadStatus()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error('操作失败')
  } finally {
    resetting.value = false
  }
}

// ─── Session Actions ──────────────────────────────────────────────────────────
async function createNewSession() {
  try {
    await createSessionApi('新建会话')
    ElMessage.success('新会话已创建')
    await loadSessions()
  } catch (e) {
    ElMessage.error('创建会话失败')
  }
}

async function deleteSession(sessionId: string) {
  try {
    await deleteSessionApi(sessionId)
    ElMessage.success('会话已删除')
    sessions.value = sessions.value.filter(s => s.session_id !== sessionId)
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

async function viewHistory(session: AISession) {
  selectedSession.value = session
  historyDialogVisible.value = true
  historyLoading.value = true
  historyMessages.value = []
  try {
    const res = await getSessionHistoryApi(session.session_id)
    historyMessages.value = res.data
  } catch (e) {
    ElMessage.error('获取历史失败')
  } finally {
    historyLoading.value = false
  }
}

onMounted(() => {
  loadAll()
})
</script>

<style scoped lang="scss">
.ai-manage-page {
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

/* Header */
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;

  .header-left {
    display: flex;
    align-items: center;
    gap: 14px;

    .header-icon {
      width: 46px;
      height: 46px;
      border-radius: 12px;
      background: linear-gradient(135deg, #4f46e5, #8b5cf6);
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 6px 18px rgba(79, 70, 229, 0.35);
    }

    .page-title {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
      color: var(--text-main);
    }

    .page-sub {
      margin: 2px 0 0;
      font-size: 12px;
      color: var(--text-muted);
    }
  }
}

/* Status Cards */
.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 20px 22px;
  display: flex;
  align-items: center;
  gap: 16px;
  transition: all 0.25s ease;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);

  &:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.08); }
  &.card-success { border-left: 4px solid #22c55e; }
  &.card-warning  { border-left: 4px solid #f59e0b; }
  &.card-danger   { border-left: 4px solid #ef4444; }
  &.card-info     { border-left: 4px solid #4f46e5; }
  &.card-muted    { border-left: 4px solid #94a3b8; }

  .card-icon-box {
    width: 52px;
    height: 52px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 24px;
    flex-shrink: 0;
    &.card-icon-ai    { background: rgba(79, 70, 229, 0.1); }
    &.card-icon-redis { background: rgba(239, 68, 68, 0.1); }
    &.card-icon-switch{ background: rgba(34, 197, 94, 0.1); }
  }

  .card-content {
    flex: 1;
    min-width: 0;
    .card-value { margin-bottom: 4px; }
    .card-label { font-size: 12px; color: var(--text-muted); margin-top: 4px; }
    .card-detail { font-size: 11px; color: var(--text-regular); margin-top: 2px; font-family: monospace; }
  }
}

/* Config Card */
.config-card {
  padding: 20px 24px;
}

.section-header {
  margin-bottom: 20px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);

  .el-icon { color: var(--primary-color); font-size: 16px; }
  .override-tag { margin-left: 4px; }
}

.config-form {
  max-width: 860px;

  .api-key-row {
    display: flex;
    gap: 8px;
    align-items: center;
    width: 100%;
    .api-key-input { flex: 1; }
  }

  .field-hint {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
    line-height: 1.4;

    code {
      background: rgba(79, 70, 229, 0.08);
      color: var(--primary-color);
      padding: 1px 5px;
      border-radius: 3px;
      font-family: monospace;
    }
  }

  .slider-row {
    width: 100%;
    .config-slider {
      width: 100%;
      :deep(.el-slider__runway) { margin: 8px 0; }
    }
  }

  .form-actions {
    display: flex;
    gap: 12px;
    margin-top: 4px;
  }
}

/* Sessions */
.sessions-card {
  padding: 20px 24px;
}

.session-id-text {
  font-family: monospace;
  font-size: 11px;
  color: var(--text-muted);
}

.session-title {
  font-weight: 500;
  color: var(--text-main);
}

/* History Dialog */
.history-dialog :deep(.el-dialog__body) {
  padding: 16px 20px;
  max-height: 60vh;
  overflow-y: auto;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 100px;
}

.history-msg {
  display: flex;
  flex-direction: column;
  gap: 6px;

  &.user { align-items: flex-end; }
  &.assistant { align-items: flex-start; }
  .role-tag { align-self: flex-start; }
  &.user .role-tag { align-self: flex-end; }

  .msg-content {
    max-width: 90%;
    padding: 10px 14px;
    border-radius: 10px;
    font-size: 13px;
    line-height: 1.6;
    word-break: break-word;
    background: rgba(248, 250, 252, 0.95);
    border: 1px solid var(--border-light);

    :deep(p) { margin: 0 0 4px; }
    :deep(p:last-child) { margin: 0; }
    :deep(strong) { color: var(--text-main); }
    :deep(code) { background: rgba(79, 70, 229, 0.1); color: var(--primary-color); padding: 1px 4px; border-radius: 3px; }
  }

  &.user .msg-content {
    background: var(--primary-color);
    color: #fff;
    border-color: transparent;
    :deep(strong) { color: #fff; }
    :deep(code) { background: rgba(255,255,255,0.2); color: #fff; }
  }
}

/* Dark mode */
html.dark {
  .stat-card {
    background: var(--bg-card);
    border-color: rgba(255, 255, 255, 0.08);
  }
  .history-msg .msg-content {
    background: rgba(30, 41, 59, 0.85);
    border-color: rgba(255, 255, 255, 0.08);
  }
}
</style>
