<template>
  <div class="ai-sprite-wrapper">
    <!-- Floating 3D Sprite Trigger Bubble -->
    <transition name="sprite-trigger">
    <div
      v-if="!isOpen"
      class="ai-sprite-trigger flex-center"
      :class="[currentVisualState, { 'is-pulsing': !hasOpenedOnce }]"
      @click="handleTriggerClick"
      @mouseenter="onHoverTrigger"
      @mouseleave="onLeaveTrigger"
      title="AIPM 智能小精灵 (3D 粒子流光体)"
    >
      <div class="sprite-halo"></div>
      <div class="sprite-3d-box">
        <AetherSpriteCanvas
          ref="sprite3DRef"
          mode="mini"
          :state="currentVisualState"
          theme="nebula"
          :interactive="true"
        />
      </div>
      <span class="sprite-badge">3D AI</span>
    </div>
    </transition>

    <!-- Chat Panel -->
    <transition name="sprite-panel">
      <div v-if="isOpen" class="ai-chat-panel vben-card">
        <!-- Panel Header -->
        <div class="panel-header flex-between">
          <div class="header-left flex-center">
            <div class="header-bot-icon flex-center">
              <AetherSpriteCanvas
                mode="mini"
                :state="isThinking ? 'thinking' : (isStreaming ? 'typing' : 'idle')"
                theme="nebula"
                :interactive="false"
                class="header-mini-sprite"
              />
            </div>
            <div class="header-meta">
              <div class="meta-title flex-center">
                <span>AIPM 智能小精灵</span>
                <span
                  class="model-tag"
                  v-if="capabilities?.model_name"
                  :title="`${capabilities?.provider || 'DeepSeek'} · ${capabilities.model_name}`"
                >{{ capabilities.model_name }}</span>
                <span class="status-dot" :class="capabilities?.is_deepseek_configured ? 'online' : 'offline'" :title="capabilities?.is_deepseek_configured ? 'AI 已连接' : 'AI 离线 (本地模式)'"></span>
              </div>
              <div class="meta-subtitle">
                <span>身份: {{ capabilities?.nickname || userStore.username }}</span>
                <span class="dot-separator">•</span>
                <span>可控权限 ({{ capabilities?.accessible_projects_count || 1 }}个项目)</span>
              </div>
            </div>
          </div>

          <div class="header-actions flex-center">
            <el-icon class="action-btn" title="清空上下文" @click="clearMessages"><Delete /></el-icon>
            <el-icon class="action-btn" title="最小化" @click="toggleOpen"><Minus /></el-icon>
          </div>
        </div>

        <!-- Role Context & Permission Notice Bar -->
        <div class="permission-notice-bar flex-between">
          <span>🔒 已启用 RBAC 权限隔离机制，仅检索您授权的项目与工时</span>
          <el-tag size="small" type="info" effect="plain" class="role-chip">
            {{ capabilities?.roles?.[0] || '研发' }}
          </el-tag>
        </div>

        <!-- Chat Messages Scroll Area -->
        <div class="messages-container" ref="messagesContainerRef">
          <div v-for="(msg, idx) in messages" :key="idx" class="message-row" :class="msg.role">
            <!-- Bot Avatar -->
            <div v-if="msg.role === 'assistant'" class="msg-avatar bot flex-center">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
                <path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-1H2a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 0 1 2-2zM7.5 13a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3zm9 0a1.5 1.5 0 1 0 0 3 1.5 1.5 0 0 0 0-3z"/>
              </svg>
            </div>

            <!-- Message Bubble -->
            <div class="message-bubble" :class="msg.role">
              <!-- Markdown Rendered Content -->
              <div v-if="msg.role === 'assistant'" class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
              <div v-else class="user-text">{{ msg.content }}</div>

              <!-- Typing Blinking Indicator -->
              <span v-if="msg.role === 'assistant' && isStreaming && idx === messages.length - 1" class="typing-cursor"></span>
            </div>

            <!-- User Avatar -->
            <div v-if="msg.role === 'user'" class="msg-avatar user flex-center">
              <el-avatar :size="28" :src="userStore.userAvatar" />
            </div>
          </div>

          <!-- Thinking Spinner when awaiting first token -->
          <div v-if="isThinking" class="message-row assistant">
            <div class="msg-avatar bot flex-center">
              <el-icon class="is-loading"><Loading /></el-icon>
            </div>
            <div class="message-bubble assistant thinking-bubble flex-center">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="thinking-label">DeepSeek 正在结合您的权限检索数据...</span>
            </div>
          </div>
        </div>

        <!-- Quick Prompt Chips -->
        <div class="prompt-chips-wrapper" v-if="capabilities?.prompt_chips?.length">
          <div
            v-for="(chip, cIdx) in capabilities.prompt_chips"
            :key="cIdx"
            class="prompt-chip"
            @click="sendPrompt(chip)"
          >
            {{ chip }}
          </div>
        </div>

        <!-- Input Box Area -->
        <div class="chat-input-area">
          <div class="input-container">
            <el-input
              v-model="inputQuery"
              type="textarea"
              :rows="2"
              resize="none"
              placeholder="向 AI 小精灵提问，如：分析项目风险 / 查询我的待办 / 帮我创建任务..."
              @keydown.enter.prevent="handleEnter"
            />
            <div class="input-actions flex-between">
              <span class="key-hint">按 Enter 发送，Shift+Enter 换行</span>
              <el-button
                type="primary"
                size="small"
                :loading="isStreaming || isThinking"
                :disabled="!inputQuery.trim()"
                @click="handleSubmit"
              >
                <template #icon><Promotion /></template>
                发送
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick, computed } from 'vue'
import { useUserStore } from '@/store/modules/user'
import {
  getAICapabilitiesApi, createSessionApi, streamAIChatApi,
  type AICapabilities
} from '@/api/ai'
import { Delete, Minus, Promotion, Loading } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import AetherSpriteCanvas from '@/components/AetherSprite/AetherSpriteCanvas.vue'

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true
})

