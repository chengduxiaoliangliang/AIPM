import request, { http } from './request'

// ─── Types ────────────────────────────────────────────────────────────────────

export interface KBPageBrief {
  id: number
  slug: string
  title: string
  page_type: string
  summary?: string | null
  tags?: string | null
  updated_at: string
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

// ─── API ──────────────────────────────────────────────────────────────────────

export function listKBProjectsApi() {
  return request<KBProjectSummary[]>({ url: '/kb/projects', method: 'GET' })
}

export function getKBStructureApi(projectId: number) {
  return request<KBStructure>({ url: `/kb/projects/${projectId}/structure`, method: 'GET' })
}

export function getKBGraphApi(projectId: number) {
  return request<any>({ url: `/kb/projects/${projectId}/graph`, method: 'GET' })
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
