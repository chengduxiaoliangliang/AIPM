import request from './request'
import type { UserInfo, Department, Role, PaginatedData } from '@/types'

// User APIs
export function listUsersApi(params: any) {
  return request<PaginatedData<UserInfo>>({
    url: '/users',
    method: 'GET',
    params
  })
}

export function getAllUsersApi() {
  return request<UserInfo[]>({
    url: '/users/all',
    method: 'GET'
  })
}

export function createUserApi(data: any) {
  return request<UserInfo>({
    url: '/users',
    method: 'POST',
    data
  })
}

export function updateUserApi(id: number, data: any) {
  return request<UserInfo>({
    url: `/users/${id}`,
    method: 'PUT',
    data
  })
}

export function deleteUserApi(id: number) {
  return request<null>({
    url: `/users/${id}`,
    method: 'DELETE'
  })
}

export function changePasswordApi(data: { old_password: string; new_password: string }) {
  return request<null>({
    url: '/users/change_password',
    method: 'POST',
    data
  })
}

// Role APIs
export function listRolesApi() {
  return request<Role[]>({
    url: '/roles',
    method: 'GET'
  })
}

export function listPermissionsApi() {
  return request<any[]>({
    url: '/roles/permissions',
    method: 'GET'
  })
}

export function createRoleApi(data: any) {
  return request<Role>({
    url: '/roles',
    method: 'POST',
    data
  })
}

export function updateRoleApi(id: number, data: any) {
  return request<Role>({
    url: `/roles/${id}`,
    method: 'PUT',
    data
  })
}

export function deleteRoleApi(id: number) {
  return request<null>({
    url: `/roles/${id}`,
    method: 'DELETE'
  })
}

// Department APIs
export function listDepartmentsApi() {
  return request<Department[]>({
    url: '/depts',
    method: 'GET'
  })
}

export function createDepartmentApi(data: any) {
  return request<Department>({
    url: '/depts',
    method: 'POST',
    data
  })
}

export function updateDepartmentApi(id: number, data: any) {
  return request<Department>({
    url: `/depts/${id}`,
    method: 'PUT',
    data
  })
}

export function deleteDepartmentApi(id: number) {
  return request<null>({
    url: `/depts/${id}`,
    method: 'DELETE'
  })
}