const userStore = useUserStore()
const isOpen = ref(false)
const hasOpenedOnce = ref(false)
const spriteState = ref<'idle' | 'curious' | 'thinking' | 'typing' | 'bouncy'>('idle')
const isHovered = ref(false)
const sprite3DRef = ref<InstanceType<typeof AetherSpriteCanvas>>()
const capabilities = ref<AICapabilities | null>(null)
const messagesContainerRef = ref<HTMLElement>()
const currentSessionId = ref<string | null>(null)

const inputQuery = ref('')
const isThinking = ref(false)
const isStreaming = ref(false)

const currentVisualState = computed<'idle' | 'curious' | 'thinking' | 'typing' | 'bouncy'>(() => {
  if (isThinking.value) return 'thinking'
  if (isStreaming.value) return 'typing'
  if (isHovered.value) return 'curious'
  return spriteState.value
})

function onHoverTrigger() {
  isHovered.value = true
}

function onLeaveTrigger() {
  isHovered.value = false
}

function handleTriggerClick() {
  sprite3DRef.value?.triggerBounce()
  setTimeout(() => {
    toggleOpen()
  }, 120)
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

const messages = reactive<ChatMessage[]>([])

function renderMarkdown(raw: string): string {
  return md.render(raw || '')
}

async function loadCapabilities() {
  try {
    const res = await getAICapabilitiesApi()
    capabilities.value = res.data

    // Restore most recent session or create a new one
    if (res.data.current_session_id) {
      currentSessionId.value = res.data.current_session_id
    } else {
      const sessRes = await createSessionApi()
      currentSessionId.value = sessRes.data.session_id
    }

    // Initial welcome message
    if (messages.length === 0) {
      messages.push({
        role: 'assistant',
        content: `👋 **你好，${res.data.nickname}！我是您的 AIPM 智能项目小精灵** 🧚✨\n\n我已根据您的账号角色绑定了权限范围，可以帮您**查询名下任务、分析项目风险、检索工时或协助创建任务**。\n\n请点击下方快捷指令或直接向我提问！`
      })
    }
  } catch (e) {
    // ignore
  }
}

function toggleOpen() {
  isOpen.value = !isOpen.value
  if (isOpen.value) {
    hasOpenedOnce.value = true
    if (!capabilities.value) {
      loadCapabilities()
    }
    scrollToBottom()
  }
}

async function clearMessages() {
  messages.length = 0
  // Create a fresh session
  try {
    const sessRes = await createSessionApi()
    currentSessionId.value = sessRes.data.session_id
  } catch (e) {
    currentSessionId.value = null
  }
  if (capabilities.value) {
    messages.push({
      role: 'assistant',
      content: `🧹 **上下文已清空，已开启新的对话**。我是您的智能助手，随时听候您的指令！`
    })
  }
}

function sendPrompt(prompt: string) {
  // Strip icon prefix if any
  const cleanPrompt = prompt.replace(/^[\p{Emoji}\s]+/u, '')
  inputQuery.value = cleanPrompt
  handleSubmit()
}

function handleEnter(e: KeyboardEvent) {
  if (!e.shiftKey) {
    handleSubmit()
  }
}

async function handleSubmit() {
  const query = inputQuery.value.trim()
  if (!query || isStreaming.value || isThinking.value) return

  inputQuery.value = ''
  messages.push({ role: 'user', content: query })
  scrollToBottom()

  isThinking.value = true
  spriteState.value = 'thinking'

  // Prepare history (last 4 items)
  const historyPayload = messages.slice(0, -1).map(m => ({ role: m.role, content: m.content }))

  // Prepare placeholder assistant message
  let currentAssistantMsgIndex = -1

  await streamAIChatApi(query, {
    sessionId: currentSessionId.value,
    history: historyPayload,
    onToken: (token: string) => {
      if (isThinking.value) {
        isThinking.value = false
        isStreaming.value = true
        spriteState.value = 'typing'
        messages.push({ role: 'assistant', content: token })
        currentAssistantMsgIndex = messages.length - 1
      } else if (currentAssistantMsgIndex >= 0) {
        messages[currentAssistantMsgIndex].content += token
      }
      scrollToBottom()
    },
    onFinish: () => {
      isThinking.value = false
      isStreaming.value = false
      spriteState.value = 'idle'
      scrollToBottom()
    },
    onError: (err: any) => {
      isThinking.value = false
      isStreaming.value = false
      spriteState.value = 'idle'
      messages.push({
        role: 'assistant',
        content: `⚠️ 对话服务暂时异常: ${err.message || '网络连接失败，请稍后重试'}`
      })
      scrollToBottom()
    }
  })
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesContainerRef.value) {
      messagesContainerRef.value.scrollTop = messagesContainerRef.value.scrollHeight
    }
  })
}

