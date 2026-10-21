<template>
  <div class="project-list-page page-container">
    <!-- Header / Search Filter Bar -->
    <div class="table-search-bar flex-between">
      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="关键词">
          <el-input
            v-model="queryForm.keyword"
            placeholder="项目名称 / 标识 / 描述"
            clearable
            @keyup.enter="handleSearch"
            style="width: 170px"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="queryForm.status" placeholder="全部状态" clearable style="width: 116px">
            <el-option label="规划中" value="planning" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="测试中" value="testing" />
            <el-option label="已完成" value="completed" />
            <el-option label="已挂起" value="suspended" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="queryForm.priority" placeholder="全部优先级" clearable style="width: 116px">
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

      <div class="action-buttons">
        <el-radio-group v-model="viewMode" size="small" style="margin-right: 12px">
          <el-radio-button label="card"><el-icon><Grid /></el-icon></el-radio-button>
          <el-radio-button label="table"><el-icon><List /></el-icon></el-radio-button>
        </el-radio-group>

        <el-button :icon="Download" @click="importRef?.open()">导入项目</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreateDrawer">创建项目</el-button>
      </div>
    </div>

    <!-- Card View Mode -->
    <div v-if="viewMode === 'card'" v-loading="loading" class="project-cards-grid">
      <el-row :gutter="16">
        <el-col
          v-for="proj in projects"
          :key="proj.id"
          :xs="24"
          :sm="12"
          :md="8"
          :lg="8"
          style="margin-bottom: 16px"
        >
          <div class="project-card vben-card" @click="goToDetail(proj.id)">
            <!-- Cover image header if available -->
            <div class="card-banner" :style="{ backgroundImage: `url(${proj.cover_image})` }">
              <div class="banner-overlay">
                <StatusTag :status="proj.status" type="project" effect="dark" />
                <StatusTag :status="proj.priority" type="priority" effect="dark" />
              </div>
            </div>

            <div class="card-main">
              <div class="project-header">
                <div class="project-title">{{ proj.name }}</div>
                <div class="project-code">{{ proj.code }}</div>
              </div>

              <div class="project-desc">{{ proj.description || '暂无项目描述' }}</div>

              <div class="project-progress">
                <div class="progress-info">
                  <span>研发进度</span>
                  <span class="progress-val">{{ proj.progress }}%</span>
                </div>
                <el-progress
                  :percentage="proj.progress"
                  :stroke-width="6"
                  :show-text="false"
                  :color="proj.progress >= 80 ? '#67C23A' : proj.progress >= 40 ? '#409EFF' : '#E6A23C'"
                />
              </div>

              <div class="card-footer">
                <div class="owner-info">
                  <el-avatar :size="24" :src="proj.owner_avatar" />
                  <span class="owner-name">{{ proj.owner_name }}</span>
                </div>
                <div class="meta-counts">
                  <span><el-icon><User /></el-icon> {{ proj.member_count }}</span>
                  <span><el-icon><Checked /></el-icon> {{ proj.completed_task_count }}/{{ proj.task_count }}</span>
                </div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- Table View Mode -->
    <div v-else class="table-card" v-loading="loading">
      <el-table :data="projects" stripe style="width: 100%">
        <el-table-column prop="name" label="项目名称" min-width="180">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="goToDetail(row.id)">
              <strong>{{ row.name }}</strong>
            </el-link>
            <div style="font-size: 11px; color: var(--text-muted)">{{ row.code }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.status" type="project" />
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="100" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.priority" type="priority" />
          </template>
        </el-table-column>
        <el-table-column label="负责人" width="130">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 6px">
              <el-avatar :size="24" :src="row.owner_avatar" />
              <span>{{ row.owner_name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="进度" min-width="150">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" :stroke-width="8" />
          </template>
        </el-table-column>
        <el-table-column prop="budget" label="预算 / 消耗 (¥)" width="160">
          <template #default="{ row }">
            <span>¥{{ row.budget.toLocaleString() }}</span>
            <div style="font-size: 11px; color: var(--text-muted)">已用: ¥{{ row.consumed_budget.toLocaleString() }}</div>
          </template>
        </el-table-column>
        <el-table-column label="周期" width="180">
          <template #default="{ row }">
            <div style="font-size: 12px">{{ row.start_date || '未设置' }} 至 {{ row.end_date || '未设置' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="goToDetail(row.id)">详情</el-button>
            <el-button link type="primary" size="small" @click="openEditDrawer(row)">编辑</el-button>
            <el-button link type="primary" size="small" @click="handleExport(row)">导出</el-button>
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
          :page-sizes="[9, 18, 30]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadProjects"
          @current-change="loadProjects"
        />
      </div>
    </div>

    <!-- Create/Edit Project Drawer -->
    <el-drawer
      v-model="drawerVisible"
      :title="isEdit ? '编辑项目' : '新建项目'"
      size="560px"
      :destroy-on-close="true"
    >
      <el-form
        ref="projectFormRef"
        :model="projectForm"
        :rules="projectRules"
        label-position="top"
      >
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="projectForm.name" placeholder="请输入项目名称" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="项目唯一编码" prop="code">
              <el-input v-model="projectForm.code" :disabled="isEdit" placeholder="例如 AIPM-2026" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目负责人" prop="owner_id">
              <el-select v-model="projectForm.owner_id" placeholder="选择负责人" style="width: 100%">
                <el-option
                  v-for="u in usersList"
                  :key="u.id"
                  :label="`${u.nickname} (${u.username})`"
                  :value="u.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="状态" prop="status">
              <el-select v-model="projectForm.status" style="width: 100%">
                <el-option label="规划中" value="planning" />
                <el-option label="进行中" value="in_progress" />
                <el-option label="测试中" value="testing" />
                <el-option label="已完成" value="completed" />
                <el-option label="已挂起" value="suspended" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-select v-model="projectForm.priority" style="width: 100%">
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
            <el-form-item label="项目总预算 (¥)" prop="budget">
              <el-input-number v-model="projectForm.budget" :min="0" :step="10000" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="进度 (%)" prop="progress">
              <el-slider v-model="projectForm.progress" :min="0" :max="100" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="开始日期" prop="start_date">
              <el-date-picker
                v-model="projectForm.start_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择开始日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期" prop="end_date">
              <el-date-picker
                v-model="projectForm.end_date"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="选择结束日期"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="项目封面图链接 (URL)" prop="cover_image">
          <el-input v-model="projectForm.cover_image" placeholder="https://..." />
        </el-form-item>

        <el-form-item label="项目详情描述" prop="description">
          <el-input
            v-model="projectForm.description"
            type="textarea"
            :rows="4"
            placeholder="请输入项目的背景目标与范围..."
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div style="display: flex; justify-content: flex-end; gap: 10px">
          <el-button @click="drawerVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确认提交</el-button>
        </div>
      </template>
    </el-drawer>

  <ImportDialog ref="importRef" @done="loadProjects" />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listProjectsApi, createProjectApi, updateProjectApi, deleteProjectApi } from '@/api/project'
import { getAllUsersApi } from '@/api/user'
import StatusTag from '@/components/StatusTag.vue'
import ImportDialog from './ImportDialog.vue'
import { exportProjectApi } from '@/api/project'
import { saveBlob } from '@/utils/download'
import type { Project, UserInfo } from '@/types'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import {
  Search,
  Refresh,
  Plus,
  Grid,
  List,
  User,
  Checked,
  Download
} from '@element-plus/icons-vue'

const router = useRouter()

const loading = ref(false)
const importRef = ref<InstanceType<typeof ImportDialog>>()
const viewMode = ref<'card' | 'table'>('card')
const projects = ref<Project[]>([])
const total = ref(0)
const usersList = ref<UserInfo[]>([])

const queryForm = reactive({
  keyword: '',
  status: '',
  priority: '',
  page: 1,
  page_size: 9
})

const drawerVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)
const submitLoading = ref(false)
const projectFormRef = ref<FormInstance>()

const projectForm = reactive({
  name: '',
  code: '',
  owner_id: 1,
  status: 'in_progress',
  priority: 'medium',
  budget: 100000,
  progress: 0,
  start_date: '',
  end_date: '',
  cover_image: '',
  description: ''
})

const projectRules = reactive<FormRules>({
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入项目编码', trigger: 'blur' }],
  owner_id: [{ required: true, message: '请选择项目负责人', trigger: 'change' }]
})

async function loadProjects() {
  loading.value = true
  try {
    const res = await listProjectsApi(queryForm)
    projects.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function loadUsers() {
  const res = await getAllUsersApi()
  usersList.value = res.data
}

function handleSearch() {
  queryForm.page = 1
  loadProjects()
}

function handleReset() {
  queryForm.keyword = ''
  queryForm.status = ''
  queryForm.priority = ''
  queryForm.page = 1
  loadProjects()
}

async function handleExport(row: Project) {
  try {
    const blob = await exportProjectApi(row.id)
    saveBlob(blob, `${row.code}-${row.name}.xlsx`)
    ElMessage.success('已导出，可直接用导入功能再导入')
  } catch (e: any) {
    ElMessage.error(e?.message || '导出失败')
  }
}

function goToDetail(id: number) {
  router.push(`/project/detail/${id}`)
}

function openCreateDrawer() {
  isEdit.value = false
  editId.value = null
  Object.assign(projectForm, {
    name: '',
    code: `PRJ-${Date.now().toString().slice(-4)}`,
    owner_id: usersList.value[0]?.id || 1,
    status: 'planning',
    priority: 'medium',
    budget: 200000,
    progress: 0,
    start_date: new Date().toISOString().split('T')[0],
    end_date: '',
    cover_image: 'https://images.unsplash.com/photo-1507238691740-187a5b1d37b8?w=600&auto=format&fit=crop&q=80',
    description: ''
  })
  drawerVisible.value = true
}

function openEditDrawer(row: Project) {
  isEdit.value = true
  editId.value = row.id
  Object.assign(projectForm, {
    name: row.name,
    code: row.code,
    owner_id: row.owner_id,
    status: row.status,
    priority: row.priority,
    budget: row.budget,
    progress: row.progress,
    start_date: row.start_date || '',
    end_date: row.end_date || '',
    cover_image: row.cover_image || '',
    description: row.description || ''
  })
  drawerVisible.value = true
}

async function handleSubmit() {
  if (!projectFormRef.value) return
  await projectFormRef.value.validate(async (valid) => {
    if (valid) {
      submitLoading.value = true
      try {
        if (isEdit.value && editId.value) {
          await updateProjectApi(editId.value, projectForm)
          ElMessage.success('项目已成功更新')
        } else {
          await createProjectApi(projectForm)
          ElMessage.success('项目已成功创建')
        }
        drawerVisible.value = false
        loadProjects()
      } finally {
        submitLoading.value = false
      }
    }
  })
}

function handleDelete(id: number) {
  ElMessageBox.confirm('确定要删除该项目吗？关联任务与工单也将同步移除。', '警告', {
    confirmButtonText: '确定删除',
    cancelButtonText: '取消',
    type: 'warning'
  }).then(async () => {
    await deleteProjectApi(id)
    ElMessage.success('项目已删除')
    loadProjects()
  })
}

onMounted(() => {
  loadProjects()
  loadUsers()
})
</script>

<style scoped lang="scss">

/* 筛选区与动作区保持单行：靠收紧间距而不是让表单折行 */
.filter-form {
  flex: 1 1 auto;
  min-width: 0;

  :deep(.el-form-item) {
    margin-right: 14px;
    margin-bottom: 0;
  }
}

/* 工具栏右侧动作区：项目多/窗口窄时允许换行，但按钮本身不压缩 */
.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
  /* 不参与压缩：宁可让筛选区换行，也不要按钮被挤成两行 */
  flex: 0 0 auto;
  justify-content: flex-end;
  white-space: nowrap;

  :deep(.el-button) {
    margin-left: 0;
    flex-shrink: 0;
  }

  :deep(.el-radio-group) {
    flex-shrink: 0;
  }
}

.project-list-page {
  .project-cards-grid {
    .project-card {
      cursor: pointer;
      border-radius: var(--radius-md);
      overflow: hidden;

      .card-banner {
        height: 120px;
        background-size: cover;
        background-position: center;
        position: relative;

        .banner-overlay {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: linear-gradient(180deg, rgba(0, 0, 0, 0.4) 0%, rgba(0, 0, 0, 0.7) 100%);
          display: flex;
          align-items: flex-start;
          justify-content: space-between;
          padding: 12px;
        }
      }

      .card-main {
        padding: 16px;

        .project-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 8px;

          .project-title {
            font-size: 16px;
            font-weight: 600;
            color: var(--text-main);
          }

          .project-code {
            font-size: 11px;
            font-weight: 600;
            color: var(--primary-color);
            background-color: var(--primary-light);
            padding: 2px 6px;
            border-radius: 4px;
          }
        }

        .project-desc {
          font-size: 13px;
          color: var(--text-regular);
          height: 38px;
          line-height: 19px;
          overflow: hidden;
          text-overflow: ellipsis;
          display: -webkit-box;
          -webkit-line-clamp: 2;
          -webkit-box-orient: vertical;
          margin-bottom: 14px;
        }

        .project-progress {
          margin-bottom: 14px;

          .progress-info {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            color: var(--text-muted);
            margin-bottom: 4px;

            .progress-val {
              font-weight: 600;
              color: var(--text-main);
            }
          }
        }

        .card-footer {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding-top: 12px;
          border-top: 1px solid var(--border-color);

          .owner-info {
            display: flex;
            align-items: center;
            gap: 6px;

            .owner-name {
              font-size: 13px;
              color: var(--text-regular);
            }
          }

          .meta-counts {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 12px;
            color: var(--text-muted);

            span {
              display: flex;
              align-items: center;
              gap: 4px;
            }
          }
        }
      }
    }
  }
}
</style>
