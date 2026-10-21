import request, { http } from './request'
import type { Project, ProjectMember, Milestone, PaginatedData } from '@/types'

export interface ProjectDetail extends Project {
  members: ProjectMember[]
  milestones: Milestone[]
}

export function listProjectsApi(params?: any) {
  return request<PaginatedData<Project>>({
    url: '/projects',
    method: 'GET',
    params
  })
}

export function getAllProjectsApi() {
  return request<Project[]>({
    url: '/projects/all',
    method: 'GET'
  })
}

export function getProjectDetailApi(id: number) {
  return request<ProjectDetail>({
    url: `/projects/${id}`,
    method: 'GET'
  })
}

export function createProjectApi(data: any) {
  return request<Project>({
    url: '/projects',
    method: 'POST',
    data
  })
}

export function updateProjectApi(id: number, data: any) {
  return request<Project>({
    url: `/projects/${id}`,
    method: 'PUT',
    data
  })
}

export function deleteProjectApi(id: number) {
  return request<null>({
    url: `/projects/${id}`,
    method: 'DELETE'
  })
}

export function addProjectMemberApi(projectId: number, data: { user_id: number; project_role: string }) {
  return request<null>({
    url: `/projects/${projectId}/members`,
    method: 'POST',
    data
  })
}

export function removeProjectMemberApi(projectId: number, memberId: number) {
  return request<null>({
    url: `/projects/${projectId}/members/${memberId}`,
    method: 'DELETE'
  })
}

export function addMilestoneApi(projectId: number, data: any) {
  return request<Milestone>({
    url: `/projects/${projectId}/milestones`,
    method: 'POST',
    data
  })
}

export function updateMilestoneApi(projectId: number, milestoneId: number, data: any) {
  return request<Milestone>({
    url: `/projects/${projectId}/milestones/${milestoneId}`,
    method: 'PUT',
    data
  })
}

export function deleteMilestoneApi(projectId: number, milestoneId: number) {
  return request<null>({
    url: `/projects/${projectId}/milestones/${milestoneId}`,
    method: 'DELETE'
  })
}

// ─── 项目导入 / 导出 ─────────────────────────────────────────────────────────

export interface ImportField {
  key: string
  label: string
  required: boolean
}

export interface ImportIssue {
  level: 'error' | 'warning'
  sheet: string
  row: number
  field?: string
  message: string
}

export interface ImportSheetMeta {
  headers: string[]
  /** 列下标 → 字段 key */
  mapping: Record<string, string>
  header_row: number
  rows: Record<string, any>[]
  total: number
}

export type ImportSheetKey = 'project' | 'task' | 'milestone' | 'member'

export interface ImportPreview {
  format: 'xlsx' | 'csv'
  sheets: Record<ImportSheetKey, ImportSheetMeta>
  fields: Record<ImportSheetKey, ImportField[]>
  issues: ImportIssue[]
  summary: {
    projects: number
    tasks: number
    milestones: number
    members: number
    errors: number
    warnings: number
  }
}

export interface ImportResult {
  projects_created: number
  projects_skipped: number
  tasks_created: number
  tasks_skipped: number
  milestones_created: number
  milestones_skipped: number
  members_created: number
  members_skipped: number
  warnings?: ImportIssue[]
}

export async function downloadProjectTemplateApi(format: 'xlsx' | 'csv' = 'xlsx'): Promise<Blob> {
  const res = await http.get('/projects/import/template', {
    params: { format },
    responseType: 'blob',
    timeout: 60000
  })
  return res.data as Blob
}

export async function exportProjectApi(projectId: number): Promise<Blob> {
  const res = await http.get(`/projects/${projectId}/export`, {
    responseType: 'blob',
    timeout: 60000
  })
  return res.data as Blob
}

function buildImportForm(file: File, mapping?: Record<string, any>): FormData {
  const fd = new FormData()
  fd.append('file', file)
  if (mapping) fd.append('mapping', JSON.stringify(mapping))
  return fd
}

export function previewProjectImportApi(file: File, mapping?: Record<string, any>) {
  return request<ImportPreview>({
    url: '/projects/import/preview',
    method: 'POST',
    data: buildImportForm(file, mapping),
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  })
}

export function executeProjectImportApi(file: File, mapping?: Record<string, any>) {
  return request<ImportResult>({
    url: '/projects/import/execute',
    method: 'POST',
    data: buildImportForm(file, mapping),
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 180000
  })
}


export interface ImportLogItem {
  id: number
  username: string
  filename: string
  format: string
  projects_created: number
  projects_skipped: number
  tasks_created: number
  tasks_skipped: number
  milestones_created: number
  milestones_skipped: number
  members_created: number
  members_skipped: number
  error_count: number
  warning_count: number
  status: 'success' | 'failed'
  message: string
  created_at: string
}

export function getImportHistoryApi(limit = 8) {
  return request<ImportLogItem[]>({
    url: '/projects/import/history',
    method: 'GET',
    params: { limit }
  })
}

/** 批量导出；ids 为空表示导出全部可见项目 */
export async function exportProjectsApi(ids: number[]): Promise<Blob> {
  const res = await http.get('/projects/export', {
    params: ids.length ? { ids: ids.join(',') } : {},
    responseType: 'blob',
    timeout: 120000
  })
  return res.data as Blob
}
