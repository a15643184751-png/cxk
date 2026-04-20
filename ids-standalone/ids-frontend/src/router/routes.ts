import type { RouteRecordRaw } from 'vue-router'
import type { RoleType } from '@/types/role'

export type RouteMetaRole = {
  title?: string
  public?: boolean
  roles?: RoleType[]
}

const IDS_ROLES: RoleType[] = [
  'ids_admin',
  'ids_operator',
  'ids_auditor',
  'ids_viewer',
]

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/Login.vue'),
    meta: { public: true, title: 'IDS 登录' },
  },
  {
    path: '/upload',
    redirect: '/detection',
  },
  {
    path: '/security-blocked',
    name: 'FrontendRouteBlocked',
    component: () => import('@/views/error/SecurityBlocked.vue'),
    meta: { public: true, title: '访问已拦截' },
  },
  {
    path: '/',
    component: () => import('@/views/security/SecurityCenterLayout.vue'),
    redirect: '/overview',
    children: [
      {
        path: 'overview',
        name: 'IDSOverview',
        component: () => import('@/views/security/SecurityTrafficSessions.vue'),
        meta: { title: '总览', roles: IDS_ROLES },
      },
      {
        path: 'events',
        name: 'IDSEvents',
        component: () => import('@/views/security/SecurityIDS.vue'),
        meta: { title: '事件中心', roles: IDS_ROLES },
      },
      {
        path: 'traffic',
        redirect: '/overview',
      },
      {
        path: 'workbench',
        name: 'IDSWorkbench',
        component: () => import('@/views/security/IDSWorkbench.vue'),
        meta: { title: '分析工作台', roles: IDS_ROLES },
      },
      {
        path: 'detection',
        name: 'IDSDetectionTools',
        component: () => import('@/views/security/IDSDetectionTools.vue'),
        meta: { title: '检测工具', roles: IDS_ROLES },
      },
      {
        path: 'config',
        name: 'IDSCommunicationConfig',
        component: () => import('@/views/security/IDSCommunicationConfig.vue'),
        meta: { title: '通信配置', roles: IDS_ROLES },
      },
      {
        path: 'notifications',
        name: 'IDSNotifications',
        component: () => import('@/views/notifications/IDSNotifications.vue'),
        meta: { title: '通知配置', roles: IDS_ROLES },
      },
      {
        path: 'audit',
        name: 'IDSAudit',
        component: () => import('@/views/security/SecurityLogAudit.vue'),
        meta: { title: '审计中心', roles: IDS_ROLES },
      },
      {
        path: 'situation',
        name: 'IDSSituation',
        component: () => import('@/views/security/SecuritySituation.vue'),
        meta: { title: '安全态势', roles: IDS_ROLES },
      },
      {
        path: 'sandbox',
        name: 'IDSSandbox',
        component: () => import('@/views/security/SecuritySandbox.vue'),
        meta: { title: '文件审计', roles: IDS_ROLES },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/NotFound.vue'),
    meta: { public: true, title: '页面不存在' },
  },
]
