import { getIDSBridgeStatus } from '@/api/ids'

const IDS_CONSOLE_PORT = '5175'
const IDS_DEFAULT_REDIRECT = '/overview'
const IDS_SECURITY_ROUTE_PREFIXES = ['/security', '/ids']

function isLoopbackHost(hostname?: string) {
  const normalized = String(hostname || '').trim().toLowerCase()
  return normalized === 'localhost' || normalized === '127.0.0.1' || normalized === '::1'
}

function normalizeIdsSecurityRoutePath(path?: string) {
  if (!path) return ''
  const [pathname] = path.split(/[?#]/, 1)
  if (!pathname) return ''
  return pathname.startsWith('/') ? pathname : `/${pathname}`
}

export function isIdsSecurityCenterPath(path?: string) {
  const normalizedPath = normalizeIdsSecurityRoutePath(path)
  if (!normalizedPath) return false

  return IDS_SECURITY_ROUTE_PREFIXES.some(
    (prefix) => normalizedPath === prefix || normalizedPath.startsWith(`${prefix}/`),
  )
}

function getFallbackConsoleOrigin() {
  if (typeof window === 'undefined') {
    return `http://127.0.0.1:${IDS_CONSOLE_PORT}`
  }

  const currentUrl = new URL(window.location.href)
  currentUrl.port = IDS_CONSOLE_PORT
  currentUrl.pathname = '/'
  currentUrl.search = ''
  currentUrl.hash = ''
  return currentUrl.toString()
}

function buildIdsSecurityCenterUrl(rawBaseUrl?: string, redirectPath = IDS_DEFAULT_REDIRECT) {
  const baseUrl = rawBaseUrl || getFallbackConsoleOrigin()
  const targetUrl = new URL(
    baseUrl,
    typeof window !== 'undefined' ? window.location.origin : 'http://127.0.0.1',
  )

  if (
    typeof window !== 'undefined' &&
    !isLoopbackHost(window.location.hostname) &&
    isLoopbackHost(targetUrl.hostname)
  ) {
    targetUrl.hostname = window.location.hostname
    targetUrl.port = IDS_CONSOLE_PORT
  }

  targetUrl.pathname = '/login'
  targetUrl.search = ''
  targetUrl.hash = ''
  targetUrl.searchParams.set('autologin', '1')
  targetUrl.searchParams.set('redirect', redirectPath || IDS_DEFAULT_REDIRECT)

  return targetUrl.toString()
}

export async function resolveIdsSecurityCenterUrl(redirectPath = IDS_DEFAULT_REDIRECT) {
  try {
    const bridge = await getIDSBridgeStatus()
    if (bridge?.standalone_console_url) {
      return buildIdsSecurityCenterUrl(bridge.standalone_console_url, redirectPath)
    }
  } catch {
    // Fall back to current host + IDS frontend port when bridge status is temporarily unavailable.
  }

  return buildIdsSecurityCenterUrl(undefined, redirectPath)
}

export async function openIdsSecurityCenter(options?: {
  replace?: boolean
  redirect?: string
}) {
  const targetUrl = await resolveIdsSecurityCenterUrl(options?.redirect)

  if (typeof window !== 'undefined') {
    if (options?.replace) {
      window.location.replace(targetUrl)
    } else {
      window.location.assign(targetUrl)
    }
  }

  return targetUrl
}
