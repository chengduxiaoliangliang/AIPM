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
  padding: 18px 20px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border-radius: var(--radius-md);
  position: relative;
  overflow: hidden;

  &::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--primary-color), transparent);
    opacity: 0.8;
  }

  .stat-header {
    display: flex;
    align-items: center;
    justify-content: space-between;

    .stat-title {
      font-size: 13px;
      color: var(--text-muted);
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }

    .icon-box {
      width: 40px;
      height: 40px;
      border-radius: var(--radius-sm);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s cubic-bezier(0.4, 0, 0.2, 1);
      border: 1px solid var(--border-glass-subtle);
    }
  }

  &:hover .icon-box {
    transform: scale(1.08) translateY(-2px);
  }

  .stat-body {
    margin-top: 14px;

    .stat-value {
      font-size: 28px;
      font-weight: 800;
      color: var(--text-main);
      letter-spacing: -0.8px;

      .stat-unit {
        font-size: 14px;
        font-weight: 500;
        margin-left: 6px;
        color: var(--text-muted);
      }
    }

    .stat-footer {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 10px;
      font-size: 12px;

      .trend-tag {
        font-weight: 700;
        padding: 2px 6px;
        border-radius: var(--radius-xs);

        &.up {
          background-color: var(--success-light);
          color: var(--success-color);
        }

        &.down {
          background-color: var(--danger-light);
          color: var(--danger-color);
        }
      }

      .tip-text {
        color: var(--text-muted);
        font-weight: 500;
      }
    }
  }
}
</style>