onMounted(() => {
  loadCapabilities()
})
</script>

<style scoped lang="scss">
.ai-sprite-wrapper {
  position: fixed;
  bottom: 28px;
  right: 28px;
  z-index: 1800;
  user-select: none;
}

/* Floating Sprite Trigger Bubble */
.ai-sprite-trigger {
  width: 68px;
  height: 68px;
  border-radius: 50%;
  background: radial-gradient(circle at center, rgba(30, 27, 75, 0.95) 0%, rgba(15, 23, 42, 0.95) 100%);
  box-shadow: 0 10px 30px rgba(79, 70, 229, 0.45), 0 0 0 1.5px rgba(255, 255, 255, 0.25);
  cursor: pointer;
  position: relative;
  transition: transform 0.2s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;

  &:hover {
    transform: scale(1.06) translateY(-2px);
    box-shadow: 0 14px 32px rgba(47, 84, 232, 0.5), 0 0 0 1.5px rgba(255, 255, 255, 0.32);
  }

  &.is-pulsing {
    animation: spritePulse 2.4s infinite;
  }

  .sprite-3d-box {
    width: 68px;
    height: 68px;
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: auto;
  }

  .sprite-badge {
    position: absolute;
    top: -3px;
    right: -3px;
    background: linear-gradient(135deg, #f43f5e, #ec4899);
    color: #ffffff;
    font-size: 10px;
    font-weight: 800;
    padding: 1px 6px;
    border-radius: 10px;
    border: 1.5px solid #ffffff;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.25);
    letter-spacing: 0.5px;
  }
}

.header-mini-sprite {
  width: 38px;
  height: 38px;
  overflow: visible;
}

/* Glassmorphic Chat Panel */
.ai-chat-panel {
  width: 440px;
  height: 600px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: absolute;
  bottom: 0;
  right: 0;
  /* 面板从气泡所在位置展开，而不是从中心弹出 */
  transform-origin: bottom right;

  .panel-header {
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-color);
    background: rgba(255, 255, 255, 0.5);

    .header-bot-icon {
      width: 34px;
      height: 34px;
      border-radius: 50%;
      background: linear-gradient(135deg, #4F46E5, #06B6D4);
      color: #ffffff;
      margin-right: 10px;
    }

    .header-meta {
      .meta-title {
        gap: 8px;
        font-size: 15px;
        font-weight: 700;
        color: var(--text-main);

        .model-tag {
          font-size: 10px;
          background: rgba(79, 70, 229, 0.12);
          color: var(--primary-color);
          padding: 1px 6px;
          border-radius: 4px;
          font-weight: 700;
        }

        .status-dot {
          width: 7px;
          height: 7px;
          border-radius: 50%;
          flex-shrink: 0;
          &.online {
            background: #22c55e;
            box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.25);
            animation: statusPulse 2.5s infinite;
          }
          &.offline {
            background: #f59e0b;
            box-shadow: 0 0 0 2px rgba(245, 158, 11, 0.25);
          }
        }
      }

      .meta-subtitle {
        font-size: 11px;
        color: var(--text-muted);
        display: flex;
        align-items: center;
        gap: 6px;

        .dot-separator {
          opacity: 0.5;
        }
      }
    }

    .header-actions {
      gap: 8px;

      .action-btn {
        font-size: 16px;
        color: var(--text-muted);
        cursor: pointer;
        padding: 4px;
        border-radius: var(--radius-xs);
        transition: all 0.2s;

        &:hover {
          color: var(--primary-color);
          background: rgba(79, 70, 229, 0.08);
        }
      }
    }
  }

  .permission-notice-bar {
    padding: 6px 14px;
    background: rgba(79, 70, 229, 0.06);
    border-bottom: 1px solid rgba(79, 70, 229, 0.1);
    font-size: 11px;
    color: var(--text-regular);
    font-weight: 500;

    .role-chip {
      font-weight: 600;
    }
  }

  .messages-container {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 14px;

    .message-row {
      display: flex;
      gap: 10px;
      align-items: flex-start;

      &.user {
        justify-content: flex-end;
      }

      &.assistant {
        justify-content: flex-start;
      }

      .msg-avatar {
        width: 28px;
        height: 28px;
        border-radius: 50%;
        flex-shrink: 0;

        &.bot {
          background: linear-gradient(135deg, #4F46E5, #8B5CF6);
          color: #ffffff;
        }
      }

      .message-bubble {
        max-width: 82%;
        padding: 10px 14px;
        border-radius: var(--radius-md);
        font-size: 13px;
        line-height: 1.6;
        word-break: break-word;

        &.user {
          background: var(--primary-color);
          color: #ffffff;
          border-bottom-right-radius: 2px;
          box-shadow: 0 4px 12px rgba(79, 70, 229, 0.25);
        }

        &.assistant {
          background: rgba(248, 250, 252, 0.95);
          color: var(--text-main);
          border: 1px solid var(--border-light);
          border-bottom-left-radius: 2px;
          box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);

          &.thinking-bubble {
            display: flex;
            align-items: center;
            gap: 6px;
            color: var(--text-muted);
            font-size: 12px;

            .dot {
              width: 5px;
              height: 5px;
              background: var(--primary-color);
              border-radius: 50%;
              animation: bounce 1.4s infinite ease-in-out both;

              &:nth-child(1) { animation-delay: -0.32s; }
              &:nth-child(2) { animation-delay: -0.16s; }
            }
          }
        }

        .typing-cursor {
          display: inline-block;
          width: 3px;
          height: 14px;
          background: var(--primary-color);
          vertical-align: middle;
          margin-left: 2px;
          animation: blink 0.8s infinite;
        }
      }
    }
  }

  .prompt-chips-wrapper {
    padding: 6px 14px;
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    border-top: 1px dashed var(--border-light);
    background: rgba(255, 255, 255, 0.4);

    .prompt-chip {
      font-size: 11px;
      font-weight: 500;
      color: var(--primary-color);
      background: rgba(79, 70, 229, 0.08);
      border: 1px solid rgba(79, 70, 229, 0.2);
      padding: 3px 10px;
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        background: var(--primary-color);
        color: #ffffff;
        transform: translateY(-1px);
        box-shadow: 0 2px 6px rgba(79, 70, 229, 0.25);
      }
    }
  }

  .chat-input-area {
    padding: 12px 14px;
    border-top: 1px solid var(--border-light);
    background: rgba(255, 255, 255, 0.7);

    .input-container {
      :deep(.el-textarea__inner) {
        background: rgba(255, 255, 255, 0.8);
        border: 1px solid var(--border-light);
        border-radius: var(--radius-sm);
        font-size: 13px;
        padding: 8px 10px;

        &:focus {
          border-color: var(--primary-color);
          box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.15);
        }
      }

      .input-actions {
        margin-top: 8px;

        .key-hint {
          font-size: 11px;
          color: var(--text-muted);
        }
      }
    }
  }
}

