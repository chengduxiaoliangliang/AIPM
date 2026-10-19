import request from './request'
import type { Task, SubTask, TaskComment, PaginatedData } from '@/types'

export interface TaskDetail extends Task {
  subtasks: SubTask[]
  comments: TaskComment[]
}

export function listTasksApi(params?: any) {
  return request<PaginatedData<Task>>({
    url: '/tasks',
    method: 'GET',
    params
  })
}

export function getKanbanBoardApi(projectId?: number) {
  return request<Record<string, Task[]>>({
    url: '/tasks/kanban',
    method: 'GET',
    params: { project_id: projectId }
  })
}

export function getTaskDetailApi(id: number) {
  return request<TaskDetail>({
    url: `/tasks/${id}`,
    method: 'GET'
  })
}

export function createTaskApi(data: any) {
  return request<Task>({
    url: '/tasks',
    method: 'POST',
    data
  })
}

export function updateTaskApi(id: number, data: any) {
  return request<Task>({
    url: `/tasks/${id}`,
    method: 'PUT',
    data
  })
}

export function updateTaskStatusApi(id: number, data: { status: string; order_num?: number }) {
  return request<Task>({
    url: `/tasks/${id}/status`,
    method: 'PATCH',
    data
  })
}

export function deleteTaskApi(id: number) {
  return request<null>({
    url: `/tasks/${id}`,
    method: 'DELETE'
  })
}

export function addSubTaskApi(taskId: number, data: any) {
  return request<SubTask>({
    url: `/tasks/${taskId}/subtasks`,
    method: 'POST',
    data
  })
}

export function updateSubTaskApi(taskId: number, subtaskId: number, data: any) {
  return request<SubTask>({
    url: `/tasks/${taskId}/subtasks/${subtaskId}`,
    method: 'PUT',
    data
  })
}

export function deleteSubTaskApi(taskId: number, subtaskId: number) {
  return request<null>({
    url: `/tasks/${taskId}/subtasks/${subtaskId}`,
    method: 'DELETE'
  })
}

export function addTaskCommentApi(taskId: number, data: { content: string }) {
  return request<TaskComment>({
    url: `/tasks/${taskId}/comments`,
    method: 'POST',
    data
  })
}
