<template>
  <el-dialog
    v-model="visible"
    title="导入项目与任务"
    width="900px"
    top="5vh"
    @closed="reset"
  >
    <!-- ── 第一步：下载模板 + 上传 ─────────────────────────────── -->
    <div v-if="!preview" class="upload-step">
      <div class="hint-box">
        <div class="hint-title">导入说明</div>
        <ul>
          <li>Excel 模板含「项目 / 任务 / 里程碑 / 成员」四张表，只有「项目」表是必需的</li>
          <li>列名可以改、顺序可以调——导入时会自动识别，识别不出可手动映射</li>
          <li>任务、里程碑、成员都通过「项目编号」关联项目</li>
          <li>项目编号已存在时跳过该项目；同项目内同名任务/里程碑、同一成员自动跳过</li>
        </ul>
      </div>

      <div class="template-row">
        <el-button :icon="Download" :loading="downloading" @click="downloadTemplate('xlsx')">
          下载 Excel 模板
        </el-button>
        <el-button :icon="Download" :loading="downloading" @click="downloadTemplate('csv')">
          下载 CSV 模板
        </el-button>
        <span class="template-tip">
          Excel 四表更完整；CSV 单表用「类型」列区分，适合从其他系统导出
        </span>
      </div>

      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".xlsx,.xlsm,.csv"
        :on-change="onFileChange"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">拖拽文件到此处，或<em>点击选择</em></div>
        <template #tip>
          <div class="upload-tip">支持 .xlsx / .csv，最大 8MB，单次最多 2000 行</div>
        </template>
      </el-upload>

      <div v-if="history.length" class="history">
        <div class="history-title">最近导入</div>
        <div v-for="h in history" :key="h.id" class="history-row">
          <el-tag size="small" :type="h.status === 'success' ? 'success' : 'danger'" effect="plain">
            {{ h.status === 'success' ? '成功' : '失败' }}
          </el-tag>
          <span class="h-file" :title="h.filename">{{ h.filename }}</span>
          <span class="h-meta">{{ h.username }} · {{ h.created_at }}</span>
          <span class="h-count">
            项目 {{ h.projects_created }} · 任务 {{ h.tasks_created }}
            <template v-if="h.milestones_created"> · 里程碑 {{ h.milestones_created }}</template>
            <template v-if="h.members_created"> · 成员 {{ h.members_created }}</template>
          </span>
          <el-button
            v-if="h.can_rollback"
            link
            type="danger"
            size="small"
            class="h-rollback"
            @click="rollback(h)"
          >
            回滚
          </el-button>
          <span v-else-if="h.rolled_back" class="h-rolled">已回滚</span>
        </div>
      </div>
    </div>

    <!-- ── 第二步：预览与校验 ───────────────────────────────────── -->
    <div v-else class="preview-step" v-loading="loading">
      <div class="summary-row">
        <span v-for="s in sheetDefs" :key="s.key" class="chip">
          {{ s.short }} {{ preview.sheets[s.key].total }} 行
        </span>
        <span class="chip" :class="{ danger: preview.summary.errors > 0 }">
          错误 {{ preview.summary.errors }}
        </span>
        <span class="chip" :class="{ warn: preview.summary.warnings > 0 }">
          警告 {{ preview.summary.warnings }}
        </span>
        <span class="file-name">{{ file?.name }}</span>
        <el-button link @click="reset">重新上传</el-button>
      </div>

      <el-alert
        v-if="preview.summary.errors > 0"
        type="error"
        :closable="false"
        show-icon
        title="存在错误，修正后才能导入"
        description="错误通常来自必填缺失、项目编号对不上、成员不存在或日期格式无法识别，请按下方提示修改文件后重新上传。"
        class="alert"
      />

      <div v-if="preview.format === 'csv'" class="csv-note">
        CSV 按表头自动识别列。如需自定义列名，请对照模板说明调整表头，或改用 Excel 模板。
      </div>

      <el-tabs v-else v-model="activeSheet" class="map-tabs">
        <el-tab-pane
          v-for="s in sheetDefs"
          :key="s.key"
          :label="`${s.label}（${preview.sheets[s.key].total}）`"
          :name="s.key"
        >
          <div v-if="!preview.sheets[s.key].headers.length" class="empty-sheet">
            文件中没有「{{ s.label }}」工作表，将跳过
          </div>
          <template v-else>
            <div class="map-legend">文件中的列 → 对应的系统字段，留空表示忽略该列</div>
            <div class="map-grid">
              <div
                v-for="(header, idx) in preview.sheets[s.key].headers"
                :key="idx"
                class="map-item"
              >
                <span class="map-src" :title="header">{{ header || `第 ${idx + 1} 列` }}</span>
                <span class="map-arrow">→</span>
                <el-select
                  v-model="mappingModel[s.key][String(idx)]"
                  size="small"
                  clearable
                  placeholder="忽略此列"
                >
                  <el-option
                    v-for="f in preview.fields[s.key]"
                    :key="f.key"
                    :label="f.label + (f.required ? ' *' : '')"
                    :value="f.key"
                  />
                </el-select>
              </div>
            </div>
          </template>
        </el-tab-pane>
      </el-tabs>

      <div v-if="preview.format !== 'csv'" class="map-actions">
        <el-button size="small" :loading="loading" @click="revalidate">
          应用映射并重新校验
        </el-button>
        <span class="map-hint">改了列名对不上时，在这里手动指定即可</span>
      </div>

      <div v-if="preview.issues.length" class="issue-list">
        <div class="issue-title">校验结果（前 30 条）</div>
        <div
          v-for="(item, idx) in preview.issues.slice(0, 30)"
          :key="idx"
          class="issue"
          :class="item.level"
        >
          <el-tag size="small" :type="item.level === 'error' ? 'danger' : 'warning'" effect="plain">
            {{ item.level === 'error' ? '错误' : '警告' }}
          </el-tag>
          <span class="issue-loc">{{ item.sheet }} 第 {{ item.row }} 行</span>
          <span class="issue-msg">{{ item.message }}</span>
        </div>
      </div>

      <div class="sample">
        <div class="issue-title">
          样例数据 · {{ currentSheetLabel }}（前 5 行，按当前映射解析）
        </div>
        <el-table :data="preview.sheets[activeSheet].rows" size="small" max-height="200">
          <el-table-column
            v-for="key in mappedKeys"
            :key="key"
            :prop="key"
            :label="fieldLabel(key)"
            min-width="120"
            show-overflow-tooltip
          />
        </el-table>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button
        v-if="preview"
        type="primary"
        :loading="importing"
        :disabled="preview.summary.errors > 0"
        @click="doImport"
      >
        确认导入
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, UploadFilled } from '@element-plus/icons-vue'
import {
  downloadProjectTemplateApi,
  previewProjectImportApi,
  executeProjectImportApi,
  getImportHistoryApi,
  rollbackImportApi,
  type ImportPreview,
  type ImportLogItem,
  type ImportSheetKey
} from '@/api/project'
import { saveBlob } from '@/utils/download'

