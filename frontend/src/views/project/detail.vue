<template>
  <div class="project-detail-page page-container" v-loading="loading">
    <!-- Breadcrumb & Back -->
    <div class="detail-header flex-between">
      <div class="header-left">
        <el-button :icon="Back" @click="router.push('/project/list')">返回列表</el-button>
        <span class="detail-title">{{ project?.name }}</span>
        <StatusTag :status="project?.status" type="project" />
        <StatusTag :status="project?.priority" type="priority" />
      </div>
      <div class="header-actions">
        <el-button type="primary" :icon="Plus" @click="openAddMilestoneDialog">添加里程碑</el-button>
        <el-button :icon="UserFilled" @click="openAddMemberDialog">添加成员</el-button>
      </div>
    </div>

    <!-- Top Project Metrics Grid -->
    <el-row :gutter="16" class="metrics-row">
      <el-col :xs="24" :sm="6">
        <div class="metric-box vben-card">
          <div class="m-title">总预算</div>
          <div class="m-val">¥{{ (project?.budget || 0).toLocaleString() }}</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="6">
        <div class="metric-box vben-card">
          <div class="m-title">已消耗预算</div>
          <div class="m-val">¥{{ (project?.consumed_budget || 0).toLocaleString() }}</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="6">
        <div class="metric-box vben-card">
          <div class="m-title">关联任务交付</div>
          <div class="m-val">{{ project?.completed_task_count }} / {{ project?.task_count }} 项</div>
        </div>
      </el-col>
      <el-col :xs="24" :sm="6">
        <div class="metric-box vben-card">
          <div class="m-title">综合进度</div>
          <div class="m-val">{{ project?.progress }}%</div>
        </div>
      </el-col>
    </el-row>

    <!-- Tabs: Milestones & Members -->
    <el-tabs v-model="activeTab" class="detail-tabs vben-card">
      <!-- Milestones Tab -->
      <el-tab-pane label="项目里程碑" name="milestones">
        <div class="tab-content-wrapper">
          <el-timeline v-if="project?.milestones.length">
            <el-timeline-item
              v-for="ms in project.milestones"
              :key="ms.id"
              :timestamp="ms.due_date"
              placement="top"
              :type="ms.status === 'reached' ? 'success' : ms.status === 'delayed' ? 'danger' : 'primary'"
            >
              <div class="milestone-card vben-card">
                <div class="flex-between">
                  <span class="ms-title">{{ ms.title }}</span>
                  <div class="flex-center" style="gap: 8px">
                    <StatusTag :status="ms.status" type="milestone" />
                    <el-button link type="danger" size="small" @click="handleDeleteMilestone(ms.id)">删除</el-button>
                  </div>
                </div>
                <div class="ms-desc">{{ ms.description || '暂无里程碑说明' }}</div>
              </div>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无里程碑数据，可点击上方按钮添加" />
        </div>
      </el-tab-pane>

      <!-- Members Tab -->
      <el-tab-pane label="项目团队成员" name="members">
        <div class="tab-content-wrapper">
          <el-table :data="project?.members || []" stripe style="width: 100%">
            <el-table-column label="成员" min-width="150">
              <template #default="{ row }">
                <div style="display: flex; align-items: center; gap: 8px">
                  <el-avatar :size="30" :src="row.avatar" />
                  <div>
                    <div style="font-weight: 600">{{ row.nickname }}</div>
                    <div style="font-size: 11px; color: var(--text-muted)">@{{ row.username }}</div>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="position" label="岗位 / 职位" width="160" />
            <el-table-column label="项目角色" width="140">
              <template #default="{ row }">
                <el-tag effect="plain">{{ row.project_role }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="joined_at" label="加入时间" width="180">
              <template #default="{ row }">
                <span>{{ row.joined_at?.split('T')[0] }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" align="center">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click="handleRemoveMember(row.id)">移出</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <!-- Add Milestone Dialog -->
    <el-dialog v-model="milestoneDialogVisible" title="添加项目里程碑" width="480px">
      <el-form :model="milestoneForm" label-position="top">
        <el-form-item label="里程碑名称" required>
          <el-input v-model="milestoneForm.title" placeholder="例如 M1: 核心功能上线" />
        </el-form-item>
        <el-form-item label="目标截止日期" required>
          <el-date-picker
            v-model="milestoneForm.due_date"
            type="date"
            value-format="YYYY-MM-DD"
            placeholder="选择目标截止日期"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="milestoneForm.status" style="width: 100%">
            <el-option label="待开始" value="pending" />
            <el-option label="进行中" value="in_progress" />
            <el-option label="已达成" value="reached" />
            <el-option label="已延期" value="delayed" />
          </el-select>
        </el-form-item>
        <el-form-item label="详细目标说明">
          <el-input v-model="milestoneForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="milestoneDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAddMilestone">确认添加</el-button>
      </template>
    </el-dialog>

    <!-- Add Member Dialog -->
    <el-dialog v-model="memberDialogVisible" title="添加项目成员" width="440px">
      <el-form :model="memberForm" label-position="top">
        <el-form-item label="选择系统用户" required>
          <el-select v-model="memberForm.user_id" placeholder="选择用户" style="width: 100%">
            <el-option
              v-for="u in allUsers"
              :key="u.id"
              :label="`${u.nickname} (${u.username}) - ${u.position || '成员'}`"
              :value="u.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="项目内职责角色">
          <el-select v-model="memberForm.project_role" style="width: 100%">
            <el-option label="项目经理 (PM)" value="pm" />
            <el-option label="技术负责人 (Tech Lead)" value="tech_lead" />
            <el-option label="研发工程师 (Developer)" value="developer" />
            <el-option label="测试工程师 (QA)" value="qa" />
            <el-option label="UI/UX 设计师 (Designer)" value="designer" />
            <el-option label="观察员 (Viewer)" value="viewer" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="memberDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitAddMember">确认添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  getProjectDetailApi,
  addMilestoneApi,
  deleteMilestoneApi,
  addProjectMemberApi,
  removeProjectMemberApi,
  type ProjectDetail
} from '@/api/project'
import { getAllUsersApi } from '@/api/user'
import StatusTag from '@/components/StatusTag.vue'
import type { UserInfo } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, Plus, UserFilled } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const projectId = Number(route.params.id)
const loading = ref(false)
const project = ref<ProjectDetail | null>(null)
const activeTab = ref('milestones')
const allUsers = ref<UserInfo[]>([])

