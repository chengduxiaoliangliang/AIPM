<template>
  <div v-if="visible" class="slider-captcha-overlay" @click.self="handleClose">
    <div
      class="slider-captcha-box"
      :class="{ 'is-shaking': isFailed }"
      role="dialog"
      aria-modal="true"
      aria-label="安全人机验证"
    >
      <!-- Modal Header -->
      <div class="captcha-header flex-between">
        <div class="captcha-title-wrap">
          <el-icon class="title-icon"><Lock /></el-icon>
          <span class="captcha-title">安全人机验证</span>
        </div>
        <div class="captcha-actions flex-center">
          <button
            type="button"
            class="action-btn"
            aria-label="换一张"
            :disabled="loading"
            @click="fetchCaptcha"
          >
            <el-icon :class="{ 'is-spinning': loading }"><Refresh /></el-icon>
          </button>
          <button type="button" class="action-btn" aria-label="关闭验证" @click="handleClose">
            <el-icon><Close /></el-icon>
          </button>
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
import { ref, reactive, watch, onMounted, onUnmounted } from 'vue'
import { getSliderCaptchaApi, verifySliderCaptchaApi, type SliderCaptchaData } from '@/api/auth'
import { Refresh, Close, DArrowRight, Check, Lock } from '@element-plus/icons-vue'

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

/** Esc 关闭：对话框的基本预期 */
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.visible) handleClose()
}

onMounted(() => window.addEventListener('keydown', onKeydown))

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('mousemove', onDragging)
  window.removeEventListener('mouseup', endDrag)
  window.removeEventListener('touchmove', onDragging)
  window.removeEventListener('touchend', endDrag)
})
</script>

<style scoped lang="scss">
/* 与登录页同一套深色语言：发丝线、无玻璃、强调色只给手柄 */
$surface: #0b111b;
$line: rgba(255, 255, 255, 0.09);
$line-strong: rgba(255, 255, 255, 0.16);
$text: #e9edf4;
$muted: #8b96a6;
$faint: #5d6879;
$accent: #4d6bfe;

.slider-captcha-overlay {
  position: fixed;
  inset: 0;
  background: rgba(4, 7, 12, 0.72);
  backdrop-filter: blur(6px);
  -webkit-backdrop-filter: blur(6px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  animation: fadeIn 0.18s ease-out;

  .slider-captcha-box {
    width: 376px;
    background: $surface;
    border: 1px solid $line;
    border-radius: 12px;
    box-shadow: 0 32px 64px -24px rgba(0, 0, 0, 0.9);
    padding: 16px 18px 18px;
    user-select: none;

    &.is-shaking {
      animation: shake 0.4s ease-in-out;
    }

    .captcha-header {
      margin-bottom: 14px;

      .captcha-title-wrap {
        display: flex;
        align-items: center;
        gap: 7px;
      }

      .title-icon {
        font-size: 13px;
        color: $faint;
      }

      .captcha-title {
        font-size: 13px;
        font-weight: 600;
        color: $text;
        letter-spacing: -0.01em;
      }

      .captcha-actions {
        gap: 2px;

        .action-btn {
          width: 26px;
          height: 26px;
          padding: 0;
          border: none;
          border-radius: 6px;
          background: transparent;
          color: $faint;
          font-size: 14px;
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
          transition: background-color 0.16s ease, color 0.16s ease;

          &:hover:not(:disabled) {
            background: rgba(255, 255, 255, 0.07);
            color: $text;
          }

          &:focus-visible {
            outline: 2px solid $accent;
            outline-offset: 1px;
          }

          &:disabled {
            opacity: 0.5;
            cursor: default;
          }

          .is-spinning {
            animation: spin 1s linear infinite;
          }
        }
      }
    }

    .captcha-img-wrapper {
      width: 320px;
      height: 160px;
      border-radius: 8px;
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.1);

      /* v-loading 默认是白色遮罩，深色卡片上会闪一块白 */
      --el-mask-color: rgba(11, 17, 27, 0.72);

      :deep(.el-loading-spinner .path) {
        stroke: #4d6bfe;
      }

      .captcha-bg-img {
        width: 100%;
        height: 100%;
        display: block;
        object-fit: cover;
      }

      .captcha-slider-piece {
        position: absolute;
        cursor: pointer;
        filter: drop-shadow(0 2px 6px rgba(0, 0, 0, 0.55));
        pointer-events: none;
        z-index: 10;
      }

      .captcha-status-banner {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        padding: 6px 12px;
        font-size: 11.5px;
        font-weight: 500;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        backdrop-filter: blur(6px);
        animation: slideUp 0.2s ease-out;

        &.success {
          background: rgba(31, 157, 99, 0.92);
        }

        &.fail {
          background: rgba(212, 80, 75, 0.92);
        }
      }
    }

    .slider-track-container {
      margin-top: 14px;
      width: 320px;
      height: 42px;
      background: rgba(255, 255, 255, 0.045);
      border: 1px solid $line;
      border-radius: 8px;
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
        background: rgba(77, 107, 254, 0.28);
        border-radius: 8px 0 0 8px;

        &.success {
          background: rgba(53, 192, 122, 0.26);
        }

        &.fail {
          background: rgba(226, 84, 79, 0.26);
        }
      }

      .slider-tip-text {
        font-size: 12px;
        color: $faint;
        font-weight: 500;
        letter-spacing: 0.02em;
        pointer-events: none;
        transition: opacity 0.2s ease;
      }

      .slider-handle-knob {
        position: absolute;
        top: 2px;
        width: 46px;
        height: 36px;
        background: $accent;
        border: none;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: grab;
        color: #ffffff;
        font-size: 16px;
        box-shadow: 0 2px 10px rgba(77, 107, 254, 0.4);
        transition: background-color 0.16s ease, box-shadow 0.16s ease;
        z-index: 5;

        &:hover,
        &.active {
          background: #5b78ff;
          box-shadow: 0 4px 16px rgba(77, 107, 254, 0.55);
        }

        &.active {
          cursor: grabbing;
        }

        &.success {
          background: #35c07a;
          box-shadow: 0 2px 10px rgba(53, 192, 122, 0.45);
        }

        &.fail {
          background: #e2544f;
          box-shadow: 0 2px 10px rgba(226, 84, 79, 0.45);
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