const emit = defineEmits<{ (e: 'done'): void }>()

const SHEET_DEFS: { key: ImportSheetKey; label: string; short: string }[] = [
  { key: 'project', label: '项目表', short: '项目' },
  { key: 'task', label: '任务表', short: '任务' },
  { key: 'milestone', label: '里程碑表', short: '里程碑' },
  { key: 'member', label: '成员表', short: '成员' }
]

const visible = ref(false)
const downloading = ref(false)
const loading = ref(false)
const importing = ref(false)
const file = ref<File | null>(null)
const preview = ref<ImportPreview | null>(null)
const activeSheet = ref<ImportSheetKey>('project')
const history = ref<ImportLogItem[]>([])

const sheetDefs = SHEET_DEFS

const mappingModel = reactive<Record<string, Record<string, string>>>({
  project: {},
  task: {},
  milestone: {},
  member: {}
})

const currentSheetLabel = computed(
  () => SHEET_DEFS.find((s) => s.key === activeSheet.value)?.label || ''
)

function open() {
  visible.value = true
  loadHistory()
}

async function loadHistory() {
  try {
    const res = await getImportHistoryApi(8)
    history.value = res.data || []
  } catch {
    history.value = []
  }
}

function reset() {
  preview.value = null
  file.value = null
  activeSheet.value = 'project'
  for (const key of Object.keys(mappingModel)) mappingModel[key] = {}
}

