import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export type AppLocale = 'zh-CN' | 'en-US'

const LOCALE_KEY = 'campus-locale'
const SEARCH_HIST_KEY = 'campus-search-history'
const USER_INFO_KEY = 'campus-user-info-v1'

export type UserInfoStored = {
  id: number
  username: string
  real_name: string
  role: string
  department?: string
  email?: string
}

function loadUserInfoFromStorage(hasToken: boolean): UserInfoStored | null {
  if (!hasToken) return null
  try {
    const raw = localStorage.getItem(USER_INFO_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as UserInfoStored
    if (parsed && typeof parsed.username === 'string' && typeof parsed.role === 'string') {
      return parsed
    }
  } catch {
    /* ignore */
  }
  return null
}

function loadLocale(): AppLocale {
  const v = localStorage.getItem(LOCALE_KEY)
  return v === 'en-US' ? 'en-US' : 'zh-CN'
}

function loadSearchHistory(): string[] {
  try {
    const raw = localStorage.getItem(SEARCH_HIST_KEY)
    if (!raw) return []
    const arr = JSON.parse(raw)
    return Array.isArray(arr) ? arr.filter((x) => typeof x === 'string').slice(0, 20) : []
  } catch {
    return []
  }
}

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const userInfo = ref<UserInfoStored | null>(loadUserInfoFromStorage(!!token.value))

  const language = ref<AppLocale>(loadLocale())
  const searchHistory = ref<string[]>(loadSearchHistory())

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => userInfo.value?.role === 'system_admin')
  const role = computed(() => userInfo.value?.role || '')

  function setToken(t: string) {
    token.value = t
    if (t) {
      localStorage.setItem('token', t)
    } else {
      localStorage.removeItem('token')
      userInfo.value = null
      localStorage.removeItem(USER_INFO_KEY)
    }
  }

  function setUserInfo(info: UserInfoStored | null) {
    userInfo.value = info
    if (!info) {
      localStorage.removeItem(USER_INFO_KEY)
      return
    }
    try {
      localStorage.setItem(USER_INFO_KEY, JSON.stringify(info))
    } catch {
      /* ignore quota */
    }
  }

  function setLanguage(locale: AppLocale) {
    language.value = locale
    localStorage.setItem(LOCALE_KEY, locale)
  }

  function pushSearchHistory(path: string) {
    if (!path) return
    const next = [path, ...searchHistory.value.filter((p) => p !== path)].slice(0, 20)
    searchHistory.value = next
    localStorage.setItem(SEARCH_HIST_KEY, JSON.stringify(next))
  }

  function clearSearchHistory() {
    searchHistory.value = []
    localStorage.removeItem(SEARCH_HIST_KEY)
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem('token')
    localStorage.removeItem(USER_INFO_KEY)
  }

  return {
    token,
    userInfo,
    language,
    searchHistory,
    isLoggedIn,
    isAdmin,
    role,
    setToken,
    setUserInfo,
    setLanguage,
    pushSearchHistory,
    clearSearchHistory,
    logout,
  }
})
