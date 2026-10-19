<template>
  <div class="aether-sprite-lab">
    <!-- Top Header Banner -->
    <div class="lab-header">
      <div class="header-content flex-between">
        <div>
          <h1 class="lab-title">
            <span class="gradient-text">Aether Sprite</span> 3D 拟生粒子小精灵实验室
          </h1>
          <p class="lab-desc">
            基于 Simplex 空间噪声形变、二阶阻尼弹簧体积守恒 (Squash & Stretch) 与 Curl 旋度粒子场构建的拟生 3D 生灵
          </p>
        </div>
        <div class="header-tags">
          <el-tag effect="dark" type="success" round>WebGL 60FPS</el-tag>
          <el-tag effect="dark" type="warning" round>Shader + Physics</el-tag>
          <el-tag effect="dark" type="primary" round>DeepSeek 伴生体</el-tag>
        </div>
      </div>
    </div>

    <!-- Main Workspace Grid -->
    <div class="lab-grid">
      <!-- Left: 3D Stage Card -->
      <div class="stage-card">
        <div class="stage-toolbar flex-between">
          <div class="status-indicator flex-center">
            <span class="pulse-dot" :class="currentState"></span>
            <span class="status-name">当前状态: {{ stateLabels[currentState] }}</span>
          </div>
          <div class="stage-hints">
            <span>🖱️ 移动鼠标凝视 · 点击小精灵起跳 · 拖拽感受惯性</span>
          </div>
        </div>

        <div class="stage-canvas-wrapper">
          <AetherSpriteCanvas
            ref="stageSpriteRef"
            mode="fullscreen"
            :state="currentState"
            :theme="currentTheme"
            :interactive="true"
            :noise-strength="noiseStrength"
            :spring-stiffness="springStiffness"
            :spring-damping="springDamping"
            :particle-count="particleCount"
          />
        </div>

        <!-- Quick Emotion Action Buttons -->
        <div class="stage-actions">
          <el-button-group>
            <el-button
              :type="currentState === 'idle' ? 'primary' : 'default'"
              @click="setState('idle')"
            >
              🌿 闲置呼吸 (Idle)
            </el-button>
            <el-button
              :type="currentState === 'curious' ? 'primary' : 'default'"
              @click="setState('curious')"
            >
              👀 好奇探视 (Curious)
            </el-button>
            <el-button
              type="danger"
              @click="triggerJump"
            >
              ⚡ 弹性起跳 (Bounce)
            </el-button>
            <el-button
              :type="currentState === 'thinking' ? 'primary' : 'default'"
              @click="setState('thinking')"
            >
              🧠 深度思考 (Thinking)
            </el-button>
            <el-button
              :type="currentState === 'typing' ? 'primary' : 'default'"
              @click="setState('typing')"
            >
              ✨ 星尘脉冲 (Pulse)
            </el-button>
          </el-button-group>
        </div>
      </div>

      <!-- Right: Control Panel & Physics Insights -->
      <div class="control-card">
        <el-tabs v-model="activeTab" class="lab-tabs">
          <!-- Tab 1: 视觉与情绪调控 -->
          <el-tab-pane label="🎨 视觉与形态" name="visual">
            <div class="control-group">
              <div class="group-title">主题色调 (Theme Palette)</div>
              <div class="theme-picker-grid">
                <div
                  v-for="t in themeOptions"
                  :key="t.key"
                  class="theme-card"
                  :class="{ 'is-active': currentTheme === t.key }"
                  @click="currentTheme = t.key"
                >
                  <div class="theme-preview" :style="{ background: t.gradient }"></div>
                  <span class="theme-name">{{ t.name }}</span>
                </div>
              </div>
            </div>

            <div class="control-group">
              <div class="group-title">流体果冻扰动 (Simplex Noise Strength)</div>
              <div class="slider-row">
                <el-slider
                  v-model="noiseStrength"
                  :min="0.02"
                  :max="0.35"
                  :step="0.01"
                  show-input
                />
              </div>
              <p class="param-tip">控制表皮网格沿法线位移的幅度，越高越呈现液态史莱姆/水母质感。</p>
            </div>

            <div class="control-group">
              <div class="group-title">伴生星尘微粒数 (Particle Swarm Density)</div>
              <div class="slider-row">
                <el-slider
                  v-model="particleCount"
                  :min="300"
                  :max="2500"
                  :step="100"
                  show-input
                />
              </div>
              <p class="param-tip">外围受 Curl 旋度场支配的星尘微粒总数。</p>
            </div>
          </el-tab-pane>

          <!-- Tab 2: 弹簧阻尼与物理力学 -->
          <el-tab-pane label="⚙️ 物理力学与弹簧" name="physics">
            <div class="control-group">
              <div class="group-title">弹簧刚度 (Spring Stiffness - k)</div>
              <div class="slider-row">
                <el-slider
                  v-model="springStiffness"
                  :min="40"
                  :max="300"
                  :step="5"
                  show-input
                />
              </div>
              <p class="param-tip">决定跳跃与形变时的复原加速度，刚度越高跳跃回弹越迅猛。</p>
            </div>

            <div class="control-group">
              <div class="group-title">阻尼系数 (Damping - c)</div>
              <div class="slider-row">
                <el-slider
                  v-model="springDamping"
                  :min="3"
                  :max="25"
                  :step="0.5"
                  show-input
                />
              </div>
              <p class="param-tip">控制能量衰减速度，阻尼过小会持续抖动，阻尼过大则回弹迟缓。</p>
            </div>

            <div class="math-card">
              <div class="math-title">📐 物理与数学核心方程</div>
              <ul class="math-list">
                <li>
                  <strong>体积守恒 (Squash & Stretch):</strong>
                  <code>S_x = S_z = 1 / sqrt(S_y)</code>
                </li>
                <li>
                  <strong>二阶阻尼弹簧 (Harmonic Oscillator):</strong>
                  <code>F = -k(y - y_0) - c · v_y</code>
                </li>
                <li>
                  <strong>旋度涡流场 (Curl Noise Incompressibility):</strong>
                  <code>∇ · v = 0, v = ∇ × Ψ</code>
                </li>
                <li>
                  <strong>仿生微扫视 (Microsaccades):</strong>
                  <code>Δθ ~ Gaussian(0, σ), Δt ~ Exp(λ)</code>
                </li>
              </ul>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import AetherSpriteCanvas from '@/components/AetherSprite/AetherSpriteCanvas.vue'

