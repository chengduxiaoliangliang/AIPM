export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
}

export interface PaginatedData<T = any> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface UserInfo {
  id: number
  username: string
  nickname: string
  email?: string
  phone?: string
  avatar?: string
  position?: string
  is_superuser: boolean
  roles: string[]
  permissions: string[]
  department_id?: number
  department_name?: string
  created_at?: string
}

export interface Department {
  id: number
  name: string
  code: string
  parent_id?: number
  leader?: string
  phone?: string
  email?: string
  order_num: number
  status: boolean
  created_at: string
  children?: Department[]
}

export interface Role {
  id: number
  name: string
  code: string
  description?: string
  order_num: number
  status: boolean
  created_at: string
  permissions: number[]
}

export interface Project {
  id: number
  name: string
  code: string
  description?: string
  owner_id: number
  owner_name?: string
  owner_avatar?: string
  status: 'planning' | 'in_progress' | 'testing' | 'completed' | 'suspended'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  budget: number
  consumed_budget: number
  progress: number
  health: 'good' | 'warning' | 'danger'
  start_date?: string
  end_date?: string
  cover_image?: string
  member_count: number
  task_count: number
  completed_task_count: number
  created_at: string
  updated_at: string
}

export interface ProjectMember {
  id: number
  project_id: number
  user_id: number
  project_role: string
  username: string
  nickname: string
  avatar?: string
  position?: string
  joined_at: string
}

export interface Milestone {
  id: number
  project_id: number
  title: string
  description?: string
  due_date: string
  status: 'pending' | 'in_progress' | 'reached' | 'delayed'
  order_num: number
  reached_at?: string
  created_at: string
}

export interface Task {
  id: number
  project_id: number
  milestone_id?: number
  title: string
  description?: string
  task_type: 'task' | 'feature' | 'bug' | 'improvement' | 'research'
  status: 'todo' | 'in_progress' | 'in_review' | 'testing' | 'done'
  priority: 'low' | 'medium' | 'high' | 'urgent'
  creator_id: number
  assignee_id?: number
  creator_name?: string
  assignee_name?: string
  assignee_avatar?: string
  project_name?: string
  milestone_title?: string
  estimated_hours: number
  actual_hours: number
  progress: number
  start_date?: string
  due_date?: string
  order_num: number
  tags?: string
  subtask_count: number
  completed_subtask_count: number
  comment_count: number
  created_at: string
  updated_at: string
}

export interface SubTask {
  id: number
  task_id: number
  title: string
  is_completed: boolean
  assignee_id?: number
  assignee_name?: string
  created_at: string
}

export interface TaskComment {
  id: number
  task_id: number
  user_id: number
  username: string
  user_nickname: string
  user_avatar?: string
  content: string
  created_at: string
}

export interface WorkLog {
  id: number
  project_id: number
  task_id?: number
  user_id: number
  log_date: string
  hours: number
  description: string
  status: 'pending' | 'approved' | 'rejected'
  user_name?: string
  user_avatar?: string
  project_name?: string
  task_title?: string
  approver_id?: number
  approver_name?: string
  approval_remark?: string
  approved_at?: string
  created_at: string
}

export interface Issue {
  id: number
  project_id: number
  task_id?: number
  title: string
  description?: string
  severity: 'fatal' | 'critical' | 'medium' | 'low'
  priority: 'urgent' | 'high' | 'medium' | 'low'
  status: 'open' | 'in_progress' | 'resolved' | 'closed' | 'rejected'
  reporter_id: number
  assignee_id?: number
  reporter_name?: string
  assignee_name?: string
  project_name?: string
  task_title?: string
  resolution?: string
  created_at: string
  updated_at: string
}

export interface DocumentItem {
  id: number
  project_id: number
  title: string
  category: 'requirement' | 'design' | 'api' | 'deployment' | 'meeting' | 'general'
  content?: string
  version: string
  file_url?: string
  author_id: number
  author_name?: string
  project_name?: string
  created_at: string
  updated_at: string
}

export interface DashboardStats {
  metrics: {
    total_projects: number
    active_projects: number
    total_tasks: number
    in_progress_tasks: number
    completed_tasks: number
    pending_approvals: number
    total_hours: number
    total_issues: number
    open_issues: number
  }
  project_status_dist: { status: string; count: number; name: string }[]
  task_priority_dist: { priority: string; count: number; name: string }[]
  monthly_trends: { month: string; created_tasks: number; completed_tasks: number; logged_hours: number }[]
  member_workloads: { user_id: number; name: string; avatar: string; task_count: number; logged_hours: number; completion_rate: number }[]
  recent_activities: { id: number; username: string; module: string; action: string; details: string; created_at: string }[]
}
