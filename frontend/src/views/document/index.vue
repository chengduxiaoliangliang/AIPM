<template>
  <div class="kb-page page-container">
    <!-- ── Header ─────────────────────────────────────────────── -->
    <div class="kb-header vben-card">
      <div class="header-left">
        <el-select
          v-model="currentProjectId"
          placeholder="选择项目"
          style="width: 240px"
          @change="onProjectChange"
        >
          <el-option
            v-for="p in projects"
            :key="p.project_id"
            :label="p.project_name"
            :value="p.project_id"
          >
            <span>{{ p.project_name }}</span>
            <span class="opt-meta">{{ p.pages }} 页 / {{ p.sources }} 资料</span>
          </el-option>
          <el-option label="🌐 全部项目（跨项目检索）" :value="0">
            <span>🌐 全部项目</span>
            <span class="opt-meta">跨项目检索</span>
          </el-option>
        </el-select>

        <div class="kb-stats" v-if="activeSummary">
          <span><b>{{ activeSummary.pages }}</b> 页面</span>
          <span class="sep">·</span>
          <span><b>{{ activeSummary.sources }}</b> 资料</span>
          <span class="sep">·</span>
          <span><b>{{ activeSummary.links }}</b> 双链</span>
          <span class="health-chip" v-if="lint" :class="healthClass(lint.score)">
            健康分 {{ lint.score }}
          </span>
        </div>
      </div>

      <div class="header-actions">
        <el-button-group class="view-toggle">
          <el-button :type="viewMode === 'reader' ? 'primary' : ''" @click="setView('reader')">阅读</el-button>
          <el-button :type="viewMode === 'graph' ? 'primary' : ''" @click="setView('graph')">图谱</el-button>
          <el-button :type="viewMode === 'ask' ? 'primary' : ''" @click="setView('ask')">问答</el-button>
        </el-button-group>
        <el-button :icon="Plus" @click="openCreatePage">新建页面</el-button>
        <el-button type="primary" :icon="Upload" :disabled="isAllProjects" @click="uploadVisible = true">上传资料</el-button>
        <el-button :icon="DataAnalysis" :loading="linting" @click="runLint(false)">体检</el-button>
        <el-button :icon="Download" :disabled="isAllProjects" @click="exportWiki">导出</el-button>
      </div>
    </div>

    <!-- ── Ingest banner ──────────────────────────────────────── -->
    <div class="ingest-banner" v-if="runningJobs.length">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>AI 正在整理知识库（{{ runningJobs.length }} 个任务进行中）…</span>
      <span class="ingest-detail">{{ runningJobs[0]?.stage }} · {{ runningJobs[0]?.progress }}%</span>
    </div>

    <!-- ── Body ───────────────────────────────────────────────── -->
    <div class="kb-body">
      <!-- Left: structure tree -->
      <aside class="kb-side vben-card">
        <div class="side-head">
          <span class="side-title">知识结构</span>
          <el-button link :icon="Refresh" size="small" @click="reloadStructure" />
        </div>

        <el-scrollbar class="side-scroll">
          <div v-if="!structure || structure.total_pages === 0" class="side-empty">
            暂无页面，上传资料后 AI 会自动构建
          </div>

          <template v-else>
            <div v-for="g in nonEmptyGroups" :key="g.type" class="group">
              <div class="group-head" @click="toggleGroup(g.type)">
                <el-icon class="chev" :class="{ open: openGroups.includes(g.type) }"><ArrowRight /></el-icon>
                <span class="group-label">{{ g.label }}</span>
                <span class="group-count">{{ g.pages.length }}</span>
              </div>
              <div v-show="openGroups.includes(g.type)" class="group-body">
                <div
                  v-for="p in g.pages"
                  :key="p.id"
                  class="page-item"
                  :class="{ active: activePage?.id === p.id }"
                  @click="openPageById(p.id)"
                >
                  <span class="page-dot" :class="`t-${g.type}`"></span>
                  <span class="page-name">{{ p.title }}</span>
                  <span class="page-proj" v-if="isAllProjects && p.project_name">{{ p.project_name }}</span>
                </div>
              </div>
            </div>

            <div class="special-links" v-if="!isAllProjects">
              <div class="page-item" @click="openSpecial('index')">
                <el-icon><Files /></el-icon><span class="page-name">知识库索引</span>
              </div>
              <div class="page-item" @click="openSpecial('log')">
                <el-icon><Clock /></el-icon><span class="page-name">变更日志</span>
              </div>
            </div>
          </template>
        </el-scrollbar>
      </aside>

      <!-- Center: reader / graph -->
      <main class="kb-main vben-card" v-loading="pageLoading">
        <div v-if="viewMode === 'graph'" class="graph-wrap">
          <div v-show="graphHasData" ref="graphRef" class="kb-graph"></div>
          <el-empty v-if="!graphHasData" description="还没有页面，无法生成图谱" :image-size="90" />
          <div class="graph-mode" v-if="graphHasData">
            <el-button size="small" :type="graphColorMode === 'type' ? 'primary' : ''" @click="setGraphMode('type')">按类型</el-button>
            <el-button size="small" :type="graphColorMode === 'community' ? 'primary' : ''" @click="setGraphMode('community')">按社区</el-button>
          </div>
          <div class="graph-tip" v-if="graphHasData">
            节点大小 = 被引用次数 · 点击节点查看页面 · 支持拖拽与缩放
          </div>
        </div>

        <!-- Q&A over the wiki -->
        <div v-else-if="viewMode === 'ask'" class="ask-wrap">
          <el-scrollbar class="ask-scroll">
            <div class="ask-inner">
              <div class="ask-intro" v-if="!askText && !asking">
                <div class="ask-title">基于知识库提问</div>
                <div class="ask-sub">回答只使用知识库里的页面，并标注来源；资料未覆盖的内容会明确说明。</div>
                <div class="ask-scope" v-if="isAllProjects">
                  当前为跨项目检索，将同时搜索你有权访问的全部项目知识库
                </div>
                <div class="ask-samples" v-if="askSamples.length">
                  <span v-for="s in askSamples" :key="s" class="ask-sample" @click="askQuestion(s)">{{ s }}</span>
                </div>
              </div>

              <div class="ask-q" v-if="askQuestionText">Q：{{ askQuestionText }}</div>

              <div class="ask-loading" v-if="asking && !askText">
                <el-icon class="is-loading"><Loading /></el-icon>
                <span>正在检索知识库…</span>
              </div>

              <template v-if="askText">
                <div class="markdown-body" v-html="renderAnswer" @click="onContentClick"></div>
                <span class="ask-cursor" v-if="asking"></span>

                <div class="backlinks" v-if="askCitations.length">
                  <div class="bl-title">引用页面</div>
                  <div class="bl-list">
                    <span
                      v-for="c in askCitations"
                      :key="c.id"
                      class="bl-chip"
                      @click="openPageById(c.id)"
                    >
                      {{ c.title }}
                      <em v-if="c.project" class="cite-proj">{{ c.project }}</em>
                    </span>
                  </div>
                </div>

                <div class="ask-actions" v-if="!asking">
                  <el-button size="small" :icon="Document" :loading="savingAnswer" @click="saveAnswer">
                    存入知识库
                  </el-button>
                  <el-button size="small" link @click="resetAsk">重新提问</el-button>
                </div>
              </template>
            </div>
          </el-scrollbar>

          <div class="ask-input">
            <el-input
              v-model="askInput"
              placeholder="向知识库提问，例如：系统的权限模型是怎样的？"
              :disabled="asking"
              @keyup.enter="askQuestion()"
            />
            <el-button type="primary" :loading="asking" @click="askQuestion()">提问</el-button>
          </div>
        </div>

        <template v-else-if="activePage">
          <div class="page-toolbar">
            <div class="pt-left">
              <el-tag size="small" effect="plain" :type="tagType(activePage.page_type)">
                {{ typeLabel(activePage.page_type) }}
              </el-tag>
              <span class="pt-title">{{ activePage.title }}</span>
            </div>
            <div class="pt-actions">
              <span class="pt-meta">更新于 {{ fmtDate(activePage.updated_at) }}</span>
              <el-button
                v-if="!isReserved(activePage.slug)"
                link
                :icon="Clock"
                @click="openVersions(activePage)"
              >历史</el-button>
              <el-button
                v-if="!isReserved(activePage.slug)"
                link
                :icon="Edit"
                @click="openEditPage(activePage)"
              >编辑</el-button>
              <el-button
                v-if="!isReserved(activePage.slug)"
                link
                type="danger"
                :icon="Delete"
                @click="removePage(activePage)"
              >删除</el-button>
            </div>
          </div>

          <el-scrollbar class="reader-scroll">
            <div class="page-summary" v-if="activePage.summary">{{ activePage.summary }}</div>

            <div class="markdown-body" v-html="renderedContent" @click="onContentClick"></div>

            <div class="backlinks" v-if="activePage.inbound_links.length">
              <div class="bl-title">被以下页面引用</div>
              <div class="bl-list">
                <span
                  v-for="l in activePage.inbound_links"
                  :key="l.id"
                  class="bl-chip"
                  @click="openPageById(l.id)"
                >{{ l.title }}</span>
              </div>
            </div>

            <div class="page-sources" v-if="activePage.sources.length">
              <div class="bl-title">来源资料</div>
              <div class="bl-list">
                <span v-for="s in activePage.sources" :key="s.id" class="src-chip">
                  <el-icon><Document /></el-icon>{{ s.name }}
                </span>
              </div>
            </div>
          </el-scrollbar>
        </template>

        <el-empty v-else description="从左侧选择一个页面，或上传资料让 AI 自动生成" />
      </main>

      <!-- Right: sources + health -->
      <aside class="kb-right vben-card">
        <div class="side-head">
          <span class="side-title">资料库</span>
          <el-button link :icon="Upload" size="small" @click="uploadVisible = true" />
        </div>

        <el-scrollbar class="right-scroll">
          <div v-if="!sources.length" class="side-empty">
            {{ isAllProjects ? '跨项目模式下不显示资料列表，请切换到具体项目上传或管理资料' : '还没有上传任何资料' }}
          </div>

          <div v-for="s in sources" :key="s.id" class="src-item">
            <div class="src-main">
              <div class="src-name" :title="s.original_name">{{ s.original_name }}</div>
              <div class="src-meta">
                {{ fmtSize(s.size_bytes) }}
                <span v-if="s.char_count">· {{ s.char_count }} 字</span>
              </div>
            </div>
            <div class="src-side">
              <el-tag size="small" :type="srcTagType(s.status)" effect="plain">
                {{ srcStatusText(s.status) }}
              </el-tag>
              <div class="src-ops">
                <el-tooltip content="下载原文件" placement="top">
                  <el-icon class="op" @click="downloadSource(s)"><Download /></el-icon>
                </el-tooltip>
                <el-tooltip content="重新摄入" placement="top">
                  <el-icon class="op" @click="ingestOne(s)" :class="{ disabled: s.status === 'ingesting' }">
                    <MagicStick />
                  </el-icon>
                </el-tooltip>
                <el-tooltip content="删除" placement="top">
                  <el-icon class="op danger" @click="removeSource(s)"><Delete /></el-icon>
                </el-tooltip>
              </div>
            </div>
            <div class="src-error" v-if="s.error_message">{{ s.error_message }}</div>
          </div>
        </el-scrollbar>

        <div class="health-card" v-if="lint">
          <div class="hc-head">
            <span>最近体检</span>
            <span class="hc-score" :class="healthClass(lint.score)">{{ lint.score }}</span>
          </div>
          <div class="hc-bar">
            <div class="hc-fill" :class="healthClass(lint.score)" :style="{ width: lint.score + '%' }"></div>
          </div>
          <div class="hc-meta">
            {{ lint.issues.length }} 个问题 · {{ fmtDate(lint.created_at) }}
          </div>
          <el-button link type="primary" size="small" @click="lintVisible = true">查看报告</el-button>
        </div>
      </aside>
    </div>

    <!-- ── Upload dialog ──────────────────────────────────────── -->
    <el-dialog v-model="uploadVisible" title="上传资料" width="620px">
      <div class="upload-hint">
        支持 PDF / Word / Excel / Markdown / TXT / 代码等格式。上传后会自动抽取正文，并交由 AI 整理进知识库。
      </div>
      <el-upload
        drag
        multiple
        :auto-upload="false"
        :file-list="uploadFileList"
        :on-change="onFileChange"
        :on-remove="onFileRemove"
        :limit="10"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">拖拽文件到此处，或<em>点击选择</em></div>
        <template #tip>
          <div class="el-upload__tip">单个文件不超过 25MB，一次最多 10 个</div>
        </template>
      </el-upload>
      <template #footer>
        <el-button @click="uploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploading" @click="submitUpload">
          上传并整理（{{ uploadFileList.length }}）
        </el-button>
      </template>
    </el-dialog>

    <!-- ── Page editor ────────────────────────────────────────── -->
    <el-dialog v-model="editorVisible" :title="editingId ? '编辑页面' : '新建页面'" width="760px">
      <el-form :model="pageForm" label-position="top">
        <el-row :gutter="16">
          <el-col :span="16">
            <el-form-item label="标题" required>
              <el-input v-model="pageForm.title" placeholder="页面标题" />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="页面类型">
              <el-select v-model="pageForm.page_type" style="width: 100%">
                <el-option v-for="t in pageTypes" :key="t.value" :label="t.label" :value="t.value" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="一句话摘要">
          <el-input v-model="pageForm.summary" placeholder="用于索引页展示" />
        </el-form-item>
        <el-form-item label="正文（Markdown，使用 [[页面标题]] 建立双链）">
          <el-input v-model="pageForm.content" type="textarea" :rows="16" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitPage">保存</el-button>
      </template>
    </el-dialog>

    <!-- ── Lint drawer ────────────────────────────────────────── -->
    <el-drawer v-model="lintVisible" title="知识库体检报告" size="560px">
      <div v-if="lint" class="lint-box">
        <div class="lint-score-row">
          <div class="lint-score" :class="healthClass(lint.score)">{{ lint.score }}</div>
          <div class="lint-score-meta">
            <div>健康分</div>
            <div class="muted">{{ fmtDate(lint.created_at) }}</div>
          </div>
        </div>

        <div class="lint-stats">
          <div v-for="(v, k) in lint.stats" :key="k" class="ls-item">
            <div class="ls-v">{{ v }}</div>
            <div class="ls-k">{{ statLabel(String(k)) }}</div>
          </div>
        </div>

        <el-empty v-if="!lint.issues.length" description="没有发现问题，知识库很健康" :image-size="80" />

        <div v-for="(iss, i) in lint.issues" :key="i" class="issue">
          <div class="issue-head">
            <el-tag size="small" :type="severityType(iss.severity)" effect="dark">
              {{ severityText(iss.severity) }}
            </el-tag>
            <span class="issue-type">{{ issueTypeText(iss.type) }}</span>
            <span class="issue-page" v-if="iss.page">{{ iss.page }}</span>
          </div>
          <div class="issue-detail">{{ iss.detail }}</div>
          <div class="issue-sug" v-if="iss.suggestion">建议：{{ iss.suggestion }}</div>
        </div>
      </div>
    </el-drawer>

    <!-- ── Version history ─────────────────────────────────────── -->
    <el-drawer v-model="versionVisible" title="页面历史" size="600px">
      <div v-if="!versions.length" class="side-empty">还没有历史版本</div>
      <div v-else class="ver-box">
        <div class="ver-list">
          <div
            v-for="v in versions"
            :key="v.id"
            class="ver-item"
            :class="{ active: activeVersion?.id === v.id }"
            @click="previewVersion(v)"
          >
            <div class="ver-head">
              <span class="ver-no">v{{ v.version_no }}</span>
              <el-tag size="small" effect="plain">{{ changeTypeText(v.change_type) }}</el-tag>
              <span class="ver-time">{{ fmtDate(v.created_at) }}</span>
            </div>
            <div class="ver-title">{{ v.title }}</div>
          </div>
        </div>

        <div class="ver-preview" v-if="activeVersion">
          <div class="ver-preview-head">
            <span>v{{ activeVersion.version_no }} 内容预览</span>
            <el-button size="small" type="primary" @click="doRestore(activeVersion)">
              回滚到此版本
            </el-button>
          </div>
          <div class="markdown-body" v-html="renderVersionContent"></div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Plus, Upload, Download, Refresh, Edit, Delete, DataAnalysis, MagicStick,
  Document, Files, Clock, ArrowRight, Loading, UploadFilled
} from '@element-plus/icons-vue'
import {
  listKBProjectsApi, getKBStructureApi, listKBSourcesApi, getKBPageApi,
  createKBPageApi, updateKBPageApi, deleteKBPageApi, uploadKBSourcesApi,
  deleteKBSourceApi, ingestKBSourceApi, listKBJobsApi, runKBLintApi,
  getLatestKBLintApi, downloadKBSourceApi, exportKBWikiApi, getKBGraphApi,
  listKBPageVersionsApi, getKBVersionApi, restoreKBVersionApi,
  streamAskKBApi, getKBStructureAllApi, getKBGraphAllApi, runKBLintAllApi
} from '@/api/kb'
import type {
  KBProjectSummary, KBStructure, KBSource, KBPageBrief, KBPageDetail,
  KBLintReport, KBIngestJob, KBPageVersionBrief, KBPageVersionDetail, KBAskCitation
} from '@/api/kb'