const stageSpriteRef = ref<InstanceType<typeof AetherSpriteCanvas>>()
const activeTab = ref('visual')
const currentState = ref<'idle' | 'curious' | 'thinking' | 'typing' | 'bouncy'>('idle')
const currentTheme = ref<'nebula' | 'aurora' | 'sunset' | 'cyber' | 'gold'>('nebula')

const noiseStrength = ref(0.14)
const springStiffness = ref(130)
const springDamping = ref(11)
const particleCount = ref(1200)

const stateLabels: Record<string, string> = {
  idle: '平静呼吸 (Idle)',
  curious: '好奇注视 (Curious)',
  thinking: '深度思考中 (Thinking)',
  typing: '星尘脉冲 (Typing)',
  bouncy: '弹性跳跃 (Bouncy)'
}

interface ThemeItem {
  key: 'nebula' | 'aurora' | 'sunset' | 'cyber' | 'gold'
  name: string
  gradient: string
}

const themeOptions: ThemeItem[] = [
  { key: 'nebula', name: '极光星云 (Nebula)', gradient: 'linear-gradient(135deg, #4f46e5, #06b6d4)' },
  { key: 'aurora', name: '极地翡翠 (Aurora)', gradient: 'linear-gradient(135deg, #059669, #22d3ee)' },
  { key: 'sunset', name: '晚霞烈阳 (Sunset)', gradient: 'linear-gradient(135deg, #db2777, #f59e0b)' },
  { key: 'cyber', name: '赛博霓虹 (Cyber)', gradient: 'linear-gradient(135deg, #2563eb, #f43f5e)' },
  { key: 'gold', name: '耀世金芒 (Gold)', gradient: 'linear-gradient(135deg, #d97706, #facc15)' }
]

function setState(s: 'idle' | 'curious' | 'thinking' | 'typing' | 'bouncy') {
  currentState.value = s
  if (s === 'typing') {
    stageSpriteRef.value?.triggerPulse()
  }
}

function triggerJump() {
  currentState.value = 'bouncy'
  stageSpriteRef.value?.triggerBounce(4.8)
}

function handleStageClick() {
  triggerJump()
}
</script>

