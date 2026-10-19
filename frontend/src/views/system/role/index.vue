<template>
  <div class="system-role-page page-container">
    <div class="table-search-bar flex-between">
      <div class="page-header-title">系统角色与权限分配</div>
      <el-button type="primary" :icon="Plus" @click="openCreateRole">新增角色</el-button>
    </div>

    <!-- Table -->
    <div class="table-card" v-loading="loading">
      <el-table :data="roles" stripe style="width: 100%">
        <el-table-column prop="name" label="角色名称" width="160" />
        <el-table-column prop="code" label="角色标识 (Role Code)" width="180">
          <template #default="{ row }">
            <el-tag effect="plain" type="primary">{{ row.code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="角色职能描述" min-width="220" />
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'danger'" size="small">
              {{ row.status ? '正常' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEditRole(row)">编辑/权限</el-button>
            <el-button link type="danger" size="small" :disabled="row.code === 'ADMIN'" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Create/Edit Role Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑角色与分配权限' : '新增系统角色'" width="520px">
      <el-form :model="roleForm" label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="角色名称" required>
              <el-input v-model="roleForm.name" placeholder="例如 项目经理" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="角色标识代码" required>
              <el-input v-model="roleForm.code" :disabled="isEdit && roleForm.code === 'ADMIN'" placeholder="例如 PM" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="角色描述说明">
          <el-input v-model="roleForm.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="菜单与操作权限勾选">
          <div style="border: 1px solid var(--border-color); border-radius: 6px; padding: 10px; width: 100%; max-height: 240px; overflow-y: auto">
            <el-checkbox-group v-model="roleForm.permission_ids">
              <el-row :gutter="10">
                <el-col v-for="p in allPermissions" :key="p.id" :span="12">
                  <el-checkbox :label="p.id">{{ p.name }}</el-checkbox>
                </el-col>
              </el-row>
            </el-checkbox-group>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitRole">确认保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listRolesApi, listPermissionsApi, createRoleApi, updateRoleApi, deleteRoleApi } from '@/api/user'
import type { Role } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

const loading = ref(false)
const roles = ref<Role[]>([])
const allPermissions = ref<any[]>([])

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)

const roleForm = reactive({
  name: '',
  code: '',
  description: '',
  permission_ids: [] as number[]
})

async function loadRoles() {
  loading.value = true
  try {
    const res = await listRolesApi()
    roles.value = res.data
  } finally {
    loading.value = false
  }
}

async function loadPermissions() {
  const res = await listPermissionsApi()
  allPermissions.value = res.data
}

function openCreateRole() {
  isEdit.value = false
  editId.value = null
  Object.assign(roleForm, {
    name: '',
    code: '',
    description: '',
    permission_ids: []
  })
  dialogVisible.value = true
}

function openEditRole(row: Role) {
  isEdit.value = true
  editId.value = row.id
  Object.assign(roleForm, {
    name: row.name,
    code: row.code,
    description: row.description || '',
    permission_ids: row.permissions || []
  })
  dialogVisible.value = true
}

async function submitRole() {
  if (!roleForm.name || !roleForm.code) {
    ElMessage.warning('请填写角色名称与标识代码')
    return
  }
  if (isEdit.value && editId.value) {
    await updateRoleApi(editId.value, roleForm)
    ElMessage.success('角色已更新')
  } else {
    await createRoleApi(roleForm)
    ElMessage.success('角色创建成功')
  }
  dialogVisible.value = false
  loadRoles()
}

function handleDelete(id: number) {
  ElMessageBox.confirm('确定删除该系统角色吗？', '提示', { type: 'warning' }).then(async () => {
    await deleteRoleApi(id)
    ElMessage.success('角色已删除')
    loadRoles()
  })
}

onMounted(() => {
  loadRoles()
  loadPermissions()
})
</script>

<style scoped>
</style>