const md = new MarkdownIt({ html: false, linkify: true, breaks: true })

const projects = ref<KBProjectSummary[]>([])
const currentProjectId = ref<number>()
const structure = ref<KBStructure | null>(null)
const sources = ref<KBSource[]>([])
const activePage = ref<KBPageDetail | null>(null)
const lint = ref<KBLintReport | null>(null)
const jobs = ref<KBIngestJob[]>([])

const pageLoading = ref(false)
const linting = ref(false)
const uploading = ref(false)
const saving = ref(false)

const uploadVisible = ref(false)
const editorVisible = ref(false)
const lintVisible = ref(false)
const uploadFileList = ref<any[]>([])
const openGroups = ref<string[]>(['overview', 'topic'])

// Graph view
const viewMode = ref<'reader' | 'graph' | 'ask'>('reader')
const graphRef = ref<HTMLElement>()
const graphHasData = ref(false)
const graphColorMode = ref<'type' | 'community'>('type')
let graphChart: echarts.ECharts | null = null

// Version history
const versionVisible = ref(false)
const versions = ref<KBPageVersionBrief[]>([])
const activeVersion = ref<KBPageVersionDetail | null>(null)
const versionPageId = ref<number | null>(null)

// Knowledge-base Q&A
const askInput = ref('')
const askQuestionText = ref('')
const askText = ref('')
const askCitations = ref<KBAskCitation[]>([])
const asking = ref(false)
const savingAnswer = ref(false)

