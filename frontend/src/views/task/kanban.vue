<template>
  <div class="task-kanban-page page-container" v-loading="loading">
    <!-- Top Filter Bar -->
    <div class="table-search-bar flex-between">
      <div class="filter-left flex-center" style="gap: 12px">
        <span class="filter-label">项目选择：</span>
        <el-select
          v-model="selectedProjectId"
          placeholder="全部项目"
          clearable
          style="width: 220px"
          @change="loadKanban"
        >
          <el-option
            v-for="p in projects"
            :key="p.id"
            :label="`${p.name} (${p.code})`"
            :value="p.id"
          />
        </el-select>
        <el-button :icon="Refresh" @click="loadKanban">刷新看板</el-button>
      </div>

      <el-button type="primary" :icon="Plus" @click="openCreateTaskDialog">新建任务</el-button>
    </div>

    <!-- Kanban Columns Container -->
    <div class="kanban-board-container">
      <div
        v-for="col in columns"
        :key="col.key"
        class="kanban-column"
      >
        <!-- Column Header -->
        <div class="column-header flex-between">
          <div class="column-title-box">
            <span class="col-indicator" :style="{ backgroundColor: col.color, boxShadow: `0 0 8px ${col.color}` }"></span>
            <span class="col-title">{{ col.title }}</span>
            <span class="col-count">{{ board[col.key]?.length || 0 }}</span>
          </div>
          <el-button
            link
            :icon="Plus"
            size="small"
            @click="openCreateTaskForColumn(col.key)"
          />
        </div>

        <!-- Column Task List (Draggable with SortableJS) -->
        <div
          :id="`column-${col.key}`"
          class="column-task-list"
          :data-status="col.key"
        >
          <div
            v-for="task in board[col.key] || []"
            :key="task.id"
            :data-id="task.id"
            class="task-card"
            @click="openTaskDetail(task.id)"
          >
            <div class="task-card-header flex-between">
              <span class="project-tag">{{ task.project_name || '项目' }}</span>
              <StatusTag :status="task.priority" type="priority" size="small" />
            </div>

            <div class="task-card-title">{{ task.title }}</div>

            <div v-if="task.tags" class="task-tags">
              <span v-for="tag in task.tags.split(',')" :key="tag" class="tag-chip">
                {{ tag.trim() }}
              </span>
            </div>

            <div class="task-card-footer flex-between">
              <div class="task-meta">
                <span v-if="task.subtask_count" class="meta-item">
                  <el-icon><Checked /></el-icon> {{ task.completed_subtask_count }}/{{ task.subtask_count }}
                </span>
                <span v-if="task.comment_count" class="meta-item">
                  <el-icon><ChatDotRound /></el-icon> {{ task.comment_count }}
                </span>
                <span v-if="task.estimated_hours" class="meta-item">
                  <el-icon><Timer /></el-icon> {{ task.estimated_hours }}h
                </span>
              </div>

              <div class="task-assignee">
                <el-avatar :size="22" :src="task.assignee_avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=user'" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Task Detail Drawer -->
    <el-drawer
      v-model="detailDrawerVisible"
      title="任务详情"
      size="620px"
      :destroy-on-close="true"
    >
      <div v-if="currentTask" class="task-drawer-content">
        <div class="drawer-header flex-between">
          <div class="flex-center" style="gap: 8px">
            <StatusTag :status="currentTask.status" type="task" />
            <StatusTag :status="currentTask.priority" type="priority" />
          </div>
          <el-button link type="danger" size="small" @click="handleDeleteTask(currentTask.id)">删除任务</el-button>
        </div>

        <h3 class="task-title-lg">{{ currentTask.title }}</h3>
        <p class="task-desc-box">{{ currentTask.description || '暂无详细描述' }}</p>

        <!-- Meta Grid -->
        <div class="task-info-grid">
          <div class="info-row">
            <span class="info-label">所属项目：</span>
            <span class="info-val">{{ currentTask.project_name }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">执行人：</span>
            <span class="info-val">{{ currentTask.assignee_name || '未分配' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">预估 / 实际工时：</span>
            <span class="info-val">{{ currentTask.estimated_hours }}h / {{ currentTask.actual_hours }}h</span>
          </div>
          <div class="info-row">
            <span class="info-label">截止日期：</span>
            <span class="info-val">{{ currentTask.due_date || '未设置' }}</span>
          </div>
        </div>

        <!-- Subtasks Section -->
        <div class="section-divider">
          <div class="section-title flex-between">
            <span>子任务清单 ({{ currentTask.subtasks?.length || 0 }})</span>
            <el-button link type="primary" size="small" @click="showAddSubtask = true">+ 添加子任务</el-button>
          </div>

          <div v-if="showAddSubtask" class="add-subtask-box">
            <el-input v-model="newSubtaskTitle" placeholder="输入子任务内容后回车" size="small" @keyup.enter="submitAddSubtask" />
            <el-button size="small" type="primary" @click="submitAddSubtask">确认</el-button>
            <el-button size="small" @click="showAddSubtask = false">取消</el-button>
          </div>

          <div class="subtasks-list">
            <div v-for="sub in currentTask.subtasks" :key="sub.id" class="subtask-item flex-between">
              <el-checkbox v-model="sub.is_completed" @change="toggleSubtask(sub)">
                <span :class="{ 'is-done': sub.is_completed }">{{ sub.title }}</span>
              </el-checkbox>
              <el-button link type="danger" size="small" @click="removeSubtask(sub.id)">删除</el-button>
            </div>
          </div>
        </div>

        <!-- Comments Section -->
        <div class="section-divider">
          <div class="section-title">动态与评论</div>

          <div class="add-comment-box">
            <el-input
              v-model="newComment"
              type="textarea"
              :rows="2"
              placeholder="发表对该任务的进展反馈或提问..."
            />
            <div style="text-align: right; margin-top: 8px">
              <el-button type="primary" size="small" :loading="commentLoading" @click="submitComment">发表评论</el-button>
            </div>
          </div>

          <div class="comments-list">
            <div v-for="c in currentTask.comments" :key="c.id" class="comment-item">
              <el-avatar :size="28" :src="c.user_avatar" />
              <div class="comment-bubble">
                <div class="comment-meta">
                  <span class="user">{{ c.user_nickname }}</span>
                  <span class="time">{{ c.created_at?.split('T')[0] }}</span>
                </div>
                <div class="text">{{ c.content }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </el-drawer>

    <!-- Create Task Dialog -->
    <el-dialog v-model="createDialogVisible" title="创建新任务" width="520px">
      <el-form :model="taskForm" label-position="top">
        <el-form-item label="任务标题" required>
          <el-input v-model="taskForm.title" placeholder="例如 实现用户登录与权限校验" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="所属项目" required>
              <el-select v-model="taskForm.project_id" placeholder="选择项目" style="width: 100%">
                <el-option
                  v-for="p in projects"
                  :key="p.id"
                  :label="p.name"
                  :value="p.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="指派执行人">
              <el-select v-model="taskForm.assignee_id" placeholder="选择成员" clearable style="width: 100%">
                <el-option
                  v-for="u in usersList"
                  :key="u.id"
                  :label="u.nickname"
                  :value="u.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="初始状态">
              <el-select v-model="taskForm.status" style="width: 100%">
                <el-option label="待处理 (To Do)" value="todo" />
                <el-option label="进行中 (In Progress)" value="in_progress" />
                <el-option label="评审中 (In Review)" value="in_review" />
                <el-option label="测试中 (Testing)" value="testing" />
                <el-option label="已完成 (Done)" value="done" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级">
              <el-select v-model="taskForm.priority" style="width: 100%">
                <el-option label="紧急" value="urgent" />
                <el-option label="高" value="high" />
                <el-option label="中" value="medium" />
                <el-option label="低" value="low" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="预估工时 (h)">
              <el-input-number v-model="taskForm.estimated_hours" :min="0.5" :step="1" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="截止日期">
              <el-date-picker
                v-model="taskForm.due_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择截止日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="标签 (逗号隔开)">
          <el-input v-model="taskForm.tags" placeholder="例如 Vue3, UI, Bug" />
        </el-form-item>
        <el-form-item label="详细说明">
          <el-input v-model="taskForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitCreateTask">确认创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, nextTick } from 'vue'
import Sortable from 'sortablejs'
import {
  getKanbanBoardApi,
  getTaskDetailApi,
  createTaskApi,
  updateTaskStatusApi,
  deleteTaskApi,
  addSubTaskApi,
  updateSubTaskApi,
  deleteSubTaskApi,
  addTaskCommentApi,
  type TaskDetail
} from '@/api/task'
import { getAllProjectsApi } from '@/api/project'
import { getAllUsersApi } from '@/api/user'
import StatusTag from '@/components/StatusTag.vue'
import type { Task, Project, UserInfo, SubTask } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  Plus,
  Checked,
  ChatDotRound,
  Timer
} from '@element-plus/icons-vue'

const loading = ref(false)
const selectedProjectId = ref<number | undefined>(undefined)
const projects = ref<Project[]>([])
const usersList = ref<UserInfo[]>([])

const columns = [
  { key: 'todo', title: '待处理 (To Do)', color: '#64748b' },
  { key: 'in_progress', title: '进行中 (In Progress)', color: '#4f46e5' },
  { key: 'in_review', title: '评审中 (In Review)', color: '#f59e0b' },
  { key: 'testing', title: '测试中 (Testing)', color: '#06b6d4' },
  { key: 'done', title: '已完成 (Done)', color: '#10b981' }
]

const board = ref<Record<string, Task[]>>({
  todo: [],
  in_progress: [],
  in_review: [],
  testing: [],
  done: []
})

const detailDrawerVisible = ref(false)
const currentTask = ref<TaskDetail | null>(null)
const showAddSubtask = ref(false)
const newSubtaskTitle = ref('')
const newComment = ref('')
const commentLoading = ref(false)

const createDialogVisible = ref(false)
const taskForm = reactive({
  title: '',
  project_id: 1,
  assignee_id: undefined as number | undefined,
  status: 'todo',
  priority: 'medium',
  estimated_hours: 8,
  due_date: new Date().toISOString().split('T')[0],
  tags: '',
  description: ''
})

async function loadProjects() {
  const res = await getAllProjectsApi()
  projects.value = res.data
  if (projects.value.length > 0 && !selectedProjectId.value) {
    selectedProjectId.value = projects.value[0].id
  }
}

async function loadUsers() {
  const res = await getAllUsersApi()
  usersList.value = res.data
}

async function loadKanban() {
  loading.value = true
  try {
    const res = await getKanbanBoardApi(selectedProjectId.value)
    board.value = res.data
    await nextTick()
    initSortables()
  } finally {
    loading.value = false
  }
}

function initSortables() {
  columns.forEach((col) => {
    const el = document.getElementById(`column-${col.key}`)
    if (el) {
      Sortable.create(el, {
        group: 'kanban-tasks',
        animation: 200,
        ghostClass: 'sortable-ghost',
        onEnd: async (evt) => {
          const taskId = Number(evt.item.dataset.id)
          const targetCol = evt.to.dataset.status
          if (taskId && targetCol) {
            await updateTaskStatusApi(taskId, { status: targetCol, order_num: evt.newIndex })
            ElMessage.success('任务状态已流转更新')
          }
        }
      })
    }
  })
}

async function openTaskDetail(id: number) {
  const res = await getTaskDetailApi(id)
  currentTask.value = res.data
  detailDrawerVisible.value = true
}

function openCreateTaskDialog() {
  taskForm.project_id = selectedProjectId.value || projects.value[0]?.id || 1
  taskForm.status = 'todo'
  taskForm.title = ''
  taskForm.description = ''
  createDialogVisible.value = true
}

function openCreateTaskForColumn(colKey: string) {
  openCreateTaskDialog()
  taskForm.status = colKey
}

async function submitCreateTask() {
  if (!taskForm.title) {
    ElMessage.warning('请输入任务标题')
    return
  }
  await createTaskApi(taskForm)
  ElMessage.success('任务创建成功')
  createDialogVisible.value = false
  loadKanban()
}

function handleDeleteTask(id: number) {
  ElMessageBox.confirm('确定删除该任务吗？', '提示', { type: 'warning' }).then(async () => {
    await deleteTaskApi(id)
    ElMessage.success('任务已删除')
    detailDrawerVisible.value = false
    loadKanban()
  })
}

async function submitAddSubtask() {
  if (!newSubtaskTitle.value.trim() || !currentTask.value) return
  const res = await addSubTaskApi(currentTask.value.id, { title: newSubtaskTitle.value })
  currentTask.value.subtasks.push(res.data)
  newSubtaskTitle.value = ''
  showAddSubtask.value = false
}

async function toggleSubtask(sub: SubTask) {
  if (!currentTask.value) return
  await updateSubTaskApi(currentTask.value.id, sub.id, { is_completed: sub.is_completed })
}

async function removeSubtask(subId: number) {
  if (!currentTask.value) return
  await deleteSubTaskApi(currentTask.value.id, subId)
  currentTask.value.subtasks = currentTask.value.subtasks.filter((s) => s.id !== subId)
}

async function submitComment() {
  if (!newComment.value.trim() || !currentTask.value) return
  commentLoading.value = true
  try {
    const res = await addTaskCommentApi(currentTask.value.id, { content: newComment.value })
    currentTask.value.comments.push(res.data)
    newComment.value = ''
    ElMessage.success('评论已发表')
  } finally {
    commentLoading.value = false
  }
}

onMounted(async () => {
  await loadProjects()
  await loadUsers()
  await loadKanban()
})
</script>

<style scoped lang="scss">
.task-kanban-page {
  .kanban-board-container {
    display: flex;
    gap: 18px;
    overflow-x: auto;
    padding-bottom: 16px;
    min-height: calc(100vh - 180px);

    .kanban-column {
      flex: 0 0 290px;
      background: var(--bg-card);
      backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
      -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
      border-radius: var(--radius-md);
      border: 1px solid var(--border-glass);
      box-shadow: var(--shadow-glass);
      display: flex;
      flex-direction: column;
      max-height: calc(100vh - 190px);

      .column-header {
        padding: 14px 16px;
        border-bottom: 1px solid var(--border-glass-subtle);

        .column-title-box {
          display: flex;
          align-items: center;
          gap: 8px;

          .col-indicator {
            width: 8px;
            height: 8px;
            border-radius: 50%;
          }

          .col-title {
            font-size: 13px;
            font-weight: 700;
            color: var(--text-main);
          }

          .col-count {
            font-size: 11px;
            font-weight: 700;
            background: rgba(79, 70, 229, 0.12);
            color: var(--primary-color);
            padding: 1px 7px;
            border-radius: 10px;
          }
        }
      }

      .column-task-list {
        flex: 1;
        overflow-y: auto;
        padding: 12px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        min-height: 100px;
      }
    }
  }

  .task-card {
    padding: 14px;
    cursor: grab;
    border-radius: var(--radius-sm);
    background: rgba(255, 255, 255, 0.7);
    border: 1px solid var(--border-glass);
    box-shadow: var(--shadow-sm);
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);

    &:hover {
      box-shadow: var(--shadow-md);
      border-color: var(--primary-color);
      transform: translateY(-2px);
    }

    .project-tag {
      font-size: 11px;
      font-weight: 700;
      color: var(--primary-color);
      background: var(--primary-light);
      padding: 1px 6px;
      border-radius: var(--radius-xs);
    }

    .task-card-title {
      font-size: 14px;
      font-weight: 600;
      color: var(--text-main);
      margin: 10px 0;
      line-height: 1.4;
    }

    .task-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      margin-bottom: 10px;

      .tag-chip {
        font-size: 10px;
        font-weight: 600;
        background: rgba(148, 163, 184, 0.15);
        color: var(--text-regular);
        padding: 2px 6px;
        border-radius: var(--radius-xs);
      }
    }

    .task-card-footer {
      padding-top: 10px;
      border-top: 1px dashed var(--border-glass-subtle);

      .task-meta {
        display: flex;
        gap: 8px;
        font-size: 11px;
        color: var(--text-muted);
        font-weight: 500;

        .meta-item {
          display: flex;
          align-items: center;
          gap: 2px;
        }
      }
    }
  }

  .sortable-ghost {
    opacity: 0.35;
    background-color: var(--primary-light) !important;
  }

  .task-drawer-content {
    .task-title-lg {
      font-size: 18px;
      font-weight: 700;
      margin: 12px 0 8px;
      color: var(--text-main);
    }

    .task-desc-box {
      font-size: 14px;
      color: var(--text-regular);
      line-height: 1.5;
      margin-bottom: 16px;
    }

    .task-info-grid {
      background: var(--bg-hover);
      padding: 14px 18px;
      border-radius: var(--radius-sm);
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 20px;
      border: 1px solid var(--border-glass-subtle);

      .info-row {
        font-size: 13px;
        .info-label { color: var(--text-muted); }
        .info-val { font-weight: 600; color: var(--text-main); }
      }
    }

    .section-divider {
      margin-top: 24px;
      padding-top: 16px;
      border-top: 1px solid var(--border-glass-subtle);

      .section-title {
        font-size: 14px;
        font-weight: 700;
        margin-bottom: 12px;
        color: var(--text-main);
      }

      .add-subtask-box {
        display: flex;
        gap: 8px;
        margin-bottom: 12px;
      }

      .subtasks-list {
        display: flex;
        flex-direction: column;
        gap: 8px;

        .subtask-item {
          padding: 8px 12px;
          background: var(--bg-hover);
          border-radius: var(--radius-xs);
          border: 1px solid var(--border-glass-subtle);

          .is-done {
            text-decoration: line-through;
            color: var(--text-muted);
          }
        }
      }

      .comments-list {
        margin-top: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;

        .comment-item {
          display: flex;
          gap: 10px;

          .comment-bubble {
            flex: 1;
            background: var(--bg-hover);
            padding: 10px 14px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border-glass-subtle);

            .comment-meta {
              display: flex;
              justify-content: space-between;
              font-size: 12px;
              margin-bottom: 4px;
              .user { font-weight: 700; color: var(--text-main); }
              .time { color: var(--text-muted); }
            }

            .text {
              font-size: 13px;
              color: var(--text-regular);
            }
          }
        }
      }
    }
  }
}
</style>
