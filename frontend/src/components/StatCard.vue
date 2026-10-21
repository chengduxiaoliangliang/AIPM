<template>
  <div class="stat-card vben-card" :class="customClass">
    <div class="stat-header">
      <span class="stat-title">{{ title }}</span>
      <div class="icon-box" :style="{ backgroundColor: iconBg, color: iconColor }">
        <el-icon :size="20"><component :is="icon" /></el-icon>
      </div>
    </div>
    <div class="stat-body">
      <div class="stat-value">{{ value }}<span class="stat-unit" v-if="unit">{{ unit }}</span></div>
      <div class="stat-footer" v-if="trend !== undefined || tip">
        <span v-if="trend !== undefined" class="trend-tag" :class="trend >= 0 ? 'up' : 'down'">
          {{ trend >= 0 ? '↑' : '↓' }} {{ Math.abs(trend) }}%
        </span>
        <span class="tip-text">{{ tip }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title: string
  value: string | number
  unit?: string
  icon: any
  iconBg?: string
  iconColor?: string
  trend?: number
  tip?: string
  customClass?: string
}>()
</script>

<style scoped lang="scss">
.stat-card {
  position: relative;
  padding: 16px 18px 15px;
  border-radius: var(--radius-lg);
  overflow: hidden;

  /* 角落刻度线：仪表感来自"标记"，而不是发光 */
  &::before,
  &::after {
    content: '';
    position: absolute;
    width: 9px;
    height: 9px;
    border-color: var(--primary-glow);
    border-style: solid;
    pointer-events: none;
    opacity: 0.9;
  }

  &::before {
    top: 7px;
    right: 7px;
    border-width: 1px 1px 0 0;
  }

  &::after {
    bottom: 7px;
    left: 7px;
    border-width: 0 0 1px 1px;
  }

  .stat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;

    .stat-title {
      font-size: 12.5px;
      font-weight: 500;
      color: var(--text-muted);
      letter-spacing: 0.01em;
    }

    .icon-box {
      width: 30px;
      height: 30px;
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
    }
  }

  .stat-body {
    margin-top: 12px;

    .stat-value {
      font-family: var(--font-mono);
      font-size: 27px;
      font-weight: 600;
      line-height: 1.15;
      color: var(--text-main);
      letter-spacing: -0.02em;
      font-variant-numeric: tabular-nums;

      .stat-unit {
        font-family: var(--font-sans);
        font-size: 12.5px;
        font-weight: 500;
        margin-left: 5px;
        color: var(--text-faint);
        letter-spacing: 0;
      }
    }

    .stat-footer {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 10px;
      font-size: 11.5px;

      .trend-tag {
        font-family: var(--font-mono);
        font-size: 11px;
        font-weight: 600;
        padding: 1px 5px;
        border-radius: 3px;

        &.up {
          background: var(--success-light);
          color: var(--success-color);
        }

        &.down {
          background: var(--danger-light);
          color: var(--danger-color);
        }
      }

      .tip-text {
        color: var(--text-faint);
      }
    }
  }
}
</style>