const editingId = ref<number | null>(null)
const pageForm = reactive({ title: '', page_type: 'topic', summary: '', content: '' })

const pageTypes = [
  { value: 'overview', label: '综述' },
  { value: 'topic', label: '主题' },
  { value: 'entity', label: '实体' },
  { value: 'comparison', label: '对比' },
  { value: 'decision', label: '决策' },
  { value: 'source', label: '资料' }
]

const TYPE_LABEL: Record<string, string> = {
  overview: '综述', topic: '主题', entity: '实体', comparison: '对比',
  decision: '决策', source: '资料', index: '索引', log: '日志'
}

const activeSummary = computed(() =>
  projects.value.find((p) => p.project_id === currentProjectId.value)
)

/** project_id 0 means "all projects" (cross-project mode). */
const isAllProjects = computed(() => currentProjectId.value === 0)

const nonEmptyGroups = computed(() =>
  (structure.value?.groups || []).filter((g) => g.pages.length > 0)
)

const runningJobs = computed(() =>
  jobs.value.filter((j) => j.status === 'running' || j.status === 'queued')
)

/** Render markdown, turning [[Page Title]] into an in-app link. */
function renderMarkdown(src: string) {
  const withLinks = (src || '').replace(
    /\[\[([^\[\]|]{1,120})(?:\|([^\[\]]{1,120}))?\]\]/g,
    (_m, target, label) => `[${label || target}](#wiki:${encodeURIComponent(String(target).trim())})`
  )
  return md.render(withLinks)
}

