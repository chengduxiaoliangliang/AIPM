<template>
  <div class="system-user-page page-container">
    <div class="table-search-bar flex-between">
      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="关键词">
          <el-input v-model="queryForm.keyword" placeholder="用户名 / 昵称 / 邮箱" clearable @keyup.enter="handleSearch" style="width: 180px" />
        </el-form-item>
        <el-form-item label="部门">
          <el-tree-select
            v-model="queryForm.department_id"
            :data="departments"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            placeholder="选择部门"
            clearable
            check-strictly
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <div>
        <el-button type="primary" :icon="Plus" @click="openCreateUser">新增用户</el-button>
      </div>
    </div>

    <!-- Table -->
    <div class="table-card" v-loading="loading">
      <el-table :data="users" stripe style="width: 100%">
        <el-table-column label="用户" min-width="160">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 8px">
              <el-avatar :size="32" :src="row.avatar" />
              <div>
                <div style="font-weight: 600">{{ row.nickname }}</div>
                <div style="font-size: 11px; color: var(--text-muted)">@{{ row.username }}</div>
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="department_name" label="所属部门" width="140">
          <template #default="{ row }">
            <span>{{ row.department_name || '未分配' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="position" label="职位" width="150" />
        <el-table-column label="角色" min-width="150">
          <template #default="{ row }">
            <el-tag v-for="r in row.roles" :key="r" size="small" style="margin-right: 4px">{{ r }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="160" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'danger'" size="small">
              {{ row.status ? '正常' : '禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditUser(row)">编辑</el-button>
            <el-button link type="danger" size="small" :disabled="row.is_superuser" @click="handleDelete(row.id)">删除</el-button>
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
          @size-change="loadUsers"
          @current-change="loadUsers"
        />
      </div>
    </div>

    <!-- Create/Edit User Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑用户' : '新增系统用户'" width="500px">
      <el-form :model="userForm" label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="用户名" required>
              <el-input v-model="userForm.username" :disabled="isEdit" placeholder="英文登录名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="用户昵称" required>
              <el-input v-model="userForm.nickname" placeholder="例如 张三" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item v-if="!isEdit" label="初始登录密码" required>
          <el-input v-model="userForm.password" placeholder="默认 123456" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="所属部门">
              <el-tree-select
                v-model="userForm.department_id"
                :data="departments"
                :props="{ label: 'name', value: 'id', children: 'children' }"
                check-strictly
                placeholder="选择部门"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="职位">
              <el-input v-model="userForm.position" placeholder="例如 高级前端" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="关联角色">
          <el-select v-model="userForm.role_ids" multiple placeholder="分配角色" style="width: 100%">
            <el-option v-for="r in rolesList" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="userForm.email" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitUser">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listUsersApi, createUserApi, updateUserApi, deleteUserApi, listDepartmentsApi, listRolesApi } from '@/api/user'
import type { UserInfo, Department, Role } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'

const loading = ref(false)
const users = ref<UserInfo[]>([])
const total = ref(0)
const departments = ref<Department[]>([])
const rolesList = ref<Role[]>([])

const queryForm = reactive({
  keyword: '',
  department_id: undefined as number | undefined,
  page: 1,
  page_size: 10
})

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)

const userForm = reactive({
  username: '',
  nickname: '',
  password: 'password123',
  department_id: undefined as number | undefined,
  position: '',
  email: '',
  role_ids: [] as number[]
})

async function loadUsers() {
  loading.value = true
  try {
    const res = await listUsersApi(queryForm)
    users.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

async function loadMetadata() {
  const [dRes, rRes] = await Promise.all([listDepartmentsApi(), listRolesApi()])
  departments.value = dRes.data
  rolesList.value = rRes.data
}

function handleSearch() {
  queryForm.page = 1
  loadUsers()
}

function handleReset() {
  queryForm.keyword = ''
  queryForm.department_id = undefined
  queryForm.page = 1
  loadUsers()
}

function openCreateUser() {
  isEdit.value = false
  editId.value = null
  Object.assign(userForm, {
    username: '',
    nickname: '',
    password: 'password123',
    department_id: undefined,
    position: '',
    email: '',
    role_ids: []
  })
  dialogVisible.value = true
}

function openEditUser(row: UserInfo) {
  isEdit.value = true
  editId.value = row.id
  Object.assign(userForm, {
    username: row.username,
    nickname: row.nickname,
    department_id: row.department_id,
    position: row.position || '',
    email: row.email || '',
    role_ids: (row as any).role_ids || []
  })
  dialogVisible.value = true
}

async function submitUser() {
  if (!userForm.username || !userForm.nickname) {
    ElMessage.warning('请填写用户名与昵称')
    return
  }
  if (isEdit.value && editId.value) {
    await updateUserApi(editId.value, userForm)
    ElMessage.success('用户已更新')
  } else {
    await createUserApi(userForm)
    ElMessage.success('用户创建成功')
  }
  dialogVisible.value = false
  loadUsers()
}

function handleDelete(id: number) {
  ElMessageBox.confirm('确定删除该用户吗？', '提示', { type: 'warning' }).then(async () => {
    await deleteUserApi(id)
    ElMessage.success('用户已删除')
    loadUsers()
  })
}

onMounted(() => {
  loadMetadata()
  loadUsers()
})
</script>

<style scoped>
</style>