/** 当前 sheet 已映射的字段 key，用于样例表格列 */
const mappedKeys = computed(() => {
  if (!preview.value) return []
  const keys = Object.values(mappingModel[activeSheet.value] || {}).filter(Boolean)
  return Array.from(new Set(keys))
})

function fieldLabel(key: string): string {
  const list = preview.value?.fields[activeSheet.value] || []
  return list.find((f) => f.key === key)?.label || key
}

async function rollback(h: ImportLogItem) {
  try {
    await ElMessageBox.confirm(
      `将删除这次导入创建的 ${h.projects_created} 个项目、${h.tasks_created} 个任务、` +
        `${h.milestones_created} 个里程碑、${h.members_created} 个成员。此操作不可撤销。`,
      '回滚这次导入',
      { confirmButtonText: '确认回滚', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    const res = await rollbackImportApi(h.id)
    ElMessage.success(res.message || '回滚完成')
    await loadHistory()
    emit('done')
  } catch (e: any) {
    ElMessage.error(e?.message || '回滚失败')
  }
}

async function downloadTemplate(format: 'xlsx' | 'csv') {
  downloading.value = true
  try {
    const blob = await downloadProjectTemplateApi(format)
    saveBlob(blob, `项目导入模板.${format}`)
    ElMessage.success(`${format === 'csv' ? 'CSV' : 'Excel'} 模板已下载`)
  } catch (e: any) {
    ElMessage.error(e?.message || '模板下载失败')
  } finally {
    downloading.value = false
  }
}

async function onFileChange(uploadFile: any) {
  const raw: File | undefined = uploadFile?.raw
  if (!raw) return
  if (!/\.(xlsx|xlsm|csv)$/i.test(raw.name)) {
    ElMessage.warning('仅支持 .xlsx 或 .csv 格式')
    return
  }
  file.value = raw
  await loadPreview()
}

async function loadPreview(mapping?: Record<string, any>) {
  if (!file.value) return
  loading.value = true
  try {
    const res = await previewProjectImportApi(file.value, mapping)
    preview.value = res.data
    if (!mapping) {
      // 首次解析：用服务端的自动映射初始化
      for (const s of SHEET_DEFS) {
        mappingModel[s.key] = { ...(res.data.sheets[s.key].mapping || {}) }
      }
      const first = SHEET_DEFS.find((s) => res.data.sheets[s.key].headers.length)
      activeSheet.value = first?.key || 'project'
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '文件解析失败')
    reset()
  } finally {
    loading.value = false
  }
}

async function revalidate() {
  const payload: Record<string, Record<string, string>> = {}
  for (const s of SHEET_DEFS) payload[s.key] = cleanMapping(mappingModel[s.key])
  await loadPreview(payload)
  ElMessage.success('已按新映射重新校验')
}

function cleanMapping(m: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(m).filter(([, v]) => !!v))
}

async function doImport() {
  if (!file.value || !preview.value) return

  const { projects, tasks, milestones, members, errors } = preview.value.summary
  if (errors > 0) return

  try {
    await ElMessageBox.confirm(
      `将导入 ${projects} 个项目、${tasks} 个任务、${milestones} 个里程碑、${members} 个成员。` +
        '已存在的项目编号会跳过。',
      '确认导入',
      { confirmButtonText: '开始导入', cancelButtonText: '再检查一下' }
    )
  } catch {
    return
  }

  importing.value = true
  try {
    const payload: Record<string, Record<string, string>> = {}
    for (const s of SHEET_DEFS) payload[s.key] = cleanMapping(mappingModel[s.key])

    const res = await executeProjectImportApi(file.value, payload)
    const d = res.data
    const skipped =
      d.projects_skipped + d.tasks_skipped + d.milestones_skipped + d.members_skipped
    ElMessage.success(
      `导入完成：新增 ${d.projects_created} 项目 / ${d.tasks_created} 任务 / ` +
        `${d.milestones_created} 里程碑 / ${d.members_created} 成员` +
        (skipped ? `；跳过 ${skipped} 条已存在记录` : '')
    )
    await loadHistory()
    visible.value = false
    emit('done')
  } catch (e: any) {
    ElMessage.error(e?.message || '导入失败')
  } finally {
    importing.value = false
  }
}

defineExpose({ open })
</script>

<style scoped lang="scss">
.hint-box {
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  margin-bottom: 14px;

  .hint-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-main);
    margin-bottom: 6px;
  }

  ul {
    margin: 0;
    padding-left: 18px;
    font-size: 12.5px;
    color: var(--text-muted);
    line-height: 1.9;
  }
}

