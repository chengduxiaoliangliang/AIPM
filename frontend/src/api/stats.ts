import request from './request'
import type { DashboardStats, PaginatedData } from '@/types'

export function getDashboardStatsApi() {
  return request<DashboardStats>({
    url: '/stats/dashboard',
    method: 'GET'
  })
}

export function listAuditLogsApi(params?: any) {
  return request<PaginatedData<any>>({
    url: '/logs',
    method: 'GET',
    params
  })
}
