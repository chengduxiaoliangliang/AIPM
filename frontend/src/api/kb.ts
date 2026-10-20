import request, { http } from './request'
import { authStorage } from '@/utils/auth'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface KBPageBrief {
  id: number
  slug: string
  title: string
  page_type: string
  summary?: string | null
  tags?: string | null
  updated_at: string
  project_id?: number
  project_name?: string
}

export interface KBLinkRef {
  id: number
  title: string
  page_type: string
}

export interface KBPageDetail extends KBPageBrief {
  project_id: number
  content?: string | null
  source_ids?: number[]
  generated_by?: string
  created_at: string
  inbound_links: KBLinkRef[]
  outbound_links: KBLinkRef[]
  sources: { id: number; name: string; status: string }[]
}

export interface KBSource {
  id: number
  project_id: number
  original_name: string
  mime_type?: string
  size_bytes: number
  char_count: number
  status: 'uploaded' | 'ready' | 'ingesting' | 'indexed' | 'failed'
  extraction_note?: string
  error_message?: string
  uploaded_by?: number
  created_at: string
}

export interface KBIngestJob {
  id: number
  project_id: number
  source_id?: number
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  stage: string
  progress: number
  message?: string
  pages_created: number
  pages_updated: number
  used_llm?: string
  started_at?: string
  finished_at?: string
  created_at: string
}

export interface KBLintIssue {
  type: string
  severity: 'high' | 'medium' | 'low'
  page?: string | null
  detail: string
  suggestion?: string
  source?: string
}

export interface KBLintReport {
  id: number
  project_id: number
  score: number
  issues: KBLintIssue[]
  stats: Record<string, any>
  created_at: string
}

export interface KBProjectSummary {
  project_id: number
  project_name: string
  project_code?: string
  pages: number
  sources: number
  indexed_sources: number
  links: number
  last_updated?: string
  health_score?: number | null
}

export interface KBStructureGroup {
  type: string
  label: string
  pages: KBPageBrief[]
}

export interface KBStructure {
  project_id: number
  project_name: string
  groups: KBStructureGroup[]
  special: Record<string, KBPageBrief>
  total_pages: number
}

export interface KBGraphNode {
  id: number
  title: string
  type: string
  inbound: number
  community?: number
  reserved: boolean
  project_id?: number
  project_name?: string
}

export interface KBGraphEdge {
  source: number
  target: number
}

export interface KBCommunity {
  id: number
  label: string
  size: number
  pages: number[]
}

export interface KBGraph {
  nodes: KBGraphNode[]
  edges: KBGraphEdge[]
  communities?: KBCommunity[]
}

export interface KBPageVersionBrief {
  id: number
  page_id: number
  version_no: number
  title: string
  change_type: string
  source_id?: number | null
  created_at: string
}

export interface KBPageVersionDetail extends KBPageVersionBrief {
  summary?: string | null
  content?: string | null
  tags?: string | null
  page_type?: string | null
}

export interface KBAskCitation {
  id: number
  title: string
  page_type: string
  project?: string
}

export interface KBAskResult {
  answer: string
  citations: KBAskCitation[]
  used_llm: boolean
  saved_page_id?: number | null
  saved_page_title?: string | null
}

// ─── API ──────────────────────────────────────────────────────────────────────

export function listKBProjectsApi() {
  return request<KBProjectSummary[]>({ url: '/kb/projects', method: 'GET' })
}

export function getKBStructureApi(projectId: number) {
  return request<KBStructure>({ url: `/kb/projects/${projectId}/structure`, method: 'GET' })
}

export function getKBGraphApi(projectId: number) {
  return request<KBGraph>({ url: `/kb/projects/${projectId}/graph`, method: 'GET' })
}

export function listKBPagesApi(projectId: number, params?: any) {
  return request<KBPageBrief[]>({ url: `/kb/projects/${projectId}/pages`, method: 'GET', params })
}

export function getKBPageApi(pageId: number) {
  return request<KBPageDetail>({ url: `/kb/pages/${pageId}`, method: 'GET' })
}

export function createKBPageApi(projectId: number, data: any) {
  return request<KBPageBrief>({ url: `/kb/projects/${projectId}/pages`, method: 'POST', data })
}

export function updateKBPageApi(pageId: number, data: any) {
  return request<KBPageBrief>({ url: `/kb/pages/${pageId}`, method: 'PUT', data })
}

export function deleteKBPageApi(pageId: number) {
  return request<null>({ url: `/kb/pages/${pageId}`, method: 'DELETE' })
}

export function listKBSourcesApi(projectId: number) {
  return request<KBSource[]>({ url: `/kb/projects/${projectId}/sources`, method: 'GET' })
}

