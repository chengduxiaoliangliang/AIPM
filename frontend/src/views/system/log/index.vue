<template>
  <div class="system-log-page page-container">
    <div class="table-search-bar flex-between">
      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="关键词">
          <el-input v-model="queryForm.keyword" placeholder="操作人 / 日志详情 / IP" clearable @keyup.enter="handleSearch" style="width: 200px" />
        </el-form-item>
        <el-form-item label="业务模块">
          <el-select v-model="queryForm.module" placeholder="全部模块" clearable style="width: 140px">
            <el-option label="认证" value="认证" />
            <el-option label="项目管理" value="项目管理" />
            <el-option label="任务协作" value="任务协作" />
            <el-option label="工时管理" value="工时管理" />
            <el-option label="缺陷跟踪" value="缺陷跟踪" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- Table -->
    <div class="table-card" v-loading="loading">
      <el-table :data="logs" stripe style="width: 100%">
        <el-table-column prop="username" label="操作人" width="120" />
        <el-table-column prop="module" label="模块" width="120">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.module }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="action" label="操作类型" width="120">
          <template #default="{ row }">
            <el-tag :type="row.action === '删除' ? 'danger' : row.action === '创建' ? 'success' : 'primary'" size="small">
              {{ row.action }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="details" label="操作详情内容" min-width="260" />
        <el-table-column prop="ip" label="请求 IP" width="140" />
        <el-table-column prop="status_code" label="状态码" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status_code === 200 ? 'success' : 'danger'" size="small">
              {{ row.status_code }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="操作时间" width="180" />
      </el-table>

      <!-- Pagination -->
      <div style="margin-top: 16px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="queryForm.page"
          v-model:page-size="queryForm.page_size"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadLogs"
          @current-change="loadLogs"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listAuditLogsApi } from '@/api/stats'
import { Search, Refresh } from '@element-plus/icons-vue'

const loading = ref(false)
const logs = ref<any[]>([])
const total = ref(0)

const queryForm = reactive({
  keyword: '',
  module: '',
  page: 1,
  page_size: 10
})

async function loadLogs() {
  loading.value = true
  try {
    const res = await listAuditLogsApi(queryForm)
    logs.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  queryForm.page = 1
  loadLogs()
}

function handleReset() {
  queryForm.keyword = ''
  queryForm.module = ''
  queryForm.page = 1
  loadLogs()
}

onMounted(() => {
  loadLogs()
})
</script>

<style scoped>
</style>
