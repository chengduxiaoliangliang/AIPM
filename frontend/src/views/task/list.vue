<template>
  <div class="task-list-page page-container">
    <!-- Filter Form -->
    <div class="table-search-bar flex-between">
      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="关键词">
          <el-input
            v-model="queryForm.keyword"
            placeholder="任务标题 / 标签"
            clearable
            @keyup.enter="handleSearch"
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="queryForm.project_id" placeholder="全部项目" clearable style="width: 180px">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="全部状态" clearable style="width: 130px">
            <el-option label="待处理" value="todo" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="评审中" value="in_review" />
            <el-option label="测试中" value="testing" />
            <el-option label="已完成" value="done" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="queryForm.priority" placeholder="全部优先级" clearable style="width: 120px">
            <el-option label="紧急" value="urgent" />
            <el-option label="高" value="high" />
            <el-option label="中" value="medium" />
            <el-option label="低" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <div>
        <el-button type="primary" :icon="Plus" @click="openCreateTask">新建任务</el-button>
      </div>
    </div>

    <!-- Table View -->
    <div class="table-card" v-loading="loading">
      <el-table :data="tasks" stripe style="width: 100%">
        <el-table-column prop="title" label="任务名称" min-width="220">
          <template #default="{ row }">
            <div style="font-weight: 600; color: var(--text-main)">{{ row.title }}</div>
            <div style="font-size: 11px; color: var(--text-muted)">{{ row.project_name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.status" type="task" />
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="100" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.priority" type="priority" />
          </template>
        </el-table-column>
        <el-table-column label="执行人" width="130">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 6px">
              <el-avatar :size="24" :src="row.assignee_avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=user'" />
              <span>{{ row.assignee_name || '未分配' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="预估 / 实际工时" width="140" align="center">
          <template #default="{ row }">
            <span>{{ row.estimated_hours }}h / {{ row.actual_hours }}h</span>
          </template>
        </el-table-column>
        <el-table-column prop="due_date" label="截止日期" width="130" align="center">
          <template #default="{ row }">
            <span>{{ row.due_date || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditTask(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="queryForm.page"
          v-model:page-size="queryForm.page_size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadTasks"
          @current-change="loadTasks"
        />
      </div>
    </div>

    <!-- Edit Task Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑任务' : '新建任务'" width="500px">
      <el-form :model="taskForm" label-position="top">
        <el-form-item label="任务标题" required>
          <el-input v-model="taskForm.title" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="所属项目" required>
              <el-select v-model="taskForm.project_id" style="width: 100%">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="指派执行人">
              <el-select v-model="taskForm.assignee_id" clearable style="width: 100%">
                <el-option v-for="u in usersList" :key="u.id" :label="u.nickname" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="taskForm.status" style="width: 100%">
                <el-option label="待处理" value="todo" />
                <el-option label="进行中" value="in_progress" />
                <el-option label="评审中" value="in_review" />
                <el-option label="测试中" value="testing" />
                <el-option label="已完成" value="done" />
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
              <el-input-number v-model="taskForm.estimated_hours" :min="0.5" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="截止日期">
              <el-date-picker
                v-model="taskForm.due_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="任务描述">
          <el-input v-model="taskForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTask">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listTasksApi, createTaskApi, updateTaskApi, deleteTaskApi } from '@/api/task'
import { getAllProjectsApi } from '@/api/project'
import { getAllUsersApi } from '@/api/user'
import StatusTag from '@/components/StatusTag.vue'
import type { Task, Project, UserInfo } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'

const loading = ref(false)
const tasks = ref<Task[]>([])
const total = ref(0)
const projects = ref<Project[]>([])
const usersList = ref<UserInfo[]>([])

const queryForm = reactive({
  keyword: '',
  project_id: undefined as number | undefined,
  status: '',
  priority: '',
  page: 1,
  page_size: 10
})

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)

const taskForm = reactive({
  title: '',
  project_id: 1,
  assignee_id: undefined as number | undefined,
  status: 'todo',
  priority: 'medium',
  estimated_hours: 8,
  due_date: '',
  description: ''
})

async function loadTasks() {
  loading.value = true
  try {
    const res = await listTasksApi(queryForm)
    tasks.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function loadMetadata() {
  const [projRes, userRes] = await Promise.all([getAllProjectsApi(), getAllUsersApi()])
  projects.value = projRes.data
  usersList.value = userRes.data
}

function handleSearch() {
  queryForm.page = 1
  loadTasks()
}

function handleReset() {
  queryForm.keyword = ''
  queryForm.project_id = undefined
  queryForm.status = ''
  queryForm.priority = ''
  queryForm.page = 1
  loadTasks()
}

function openCreateTask() {
  isEdit.value = false
  editId.value = null
  Object.assign(taskForm, {
    title: '',
    project_id: projects.value[0]?.id || 1,
    assignee_id: undefined,
    status: 'todo',
    priority: 'medium',
    estimated_hours: 8,
    due_date: new Date().toISOString().split('T')[0],
    description: ''
  })
  dialogVisible.value = true
}

function openEditTask(row: Task) {
  isEdit.value = true
  editId.value = row.id
  Object.assign(taskForm, {
    title: row.title,
    project_id: row.project_id,
    assignee_id: row.assignee_id,
    status: row.status,
    priority: row.priority,
    estimated_hours: row.estimated_hours,
    due_date: row.due_date || '',
    description: row.description || ''
  })
  dialogVisible.value = true
}

async function submitTask() {
  if (!taskForm.title) {
    ElMessage.warning('请输入任务标题')
    return
  }
  if (isEdit.value && editId.value) {
    await updateTaskApi(editId.value, taskForm)
    ElMessage.success('任务已更新')
  } else {
    await createTaskApi(taskForm)
    ElMessage.success('任务已创建')
  }
  dialogVisible.value = false
  loadTasks()
}

function handleDelete(id: number) {
  ElMessageBox.confirm('确定删除该任务吗？', '提示', { type: 'warning' }).then(async () => {
    await deleteTaskApi(id)
    ElMessage.success('任务已删除')
    loadTasks()
  })
}

onMounted(() => {
  loadMetadata()
  loadTasks()
})
</script>

<style scoped>
</style>