/* Animations */

/* 面板：从右下角"长"出来，进入稍慢、离开更快（更跟手） */
.sprite-panel-enter-active {
  transition: opacity 0.2s ease,
    transform 0.26s cubic-bezier(0.16, 1, 0.3, 1);
}

.sprite-panel-leave-active {
  transition: opacity 0.15s ease,
    transform 0.18s cubic-bezier(0.4, 0, 1, 1);
}

.sprite-panel-enter-from {
  opacity: 0;
  transform: scale(0.94) translateY(10px);
}

.sprite-panel-leave-to {
  opacity: 0;
  transform: scale(0.97) translateY(4px);
}

/* 气泡：与面板交叉过渡，视觉上像"气泡撑开成面板" */
.sprite-trigger-enter-active {
  transition: opacity 0.18s ease,
    transform 0.24s cubic-bezier(0.16, 1, 0.3, 1);
}

.sprite-trigger-leave-active {
  transition: opacity 0.12s ease,
    transform 0.16s cubic-bezier(0.4, 0, 1, 1);
}

.sprite-trigger-enter-from,
.sprite-trigger-leave-to {
  opacity: 0;
  transform: scale(0.86);
}

@keyframes spritePulse {
  0% { box-shadow: 0 0 0 0 rgba(79, 70, 229, 0.6); }
  70% { box-shadow: 0 0 0 14px rgba(79, 70, 229, 0); }
  100% { box-shadow: 0 0 0 0 rgba(79, 70, 229, 0); }
}

