import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { loginApi, getUserInfoApi, logoutApi } from '@/api/auth'
import { authStorage } from '@/utils/auth'
import type { UserInfo } from '@/types'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(authStorage.getToken())
  const userInfo = ref<UserInfo | null>(authStorage.getUser())

  const isAuthenticated = computed(() => !!token.value)
  const username = computed(() => userInfo.value?.nickname || userInfo.value?.username || '用户')
  const userAvatar = computed(() => userInfo.value?.avatar || 'https://api.dicebear.com/7.x/bottts/svg?seed=aipm')
  const roles = computed(() => userInfo.value?.roles || [])
  const permissions = computed(() => userInfo.value?.permissions || [])

  async function login(loginParams: { username: string; password: string; captcha_token?: string }) {
    const res = await loginApi(loginParams)

    // Starting a new session in this tab: drop any identity left over from a
    // previous account before writing the new one.
    userInfo.value = null
    authStorage.removeUser()

    token.value = res.data.token
    authStorage.setToken(res.data.token)

    // Fetch fresh user info & permissions
    await fetchUserInfo()
    return res
  }

  async function fetchUserInfo() {
    try {
      const res = await getUserInfoApi()
      userInfo.value = res.data
      authStorage.setUser(res.data)
      return res.data
    } catch (e) {
      await logout()
      throw e
    }
  }

  async function logout() {
    try {
      if (token.value) {
        await logoutApi()
      }
    } catch (e) {
      // ignore — the local session is cleared regardless
    } finally {
      token.value = ''
      userInfo.value = null
      authStorage.clear()
    }
  }

  /** Drop local state without calling the API (used when a token is rejected). */
  function resetLocalSession() {
    token.value = ''
    userInfo.value = null
    authStorage.clear()
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
    resetLocalSession,
    hasPermission
  }
})
