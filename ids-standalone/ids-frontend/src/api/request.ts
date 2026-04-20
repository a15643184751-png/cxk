import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import router from '@/router'

const directBaseURL = import.meta.env.VITE_API_BASE

function buildDevBaseCandidates() {
  if (typeof window !== 'undefined') {
    const port = window.location.port || ''
    if (port === '5175' || port === '4175') {
      return [
        'http://127.0.0.1:8170/api',
        'http://127.0.0.1:8171/api',
      ]
    }
  }

  return [
    'http://127.0.0.1:8170/api',
    'http://127.0.0.1:8171/api',
  ]
}

const shouldAutoPickDevBase =
  import.meta.env.DEV && (!directBaseURL || directBaseURL === '/api')

function isLocalAccess(): boolean {
  if (typeof window === 'undefined') return true
  const host = window.location.hostname
  return host === 'localhost' || host === '127.0.0.1'
}

let resolvedBaseURL: string | null = shouldAutoPickDevBase
  ? null
  : (directBaseURL || (import.meta.env.DEV ? null : '/api'))
let resolvingBaseURL: Promise<string> | null = null

async function pickDevBaseURL() {
  const candidates = buildDevBaseCandidates()
  for (const candidate of candidates) {
    try {
      const res = await fetch(`${candidate}/health`, {
        method: 'GET',
        cache: 'no-store',
      })
      if (res.ok) {
        return candidate
      }
    } catch {
      // ignore and try next candidate
    }
  }

  return candidates[0]
}

async function resolveBaseURL() {
  if (!isLocalAccess()) return '/api'
  if (resolvedBaseURL) return resolvedBaseURL
  if (!import.meta.env.DEV) return '/api'

  if (!resolvingBaseURL) {
    resolvingBaseURL = pickDevBaseURL().then((baseURL) => {
      resolvedBaseURL = baseURL
      return baseURL
    })
  }

  return resolvingBaseURL
}

export async function resolveAPIURL(path: string) {
  const baseURL = await resolveBaseURL()
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${baseURL.replace(/\/$/, '')}${normalizedPath}`
}

const request = axios.create({
  baseURL: resolvedBaseURL || '/api',
  timeout: 60000,
  headers: { 'Content-Type': 'application/json' },
})

request.interceptors.request.use(
  async (config) => {
    config.baseURL = await resolveBaseURL()
    const userStore = useUserStore()
    if (userStore.token) {
      config.headers.Authorization = `Bearer ${userStore.token}`
    }
    if (config.data instanceof FormData) {
      delete config.headers['Content-Type']
    }
    return config
  },
  (err) => Promise.reject(err),
)

request.interceptors.response.use(
  (res) => {
    const { code, message } = res.data as { code?: number; message?: string }
    if (code !== undefined && code !== 200) {
      ElMessage.error(message || '请求失败')
      return Promise.reject(new Error(message as string))
    }
    return res.data
  },
  (err) => {
    if (err.response?.status === 401) {
      useUserStore().logout()
      void router.push('/login')
    }

    const isTimeout =
      err.code === 'ECONNABORTED' || /timeout/i.test(String(err?.message || ''))

    const msg =
      isTimeout
        ? '请求处理超过 60 秒，AI 研判或样本审计仍在执行，请稍后重试'
        : err.code === 'ERR_NETWORK'
          ? '无法连接安全分析服务，请确认 8170 或 8171 端口服务已启动'
          : (err.response?.data?.detail ||
              err.response?.data?.message ||
              err.message ||
              '网络错误')

    ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    return Promise.reject(err)
  },
)

export default request