<style scoped lang="scss">
.aether-sprite-lab {
  padding: 24px;
  min-height: calc(100vh - 90px);
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.lab-header {
  background: linear-gradient(135deg, rgba(30, 27, 75, 0.85) 0%, rgba(15, 23, 42, 0.9) 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  padding: 20px 24px;
  border-radius: var(--radius-lg, 16px);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2);

  .lab-title {
    font-size: 22px;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 6px;

    .gradient-text {
      background: linear-gradient(135deg, #818cf8, #38bdf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
  }

  .lab-desc {
    font-size: 13px;
    color: #94a3b8;
    line-height: 1.5;
  }

  .header-tags {
    display: flex;
    gap: 8px;
  }
}

.lab-grid {
  display: grid;
  grid-template-columns: 1.3fr 1fr;
  gap: 20px;
  flex: 1;

  @media (max-width: 1024px) {
    grid-template-columns: 1fr;
  }
}

.stage-card {
  background: radial-gradient(circle at center, #0f1123 0%, #05060a 100%);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-lg, 16px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 16px 40px rgba(0, 0, 0, 0.35);
  position: relative;

  .stage-toolbar {
    padding: 14px 20px;
    background: rgba(255, 255, 255, 0.03);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);

    .status-indicator {
      gap: 10px;
      font-size: 13px;
      font-weight: 600;
      color: #f1f5f9;

      .pulse-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #22c55e;
        box-shadow: 0 0 10px #22c55e;
        animation: dotPulse 2s infinite;

        &.thinking { background: #f59e0b; box-shadow: 0 0 10px #f59e0b; }
        &.typing { background: #ec4899; box-shadow: 0 0 10px #ec4899; }
        &.bouncy { background: #38bdf8; box-shadow: 0 0 10px #38bdf8; }
      }
    }

    .stage-hints {
      font-size: 11px;
      color: #64748b;
      letter-spacing: 0.5px;
    }
  }

  .stage-canvas-wrapper {
    flex: 1;
    min-height: 480px;
    height: 520px;
    width: 100%;
    position: relative;
    cursor: grab;
    display: flex;
    flex-direction: column;

    &:active {
      cursor: grabbing;
    }
  }

  .stage-actions {
    padding: 16px 20px;
    background: rgba(255, 255, 255, 0.03);
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    justify-content: center;
  }
}

.control-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: var(--radius-lg, 16px);
  padding: 20px;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.08);

  .control-group {
    margin-bottom: 22px;

    .group-title {
      font-size: 14px;
      font-weight: 700;
      color: var(--text-main, #1e293b);
      margin-bottom: 10px;
    }

    .param-tip {
      font-size: 11px;
      color: #64748b;
      margin-top: 4px;
    }
  }

  .theme-picker-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 10px;

    .theme-card {
      padding: 8px;
      border-radius: 10px;
      border: 1.5px solid transparent;
      background: rgba(241, 245, 249, 0.7);
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s;

      &:hover {
        transform: translateY(-2px);
        background: #ffffff;
      }

      &.is-active {
        border-color: var(--primary-color, #4f46e5);
        background: #ffffff;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.15);
      }

      .theme-preview {
        width: 22px;
        height: 22px;
        border-radius: 50%;
        flex-shrink: 0;
      }

      .theme-name {
        font-size: 12px;
        font-weight: 600;
        color: #334155;
      }
    }
  }

  .math-card {
    background: #0f172a;
    border-radius: 12px;
    padding: 16px;
    color: #e2e8f0;
    margin-top: 16px;

    .math-title {
      font-size: 13px;
      font-weight: 700;
      color: #38bdf8;
      margin-bottom: 10px;
    }

    .math-list {
      list-style: none;
      padding: 0;
      margin: 0;
      display: flex;
      flex-direction: column;
      gap: 10px;
      font-size: 12px;

      li {
        line-height: 1.5;

        strong {
          color: #f1f5f9;
          display: block;
          margin-bottom: 2px;
        }

        code {
          background: rgba(255, 255, 255, 0.1);
          padding: 2px 6px;
          border-radius: 4px;
          color: #a5f3fc;
          font-family: monospace;
          font-size: 11px;
        }
      }
    }
  }
}

@keyframes dotPulse {
  0% { transform: scale(0.95); opacity: 0.8; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.95); opacity: 0.8; }
}

html.dark {
  .control-card {
    background: rgba(17, 24, 39, 0.85);
    border-color: rgba(255, 255, 255, 0.08);

    .control-group .group-title {
      color: #f1f5f9;
    }

    .theme-picker-grid .theme-card {
      background: rgba(30, 41, 59, 0.7);

      .theme-name {
        color: #e2e8f0;
      }

      &.is-active {
        background: #1e293b;
      }
    }
  }
}
</style>
