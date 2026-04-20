import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const TOKEN_STORAGE_KEY = 'ids-access-token'
const USER_INFO_STORAGE_KEY = 'ids-user-info'

type StoredUserInfo = {
  id: number
  username: string
  real_name: string
  role: string
  department?: string
  phone?: string
}

function readStoredUserInfo(): StoredUserInfo | null {
  try {
    const raw = localStorage.getItem(USER_INFO_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<StoredUserInfo> | null
    if (!parsed || typeof parsed !== 'object') return null
    const id = Number(parsed.id || 0)
    const username = String(parsed.username || '').trim()
    const realName = String(parsed.real_name || '').trim()
    const role = String(parsed.role || '').trim()
    if (!id || !username || !role) return null
    return {
      id,
      username,
      real_name: realName || username,
      role,
      department: parsed.department ? String(parsed.department) : '',
      phone: parsed.phone ? String(parsed.phone) : '',
    }
  } catch {
    return null
  }
}

function writeStoredUserInfo(info: StoredUserInfo | null) {
  if (!info) {
    localStorage.removeItem(USER_INFO_STORAGE_KEY)
    return
  }
  localStorage.setItem(USER_INFO_STORAGE_KEY, JSON.stringify(info))
}

export const useUserStore = defineStore('ids-user', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_STORAGE_KEY) || '')
  const userInfo = ref<StoredUserInfo | null>(readStoredUserInfo())

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => userInfo.value?.role === 'ids_admin')
  const role = computed(() => userInfo.value?.role || '')

  function setToken(value: string) {
    token.value = value
    if (value) {
      localStorage.setItem(TOKEN_STORAGE_KEY, value)
    } else {
      localStorage.removeItem(TOKEN_STORAGE_KEY)
      userInfo.value = null
      writeStoredUserInfo(null)
    }
  }

  function setUserInfo(info: StoredUserInfo | null) {
    userInfo.value = info
    writeStoredUserInfo(info)
  }

  function logout() {
    token.value = ''
    userInfo.value = null
    localStorage.removeItem(TOKEN_STORAGE_KEY)
    localStorage.removeItem(USER_INFO_STORAGE_KEY)
  }

  return {
    token,
    userInfo,
    isLoggedIn,
    isAdmin,
    role,
    setToken,
    setUserInfo,
    logout,
  }
})
