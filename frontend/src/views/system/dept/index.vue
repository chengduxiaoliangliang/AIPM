<template>
  <div class="system-dept-page page-container">
    <div class="table-search-bar flex-between">
      <div class="page-header-title">组织与部门架构体系</div>
      <el-button type="primary" :icon="Plus" @click="openCreateDept(null)">新增顶级部门</el-button>
    </div>

    <!-- Tree Table -->
    <div class="table-card" v-loading="loading">
      <el-table :data="departments" row-key="id" default-expand-all stripe style="width: 100%">
        <el-table-column prop="name" label="部门名称" min-width="200" />
        <el-table-column prop="code" label="部门编码" width="160">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="leader" label="负责人" width="140" />
        <el-table-column prop="phone" label="联系电话" width="140" />
        <el-table-column prop="email" label="部门邮箱" min-width="160" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status ? 'success' : 'danger'" size="small">
              {{ row.status ? '正常' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right" align="center">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openCreateDept(row.id)">+ 子部门</el-button>
            <el-button link type="primary" size="small" @click="openEditDept(row)">编辑</el-button>
            <el-button link type="danger" size="small" @click="handleDelete(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Create/Edit Dept Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑部门信息' : '新增组织部门'" width="480px">
      <el-form :model="deptForm" label-position="top">
        <el-form-item label="部门名称" required>
          <el-input v-model="deptForm.name" placeholder="例如 前端研发部" />
        </el-form-item>
        <el-form-item label="部门唯一编码" required>
          <el-input v-model="deptForm.code" :disabled="isEdit" placeholder="例如 FE_DEPT" />
        </el-form-item>
        <el-form-item label="上级所属部门">
          <el-tree-select
            v-model="deptForm.parent_id"
            :data="departments"
            :props="{ label: 'name', value: 'id', children: 'children' }"
            check-strictly
            clearable
            placeholder="留空为顶级部门"
            style="width: 100%"
          />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="部门负责人">
              <el-input v-model="deptForm.leader" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="deptForm.phone" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="部门邮箱">
          <el-input v-model="deptForm.email" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitDept">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listDepartmentsApi, createDepartmentApi, updateDepartmentApi, deleteDepartmentApi } from '@/api/user'
import type { Department } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'

const loading = ref(false)
const departments = ref<Department[]>([])

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)

const deptForm = reactive({
  name: '',
  code: '',
  parent_id: undefined as number | undefined,
  leader: '',
  phone: '',
  email: ''
})

async function loadDepartments() {
  loading.value = true
  try {
    const res = await listDepartmentsApi()
    departments.value = res.data
  } finally {
    loading.value = false
  }
}

function openCreateDept(parentId: number | null) {
  isEdit.value = false
  editId.value = null
  Object.assign(deptForm, {
    name: '',
    code: `DEPT_${Date.now().toString().slice(-4)}`,
    parent_id: parentId || undefined,
    leader: '',
    phone: '',
    email: ''
  })
  dialogVisible.value = true
}

function openEditDept(row: Department) {
  isEdit.value = true
  editId.value = row.id
  Object.assign(deptForm, {
    name: row.name,
    code: row.code,
    parent_id: row.parent_id,
    leader: row.leader || '',
    phone: row.phone || '',
    email: row.email || ''
  })
  dialogVisible.value = true
}

async function submitDept() {
  if (!deptForm.name || !deptForm.code) {
    ElMessage.warning('请填写部门名称与编码')
    return
  }
  if (isEdit.value && editId.value) {
    await updateDepartmentApi(editId.value, deptForm)
    ElMessage.success('部门已更新')
  } else {
    await createDepartmentApi(deptForm)
    ElMessage.success('部门创建成功')
  }
  dialogVisible.value = false
  loadDepartments()
}

function handleDelete(id: number) {
  ElMessageBox.confirm('确定删除该部门吗？', '提示', { type: 'warning' }).then(async () => {
    await deleteDepartmentApi(id)
    ElMessage.success('部门已删除')
    loadDepartments()
  })
}

onMounted(() => {
  loadDepartments()
})
</script>

<style scoped>
</style>