const milestoneDialogVisible = ref(false)
const milestoneForm = reactive({
  title: '',
  due_date: new Date().toISOString().split('T')[0],
  status: 'pending',
  description: ''
})

const memberDialogVisible = ref(false)
const memberForm = reactive({
  user_id: undefined as number | undefined,
  project_role: 'developer'
})

async function loadDetail() {
  loading.value = true
  try {
    const res = await getProjectDetailApi(projectId)
    project.value = res.data
  } finally {
    loading.value = false
  }
}

async function loadUsers() {
  const res = await getAllUsersApi()
  allUsers.value = res.data
}

function openAddMilestoneDialog() {
  milestoneForm.title = ''
  milestoneForm.due_date = new Date().toISOString().split('T')[0]
  milestoneForm.status = 'pending'
  milestoneForm.description = ''
  milestoneDialogVisible.value = true
}

async function submitAddMilestone() {
  if (!milestoneForm.title || !milestoneForm.due_date) {
    ElMessage.warning('请填写里程碑名称与截止日期')
    return
  }
  await addMilestoneApi(projectId, milestoneForm)
  ElMessage.success('里程碑添加成功')
  milestoneDialogVisible.value = false
  loadDetail()
}

function handleDeleteMilestone(msId: number) {
  ElMessageBox.confirm('确定删除该里程碑节点吗？', '提示', { type: 'warning' }).then(async () => {
    await deleteMilestoneApi(projectId, msId)
    ElMessage.success('里程碑已删除')
    loadDetail()
  })
}

function openAddMemberDialog() {
  memberForm.user_id = allUsers.value[0]?.id
  memberForm.project_role = 'developer'
  memberDialogVisible.value = true
}

async function submitAddMember() {
  if (!memberForm.user_id) {
    ElMessage.warning('请选择要添加的用户')
    return
  }
  await addProjectMemberApi(projectId, {
    user_id: memberForm.user_id,
    project_role: memberForm.project_role
  })
  ElMessage.success('成员添加成功')
  memberDialogVisible.value = false
  loadDetail()
}

function handleRemoveMember(memberId: number) {
  ElMessageBox.confirm('确定将该成员移出项目吗？', '提示', { type: 'warning' }).then(async () => {
    await removeProjectMemberApi(projectId, memberId)
    ElMessage.success('成员已移出')
    loadDetail()
  })
}

onMounted(() => {
  loadDetail()
  loadUsers()
})
</script>

<style scoped lang="scss">
.project-detail-page {
  .detail-header {
    background-color: var(--bg-card);
    padding: 16px 20px;
    border-radius: var(--radius-md);
    margin-bottom: 16px;
    border: 1px solid var(--border-color);

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;

      .detail-title {
        font-size: 18px;
        font-weight: 700;
        color: var(--text-main);
      }
    }
  }

  .metrics-row {
    margin-bottom: 16px;

    .metric-box {
      padding: 16px;
      text-align: center;

      .m-title {
        font-size: 13px;
        color: var(--text-muted);
        margin-bottom: 6px;
      }

      .m-val {
        font-size: 20px;
        font-weight: 700;
        color: var(--text-main);
      }
    }
  }

  .detail-tabs {
    padding: 16px;

    .tab-content-wrapper {
      padding: 16px 8px;
    }

    .milestone-card {
      padding: 12px 16px;
      margin-bottom: 8px;

      .ms-title {
        font-weight: 600;
        font-size: 14px;
        color: var(--text-main);
      }

      .ms-desc {
        font-size: 13px;
        color: var(--text-regular);
        margin-top: 6px;
      }
    }
  }
}
</style>
