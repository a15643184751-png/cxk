import type { RouteLocationNormalized } from 'vue-router'
import { createRouter, createWebHistory } from 'vue-router'
import { getUserInfo } from '@/api/auth'
import { useUserStore } from '@/stores/user'
import type { RoleType } from '@/types/role'
import {
  inspectBrowserRouteThreat,
  routeNeedsBrowserProbe,
  routeQuerySnippet,
} from '@/utils/browserRouteGuard'
import { routes } from './routes'
import type { RouteMetaRole } from './routes'

const router = createRouter({
  history: createWebHistory(),
  routes,
})

function getDefaultRedirect(_role?: RoleType): string {
  return '/overview'
}

function buildBrowserRouteBlockedRedirect(
  to: RouteLocationNormalized,
  probe: Awaited<ReturnType<typeof inspectBrowserRouteThreat>>,
) {
  if (to.name === 'FrontendRouteBlocked') return null
  const blocked =
    Boolean(probe.data?.blocked || probe.data?.should_block) ||
    (probe.status === 403 && probe.data?.code === 'IDS_BROWSER_ROUTE_BLOCKED')
  if (!blocked) return null

  const blockedQuery: Record<string, string> = {
    attack: String(probe.data?.attack_type || 'unknown'),
    path: to.path || '/',
    query: routeQuerySnippet(to.fullPath),
  }

  const incidentId = Number(probe.data?.incident_id || 0)
  const riskScore = Number(probe.data?.risk_score || 0)

  if (Number.isFinite(incidentId) && incidentId > 0) {
    blockedQuery.incident = String(incidentId)
  }

  if (Number.isFinite(riskScore) && riskScore > 0) {
    blockedQuery.risk = String(riskScore)
  }

  return {
    name: 'FrontendRouteBlocked',
    replace: true,
    query: blockedQuery,
  }
}

router.beforeEach(async (to) => {
  if (routeNeedsBrowserProbe(to.fullPath)) {
    const probe = await inspectBrowserRouteThreat({
      path: to.path || '/',
      fullPath: to.fullPath,
    })
    const blockedRedirect = buildBrowserRouteBlockedRedirect(to, probe)
    if (blockedRedirect) {
      return blockedRedirect
    }
  }

  const userStore = useUserStore()
  const isPublic = Boolean(to.meta.public)

  if (isPublic) {
    return true
  }

  if (!userStore.token) {
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  if (!userStore.userInfo) {
    try {
      const response: any = await getUserInfo()
      const user = response?.data ?? response
      userStore.setUserInfo(user ?? null)
    } catch {
      userStore.logout()
      return { name: 'Login', query: { redirect: to.fullPath } }
    }
  }

  const routeRoles = (to.meta as RouteMetaRole)?.roles as RoleType[] | undefined
  const userRole = userStore.userInfo?.role as RoleType | undefined

  if (routeRoles?.length && userRole && !routeRoles.includes(userRole)) {
    return getDefaultRedirect(userRole)
  }

  if (to.path === '/') {
    return getDefaultRedirect(userRole)
  }

  return true
})

export default router
