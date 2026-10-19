import type { Router } from 'vue-router'
import { useUserStore } from '@/store/modules/user'
import { useTagsStore } from '@/store/modules/tags'

const WHITE_LIST = ['/login']

export function setupRouterGuard(router: Router) {
  router.beforeEach(async (to, from, next) => {
    const userStore = useUserStore()
    const token = localStorage.getItem('aipm_token')

    if (token) {
      if (to.path === '/login') {
        next({ path: '/dashboard' })
      } else {
        if (!userStore.userInfo) {
          try {
            await userStore.fetchUserInfo()
            next({ ...to, replace: true })
          } catch (error) {
            userStore.logout()
            next(`/login?redirect=${encodeURIComponent(to.fullPath)}`)
          }
        } else {
          next()
        }
      }
    } else {
      if (WHITE_LIST.includes(to.path)) {
        next()
      } else {
        next(`/login?redirect=${encodeURIComponent(to.fullPath)}`)
      }
    }
  })

  router.afterEach((to) => {
    const tagsStore = useTagsStore()
    tagsStore.addVisitedTag(to)
    
    // Set Document Title
    const title = (to.meta.title as string) || 'AIPM'
    document.title = `${title} - AIPM 智能项目管理系统`
  })
}
