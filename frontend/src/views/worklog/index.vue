<template>
  <div class="worklog-page page-container">
    <!-- Filter Bar -->
    <div class="table-search-bar flex-between">
      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="所属项目">
          <el-select v-model="queryForm.project_id" placeholder="全部项目" clearable style="width: 180px">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="审批状态">
          <el-select v-model="queryForm.status" placeholder="全部状态" clearable style="width: 130px">
            <el-option label="待审批" value="pending" />
            <el-option label="已通过" value="approved" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <div>
        <el-button type="primary" :icon="Plus" @click="openCreateLogDialog">填报工时</el-button>
      </div>
    </div>

    <!-- Table -->
    <div class="table-card" v-loading="loading">
      <el-table :data="worklogs" stripe style="width: 100%">
        <el-table-column label="填报人" width="150">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 8px">
              <el-avatar :size="26" :src="row.user_avatar || 'https://api.dicebear.com/7.x/avataaars/svg?seed=user'" />
              <span style="font-weight: 500">{{ row.user_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="log_date" label="工作日期" width="130" />
        <el-table-column prop="hours" label="耗时 (h)" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="primary">{{ row.hours }} 小时</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="project_name" label="关联项目" width="180" />
        <el-table-column prop="description" label="工作内容与产出说明" min-width="240" />
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'approved' ? 'success' : row.status === 'rejected' ? 'danger' : 'warning'"
              size="small"
            >
              {{ row.status === 'approved' ? '已通过' : row.status === 'rejected' ? '已驳回' : '待审批' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="审批人 / 意见" width="180">
          <template #default="{ row }">
            <div v-if="row.approver_name" style="font-size: 12px">
              <div>{{ row.approver_name }}</div>
              <div v-if="row.approval_remark" style="color: var(--text-muted)">{{ row.approval_remark }}</div>
            </div>
            <span v-else style="color: var(--text-muted); font-size: 12px">暂未审批</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <template v-if="row.status === 'pending'">
              <el-button link type="success" size="small" @click="handleApprove(row, 'approved')">通过</el-button>
              <el-button link type="danger" size="small" @click="handleApprove(row, 'rejected')">驳回</el-button>
            </template>
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
          @size-change="loadWorkLogs"
          @current-change="loadWorkLogs"
        />
      </div>
    </div>

    <!-- Create WorkLog Dialog -->
    <el-dialog v-model="createDialogVisible" title="填报每日工时" width="480px">
      <el-form :model="logForm" label-position="top">
        <el-form-item label="关联项目" required>
          <el-select v-model="logForm.project_id" style="width: 100%" @change="loadProjectTasks">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联任务 (可选)">
          <el-select v-model="logForm.task_id" placeholder="选择任务" clearable style="width: 100%">
            <el-option v-for="t in projectTasks" :key="t.id" :label="t.title" :value="t.id" />
          </el-select>
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="工作日期" required>
              <el-date-picker
                v-model="logForm.log_date"
                type="date"
                value-format="YYYY-MM-DD"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="投入工时 (h)" required>
              <el-input-number v-model="logForm.hours" :min="0.5" :max="24" :step="0.5" style="width: 100%" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="工作成果与描述" required>
          <el-input v-model="logForm.description" type="textarea" :rows="3" placeholder="简述今日完成的功能模块与解决的问题..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitWorkLog">确认填报</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listWorkLogsApi, createWorkLogApi, approveWorkLogApi, deleteWorkLogApi } from '@/api/worklog'
import { getAllProjectsApi } from '@/api/project'
import { listTasksApi } from '@/api/task'
import type { WorkLog, Project, Task } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'

const loading = ref(false)
const worklogs = ref<WorkLog[]>([])
const total = ref(0)
const projects = ref<Project[]>([])
const projectTasks = ref<Task[]>([])

const queryForm = reactive({
  project_id: undefined as number | undefined,
  status: '',
  page: 1,
  page_size: 10
})

const createDialogVisible = ref(false)
const logForm = reactive({
  project_id: 1,
  task_id: undefined as number | undefined,
  log_date: new Date().toISOString().split('T')[0],
  hours: 8,
  description: ''
})

async function loadWorkLogs() {
  loading.value = true
  try {
    const res = await listWorkLogsApi(queryForm)
    worklogs.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  const res = await getAllProjectsApi()
  projects.value = res.data
}

async function loadProjectTasks(projectId: number) {
  if (!projectId) return
  const res = await listTasksApi({ project_id: projectId, page_size: 50 })
  projectTasks.value = res.data.items
}

function handleSearch() {
  queryForm.page = 1
  loadWorkLogs()
}

function handleReset() {
  queryForm.project_id = undefined
  queryForm.status = ''
  queryForm.page = 1
  loadWorkLogs()
}

function openCreateLogDialog() {
  logForm.project_id = projects.value[0]?.id || 1
  logForm.task_id = undefined
  logForm.log_date = new Date().toISOString().split('T')[0]
  logForm.hours = 8
  logForm.description = ''
  loadProjectTasks(logForm.project_id)
  createDialogVisible.value = true
}

async function submitWorkLog() {
  if (!logForm.description) {
    ElMessage.warning('请填写工作说明')
    return
  }
  await createWorkLogApi(logForm)
  ElMessage.success('工时已填报')
  createDialogVisible.value = false
  loadWorkLogs()
}

function handleApprove(row: WorkLog, status: 'approved' | 'rejected') {
  ElMessageBox.prompt(
    status === 'approved' ? '审批通过备注 (选填)' : '请输入驳回原因',
    '工时审批',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPlaceholder: status === 'approved' ? '符合研发排期' : '工时超出预估，需重新确认'
    }
  ).then(async ({ value }) => {
    await approveWorkLogApi(row.id, { status, approval_remark: value })
    ElMessage.success(`工时已${status === 'approved' ? '通过' : '驳回'}`)
    loadWorkLogs()
  })
}

function handleDelete(id: number) {
  ElMessageBox.confirm('确定删除该工时记录吗？', '提示', { type: 'warning' }).then(async () => {
    await deleteWorkLogApi(id)
    ElMessage.success('工时记录已删除')
    loadWorkLogs()
  })
}

onMounted(() => {
  loadProjects()
  loadWorkLogs()
})
</script>

<style scoped>
</style>
