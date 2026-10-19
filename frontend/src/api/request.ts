import axios, { AxiosRequestConfig, AxiosResponse } from 'axios'
import { ElMessage, ElNotification } from 'element-plus'
import type { ApiResponse } from '@/types'

const service = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor
service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('aipm_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
service.interceptors.response.use(
  (response: AxiosResponse<ApiResponse>) => {
    const res = response.data
    // If custom code is present and not 200/201
    if (res.code && res.code !== 200 && res.code !== 201) {
      ElMessage.error(res.message || '请求处理失败')
      return Promise.reject(new Error(res.message || 'Error'))
    }
    return response
  },
  (error) => {
    if (error.response) {
      const status = error.response.status
      const data = error.response.data
      const message = (data && data.detail && typeof data.detail === 'string') 
        ? data.detail 
        : (data && data.message) 
        ? data.message 
        : (data && data.detail && data.detail.message)
        ? data.detail.message
        : '网络请求异常'

      if (status === 401) {
        localStorage.removeItem('aipm_token')
        localStorage.removeItem('aipm_user')
        ElNotification.error({
          title: '认证过期',
          message: '登录状态已失效，请重新登录'
        })
        if (window.location.pathname !== '/login') {
          window.location.href = '/login'
        }
      } else if (status === 403) {
        ElMessage.error(message || '无权访问该资源')
      } else {
        ElMessage.error(message || `请求失败 (${status})`)
      }
    } else {
      ElMessage.error('网络连接中断或超时，请检查后端服务')
    }
    return Promise.reject(error)
  }
)

export default async function request<T = any>(config: AxiosRequestConfig): Promise<ApiResponse<T>> {
  const response = await service.request<ApiResponse<T>>(config)
  return response.data
}