const renderedContent = computed(() => renderMarkdown(activePage.value?.content || ''))
const renderAnswer = computed(() => renderMarkdown(askText.value))
const renderVersionContent = computed(() => renderMarkdown(activeVersion.value?.content || ''))

/** Question suggestions derived from the project's own pages. */
const askSamples = computed(() => {
  const pages = nonEmptyGroups.value.flatMap((g) => g.pages).slice(0, 4)
  return pages.map((p) => `${p.title} 讲了什么？`)
})

// ─── formatting helpers ──────────────────────────────────────────────────────
function typeLabel(t: string) { return TYPE_LABEL[t] || t }
function isReserved(slug: string) { return slug === 'index' || slug === 'log' }
function tagType(t: string) {
  return ({ overview: 'success', topic: '', entity: 'warning', comparison: 'info', decision: 'danger' } as any)[t] || ''
}
function fmtDate(d?: string) { return d ? d.replace('T', ' ').slice(0, 16) : '' }
function fmtSize(n: number) {
  if (!n) return '0 B'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}
function healthClass(score: number) { return score >= 80 ? 'good' : score >= 60 ? 'warn' : 'bad' }
function srcStatusText(s: string) {
  return ({ uploaded: '待解析', ready: '待摄入', ingesting: '整理中', indexed: '已入库', failed: '失败' } as any)[s] || s
}
function srcTagType(s: string) {
  return ({ uploaded: 'info', ready: 'warning', ingesting: 'primary', indexed: 'success', failed: 'danger' } as any)[s] || 'info'
}
function severityType(s: string) {
  return ({ high: 'danger', medium: 'warning', low: 'info' } as any)[s] || 'info'
}
function severityText(s: string) {
  return ({ high: '高', medium: '中', low: '低' } as any)[s] || s
}
function issueTypeText(t: string) {
  return ({
    orphan: '孤立页面', broken_link: '断链', thin_content: '内容过薄',
    unindexed_source: '资料未摄入', extraction_failed: '解析失败',
    no_overview: '缺少综述', empty_wiki: '空知识库',
    contradiction: '内容矛盾', stale: '结论过时',
    missing_concept: '缺失概念', gap: '信息缺口'
  } as any)[t] || t
}
function statLabel(k: string) {
  return ({
    pages: '页面', sources: '资料', indexed_sources: '已入库',
    links: '双链', orphans: '孤岛', broken_links: '断链'
  } as any)[k] || k
}

// ─── knowledge graph ─────────────────────────────────────────────────────────
const GRAPH_COLORS: Record<string, string> = {
  overview: '#36b37e', topic: '#409eff', entity: '#e6a23c',
  comparison: '#909399', decision: '#f56c6c', source: '#b39ddb',
  index: '#cfd3d8', log: '#cfd3d8'
}

const COMMUNITY_COLORS = [
  '#409eff', '#36b37e', '#e6a23c', '#f56c6c', '#b39ddb',
  '#13c2c2', '#fa8c16', '#722ed1', '#52c41a', '#eb2f96'
]

async function setView(v: 'reader' | 'graph' | 'ask') {
  viewMode.value = v
  if (v === 'graph') {
    await nextTick()
    await renderGraph()
  }
}

async function setGraphMode(mode: 'type' | 'community') {
  graphColorMode.value = mode
  await renderGraph()
}

async function renderGraph() {
  if (!hasProject()) return
  const res = isAllProjects.value
    ? await getKBGraphAllApi()
    : await getKBGraphApi(currentProjectId.value as number)
  const nodes: any[] = res.data?.nodes || []
  const edges: any[] = res.data?.edges || []
  const communities: any[] = res.data?.communities || []
  graphHasData.value = nodes.length > 0
  await nextTick()

  if (!graphHasData.value || !graphRef.value) {
    graphChart?.dispose()
    graphChart = null
    return
  }

  if (!graphChart) graphChart = echarts.init(graphRef.value)

  const byCommunity = graphColorMode.value === 'community' && communities.length > 0

  // Category 0..n-1 must line up with the node's `category` index.
  const cats: string[] = byCommunity
    ? communities.map((c: any) => `簇${c.id + 1}·${c.label}`)
    : Array.from(new Set(nodes.map((n) => n.type)))
  const catIndex = byCommunity
    ? new Map(communities.map((c: any) => [c.id, c.id]))
    : new Map(cats.map((c, i) => [c, i]))

  const catColor = (i: number) => (byCommunity
    ? COMMUNITY_COLORS[i % COMMUNITY_COLORS.length]
    : (GRAPH_COLORS[cats[i]] || '#909399'))

  graphChart.setOption({
    tooltip: {
      formatter: (p: any) => {
        if (p.dataType !== 'node') return ''
        const comm = byCommunity && communities[p.data.comm]
          ? `<br/>社区：${communities[p.data.comm].label}`
          : ''
        return `<b>${p.data.name}</b><br/>类型：${typeLabel(p.data.rawType)}`
          + `<br/>被引用：${p.data.value} 次${comm}`
      }
    },
    legend: [{
      data: cats,
      bottom: 8, icon: 'circle', itemWidth: 8, itemHeight: 8,
      textStyle: { fontSize: 11 }
    }],
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      force: { repulsion: 280, edgeLength: [90, 180], gravity: 0.08, friction: 0.2 },
      label: { show: true, position: 'right', fontSize: 11, color: '#4a5568', formatter: '{b}' },
      lineStyle: { color: 'source', curveness: 0.12, opacity: 0.45, width: 1 },
      emphasis: { focus: 'adjacency', lineStyle: { width: 2, opacity: 0.9 } },
      categories: cats.map((name, i) => ({
        name,
        itemStyle: { color: catColor(i) }
      })),
      data: nodes.map((n) => ({
        id: String(n.id),
        name: n.title,
        rawType: n.type,
        comm: n.community ?? 0,
        value: n.inbound || 0,
        category: byCommunity ? (catIndex.get(n.community ?? 0) ?? 0) : catIndex.get(n.type),
        symbolSize: n.reserved ? 10 : Math.min(40, 13 + (n.inbound || 0) * 2.5)
      })),
      edges: edges.map((e) => ({ source: String(e.source), target: String(e.target) }))
    }]
  }, true)

  graphChart.off('click')
  graphChart.on('click', (p: any) => {
    if (p.dataType !== 'node') return
    const id = Number(p.data.id)
    if (id) {
      viewMode.value = 'reader'
      openPageById(id)
    }
  })
}