export function uploadKBSourcesApi(projectId: number, files: File[]) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  return request<KBSource[]>({
    url: `/kb/projects/${projectId}/sources`,
    method: 'POST',
    data: fd,
    timeout: 180000
  })
}

export function deleteKBSourceApi(sourceId: number) {
  return request<null>({ url: `/kb/sources/${sourceId}`, method: 'DELETE' })
}

export function ingestKBSourceApi(sourceId: number) {
  return request<{ source_id: number; status: string }>({
    url: `/kb/sources/${sourceId}/ingest`,
    method: 'POST',
    timeout: 60000
  })
}

export function listKBJobsApi(projectId: number, sourceId?: number) {
  return request<KBIngestJob[]>({
    url: `/kb/projects/${projectId}/jobs`,
    method: 'GET',
    params: sourceId ? { source_id: sourceId } : undefined
  })
}

export function runKBLintApi(projectId: number) {
  return request<KBLintReport>({
    url: `/kb/projects/${projectId}/lint`,
    method: 'POST',
    timeout: 240000
  })
}

export function getLatestKBLintApi(projectId: number) {
  return request<KBLintReport | null>({
    url: `/kb/projects/${projectId}/lint/latest`,
    method: 'GET'
  })
}

export async function downloadKBSourceApi(sourceId: number): Promise<Blob> {
  const res = await http.get(`/kb/sources/${sourceId}/download`, {
    responseType: 'blob',
    timeout: 120000
  })
  return res.data as Blob
}

export async function exportKBWikiApi(projectId: number): Promise<Blob> {
  const res = await http.get(`/kb/projects/${projectId}/export`, {
    responseType: 'blob',
    timeout: 120000
  })
  return res.data as Blob
}

// ─── page versions ────────────────────────────────────────────────────────────

export function listKBPageVersionsApi(pageId: number) {
  return request<KBPageVersionBrief[]>({
    url: `/kb/pages/${pageId}/versions`,
    method: 'GET'
  })
}

export function getKBVersionApi(versionId: number) {
  return request<KBPageVersionDetail>({
    url: `/kb/versions/${versionId}`,
    method: 'GET'
  })
}

export function restoreKBVersionApi(versionId: number) {
  return request<KBPageBrief>({
    url: `/kb/versions/${versionId}/restore`,
    method: 'POST',
    timeout: 60000
  })
}

// ─── knowledge-base Q&A ───────────────────────────────────────────────────────

export function askKBApi(
  projectId: number,
  payload: { question: string; save_as_page?: boolean; page_type?: string }
) {
  return request<KBAskResult>({
    url: `/kb/projects/${projectId}/ask`,
    method: 'POST',
    data: payload,
    timeout: 240000
  })
}

// ─── cross-project ────────────────────────────────────────────────────────────

export function getKBStructureAllApi() {
  return request<KBStructure>({ url: '/kb/structure/all', method: 'GET' })
}

export function getKBGraphAllApi() {
  return request<KBGraph>({ url: '/kb/graph/all', method: 'GET' })
}

export function runKBLintAllApi() {
  return request<{ project_id: number; project_name: string; score: number; issues: number }[]>({
    url: '/kb/lint/all',
    method: 'POST',
    timeout: 600000
  })
}

// ─── streamed Q&A ─────────────────────────────────────────────────────────────

/**
 * Ask the knowledge base and stream the answer token by token.
 * Pass `projectId = null` to search across all accessible projects.
 */
export async function streamAskKBApi(
  projectId: number | null,
  question: string,
  handlers: {
    onCitations?: (c: KBAskCitation[]) => void
    onToken: (t: string) => void
    onFinish: () => void
    onError: (e: any) => void
  }
) {
  const { onCitations, onToken, onFinish, onError } = handlers
  const token = authStorage.getToken()
  const url = projectId
    ? `/api/v1/kb/projects/${projectId}/ask/stream`
    : '/api/v1/kb/ask/stream'

  let finished = false
  const finishOnce = () => {
    if (!finished) {
      finished = true
      onFinish()
    }
  }

  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({ question })
    })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)

    const reader = response.body?.getReader()
    const decoder = new TextDecoder('utf-8')
    if (!reader) throw new Error('当前浏览器不支持流式响应')

    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const frames = buffer.split('\n\n')
      buffer = frames.pop() || ''

      for (const frame of frames) {
        const line = frame.trim()
        if (!line.startsWith('data: ')) continue
        try {
          const d = JSON.parse(line.slice(6))
          if (d.status === 'citations' && d.citations) onCitations?.(d.citations)
          else if (d.status === 'streaming' && d.content) onToken(d.content)
          else if (d.status === 'finished') finishOnce()
        } catch {
          // ignore partial frames
        }
      }
    }
    finishOnce()
  } catch (e) {
    onError(e)
  }
}
