import request from './request'
import type { WorkLog, PaginatedData } from '@/types'

export function listWorkLogsApi(params?: any) {
  return request<PaginatedData<WorkLog>>({
    url: '/worklogs',
    method: 'GET',
    params
  })
}

export function createWorkLogApi(data: any) {
  return request<WorkLog>({
    url: '/worklogs',
    method: 'POST',
    data
  })
}

export function approveWorkLogApi(id: number, data: { status: 'approved' | 'rejected'; approval_remark?: string }) {
  return request<WorkLog>({
    url: `/worklogs/${id}/approval`,
    method: 'POST',
    data
  })
}

export function deleteWorkLogApi(id: number) {
  return request<null>({
    url: `/worklogs/${id}`,
    method: 'DELETE'
  })
}
