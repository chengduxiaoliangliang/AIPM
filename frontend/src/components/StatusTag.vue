<template>
  <el-tag :type="tagType" :effect="effect" :size="size" class="status-tag">
    <span class="dot" :style="{ backgroundColor: dotColor }"></span>
    {{ tagLabel }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    status?: string
    type?: 'project' | 'task' | 'priority' | 'milestone' | 'issue' | 'worklog'
    size?: 'small' | 'default' | 'large'
    effect?: 'light' | 'dark' | 'plain'
  }>(),
  {
    type: 'project',
    size: 'small',
    effect: 'light'
  }
)

const mapping: Record<string, { label: string; tagType: string; color: string }> = {
  // Project & Task Status
  planning: { label: '规划中', tagType: 'info', color: '#909399' },
  in_progress: { label: '进行中', tagType: 'primary', color: '#409EFF' },
  in_review: { label: '评审中', tagType: 'warning', color: '#E6A23C' },
  testing: { label: '测试中', tagType: 'warning', color: '#E6A23C' },
  completed: { label: '已完成', tagType: 'success', color: '#67C23A' },
  done: { label: '已完成', tagType: 'success', color: '#67C23A' },
  todo: { label: '待处理', tagType: 'info', color: '#909399' },
  suspended: { label: '已挂起', tagType: 'danger', color: '#F56C6C' },

  // Priorities
  urgent: { label: '紧急', tagType: 'danger', color: '#F56C6C' },
  high: { label: '高', tagType: 'warning', color: '#E6A23C' },
  medium: { label: '中', tagType: 'primary', color: '#409EFF' },
  low: { label: '低', tagType: 'info', color: '#909399' },

  // Milestones
  pending: { label: '待开始', tagType: 'info', color: '#909399' },
  reached: { label: '已达成', tagType: 'success', color: '#67C23A' },
  delayed: { label: '已延期', tagType: 'danger', color: '#F56C6C' },

  // Issues
  open: { label: '待修复', tagType: 'danger', color: '#F56C6C' },
  resolved: { label: '已解决', tagType: 'success', color: '#67C23A' },
  closed: { label: '已关闭', tagType: 'info', color: '#909399' },
  rejected: { label: '已驳回', tagType: 'info', color: '#909399' },

  // WorkLogs
  approved: { label: '已通过', tagType: 'success', color: '#67C23A' }
}

const current = computed(() => {
  const st = props.status || ''
  return mapping[st] || { label: st, tagType: 'info', color: '#909399' }
})

const tagLabel = computed(() => current.value.label)
const tagType = computed(() => current.value.tagType as any)
const dotColor = computed(() => current.value.color)
</script>

<style scoped>
.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
  border-radius: 4px;
}
.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}
</style>
