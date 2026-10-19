/**
 * Authentication credential storage.
 *
 * Credentials are kept in `sessionStorage`, which is scoped to a single browser
 * tab. `localStorage` is shared by every tab of the same origin, so storing the
 * token there means a login in tab B silently overwrites tab A's token and the
 * older tab starts acting as the new account.
 *
 * Trade-off: opening the app in a brand-new tab requires signing in again.
 * That is the intended behaviour when multiple accounts are used side by side.
 */
import type { UserInfo } from '@/types'

const TOKEN_KEY = 'aipm_token'
const USER_KEY = 'aipm_user'

// Credentials written by older versions to localStorage. Purging them prevents
// a stale shared token from being picked up by a freshly opened tab.
try {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
} catch {
  /* storage may be unavailable (private mode / disabled cookies) */
}

function safeGet(key: string): string {
  try {
    return sessionStorage.getItem(key) || ''
  } catch {
    return ''
  }
}

export const authStorage = {
  getToken(): string {
    return safeGet(TOKEN_KEY)
  },

  setToken(token: string): void {
    try {
      sessionStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* ignore quota / availability errors */
    }
  },

  removeToken(): void {
    try {
      sessionStorage.removeItem(TOKEN_KEY)
    } catch {
      /* ignore */
    }
  },

  getUser(): UserInfo | null {
    const raw = safeGet(USER_KEY)
    if (!raw) return null
    try {
      return JSON.parse(raw) as UserInfo
    } catch {
      // Corrupted payload would otherwise crash the app on boot.
      this.removeUser()
      return null
    }
  },

  setUser(user: UserInfo | null): void {
    try {
      if (user) {
        sessionStorage.setItem(USER_KEY, JSON.stringify(user))
      } else {
        sessionStorage.removeItem(USER_KEY)
      }
    } catch {
      /* ignore */
    }
  },

  removeUser(): void {
    try {
      sessionStorage.removeItem(USER_KEY)
    } catch {
      /* ignore */
    }
  },

  clear(): void {
    this.removeToken()
    this.removeUser()
  }
}