.template-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
  flex-wrap: wrap;

  .template-tip {
    font-size: 12px;
    color: var(--text-faint);
  }
}

.upload-icon {
  font-size: 44px;
  color: var(--text-faint);
  margin-bottom: 6px;
}

.upload-text {
  font-size: 13px;
  color: var(--text-muted);

  em {
    color: var(--primary-color);
    font-style: normal;
  }
}

.upload-tip {
  font-size: 12px;
  color: var(--text-faint);
  margin-top: 6px;
}

.summary-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;

  .chip {
    font-size: 12px;
    padding: 2px 10px;
    border-radius: 999px;
    background: var(--bg-subtle);
    color: var(--text-regular);

    &.danger {
      background: var(--danger-light);
      color: var(--danger-color);
    }

    &.warn {
      background: var(--warning-light);
      color: var(--warning-color);
    }
  }

  .file-name {
    margin-left: auto;
    font-size: 12px;
    color: var(--text-faint);
    max-width: 220px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

.alert {
  margin-bottom: 12px;
}

.csv-note {
  font-size: 12.5px;
  color: var(--text-muted);
  background: var(--bg-subtle);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  margin-bottom: 10px;
}

.empty-sheet {
  font-size: 12.5px;
  color: var(--text-faint);
  padding: 14px 0;
}

.map-legend {
  font-size: 12px;
  color: var(--text-faint);
  margin: 0 0 8px;
}

.map-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 8px 14px;
  padding: 4px 0;
  max-height: 200px;
  overflow-y: auto;
}

.map-item {
  display: flex;
  align-items: center;
  gap: 8px;

  .map-src {
    flex: 0 0 92px;
    font-size: 12px;
    color: var(--text-muted);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .map-arrow {
    flex: 0 0 auto;
    color: var(--text-faint);
    font-size: 12px;
  }

  :deep(.el-select) {
    flex: 1;
    min-width: 0;
  }
}

.map-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 8px 0 4px;

  .map-hint {
    font-size: 12px;
    color: var(--text-faint);
  }
}

.issue-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-main);
  margin: 14px 0 8px;
}

.issue-list {
  max-height: 170px;
  overflow-y: auto;
}

.issue {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 5px 0;
  font-size: 12.5px;
  border-bottom: 1px dashed var(--border-color);

  &:last-child {
    border-bottom: none;
  }

  .issue-loc {
    flex: 0 0 auto;
    color: var(--text-faint);
  }

  .issue-msg {
    color: var(--text-regular);
  }
}

.history {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
}

.history-title {
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 8px;
}

.history-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 5px 0;
  font-size: 12px;
  color: var(--text-muted);
  border-bottom: 1px dashed var(--border-color);

  &:last-child {
    border-bottom: none;
  }

  .h-file {
    max-width: 200px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--text-regular);
  }

  .h-meta {
    color: var(--text-faint);
  }

  .h-count {
    margin-left: auto;
    color: var(--text-regular);
  }

  .h-rollback {
    flex: 0 0 auto;
  }

  .h-rolled {
    flex: 0 0 auto;
    font-size: 11.5px;
    color: var(--text-faint);
  }
}
</style>
