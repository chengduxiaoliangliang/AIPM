import request from './request'
import type { Issue, PaginatedData } from '@/types'

export function listIssuesApi(params?: any) {
  return request<PaginatedData<Issue>>({
    url: '/issues',
    method: 'GET',
    params
  })
}

export function createIssueApi(data: any) {
  return request<Issue>({
    url: '/issues',
    method: 'POST',
    data
  })
}

export function updateIssueApi(id: number, data: any) {
  return request<Issue>({
    url: `/issues/${id}`,
    method: 'PUT',
    data
  })
}

export function deleteIssueApi(id: number) {
  return request<null>({
    url: `/issues/${id}`,
    method: 'DELETE'
  })
}