function onResize() {
  graphChart?.resize()
}

// ─── data loading ────────────────────────────────────────────────────────────
async function loadProjects() {
  const res = await listKBProjectsApi()
  projects.value = res.data || []
  if (!currentProjectId.value && projects.value.length) {
    currentProjectId.value = projects.value[0].project_id
  }
}

function hasProject(): boolean {
  return typeof currentProjectId.value === 'number'
}

async function loadStructure() {
  if (!hasProject()) return
  const res = isAllProjects.value
    ? await getKBStructureAllApi()
    : await getKBStructureApi(currentProjectId.value as number)
  structure.value = res.data
}

async function loadSources() {
  // Sources belong to a single project — cross-project mode has no source list.
  if (!hasProject() || isAllProjects.value) {
    sources.value = []
    return
  }
  const res = await listKBSourcesApi(currentProjectId.value as number)
  sources.value = res.data || []
}

async function loadLint() {
  if (!hasProject() || isAllProjects.value) {
    lint.value = null
    return
  }
  const res = await getLatestKBLintApi(currentProjectId.value as number)
  lint.value = res.data || null
}

async function loadJobs() {
  if (!hasProject() || isAllProjects.value) {
    jobs.value = []
    return
  }
  const res = await listKBJobsApi(currentProjectId.value as number)
  jobs.value = res.data || []
}

async function reloadStructure() {
  await Promise.all([loadStructure(), loadSources(), loadProjects()])
}

async function onProjectChange() {
  activePage.value = null
  lint.value = null
  graphChart?.dispose()
  graphChart = null
  await Promise.all([loadStructure(), loadSources(), loadLint(), loadJobs()])
  if (viewMode.value === 'graph') {
    await renderGraph()
    return
  }
  const first = nonEmptyGroups.value[0]?.pages[0]
  if (first) openPageById(first.id)
}

function toggleGroup(type: string) {
  const i = openGroups.value.indexOf(type)
  if (i >= 0) openGroups.value.splice(i, 1)
  else openGroups.value.push(type)
}

// ─── page reading ────────────────────────────────────────────────────────────
async function openPageById(id: number) {
  pageLoading.value = true
  try {
    const res = await getKBPageApi(id)
    activePage.value = res.data
  } finally {
    pageLoading.value = false
  }
}

async function openSpecial(slug: string) {
  const p: KBPageBrief | undefined = structure.value?.special?.[slug]
  if (p) await openPageById(p.id)
  else ElMessage.info('该页面尚未生成，请先上传资料')
}

function findPageByTitle(title: string): KBPageBrief | undefined {
  const all = (structure.value?.groups || []).flatMap((g) => g.pages)
  const lower = title.trim().toLowerCase()
  return all.find((p) => p.title.trim().toLowerCase() === lower)
}

function onContentClick(e: MouseEvent) {
  const a = (e.target as HTMLElement).closest('a')
  if (!a) return
  const href = a.getAttribute('href') || ''
  if (!href.startsWith('#wiki:')) return
  e.preventDefault()
  const title = decodeURIComponent(href.slice(6))
  const target = findPageByTitle(title)
  if (target) openPageById(target.id)
  else ElMessage.warning(`页面「${title}」还不存在`)
}

// ─── upload & ingest ─────────────────────────────────────────────────────────
function onFileChange(_file: any, files: any[]) { uploadFileList.value = files }
function onFileRemove(_file: any, files: any[]) { uploadFileList.value = files }

async function submitUpload() {
  if (!currentProjectId.value || !uploadFileList.value.length) {
    ElMessage.warning('请选择要上传的文件')
    return
  }
  const files = uploadFileList.value.map((f) => f.raw).filter(Boolean) as File[]
  if (!files.length) return

  uploading.value = true
  try {
    const res = await uploadKBSourcesApi(currentProjectId.value, files)
    const created = res.data || []
    uploadVisible.value = false
    uploadFileList.value = []

    const ready = created.filter((s) => s.char_count > 0)
    const failed = created.filter((s) => s.char_count === 0)
    ElMessage.success(`已上传 ${created.length} 个文件，成功解析 ${ready.length} 个`)
    if (failed.length) {
      ElMessage.warning(`${failed.length} 个文件未能提取文本，请检查格式`)
    }

    await loadSources()

    // Every uploaded file should be organised into the wiki automatically.
    for (const s of ready) {
      try { await ingestKBSourceApi(s.id) } catch { /* surfaced by job polling */ }
    }
    if (ready.length) startPolling(true)
  } finally {
    uploading.value = false
  }
}

async function ingestOne(s: KBSource) {
  if (s.status === 'ingesting') return
  if (!s.char_count) {
    ElMessage.warning('该文件没有可用的文本内容')
    return
  }
  try {
    await ingestKBSourceApi(s.id)
    ElMessage.success('已加入整理队列')
    startPolling(false)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  }
}

// ─── polling ─────────────────────────────────────────────────────────────────
let pollTimer: number | null = null
let autoLintAfter = false

function startPolling(autoLint: boolean) {
  autoLintAfter = autoLintAfter || autoLint
  if (pollTimer) return
  pollTimer = window.setInterval(tick, 2500)
  tick()
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
}

async function tick() {
  try {
    await loadJobs()
    await loadSources()
    if (runningJobs.value.length === 0) {
      stopPolling()
      await reloadStructure()
      if (viewMode.value === 'graph') await renderGraph()
      const shouldLint = autoLintAfter
      autoLintAfter = false
      if (shouldLint) await runLint(true)
    }
  } catch {
    stopPolling()
  }
}

// ─── lint ────────────────────────────────────────────────────────────────────
async function runLint(silent: boolean) {
  if (!hasProject()) return
  linting.value = true
  try {
    // In cross-project mode, sweep every accessible project at once.
    if (isAllProjects.value) {
      const res = await runKBLintAllApi()
      const list = res.data || []
      ElMessage.success(`已完成 ${list.length} 个项目的体检`)
      await loadProjects()
      return
    }

    const res = await runKBLintApi(currentProjectId.value as number)
    lint.value = res.data
    if (!silent) lintVisible.value = true
    else if (res.data) {
      ElMessage.success(`体检完成，健康分 ${res.data.score}，发现 ${res.data.issues.length} 个问题`)
      lintVisible.value = true
    }
    await loadProjects()
  } finally {
    linting.value = false
  }
}

