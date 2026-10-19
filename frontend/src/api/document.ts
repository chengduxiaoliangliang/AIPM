import request from './request'
import type { DocumentItem, PaginatedData } from '@/types'

export function listDocumentsApi(params?: any) {
  return request<PaginatedData<DocumentItem>>({
    url: '/documents',
    method: 'GET',
    params
  })
}

export function getDocumentDetailApi(id: number) {
  return request<DocumentItem>({
    url: `/documents/${id}`,
    method: 'GET'
  })
}

export function createDocumentApi(data: any) {
  return request<DocumentItem>({
    url: '/documents',
    method: 'POST',
    data
  })
}

export function updateDocumentApi(id: number, data: any) {
  return request<DocumentItem>({
    url: `/documents/${id}`,
    method: 'PUT',
    data
  })
}

export function deleteDocumentApi(id: number) {
  return request<null>({
    url: `/documents/${id}`,
    method: 'DELETE'
  })
}
