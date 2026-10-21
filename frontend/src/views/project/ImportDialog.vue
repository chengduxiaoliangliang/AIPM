<template>
  <el-dialog
    v-model="visible"
    title="导入项目与任务"
    width="880px"
    top="6vh"
    @closed="reset"
  >
    <!-- ── 第一步：下载模板 + 上传 ─────────────────────────────── -->
    <div v-if="!preview" class="upload-step">
      <div class="hint-box">
        <div class="hint-title">导入说明</div>
        <ul>
          <li>先下载模板，按「项目」「任务」两个工作表填写，示例行请删除</li>
          <li>列名可以改、顺序可以调——导入时会自动识别，识别不出可手动映射</li>
          <li>任务通过「项目编号」关联项目；项目编号已存在时跳过该项目</li>
          <li>同一项目内同名任务会自动跳过，可安全地重复导入</li>
        </ul>
      </div>

      <div class="template-row">
        <el-button :icon="Download" :loading="downloading" @click="downloadTemplate">
          下载导入模板
        </el-button>
        <span class="template-tip">建议先用模板填一份，确认列名再批量导入</span>
      </div>

      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".xlsx,.xlsm"
        :on-change="onFileChange"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">拖拽文件到此处，或<em>点击选择</em></div>
        <template #tip>
          <div class="upload-tip">仅支持 .xlsx 格式，最大 8MB，单次最多 2000 行</div>
        </template>
      </el-upload>
    </div>

    <!-- ── 第二步：预览与校验 ───────────────────────────────────── -->
    <div v-else class="preview-step" v-loading="loading">
      <div class="summary-row">
        <span class="chip">项目 {{ preview.summary.projects }} 行</span>
        <span class="chip">任务 {{ preview.summary.tasks }} 行</span>
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
        description="错误通常来自必填缺失、项目编号对不上或日期格式无法识别，请按下方提示修改文件后重新上传。"
        class="alert"
      />

      <el-tabs v-model="activeSheet" class="map-tabs">
        <el-tab-pane label="项目表" name="project">
          <div class="map-legend">文件中的列 → 对应的系统字段，留空表示忽略该列</div>
          <div class="map-grid">
            <div v-for="(header, idx) in headers('project')" :key="idx" class="map-item">
              <span class="map-src" :title="header">{{ header || `第 ${idx + 1} 列` }}</span>
              <span class="map-arrow">→</span>
              <el-select
                v-model="mappingModel.project[String(idx)]"
                size="small"
                clearable
                placeholder="忽略此列"
              >
                <el-option
                  v-for="f in preview.fields.project"
                  :key="f.key"
                  :label="f.label + (f.required ? ' *' : '')"
                  :value="f.key"
                />
              </el-select>
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="任务表" name="task">
          <div class="map-legend">文件中的列 → 对应的系统字段，留空表示忽略该列</div>
          <div class="map-grid">
            <div v-for="(header, idx) in headers('task')" :key="idx" class="map-item">
              <span class="map-src" :title="header">{{ header || `第 ${idx + 1} 列` }}</span>
              <span class="map-arrow">→</span>
              <el-select
                v-model="mappingModel.task[String(idx)]"
                size="small"
                clearable
                placeholder="忽略此列"
              >
                <el-option
                  v-for="f in preview.fields.task"
                  :key="f.key"
                  :label="f.label + (f.required ? ' *' : '')"
                  :value="f.key"
                />
              </el-select>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <div class="map-actions">
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
        <div class="issue-title">样例数据（前 5 行，按当前映射解析）</div>
        <el-table :data="preview.sheets[activeSheet].rows" size="small" max-height="220">
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
  type ImportPreview
} from '@/api/project'
import { saveBlob } from '@/utils/download'

const emit = defineEmits<{ (e: 'done'): void }>()

const visible = ref(false)
const downloading = ref(false)
const loading = ref(false)
const importing = ref(false)
const file = ref<File | null>(null)
const preview = ref<ImportPreview | null>(null)
const activeSheet = ref<'project' | 'task'>('project')

const mappingModel = reactive<{ project: Record<string, string>; task: Record<string, string> }>({
  project: {},
  task: {}
})

function open() {
  visible.value = true
}

function reset() {
  preview.value = null
  file.value = null
  activeSheet.value = 'project'
  mappingModel.project = {}
  mappingModel.task = {}
}

function headers(sheet: 'project' | 'task'): string[] {
  return preview.value?.sheets[sheet].headers || []
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

async function downloadTemplate() {
  downloading.value = true
  try {
    const blob = await downloadProjectTemplateApi()
    saveBlob(blob, '项目导入模板.xlsx')
    ElMessage.success('模板已下载')
  } catch (e: any) {
    ElMessage.error(e?.message || '模板下载失败')
  } finally {
    downloading.value = false
  }
}

async function onFileChange(uploadFile: any) {
  const raw: File | undefined = uploadFile?.raw
  if (!raw) return
  if (!/\.(xlsx|xlsm)$/i.test(raw.name)) {
    ElMessage.warning('仅支持 .xlsx 格式')
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
      mappingModel.project = { ...res.data.sheets.project.mapping }
      mappingModel.task = { ...res.data.sheets.task.mapping }
      activeSheet.value = res.data.sheets.project.headers.length ? 'project' : 'task'
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '文件解析失败')
    reset()
  } finally {
    loading.value = false
  }
}

async function revalidate() {
  await loadPreview({
    project: cleanMapping(mappingModel.project),
    task: cleanMapping(mappingModel.task)
  })
  ElMessage.success('已按新映射重新校验')
}

function cleanMapping(m: Record<string, string>): Record<string, string> {
  return Object.fromEntries(Object.entries(m).filter(([, v]) => !!v))
}

async function doImport() {
  if (!file.value || !preview.value) return

  const { projects, tasks, errors } = preview.value.summary
  if (errors > 0) return

  try {
    await ElMessageBox.confirm(
      `将导入 ${projects} 个项目、${tasks} 个任务。项目编号已存在时会跳过。`,
      '确认导入',
      { confirmButtonText: '开始导入', cancelButtonText: '再检查一下' }
    )
  } catch {
    return
  }

  importing.value = true
  try {
    const res = await executeProjectImportApi(file.value, {
      project: cleanMapping(mappingModel.project),
      task: cleanMapping(mappingModel.task)
    })
    const d = res.data
    ElMessage.success(
      `导入完成：新增 ${d.projects_created} 个项目、${d.tasks_created} 个任务` +
        (d.projects_skipped || d.tasks_skipped
          ? `；跳过 ${d.projects_skipped} 个项目、${d.tasks_skipped} 个任务`
          : '')
    )
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

.map-legend {
  font-size: 12px;
  color: var(--text-faint);
  margin: 0 0 8px;
}

.map-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 8px 14px;
  padding: 4px 0;
}

.map-item {
  display: flex;
  align-items: center;
  gap: 8px;

  .map-src {
    flex: 0 0 96px;
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
  max-height: 190px;
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

.sample {
  margin-top: 4px;
}
</style>