@keyframes statusPulse {
  0% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.5); }
  70% { box-shadow: 0 0 0 5px rgba(34, 197, 94, 0); }
  100% { box-shadow: 0 0 0 0 rgba(34, 197, 94, 0); }
}

@keyframes sparkle {
  from { transform: scale(0.6); opacity: 0.4; }
  to { transform: scale(1.3); opacity: 1; }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* Markdown typography inside bubble */
:deep(.markdown-body) {
  font-size: 13px;
  line-height: 1.6;

  p { margin-bottom: 6px; }
  p:last-child { margin-bottom: 0; }
  strong { font-weight: 700; color: var(--text-main); }
  ul, ol { padding-left: 18px; margin-bottom: 6px; }
  li { margin-bottom: 2px; }
  code {
    background: rgba(79, 70, 229, 0.1);
    color: var(--primary-color);
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 12px;
  }
}

/* Dark mode overrides */
html.dark {
  .ai-chat-panel {
    background: rgba(17, 24, 39, 0.88);
    border-color: rgba(255, 255, 255, 0.12);

    .panel-header {
      background: rgba(17, 24, 39, 0.6);
      border-color: rgba(255, 255, 255, 0.08);
    }

    .messages-container .message-row .message-bubble.assistant {
      background: rgba(30, 41, 59, 0.85);
      border-color: rgba(255, 255, 255, 0.08);
    }

    .prompt-chips-wrapper {
      background: rgba(17, 24, 39, 0.5);
      border-color: rgba(255, 255, 255, 0.08);
    }

    .chat-input-area {
      background: rgba(17, 24, 39, 0.7);
      border-color: rgba(255, 255, 255, 0.08);

      .input-container :deep(.el-textarea__inner) {
        background: rgba(30, 41, 59, 0.8);
        border-color: rgba(255, 255, 255, 0.1);
        color: #ffffff;
      }
    }
  }
}
</style>
