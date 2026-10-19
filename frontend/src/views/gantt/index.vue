<template>
  <div class="gantt-page page-container" v-loading="loading">
    <!-- Filter Bar -->
    <div class="table-search-bar flex-between">
      <div class="flex-center" style="gap: 12px">
        <span class="filter-label">项目选择：</span>
        <el-select v-model="selectedProjectId" placeholder="选择项目" style="width: 220px" @change="loadGanttData">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-button :icon="Refresh" @click="loadGanttData">刷新排期</el-button>
      </div>

      <div class="legend-box flex-center" style="gap: 14px">
        <span class="legend-item"><span class="dot done"></span> 已完成</span>
        <span class="legend-item"><span class="dot in_progress"></span> 进行中</span>
        <span class="legend-item"><span class="dot todo"></span> 待处理</span>
      </div>
    </div>

    <!-- Gantt View Container -->
    <div class="gantt-card vben-card">
      <div class="gantt-table-header">
        <div class="col-task-name">任务 / 里程碑名称</div>
        <div class="col-assignee">负责人</div>
        <div class="col-progress">完成进度</div>
        <div class="col-timeline">排期进度条 (当前周期)</div>
      </div>

      <div class="gantt-rows-wrapper">
        <div v-for="task in tasks" :key="task.id" class="gantt-row">
          <div class="col-task-name">
            <el-icon :color="task.status === 'done' ? '#10b981' : '#4f46e5'"><Checked /></el-icon>
            <span class="task-title-text">{{ task.title }}</span>
          </div>

          <div class="col-assignee">
            <el-avatar :size="24" :src="task.assignee_avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=user'" />
            <span class="assignee-name">{{ task.assignee_name || '未分配' }}</span>
          </div>

          <div class="col-progress">
            <span class="progress-num">{{ task.progress }}%</span>
          </div>

          <div class="col-timeline">
            <div class="timeline-bar-bg">
              <div
                class="timeline-bar"
                :class="task.status"
                :style="{
                  width: `${Math.max(task.progress, 18)}%`,
                  marginLeft: `${((task.id * 7) % 30)}%`
                }"
              >
                <span class="bar-date">{{ task.start_date || '开始' }} ~ {{ task.due_date || '截止' }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getAllProjectsApi } from '@/api/project'
import { listTasksApi } from '@/api/task'
import type { Project, Task } from '@/types'
import { Refresh, Checked } from '@element-plus/icons-vue'

const loading = ref(false)
const projects = ref<Project[]>([])
const selectedProjectId = ref<number | undefined>(undefined)
const tasks = ref<Task[]>([])

async function loadProjects() {
  const res = await getAllProjectsApi()
  projects.value = res.data
  if (projects.value.length > 0 && !selectedProjectId.value) {
    selectedProjectId.value = projects.value[0].id
  }
}

async function loadGanttData() {
  if (!selectedProjectId.value) return
  loading.value = true
  try {
    const res = await listTasksApi({ project_id: selectedProjectId.value, page_size: 50 })
    tasks.value = res.data.items
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadProjects()
  await loadGanttData()
})
</script>

<style scoped lang="scss">
.gantt-page {
  .legend-box {
    font-size: 13px;
    color: var(--text-regular);
    font-weight: 500;

    .legend-item {
      display: flex;
      align-items: center;
      gap: 6px;

      .dot {
        width: 10px;
        height: 10px;
        border-radius: var(--radius-xs);

        &.done { background-color: #10b981; }
        &.in_progress { background-color: #4f46e5; }
        &.todo { background-color: #64748b; }
      }
    }
  }

  .gantt-card {
    padding: 20px;
    min-height: calc(100vh - 180px);

    .gantt-table-header {
      display: flex;
      align-items: center;
      padding: 12px 16px;
      background: var(--bg-hover);
      border-radius: var(--radius-sm);
      border: 1px solid var(--border-glass-subtle);
      font-weight: 700;
      font-size: 13px;
      color: var(--text-main);
      margin-bottom: 12px;
    }

    .col-task-name { width: 320px; display: flex; align-items: center; gap: 8px; }
    .col-assignee { width: 140px; display: flex; align-items: center; gap: 8px; font-size: 13px; }
    .col-progress { width: 100px; text-align: center; font-size: 13px; }
    .col-timeline { flex: 1; min-width: 300px; padding: 0 12px; }

    .gantt-rows-wrapper {
      display: flex;
      flex-direction: column;
      gap: 10px;

      .gantt-row {
        display: flex;
        align-items: center;
        padding: 12px 16px;
        border-radius: var(--radius-sm);
        border: 1px solid var(--border-glass);
        background: rgba(255, 255, 255, 0.6);
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);

        &:hover {
          border-color: var(--primary-color);
          box-shadow: var(--shadow-sm);
          transform: translateY(-1px);
        }

        .task-title-text {
          font-weight: 600;
          font-size: 13px;
          color: var(--text-main);
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .assignee-name {
          font-weight: 500;
          color: var(--text-regular);
        }

        .progress-num {
          font-weight: 700;
          color: var(--text-main);
        }

        .timeline-bar-bg {
          height: 26px;
          background: rgba(148, 163, 184, 0.12);
          border-radius: var(--radius-xs);
          position: relative;
          display: flex;
          align-items: center;
          border: 1px solid var(--border-glass-subtle);

          .timeline-bar {
            height: 100%;
            border-radius: var(--radius-xs);
            display: flex;
            align-items: center;
            padding: 0 10px;
            color: #ffffff;
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.15);

            &.done { background: #10b981; }
            &.in_progress, &.in_review { background: #4f46e5; }
            &.todo, &.testing { background: #06b6d4; }

            .bar-date {
              letter-spacing: 0.2px;
            }
          }
        }
      }
    }
  }
}
</style>