// ─── version history ─────────────────────────────────────────────────────────
function changeTypeText(t: string) {
  return ({ create: '创建', update: 'AI 更新', manual: '手动编辑', restore: '回滚' } as any)[t] || t
}

async function openVersions(p: KBPageDetail) {
  versionPageId.value = p.id
  versionVisible.value = true
  activeVersion.value = null
  const res = await listKBPageVersionsApi(p.id)
  versions.value = res.data || []
  if (versions.value.length) await previewVersion(versions.value[0])
}

async function previewVersion(v: KBPageVersionBrief) {
  const res = await getKBVersionApi(v.id)
  activeVersion.value = res.data
}

async function doRestore(v: KBPageVersionDetail) {
  await ElMessageBox.confirm(
    `确定回滚到 v${v.version_no}？当前内容会先保存为一个新版本，可再次回滚。`,
    '回滚确认',
    { type: 'warning' }
  )
  await restoreKBVersionApi(v.id)
  ElMessage.success(`已回滚到 v${v.version_no}`)
  versionVisible.value = false
  await reloadStructure()
  if (versionPageId.value) await openPageById(versionPageId.value)
}

// ─── knowledge-base Q&A ──────────────────────────────────────────────────────
async function askQuestion(preset?: string) {
  const q = (preset || askInput.value || '').trim()
  if (!q) {
    ElMessage.warning('请输入问题')
    return
  }
  if (!hasProject()) return

  askInput.value = q
  askQuestionText.value = q
  askText.value = ''
  askCitations.value = []
  asking.value = true

  const target = isAllProjects.value ? null : (currentProjectId.value as number)
  await streamAskKBApi(target, q, {
    onCitations: (c) => { askCitations.value = c },
    onToken: (t) => { askText.value += t },
    onFinish: () => { asking.value = false },
    onError: (e: any) => {
      asking.value = false
      ElMessage.error(e?.message || '提问失败，请稍后重试')
    }
  })
  asking.value = false
}

function resetAsk() {
  askText.value = ''
  askCitations.value = []
  askQuestionText.value = ''
}

async function saveAnswer() {
  if (!askText.value || !askQuestionText.value) return
  if (!hasProject() || isAllProjects.value) {
    ElMessage.warning('请先切换到具体项目，再保存到知识库')
    return
  }
  savingAnswer.value = true
  try {
    const refs = askCitations.value.map((c) => `- [[${c.title}]]`).join('\n')
    const content = askText.value + (refs ? `\n\n## 参考页面\n${refs}` : '')
    const res = await createKBPageApi(currentProjectId.value as number, {
      title: `问答：${askQuestionText.value.slice(0, 40)}`,
      page_type: 'topic',
      summary: askQuestionText.value.slice(0, 200),
      content
    })
    ElMessage.success(`已存入知识库：${res.data.title}`)
    await reloadStructure()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    savingAnswer.value = false
  }
}

// ─── page CRUD ───────────────────────────────────────────────────────────────
function openCreatePage() {
  editingId.value = null
  Object.assign(pageForm, { title: '', page_type: 'topic', summary: '', content: '' })
  editorVisible.value = true
}

function openEditPage(p: KBPageDetail) {
  editingId.value = p.id
  Object.assign(pageForm, {
    title: p.title,
    page_type: p.page_type,
    summary: p.summary || '',
    content: p.content || ''
  })
  editorVisible.value = true
}

async function submitPage() {
  if (!pageForm.title.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  saving.value = true
  try {
    if (editingId.value) {
      await updateKBPageApi(editingId.value, { ...pageForm })
      ElMessage.success('已保存')
    } else if (currentProjectId.value) {
      await createKBPageApi(currentProjectId.value, { ...pageForm })
      ElMessage.success('已创建')
    }
    editorVisible.value = false
    await reloadStructure()
    if (editingId.value) await openPageById(editingId.value)
  } finally {
    saving.value = false
  }
}

async function removePage(p: KBPageDetail) {
  await ElMessageBox.confirm(`确定删除页面「${p.title}」吗？`, '提示', { type: 'warning' })
  await deleteKBPageApi(p.id)
  ElMessage.success('已删除')
  activePage.value = null
  await reloadStructure()
}

// ─── sources ─────────────────────────────────────────────────────────────────
async function downloadSource(s: KBSource) {
  const blob = await downloadKBSourceApi(s.id)
  saveBlob(blob, s.original_name)
}

async function removeSource(s: KBSource) {
  await ElMessageBox.confirm(`确定删除资料「${s.original_name}」吗？`, '提示', { type: 'warning' })
  await deleteKBSourceApi(s.id)
  ElMessage.success('已删除')
  await reloadStructure()
}

async function exportWiki() {
  if (!currentProjectId.value) return
  const blob = await exportKBWikiApi(currentProjectId.value)
  const p = projects.value.find((x) => x.project_id === currentProjectId.value)
  saveBlob(blob, `${p?.project_code || 'wiki'}.zip`)
}

function saveBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.URL.revokeObjectURL(url)
}

onMounted(async () => {
  window.addEventListener('resize', onResize)
  await loadProjects()
  if (currentProjectId.value) {
    await Promise.all([loadStructure(), loadSources(), loadLint(), loadJobs()])
    const first = nonEmptyGroups.value[0]?.pages[0]
    if (first) openPageById(first.id)
    if (runningJobs.value.length) startPolling(false)
  }
})

onBeforeUnmount(() => {
  stopPolling()
  window.removeEventListener('resize', onResize)
  graphChart?.dispose()
  graphChart = null
})
</script>

<style scoped lang="scss">
.kb-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: calc(100vh - 120px);
}

