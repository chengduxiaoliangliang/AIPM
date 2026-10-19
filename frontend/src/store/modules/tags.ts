import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { RouteLocationNormalized } from 'vue-router'

export interface TagViewItem {
  name: string
  path: string
  title: string
  affix?: boolean
  fullPath?: string
}

export const useTagsStore = defineStore('tags', () => {
  const visitedTags = ref<TagViewItem[]>([
    { name: 'Dashboard', path: '/dashboard', title: '统计大盘', affix: true }
  ])

  function addVisitedTag(route: RouteLocationNormalized) {
    if (!route.meta || !route.meta.title || route.name === 'Login') return
    const exists = visitedTags.value.some((tag) => tag.path === route.path)
    if (!exists) {
      visitedTags.value.push({
        name: (route.name as string) || '',
        path: route.path,
        title: (route.meta.title as string) || '页面',
        affix: Boolean(route.meta.affix),
        fullPath: route.fullPath
      })
    }
  }

  function closeTag(path: string) {
    const idx = visitedTags.value.findIndex((t) => t.path === path)
    if (idx > -1 && !visitedTags.value[idx].affix) {
      visitedTags.value.splice(idx, 1)
    }
  }

  function closeOtherTags(currentPath: string) {
    visitedTags.value = visitedTags.value.filter(
      (tag) => tag.affix || tag.path === currentPath
    )
  }

  function closeAllTags() {
    visitedTags.value = visitedTags.value.filter((tag) => tag.affix)
  }

  return {
    visitedTags,
    addVisitedTag,
    closeTag,
    closeOtherTags,
    closeAllTags
  }
})
