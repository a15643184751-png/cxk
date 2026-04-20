import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

const IDS_BROWSER_PROBE_CANDIDATES = String(process.env.IDS_BROWSER_PROBE_TARGET || '')
  .split(',')
  .map((item) => item.trim())
  .filter(Boolean)
  .map((item) => item.replace(/\/$/, ''))
  .map((item) => (item.endsWith('/api') ? item : `${item}/api`))

if (!IDS_BROWSER_PROBE_CANDIDATES.length) {
  IDS_BROWSER_PROBE_CANDIDATES.push(
    'http://127.0.0.1:8171/api',
    'http://127.0.0.1:8170/api',
  )
}

let resolvedIdsProbeBase: string | null = null
let resolvingIdsProbeBase: Promise<string | null> | null = null

function shouldSkipIDSBrowserProbe(url: string, accept: string) {
  if (!accept.includes('text/html')) return true
  return (
    url.startsWith('/api') ||
    url.startsWith('/@vite') ||
    url.startsWith('/@fs/') ||
    url.startsWith('/@id/') ||
    url.startsWith('/src/') ||
    url.startsWith('/node_modules/') ||
    url.startsWith('/assets/') ||
    url.startsWith('/__vite') ||
    url === '/favicon.ico'
  )
}

async function resolveIdsProbeBase() {
  if (resolvedIdsProbeBase) return resolvedIdsProbeBase
  if (!resolvingIdsProbeBase) {
    resolvingIdsProbeBase = (async () => {
      for (const candidate of IDS_BROWSER_PROBE_CANDIDATES) {
        try {
          const response = await fetch(`${candidate}/health`, { method: 'GET' })
          if (response.ok) {
            resolvedIdsProbeBase = candidate
            return candidate
          }
        } catch {
          // try the next backend candidate
        }
      }
      return null
    })().finally(() => {
      resolvingIdsProbeBase = null
    })
  }
  return resolvingIdsProbeBase
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

function normalizeIp(raw: string) {
  const value = String(raw || '').trim()
  if (!value) return ''
  return value.replace(/^::ffff:/i, '').split('%', 1)[0].trim()
}

function extractSourceIp(req: {
  headers: Record<string, string | string[] | undefined>
  socket?: { remoteAddress?: string | undefined }
  connection?: { remoteAddress?: string | undefined }
}) {
  const forwarded = req.headers['x-forwarded-for']
  const realIp = req.headers['x-real-ip']
  const cfIp = req.headers['cf-connecting-ip']

  const candidates = [
    Array.isArray(forwarded) ? forwarded[0] : forwarded,
    Array.isArray(realIp) ? realIp[0] : realIp,
    Array.isArray(cfIp) ? cfIp[0] : cfIp,
    req.socket?.remoteAddress,
    req.connection?.remoteAddress,
  ]

  for (const candidate of candidates) {
    const normalized = normalizeIp(String(candidate || '').split(',', 1)[0] || '')
    if (normalized) return normalized
  }

  return ''
}

function renderBlockedHTML(payload: {
  attack_type?: string
  risk_score?: number
  incident_id?: number | null
  response_detail?: string
  path?: string
  source_ip?: string
}) {
  const attackType = escapeHtml(String(payload.attack_type || 'xss'))
  const responseDetail = escapeHtml(String(payload.response_detail || 'Request blocked by IDS security policy'))
  const path = escapeHtml(String(payload.path || '/'))
  const sourceIp = escapeHtml(String(payload.source_ip || '-'))
  const incidentId = Number(payload.incident_id || 0)
  const riskScore = Number(payload.risk_score || 0)
  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>403 - IDS Blocked</title>
    <style>
      body {
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background:
          radial-gradient(circle at top, rgba(239, 68, 68, 0.18), transparent 32%),
          linear-gradient(160deg, #07111f 0%, #0f172a 45%, #111827 100%);
        color: #e5eefc;
        font-family: "Plus Jakarta Sans", "Segoe UI", sans-serif;
      }
      .shell {
        width: min(760px, calc(100vw - 32px));
        border: 1px solid rgba(248, 113, 113, 0.32);
        background: rgba(8, 15, 28, 0.92);
        box-shadow: 0 24px 80px rgba(2, 6, 23, 0.55);
        border-radius: 20px;
        padding: 28px;
      }
      .badge {
        display: inline-block;
        margin-bottom: 14px;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(248, 113, 113, 0.16);
        color: #fca5a5;
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      h1 {
        margin: 0 0 10px;
        font-size: 30px;
      }
      p {
        margin: 0 0 18px;
        color: rgba(226, 232, 240, 0.82);
        line-height: 1.7;
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
      }
      .item {
        border: 1px solid rgba(148, 163, 184, 0.18);
        border-radius: 14px;
        padding: 12px 14px;
        background: rgba(15, 23, 42, 0.78);
      }
      .label {
        display: block;
        margin-bottom: 6px;
        font-size: 12px;
        color: rgba(148, 163, 184, 0.86);
      }
      .value {
        display: block;
        font-family: ui-monospace, "Cascadia Mono", Consolas, monospace;
        word-break: break-word;
      }
    </style>
  </head>
  <body>
    <main class="shell">
      <span class="badge">IDS blocked</span>
      <h1>403 - 安全策略已拦截请求</h1>
      <p>当前请求命中了本地路由探测阻断策略，事件已经写入安全事件中心，可继续查看攻击包、命中规则和 AI 研判。</p>
      <div class="grid">
        <div class="item">
          <span class="label">Attack Type</span>
          <span class="value">${attackType}</span>
        </div>
        <div class="item">
          <span class="label">Risk Score</span>
          <span class="value">${riskScore}</span>
        </div>
        <div class="item">
          <span class="label">Path</span>
          <span class="value">${path}</span>
        </div>
        <div class="item">
          <span class="label">Source IP</span>
          <span class="value">${sourceIp}</span>
        </div>
        <div class="item">
          <span class="label">Incident ID</span>
          <span class="value">${incidentId || '-'}</span>
        </div>
        <div class="item" style="grid-column: 1 / -1;">
          <span class="label">Decision</span>
          <span class="value">${responseDetail}</span>
        </div>
      </div>
    </main>
  </body>
</html>`
}

function idsBrowserRouteGuard() {
  return {
    name: 'ids-browser-route-guard',
    configureServer(server: {
      middlewares: {
        use: (
          handler: (
            req: {
              method?: string
              url?: string
              headers: Record<string, string | string[] | undefined>
              socket?: { remoteAddress?: string | undefined }
              connection?: { remoteAddress?: string | undefined }
            },
            res: {
              statusCode: number
              setHeader: (key: string, value: string) => void
              end: (content: string) => void
            },
            next: () => void
          ) => void | Promise<void>
        ) => void
      }
    }) {
      server.middlewares.use(async (req, res, next) => {
        const method = String(req.method || 'GET').toUpperCase()
        const rawUrl = String(req.url || '/')
        const accept = String(req.headers.accept || '')
        if (method !== 'GET' || shouldSkipIDSBrowserProbe(rawUrl, accept)) {
          next()
          return
        }

        const probeBase = await resolveIdsProbeBase()
        if (!probeBase) {
          next()
          return
        }

        const sourceIp = extractSourceIp(req)

        try {
          const url = new URL(rawUrl, 'http://127.0.0.1')
          const response = await fetch(`${probeBase}/ids/browser-route-probe`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'X-IDS-Browser-Probe': 'vite-dev-route-guard',
            },
            body: JSON.stringify({
              method,
              path: url.pathname,
              query: url.search.startsWith('?') ? url.search.slice(1) : url.search,
              user_agent: String(req.headers['user-agent'] || ''),
              headers: {
                accept,
                host: String(req.headers.host || ''),
                referer: String(req.headers.referer || ''),
                'x-source-ip': sourceIp,
              },
            }),
          })
          if (!(response.ok || response.status === 403)) {
            next()
            return
          }

          const payload = (await response.json()) as {
            blocked?: boolean
            attack_type?: string
            risk_score?: number
            incident_id?: number | null
            response_detail?: string
          }
          if (!payload.blocked) {
            next()
            return
          }

          res.statusCode = 403
          res.setHeader('Content-Type', 'text/html; charset=utf-8')
          res.setHeader('Cache-Control', 'no-store')
          res.end(
            renderBlockedHTML({
              ...payload,
              path: url.pathname + url.search,
              source_ip: sourceIp,
            }),
          )
        } catch {
          next()
        }
      })
    },
  }
}

export default defineConfig({
  plugins: [vue(), idsBrowserRouteGuard()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 5175,
    host: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8170',
        changeOrigin: true,
        secure: false,
        xfwd: true,
      },
      '/uploads': {
        target: 'http://127.0.0.1:8170',
        changeOrigin: true,
        secure: false,
        xfwd: true,
      },
    },
  },
  preview: {
    port: 4175,
    host: true,
  },
})