/* Header */
.kb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  flex-shrink: 0;
  gap: 16px;
}
.header-left { display: flex; align-items: center; gap: 18px; }
.opt-meta { float: right; color: var(--text-muted); font-size: 12px; margin-left: 16px; }
.kb-stats {
  display: flex; align-items: center; gap: 6px;
  font-size: 13px; color: var(--text-muted);
  b { color: var(--text-main); font-weight: 600; }
  .sep { opacity: .4; }
}
.health-chip {
  margin-left: 10px; padding: 2px 10px; border-radius: 999px;
  font-size: 12px; font-weight: 600;
  &.good { background: #e8f6ee; color: #1a7f45; }
  &.warn { background: #fdf3e2; color: #a56a11; }
  &.bad  { background: #fdecec; color: #b3342f; }
}
.header-actions { display: flex; gap: 8px; }

/* Ingest banner */
.ingest-banner {
  display: flex; align-items: center; gap: 8px;
  padding: 9px 16px; border-radius: 8px;
  background: #eef4ff; color: #2b5fbf; font-size: 13px;
  flex-shrink: 0;
  .ingest-detail { margin-left: auto; opacity: .75; }
}

/* Body layout */
.kb-body {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 300px;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.kb-side, .kb-main, .kb-right {
  display: flex; flex-direction: column;
  min-height: 0; overflow: hidden;
}

.view-toggle { margin-right: 4px; }

/* Knowledge graph */
.graph-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.kb-graph { width: 100%; height: 100%; }
.graph-tip {
  position: absolute; bottom: 10px; left: 50%; transform: translateX(-50%);
  font-size: 11.5px; color: var(--text-muted);
  background: rgba(255, 255, 255, .86);
  padding: 3px 12px; border-radius: 999px;
  pointer-events: none; white-space: nowrap;
}

.side-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 14px 8px;
  .side-title { font-size: 13px; font-weight: 600; color: var(--text-main); }
}
.side-scroll, .right-scroll { flex: 1; min-height: 0; }
.side-empty {
  padding: 24px 14px; font-size: 12px; color: var(--text-muted);
  line-height: 1.6; text-align: center;
}

/* Structure tree */
.group { margin-bottom: 2px; }
.group-head {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 14px; cursor: pointer; user-select: none;
  font-size: 12px; color: var(--text-regular);
  &:hover { background: var(--bg-hover, rgba(0,0,0,.03)); }
  .chev { transition: transform .18s; font-size: 12px; }
  .chev.open { transform: rotate(90deg); }
  .group-label { flex: 1; font-weight: 500; }
  .group-count {
    font-size: 11px; color: var(--text-muted);
    background: rgba(0,0,0,.05); border-radius: 999px; padding: 0 6px;
  }
}
.group-body { padding-bottom: 4px; }
.page-item {
  display: flex; align-items: center; gap: 7px;
  padding: 6px 14px 6px 26px; cursor: pointer;
  font-size: 13px; color: var(--text-regular);
  border-left: 2px solid transparent;
  &:hover { background: var(--bg-hover, rgba(0,0,0,.03)); }
  &.active {
    background: rgba(64,158,255,.09);
    border-left-color: #409eff;
    color: #2b6fd4; font-weight: 500;
  }
  .page-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
}
.page-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: #bbb; }
.t-overview { background: #36b37e; }
.t-topic { background: #409eff; }
.t-entity { background: #e6a23c; }
.t-comparison { background: #909399; }
.t-decision { background: #f56c6c; }
.t-source { background: #b39ddb; }

.special-links {
  margin-top: 10px; padding-top: 8px;
  border-top: 1px solid var(--border-color);
  .page-item { padding-left: 14px; color: var(--text-muted); }
}

/* Reader */
.page-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 22px; border-bottom: 1px solid var(--border-color);
  flex-shrink: 0; gap: 12px;
}
.pt-left { display: flex; align-items: center; gap: 10px; min-width: 0; }
.pt-title {
  font-size: 15px; font-weight: 600; color: var(--text-main);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.pt-actions { display: flex; align-items: center; gap: 4px; flex-shrink: 0; }
.pt-meta { font-size: 12px; color: var(--text-muted); margin-right: 6px; }

.reader-scroll { flex: 1; min-height: 0; }
.reader-scroll :deep(.el-scrollbar__view) { padding: 22px 26px 40px; }

.page-summary {
  font-size: 13px; color: var(--text-muted);
  background: rgba(64,158,255,.06);
  border-left: 3px solid #409eff;
  padding: 10px 14px; border-radius: 0 6px 6px 0;
  margin-bottom: 18px; line-height: 1.7;
}

.markdown-body {
  font-size: 14px; line-height: 1.8; color: var(--text-regular);
  :deep(h1) { font-size: 22px; margin: 8px 0 16px; color: var(--text-main); font-weight: 600; }
  :deep(h2) { font-size: 17px; margin: 24px 0 10px; color: var(--text-main); font-weight: 600; }
  :deep(h3) { font-size: 15px; margin: 18px 0 8px; color: var(--text-main); font-weight: 600; }
  :deep(p) { margin: 8px 0; }
  :deep(ul), :deep(ol) { padding-left: 22px; margin: 8px 0; }
  :deep(li) { margin: 4px 0; }
  :deep(code) {
    background: rgba(0,0,0,.05); padding: 1px 5px; border-radius: 4px;
    font-size: 12.5px; font-family: var(--font-mono, monospace);
  }
  :deep(pre) {
    background: #f6f7f9; padding: 12px 14px; border-radius: 8px;
    overflow-x: auto; font-size: 12.5px;
  }
  :deep(blockquote) {
    margin: 10px 0; padding: 6px 14px;
    border-left: 3px solid #d0d5dd; color: var(--text-muted);
  }
  :deep(table) { border-collapse: collapse; margin: 12px 0; width: 100%; font-size: 13px; }
  :deep(th), :deep(td) { border: 1px solid var(--border-color); padding: 6px 10px; text-align: left; }
  :deep(th) { background: #f7f8fa; font-weight: 600; }
  :deep(a) { color: #2b6fd4; text-decoration: none; }
  :deep(a:hover) { text-decoration: underline; }
}

.backlinks, .page-sources {
  margin-top: 28px; padding-top: 16px;
  border-top: 1px dashed var(--border-color);
}
.bl-title { font-size: 12px; color: var(--text-muted); margin-bottom: 8px; }
.bl-list { display: flex; flex-wrap: wrap; gap: 8px; }
.bl-chip {
  font-size: 12px; padding: 3px 10px; border-radius: 999px;
  background: rgba(64,158,255,.1); color: #2b6fd4; cursor: pointer;
  &:hover { background: rgba(64,158,255,.18); }
}
.src-chip {
  display: inline-flex; align-items: center; gap: 5px;
  font-size: 12px; padding: 3px 10px; border-radius: 6px;
  background: rgba(0,0,0,.04); color: var(--text-regular);
}

/* Sources */
.src-item {
  display: flex; gap: 8px; padding: 9px 14px;
  border-bottom: 1px solid var(--border-color);
  flex-wrap: wrap;
  &:hover { background: var(--bg-hover, rgba(0,0,0,.02)); }
}
.src-main { flex: 1; min-width: 0; }
.src-name {
  font-size: 12.5px; color: var(--text-main);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.src-meta { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.src-side { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.src-ops { display: flex; gap: 8px; }
.op {
  font-size: 13px; color: var(--text-muted); cursor: pointer;
  &:hover { color: #409eff; }
  &.danger:hover { color: #f56c6c; }
  &.disabled { opacity: .35; pointer-events: none; }
}
.src-error {
  flex-basis: 100%; font-size: 11px; color: #b3342f;
  background: #fdecec; padding: 4px 8px; border-radius: 4px;
  overflow: hidden; text-overflow: ellipsis;
}

/* Health card */
.health-card {
  flex-shrink: 0; padding: 12px 14px 14px;
  border-top: 1px solid var(--border-color);
  background: rgba(0,0,0,.015);
}
.hc-head {
  display: flex; align-items: baseline; justify-content: space-between;
  font-size: 12px; color: var(--text-muted); margin-bottom: 8px;
}
.hc-score { font-size: 20px; font-weight: 700; }
.hc-score.good, .good { color: #1a7f45; }
.hc-score.warn, .warn { color: #a56a11; }
.hc-score.bad, .bad { color: #b3342f; }
.hc-bar { height: 5px; border-radius: 999px; background: rgba(0,0,0,.07); overflow: hidden; }
.hc-fill { height: 100%; border-radius: 999px; }
.hc-fill.good { background: #36b37e; }
.hc-fill.warn { background: #e6a23c; }
.hc-fill.bad { background: #f56c6c; }
.hc-meta { font-size: 11px; color: var(--text-muted); margin: 8px 0 2px; }

/* Upload */
.upload-hint {
  font-size: 12.5px; color: var(--text-muted); line-height: 1.7;
  margin-bottom: 14px; padding: 10px 12px;
  background: rgba(64,158,255,.06); border-radius: 6px;
}

/* Lint */
.lint-box { padding: 0 4px; }
.lint-score-row { display: flex; align-items: center; gap: 14px; margin-bottom: 18px; }
.lint-score { font-size: 40px; font-weight: 700; line-height: 1; }
.lint-score-meta { font-size: 12px; color: var(--text-main); .muted { color: var(--text-muted); } }
.lint-stats {
  display: grid; grid-template-columns: repeat(3, 1fr);
  gap: 10px; margin-bottom: 20px;
}
.ls-item {
  background: rgba(0,0,0,.03); border-radius: 8px;
  padding: 10px; text-align: center;
}
.ls-v { font-size: 18px; font-weight: 600; color: var(--text-main); }
.ls-k { font-size: 11px; color: var(--text-muted); margin-top: 2px; }
.issue {
  padding: 12px 0; border-top: 1px solid var(--border-color);
}
.issue-head { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.issue-type { font-size: 12px; color: var(--text-muted); }
.issue-page {
  font-size: 11px; padding: 1px 8px; border-radius: 999px;
  background: rgba(64,158,255,.1); color: #2b6fd4;
}
.issue-detail { font-size: 13px; color: var(--text-regular); line-height: 1.6; }
.issue-sug { font-size: 12px; color: var(--text-muted); margin-top: 5px; line-height: 1.6; }

/* Graph colour-mode toggle */
.graph-mode {
  position: absolute; top: 12px; right: 12px;
  display: flex; gap: 6px;
  background: rgba(255, 255, 255, .92);
  padding: 4px; border-radius: 8px;
  box-shadow: 0 1px 6px rgba(0, 0, 0, .07);
}

/* Knowledge-base Q&A */
.ask-wrap { display: flex; flex-direction: column; flex: 1; min-height: 0; }
.ask-scroll { flex: 1; min-height: 0; }
.ask-inner { padding: 26px 30px 20px; max-width: 880px; }
.ask-intro { text-align: center; padding: 44px 0 10px; }
.ask-title { font-size: 18px; font-weight: 600; color: var(--text-main); }
.ask-sub { font-size: 13px; color: var(--text-muted); margin-top: 8px; line-height: 1.7; }
.ask-samples { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; margin-top: 20px; }
.ask-sample {
  font-size: 12.5px; padding: 6px 14px; border-radius: 999px;
  background: rgba(64, 158, 255, .08); color: #2b6fd4; cursor: pointer;
  &:hover { background: rgba(64, 158, 255, .16); }
}
.ask-q {
  font-size: 14px; font-weight: 600; color: var(--text-main);
  padding: 12px 16px; background: rgba(0, 0, 0, .03); border-radius: 8px;
  margin-bottom: 18px;
}
.ask-loading {
  display: flex; align-items: center; gap: 8px;
  font-size: 13px; color: var(--text-muted); padding: 16px 0;
}
.ask-actions { display: flex; align-items: center; gap: 10px; margin-top: 22px; }
.ask-input {
  display: flex; gap: 10px; padding: 14px 22px;
  border-top: 1px solid var(--border-color); flex-shrink: 0;
}

/* Version history */
.ver-box { display: flex; flex-direction: column; gap: 14px; }
.ver-list {
  max-height: 240px; overflow-y: auto;
  border: 1px solid var(--border-color); border-radius: 8px;
}
.ver-item {
  padding: 9px 12px; cursor: pointer;
  border-bottom: 1px solid var(--border-color);
  &:last-child { border-bottom: none; }
  &:hover { background: rgba(0, 0, 0, .025); }
  &.active { background: rgba(64, 158, 255, .09); }
}
.ver-head { display: flex; align-items: center; gap: 8px; }
.ver-no { font-size: 12px; font-weight: 700; color: #2b6fd4; }
.ver-time { font-size: 11px; color: var(--text-muted); margin-left: auto; }
.ver-title {
  font-size: 12.5px; color: var(--text-regular); margin-top: 4px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.ver-preview { border-top: 1px dashed var(--border-color); padding-top: 12px; }
.ver-preview-head {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 12px; color: var(--text-muted); margin-bottom: 10px;
}

/* Cross-project bits */
.page-proj {
  margin-left: auto; flex-shrink: 0;
  max-width: 92px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 10.5px; color: var(--text-muted);
  background: rgba(0, 0, 0, .05); border-radius: 999px; padding: 0 6px;
}
.ask-scope {
  display: inline-block; margin-top: 12px;
  font-size: 12px; color: #2b6fd4;
  background: rgba(64, 158, 255, .08);
  padding: 4px 12px; border-radius: 999px;
}
.ask-cursor {
  display: inline-block; width: 7px; height: 15px; margin-left: 2px;
  background: #409eff; vertical-align: -2px;
  animation: kb-blink 1s steps(2, start) infinite;
}
@keyframes kb-blink { to { visibility: hidden; } }
.cite-proj {
  font-style: normal; font-size: 10px; opacity: .65; margin-left: 4px;
}
</style>
