const ROUTE_THREAT_PREFLIGHT_RE =
  /(?:<|>|%3c|%3e|javascript:|vbscript:|onerror=|onload=|onclick=|onmouseover=|alert\(|eval\(|document\.cookie|\$\{jndi:|%24%7bjndi:|\.\.|%2e%2e|\/\.env\b|wp-login\.php|proxy\.php|fetchlogfiles|union(?:\+|%20|\s)+select|cmd\.exe|powershell)/i

export type BrowserRouteProbeResult = {
  matched: boolean
  blocked: boolean
  should_block?: boolean
  attack_type?: string
  risk_score?: number
  confidence?: number
  incident_id?: number | null
  response_detail?: string
  detail?: string
  code?: string
}

export function routeNeedsBrowserProbe(fullPath: string) {
  if (!fullPath) return false
  if (fullPath.startsWith('/security-blocked')) return false
  return ROUTE_THREAT_PREFLIGHT_RE.test(fullPath)
}

export function routeQuerySnippet(fullPath: string) {
  const queryIndex = fullPath.indexOf('?')
  return queryIndex >= 0 ? fullPath.slice(queryIndex + 1) : ''
}

export async function inspectBrowserRouteThreat(input: {
  path: string
  fullPath: string
  method?: string
}): Promise<{ ok: boolean; status: number; data: BrowserRouteProbeResult | null }> {
  try {
    const { resolveAPIURL } = await import('@/api/request')
    const url = await resolveAPIURL('/ids/browser-route-probe')
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        method: input.method || 'GET',
        path: input.path || '/',
        query: routeQuerySnippet(input.fullPath),
        user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
        headers: typeof document !== 'undefined' && document.referrer
          ? { referer: document.referrer }
          : {},
      }),
    })

    let data: BrowserRouteProbeResult | null = null
    try {
      data = (await res.json()) as BrowserRouteProbeResult
    } catch {
      data = null
    }

    return { ok: res.ok, status: res.status, data }
  } catch {
    return { ok: false, status: 0, data: null }
  }
}
