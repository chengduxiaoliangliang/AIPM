<template>
  <div class="document-page page-container">
    <div class="table-search-bar flex-between">
      <el-form :inline="true" :model="queryForm" class="filter-form">
        <el-form-item label="关键词">
          <el-input v-model="queryForm.keyword" placeholder="文档标题 / 内容" clearable @keyup.enter="handleSearch" style="width: 180px" />
        </el-form-item>
        <el-form-item label="所属项目">
          <el-select v-model="queryForm.project_id" placeholder="全部项目" clearable style="width: 180px">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="queryForm.category" placeholder="全部分类" clearable style="width: 130px">
            <el-option label="架构设计" value="design" />
            <el-option label="需求说明" value="requirement" />
            <el-option label="接口文档" value="api" />
            <el-option label="运维部署" value="deployment" />
            <el-option label="会议纪要" value="meeting" />
            <el-option label="通用规范" value="general" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
          <el-button :icon="Refresh" @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>

      <div>
        <el-button type="primary" :icon="Plus" @click="openCreateDoc">新建文档</el-button>
      </div>
    </div>

    <!-- Documents Grid -->
    <div class="docs-grid" v-loading="loading">
      <el-row :gutter="16">
        <el-col v-for="doc in documents" :key="doc.id" :xs="24" :sm="12" :md="8" style="margin-bottom: 16px">
          <div class="doc-card vben-card" @click="previewDoc(doc)">
            <div class="doc-header flex-between">
              <el-tag size="small" effect="plain" type="primary">{{ getCategoryName(doc.category) }}</el-tag>
              <span class="doc-version">{{ doc.version }}</span>
            </div>
            <div class="doc-title">{{ doc.title }}</div>
            <div class="doc-preview">{{ doc.content?.slice(0, 100) || '暂无内容' }}...</div>
            <div class="doc-footer flex-between">
              <span class="doc-author">作者: {{ doc.author_name }}</span>
              <div class="doc-actions">
                <el-button link type="primary" size="small" @click.stop="openEditDoc(doc)">编辑</el-button>
                <el-button link type="danger" size="small" @click.stop="handleDelete(doc.id)">删除</el-button>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- Create/Edit Doc Dialog -->
    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑知识库文档' : '新建知识库文档'" width="680px">
      <el-form :model="docForm" label-position="top">
        <el-form-item label="文档标题" required>
          <el-input v-model="docForm.title" placeholder="例如 系统架构设计与数据流转规范" />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="所属项目" required>
              <el-select v-model="docForm.project_id" style="width: 100%">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="文档分类">
              <el-select v-model="docForm.category" style="width: 100%">
                <el-option label="架构设计" value="design" />
                <el-option label="需求说明" value="requirement" />
                <el-option label="接口文档" value="api" />
                <el-option label="运维部署" value="deployment" />
                <el-option label="会议纪要" value="meeting" />
                <el-option label="通用规范" value="general" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="文档内容 (Markdown / 富文本)">
          <el-input v-model="docForm.content" type="textarea" :rows="12" placeholder="# 标题\n\n正文内容..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitDoc">保存发布</el-button>
      </template>
    </el-dialog>

    <!-- Preview Doc Drawer -->
    <el-drawer v-model="previewVisible" title="知识库文档预览" size="640px">
      <div v-if="activeDoc" class="doc-view-box">
        <h2>{{ activeDoc.title }}</h2>
        <div class="doc-view-meta">
          <span>项目: {{ activeDoc.project_name }}</span>
          <span>分类: {{ getCategoryName(activeDoc.category) }}</span>
          <span>作者: {{ activeDoc.author_name }}</span>
          <span>版本: {{ activeDoc.version }}</span>
        </div>
        <div class="doc-content-body">
          <pre class="content-pre">{{ activeDoc.content }}</pre>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { listDocumentsApi, createDocumentApi, updateDocumentApi, deleteDocumentApi } from '@/api/document'
import { getAllProjectsApi } from '@/api/project'
import type { DocumentItem, Project } from '@/types'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus } from '@element-plus/icons-vue'

