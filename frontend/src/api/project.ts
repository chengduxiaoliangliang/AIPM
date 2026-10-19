import request from './request'
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
