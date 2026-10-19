<template>
  <div v-if="visible" class="slider-captcha-overlay" @click.self="handleClose">
    <div class="slider-captcha-box vben-card" :class="{ 'is-shaking': isFailed }">
      <!-- Modal Header -->
      <div class="captcha-header flex-between">
        <span class="captcha-title">安全人机验证</span>
        <div class="captcha-actions flex-center">
          <el-icon class="action-icon" :class="{ 'is-spinning': loading }" @click="fetchCaptcha">
            <Refresh />
          </el-icon>
          <el-icon class="action-icon" @click="handleClose">
            <Close />
          </el-icon>
        </div>
      </div>

      <!-- Puzzle Image Canvas Container (320px x 160px) -->
      <div class="captcha-img-wrapper" v-loading="loading">
        <!-- Background Image with notch -->
        <img
          v-if="captchaData?.bg_image"
          :src="captchaData.bg_image"
          class="captcha-bg-img"
          alt="captcha background"
        />

        <!-- Draggable Jigsaw Piece -->
        <img
          v-if="captchaData?.slider_image"
          :src="captchaData.slider_image"
          class="captcha-slider-piece"
          :style="{
            top: `${captchaData.y}px`,
            left: `${sliderX}px`,
            width: `${captchaData.block_width}px`,
            height: `${captchaData.block_height}px`
          }"
          alt="slider piece"
        />

        <!-- Status Toast Banner -->
        <div v-if="statusText" class="captcha-status-banner" :class="isSuccess ? 'success' : 'fail'">
          <span>{{ statusText }}</span>
        </div>
      </div>

      <!-- Draggable Slider Track -->
      <div class="slider-track-container" ref="trackRef">
        <!-- Progress Bar -->
        <div
          class="slider-progress-bar"
          :class="{ success: isSuccess, fail: isFailed }"
          :style="{ width: `${sliderX + 24}px` }"
        ></div>

        <!-- Track Placeholder Tip -->
        <span class="slider-tip-text" :style="{ opacity: sliderX > 10 ? 0 : 1 }">
          向右拖动滑块完成拼图
        </span>

        <!-- Drag Handle Knob -->
        <div
          class="slider-handle-knob"
          :class="{ active: isDragging, success: isSuccess, fail: isFailed }"
          :style="{ left: `${sliderX}px` }"
          @mousedown="startDrag"
          @touchstart="startDrag"
        >
          <el-icon v-if="!isSuccess && !isFailed"><DArrowRight /></el-icon>
          <el-icon v-else-if="isSuccess"><Check /></el-icon>
          <el-icon v-else><Close /></el-icon>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch, onUnmounted } from 'vue'
import { getSliderCaptchaApi, verifySliderCaptchaApi, type SliderCaptchaData } from '@/api/auth'
import { Refresh, Close, DArrowRight, Check } from '@element-plus/icons-vue'

const props = defineProps<{
  visible: boolean
}>()

const emit = defineEmits<{
  (e: 'success', token: string): void
  (e: 'close'): void
}>()

const loading = ref(false)
const captchaData = ref<SliderCaptchaData | null>(null)
const sliderX = ref(0)
const isDragging = ref(false)
const isSuccess = ref(false)
const isFailed = ref(false)
const statusText = ref('')
const trackRef = ref<HTMLElement>()

// Trajectory recording array: [[x, y, timestamp_ms], ...]
let trackData: Array<[number, number, number]> = []
let startPageX = 0
let startPageY = 0
let startTime = 0
const MAX_DRAG_WIDTH = 320 - 58 // 320 - full_block_w

async function fetchCaptcha() {
  loading.value = true
  isSuccess.value = false
  isFailed.value = false
  statusText.value = ''
  sliderX.value = 0
  trackData = []
  try {
    const res = await getSliderCaptchaApi()
    captchaData.value = res.data
  } finally {
    loading.value = false
  }
}

watch(
  () => props.visible,
  (val) => {
    if (val) {
      fetchCaptcha()
    }
  }
)

function startDrag(e: MouseEvent | TouchEvent) {
  if (loading.value || isSuccess.value) return
  isDragging.value = true
  isFailed.value = false
  statusText.value = ''
  trackData = []

  const point = 'touches' in e ? e.touches[0] : e
  startPageX = point.pageX
  startPageY = point.pageY
  startTime = Date.now()

  trackData.push([0, 0, startTime])

  window.addEventListener('mousemove', onDragging)
  window.addEventListener('mouseup', endDrag)
  window.addEventListener('touchmove', onDragging)
  window.addEventListener('touchend', endDrag)
}

function onDragging(e: MouseEvent | TouchEvent) {
  if (!isDragging.value) return
  const point = 'touches' in e ? e.touches[0] : e
  const dx = point.pageX - startPageX
  const dy = point.pageY - startPageY
  const now = Date.now()

  // Clamp within container
  const clampedX = Math.max(0, Math.min(dx, MAX_DRAG_WIDTH))
  sliderX.value = clampedX

  trackData.push([clampedX, dy, now])
}

