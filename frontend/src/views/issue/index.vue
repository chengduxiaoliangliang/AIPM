<template>
  <div class="issue-page page-container">
    <!-- Filter Bar -->
    <div class="table-search-bar flex-between">
      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="关键词">
          <el-input v-model="queryForm.keyword" placeholder="缺陷标题 / 描述" clearable @keyup.enter="handleSearch" style="width: 180px" />
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="queryForm.project_id" placeholder="全部项目" clearable style="width: 180px">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="全部状态" clearable style="width: 120px">
            <el-option label="待修复" value="open" />
            <el-option label="修复中" value="in_progress" />
            <el-option label="已解决" value="resolved" />
            <el-option label="已关闭" value="closed" />
            <el-option label="已驳回" value="rejected" />
          </el-select>
        </el-form-item>
        <el-form-item label="严重级别">
          <el-select v-model="queryForm.severity" placeholder="全部级别" clearable style="width: 120px">
            <el-option label="致命 (Fatal)" value="fatal" />
            <el-option label="严重 (Critical)" value="critical" />
            <el-option label="一般 (Medium)" value="medium" />
            <el-option label="轻微 (Low)" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <div>
        <el-button type="danger" :icon="Plus" @click="openCreateIssue">提报缺陷</el-button>
      </div>
    </div>

    <!-- Table -->
    <div class="table-card" v-loading="loading">
      <el-table :data="issues" stripe style="width: 100%">
        <el-table-column prop="title" label="缺陷标题" min-width="200">
          <template #default="{ row }">
            <div style="font-weight: 600; color: var(--text-main)">{{ row.title }}</div>
            <div style="font-size: 11px; color: var(--text-muted)">{{ row.project_name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="严重级别" width="110" align="center">
          <template #default="{ row }">
            <el-tag
              :type="row.severity === 'fatal' || row.severity === 'critical' ? 'danger' : row.severity === 'medium' ? 'warning' : 'info'"
              size="small"
              effect="plain"
            >
              {{ row.severity === 'fatal' ? '致命' : row.severity === 'critical' ? '严重' : row.severity === 'medium' ? '一般' : '轻微' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.status" type="issue" />
          </template>
        </el-table-column>
        <el-table-column prop="reporter_name" label="提报人" width="120" />
        <el-table-column prop="assignee_name" label="处理人" width="120">
          <template #default="{ row }">
            <span>{{ row.assignee_name || '待指派' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="提报时间" width="160">
          <template #default="{ row }">
            <span>{{ row.created_at?.split('T')[0] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditIssue(row)">编辑/流转</el-button>
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
          @size-change="loadIssues"
          @current-change="loadIssues"
        />
      </div>
    </div>

    <!-- Create/Edit Issue Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '处理/编辑缺陷' : '提报缺陷工单'" width="520px">
      <el-form :model="issueForm" label-position="top">
        <el-form-item label="缺陷标题" required>
          <el-input v-model="issueForm.title" placeholder="简要描述缺陷现象" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="所属项目" required>
              <el-select v-model="issueForm.project_id" style="width: 100%">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="指派修复人员">
              <el-select v-model="issueForm.assignee_id" clearable style="width: 100%">
                <el-option v-for="u in usersList" :key="u.id" :label="u.nickname" :value="u.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="严重级别">
              <el-select v-model="issueForm.severity" style="width: 100%">
                <el-option label="致命 (Fatal)" value="fatal" />
                <el-option label="严重 (Critical)" value="critical" />
                <el-option label="一般 (Medium)" value="medium" />
                <el-option label="轻微 (Low)" value="low" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态流转">
              <el-select v-model="issueForm.status" style="width: 100%">
                <el-option label="待修复 (Open)" value="open" />
                <el-option label="修复中 (In Progress)" value="in_progress" />
                <el-option label="已解决 (Resolved)" value="resolved" />
                <el-option label="已关闭 (Closed)" value="closed" />
                <el-option label="已驳回 (Rejected)" value="rejected" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="缺陷重现步骤与现象">
          <el-input v-model="issueForm.description" type="textarea" :rows="3" placeholder="1. 打开页面... 2. 点击... 3. 出现错误" />
        </el-form-item>
        <el-form-item v-if="isEdit" label="修复方案与结论">
          <el-input v-model="issueForm.resolution" type="textarea" :rows="2" placeholder="填写代码修改点与验证结果..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitIssue">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listIssuesApi, createIssueApi, updateIssueApi, deleteIssueApi } from '@/api/issue'
import { getAllProjectsApi } from '@/api/project'
import { getAllUsersApi } from '@/api/user'
import StatusTag from '@/components/StatusTag.vue'
import type { Issue, Project, UserInfo } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'

const loading = ref(false)
const issues = ref<Issue[]>([])
const total = ref(0)
const projects = ref<Project[]>([])
const usersList = ref<UserInfo[]>([])

const queryForm = reactive({
  keyword: '',
  project_id: undefined as number | undefined,
  status: '',
  severity: '',
  page: 1,
  page_size: 10
})

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)

const issueForm = reactive({
  title: '',
  project_id: 1,
  assignee_id: undefined as number | undefined,
  severity: 'medium',
  priority: 'medium',
  status: 'open',
  description: '',
  resolution: ''
})

async function loadIssues() {
  loading.value = true
  try {
    const res = await listIssuesApi(queryForm)
    issues.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function loadMetadata() {
  const [pRes, uRes] = await Promise.all([getAllProjectsApi(), getAllUsersApi()])
  projects.value = pRes.data
  usersList.value = uRes.data
}

function handleSearch() {
  queryForm.page = 1
  loadIssues()
}

function handleReset() {
  queryForm.keyword = ''
  queryForm.project_id = undefined
  queryForm.status = ''
  queryForm.severity = ''
  queryForm.page = 1
  loadIssues()
}

function openCreateIssue() {
  isEdit.value = false
  editId.value = null
  Object.assign(issueForm, {
    title: '',
    project_id: projects.value[0]?.id || 1,
    assignee_id: undefined,
    severity: 'medium',
    status: 'open',
    description: '',
    resolution: ''
  })
  dialogVisible.value = true
}

function openEditIssue(row: Issue) {
  isEdit.value = true
  editId.value = row.id
  Object.assign(issueForm, {
    title: row.title,
    project_id: row.project_id,
    assignee_id: row.assignee_id,
    severity: row.severity,
    status: row.status,
    description: row.description || '',
    resolution: row.resolution || ''
  })
  dialogVisible.value = true
}

async function submitIssue() {
  if (!issueForm.title) {
    ElMessage.warning('请输入缺陷标题')
    return
  }
  if (isEdit.value && editId.value) {
    await updateIssueApi(editId.value, issueForm)
    ElMessage.success('缺陷工单已更新')
  } else {
    await createIssueApi(issueForm)
    ElMessage.success('缺陷已提报')
  }
  dialogVisible.value = false
  loadIssues()
}

function handleDelete(id: number) {
  ElMessageBox.confirm('确定删除该缺陷工单吗？', '提示', { type: 'warning' }).then(async () => {
    await deleteIssueApi(id)
    ElMessage.success('缺陷已删除')
    loadIssues()
  })
}

onMounted(() => {
  loadMetadata()
  loadIssues()
})
</script>

<style scoped>
</style>