const loading = ref(false)
const documents = ref<DocumentItem[]>([])
const projects = ref<Project[]>([])

const queryForm = reactive({
  keyword: '',
  project_id: undefined as number | undefined,
  category: '',
  page: 1,
  page_size: 12
})

const dialogVisible = ref(false)
const isEdit = ref(false)
const editId = ref<number | null>(null)
const previewVisible = ref(false)
const activeDoc = ref<DocumentItem | null>(null)

const docForm = reactive({
  title: '',
  project_id: 1,
  category: 'general',
  version: 'v1.0',
  content: ''
})

const categoryMap: Record<string, string> = {
  design: '架构设计',
  requirement: '需求说明',
  api: '接口文档',
  deployment: '运维部署',
  meeting: '会议纪要',
  general: '通用规范'
}

function getCategoryName(cat: string) {
  return categoryMap[cat] || cat
}

async function loadDocuments() {
  loading.value = true
  try {
    const res = await listDocumentsApi(queryForm)
    documents.value = res.data.items
  } finally {
    loading.value = false
  }
}

async function loadProjects() {
  const res = await getAllProjectsApi()
  projects.value = res.data
}

function handleSearch() {
  queryForm.page = 1
  loadDocuments()
}

function handleReset() {
  queryForm.keyword = ''
  queryForm.project_id = undefined
  queryForm.category = ''
  queryForm.page = 1
  loadDocuments()
}

function previewDoc(doc: DocumentItem) {
  activeDoc.value = doc
  previewVisible.value = true
}

function openCreateDoc() {
  isEdit.value = false
  editId.value = null
  Object.assign(docForm, {
    title: '',
    project_id: projects.value[0]?.id || 1,
    category: 'general',
    version: 'v1.0',
    content: ''
  })
  dialogVisible.value = true
}

function openEditDoc(doc: DocumentItem) {
  isEdit.value = true
  editId.value = doc.id
  Object.assign(docForm, {
    title: doc.title,
    project_id: doc.project_id,
    category: doc.category,
    version: doc.version,
    content: doc.content || ''
  })
  dialogVisible.value = true
}

async function submitDoc() {
  if (!docForm.title) {
    ElMessage.warning('请输入文档标题')
    return
  }
  if (isEdit.value && editId.value) {
    await updateDocumentApi(editId.value, docForm)
    ElMessage.success('文档已更新')
  } else {
    await createDocumentApi(docForm)
    ElMessage.success('文档已发布')
  }
  dialogVisible.value = false
  loadDocuments()
}

function handleDelete(id: number) {
  ElMessageBox.confirm('确定删除该文档吗？', '提示', { type: 'warning' }).then(async () => {
    await deleteDocumentApi(id)
    ElMessage.success('文档已删除')
    loadDocuments()
  })
}

onMounted(() => {
  loadProjects()
  loadDocuments()
})
</script>

<style scoped lang="scss">
.document-page {
  .doc-card {
    padding: 16px;
    cursor: pointer;
    border-radius: var(--radius-md);

    .doc-version {
      font-size: 11px;
      font-weight: 600;
      color: var(--text-muted);
    }

    .doc-title {
      font-size: 15px;
      font-weight: 600;
      color: var(--text-main);
      margin: 10px 0 8px;
    }

    .doc-preview {
      font-size: 12px;
      color: var(--text-regular);
      line-height: 1.5;
      height: 36px;
      overflow: hidden;
      margin-bottom: 12px;
    }

    .doc-footer {
      padding-top: 10px;
      border-top: 1px solid var(--border-color);
      font-size: 12px;
      color: var(--text-muted);
    }
  }

  .doc-view-box {
    h2 { font-size: 20px; color: var(--text-main); margin-bottom: 12px; }
    .doc-view-meta {
      display: flex;
      gap: 14px;
      font-size: 12px;
      color: var(--text-muted);
      margin-bottom: 20px;
      padding-bottom: 12px;
      border-bottom: 1px solid var(--border-color);
    }
    .content-pre {
      font-family: inherit;
      white-space: pre-wrap;
      line-height: 1.6;
      font-size: 14px;
      color: var(--text-regular);
    }
  }
}
</style>