async function endDrag() {
  if (!isDragging.value) return
  isDragging.value = false

  window.removeEventListener('mousemove', onDragging)
  window.removeEventListener('mouseup', endDrag)
  window.removeEventListener('touchmove', onDragging)
  window.removeEventListener('touchend', endDrag)

  if (!captchaData.value) return

  loading.value = true
  try {
    const res = await verifySliderCaptchaApi({
      captcha_id: captchaData.value.captcha_id,
      x: sliderX.value,
      track: trackData
    })

    if (res.data.success && res.data.captcha_token) {
      isSuccess.value = true
      statusText.value = res.data.message || `验证通过！耗时 ${res.data.elapsed_time}s`
      setTimeout(() => {
        emit('success', res.data.captcha_token!)
      }, 500)
    } else {
      handleFail(res.message || '验证失败')
    }
  } catch (err: any) {
    handleFail(err.response?.data?.message || '验证未通过，请重新对准缺口')
  } finally {
    loading.value = false
  }
}

function handleFail(msg: string) {
  isFailed.value = true
  statusText.value = msg
  setTimeout(() => {
    fetchCaptcha()
  }, 900)
}

function handleClose() {
  emit('close')
}

onUnmounted(() => {
  window.removeEventListener('mousemove', onDragging)
  window.removeEventListener('mouseup', endDrag)
  window.removeEventListener('touchmove', onDragging)
  window.removeEventListener('touchend', endDrag)
})
</script>

<style scoped lang="scss">
.slider-captcha-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  animation: fadeIn 0.2s ease-out;

  .slider-captcha-box {
    width: 360px;
    background: rgba(255, 255, 255, 0.88);
    backdrop-filter: blur(24px) saturate(200%);
    -webkit-backdrop-filter: blur(24px) saturate(200%);
    border: 1px solid rgba(255, 255, 255, 0.7);
    border-radius: var(--radius-lg);
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.25);
    padding: 18px 20px;
    user-select: none;

    &.is-shaking {
      animation: shake 0.4s ease-in-out;
    }

    .captcha-header {
      margin-bottom: 12px;

      .captcha-title {
        font-size: 15px;
        font-weight: 700;
        color: var(--text-main);
        letter-spacing: -0.3px;
      }

      .captcha-actions {
        gap: 10px;

        .action-icon {
          font-size: 16px;
          color: var(--text-muted);
          cursor: pointer;
          transition: all 0.2s ease;

          &:hover {
            color: var(--primary-color);
            transform: scale(1.15);
          }

          &.is-spinning {
            animation: spin 1s linear infinite;
          }
        }
      }
    }

    .captcha-img-wrapper {
      width: 320px;
      height: 160px;
      border-radius: var(--radius-sm);
      position: relative;
      overflow: hidden;
      box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.2);

      .captcha-bg-img {
        width: 100%;
        height: 100%;
        display: block;
        object-fit: cover;
      }

      .captcha-slider-piece {
        position: absolute;
        cursor: pointer;
        filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.4));
        pointer-events: none;
        z-index: 10;
      }

      .captcha-status-banner {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        padding: 6px 12px;
        font-size: 12px;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        animation: slideUp 0.2s ease-out;

        &.success {
          background: rgba(16, 185, 129, 0.9);
          backdrop-filter: blur(4px);
        }

        &.fail {
          background: rgba(239, 68, 68, 0.9);
          backdrop-filter: blur(4px);
        }
      }
    }

    .slider-track-container {
      margin-top: 14px;
      width: 320px;
      height: 42px;
      background: rgba(241, 245, 249, 0.8);
      border: 1px solid rgba(203, 213, 225, 0.6);
      border-radius: var(--radius-sm);
      position: relative;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: hidden;

      .slider-progress-bar {
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        background: rgba(79, 70, 229, 0.2);
        border-radius: var(--radius-sm) 0 0 var(--radius-sm);

        &.success {
          background: rgba(16, 185, 129, 0.35);
        }

        &.fail {
          background: rgba(239, 68, 68, 0.35);
        }
      }

      .slider-tip-text {
        font-size: 12px;
        color: var(--text-muted);
        font-weight: 600;
        letter-spacing: 0.5px;
        pointer-events: none;
        transition: opacity 0.2s ease;
      }

      .slider-handle-knob {
        position: absolute;
        top: 2px;
        width: 46px;
        height: 36px;
        background: #ffffff;
        border: 1px solid rgba(203, 213, 225, 0.8);
        border-radius: var(--radius-xs);
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: grab;
        color: var(--text-regular);
        font-size: 16px;
        box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1);
        transition: background-color 0.2s, border-color 0.2s;
        z-index: 5;

        &:hover,
        &.active {
          background: var(--primary-color);
          color: #ffffff;
          border-color: var(--primary-color);
          box-shadow: 0 4px 12px rgba(79, 70, 229, 0.35);
        }

        &.active {
          cursor: grabbing;
        }

        &.success {
          background: var(--success-color) !important;
          color: #ffffff !important;
          border-color: var(--success-color) !important;
        }

        &.fail {
          background: var(--danger-color) !important;
          color: #ffffff !important;
          border-color: var(--danger-color) !important;
        }
      }
    }
  }
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes shake {
  0%, 100% { transform: translateX(0); }
  20%, 60% { transform: translateX(-6px); }
  40%, 80% { transform: translateX(6px); }
}
</style>
