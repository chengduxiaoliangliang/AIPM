import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { loginApi, getUserInfoApi, logoutApi } from '@/api/auth'
import type { UserInfo } from '@/types'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('aipm_token') || '')
  const userInfo = ref<UserInfo | null>(
    localStorage.getItem('aipm_user') ? JSON.parse(localStorage.getItem('aipm_user')!) : null
  )

  const isAuthenticated = computed(() => !!token.value)
  const username = computed(() => userInfo.value?.nickname || userInfo.value?.username || '用户')
  const userAvatar = computed(() => userInfo.value?.avatar || 'https://api.dicebear.com/7.x/bottts/svg?seed=aipm')
  const roles = computed(() => userInfo.value?.roles || [])
  const permissions = computed(() => userInfo.value?.permissions || [])

  async function login(loginParams: { username: string; password: string; captcha_token?: string }) {
    const res = await loginApi(loginParams)
    token.value = res.data.token
    localStorage.setItem('aipm_token', res.data.token)
    
    // Fetch fresh user info & permissions
    await fetchUserInfo()
    return res
  }

  async function fetchUserInfo() {
    try {
      const res = await getUserInfoApi()
      userInfo.value = res.data
      localStorage.setItem('aipm_user', JSON.stringify(res.data))
      return res.data
    } catch (e) {
      logout()
      throw e
    }
  }

  async function logout() {
    try {
      if (token.value) {
        await logoutApi()
      }
    } catch (e) {
      // ignore
    } finally {
      token.value = ''
      userInfo.value = null
      localStorage.removeItem('aipm_token')
      localStorage.removeItem('aipm_user')
    }
  }

  function hasPermission(perm: string): boolean {
    if (userInfo.value?.is_superuser) return true
    if (permissions.value.includes('*')) return true
    return permissions.value.includes(perm)
  }

  return {
    token,
    userInfo,
    isAuthenticated,
    username,
    userAvatar,
    roles,
    permissions,
    login,
    fetchUserInfo,
    logout,
    hasPermission
  }
})
