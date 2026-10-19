import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const isCollapse = ref<boolean>(localStorage.getItem('aipm_sidebar_collapse') === 'true')
  const isDark = ref<boolean>(
    localStorage.getItem('aipm_theme_dark') === 'true' ||
    window.matchMedia('(prefers-color-scheme: dark)').matches
  )

  // Initialize dark class on HTML
  if (isDark.value) {
    document.documentElement.classList.add('dark')
  } else {
    document.documentElement.classList.remove('dark')
  }

  function toggleSidebar() {
    isCollapse.value = !isCollapse.value
    localStorage.setItem('aipm_sidebar_collapse', String(isCollapse.value))
  }

  function toggleDarkMode() {
    isDark.value = !isDark.value
    localStorage.setItem('aipm_theme_dark', String(isDark.value))
    if (isDark.value) {
      document.documentElement.classList.add('dark')
    } else {
      document.documentElement.classList.remove('dark')
    }
  }

  return {
    isCollapse,
    isDark,
    toggleSidebar,
    toggleDarkMode
  }
})
