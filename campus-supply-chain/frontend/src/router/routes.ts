import type { RouteRecordRaw } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import type { RoleType } from '@/types/role'

export type RouteMetaRole = {
  title?: string
  /** 顶栏展示的全局平台名（如教师智能工作台） */
  platformTitle?: string
  icon?: string
  hideInMenu?: boolean
  menuGroup?: string
  roles?: RoleType[]
}

export const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/login/Login.vue'),
    meta: { public: true, title: '登录' },
  },
  {
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('@/views/auth/ForgotPassword.vue'),
    meta: { public: true, title: '忘记密码' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/auth/Register.vue'),
    meta: { public: true, title: '注册' },
  },
  {
    path: '/upload',
    name: 'PublicUpload',
    component: () => import('@/views/upload/PublicUpload.vue'),
    meta: { public: true, title: '匿名反馈材料上传' },
  },
  {
    path: '/',
    component: AppLayout,
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/dashboard/Dashboard.vue'),
        meta: {
          title: '工作台',
          icon: 'Odometer',
          menuGroup: 'dashboard',
          roles: ['system_admin', 'logistics_admin', 'warehouse_procurement', 'campus_supplier'],
        },
      },
      {
        path: 'purchase',
        name: 'PurchaseList',
        component: () => import('@/views/purchase/PurchaseList.vue'),
        meta: {
          title: '审批台',
          icon: 'ShoppingCart',
          menuGroup: 'dashboard',
          roles: ['logistics_admin'],
        },
      },
      {
        path: 'dashboard/analysis',
        name: 'DashboardAnalysis',
        component: () => import('@/views/screen/WarehouseScreen.vue'),
        meta: {
          title: '全景大屏',
          icon: 'DataLine',
          menuGroup: 'dashboard',
          roles: ['system_admin', 'logistics_admin', 'warehouse_procurement', 'campus_supplier'],
        },
      },
      {
        path: 'profile',
        name: 'UserProfile',
        component: () => import('@/views/profile/UserCenter.vue'),
        meta: {
          title: '个人中心',
          icon: 'User',
          hideInMenu: true,
          roles: ['system_admin', 'logistics_admin', 'warehouse_procurement', 'campus_supplier', 'counselor_teacher'],
        },
      },
      // 后勤管理员 + 仓储采购员
      {
        path: 'goods',
        name: 'GoodsList',
        component: () => import('@/views/goods/GoodsList.vue'),
        meta: { title: '物资管理', icon: 'Box', roles: ['logistics_admin', 'warehouse_procurement'] },
      },
      {
        path: 'purchase/apply',
        name: 'PurchaseApply',
        component: () => import('@/views/purchase/PurchaseApply.vue'),
        meta: { title: '采购申请', icon: 'Edit', roles: ['counselor_teacher'] },
      },
      // 仓储 - 后勤管理员 + 仓储采购员
      {
        path: 'stock/in',
        name: 'StockInList',
        component: () => import('@/views/stock/StockInList.vue'),
        meta: { title: '入库管理', icon: 'Upload', menuGroup: 'stock', roles: ['warehouse_procurement'] },
      },
      {
        path: 'stock/out',
        name: 'StockOutList',
        component: () => import('@/views/stock/StockOutList.vue'),
        meta: { title: '出库管理', icon: 'Download', menuGroup: 'stock', roles: ['warehouse_procurement'] },
      },
      {
        path: 'stock/inventory',
        name: 'InventoryList',
        redirect: (to) => ({ path: '/goods', query: { ...to.query, tab: 'stock' } }),
        meta: { hideInMenu: true, roles: ['warehouse_procurement'] },
      },
      // 配送 - 仅仓储执行
      {
        path: 'delivery',
        name: 'DeliveryList',
        component: () => import('@/views/delivery/DeliveryList.vue'),
        meta: { title: '配送管理', icon: 'Van', menuGroup: 'stock', roles: ['warehouse_procurement'] },
      },
      {
        path: 'delivery/map',
        name: 'DeliveryMap',
        component: () => import('@/views/delivery/DeliveryMap.vue'),
        meta: { title: '配送地图', icon: 'Location', menuGroup: 'stock', roles: ['warehouse_procurement'] },
      },
      // 原独立仓储大屏路径合并至 /dashboard/analysis（仓储端侧栏显示为「仓储大屏」）
      {
        path: 'screen/warehouse',
        name: 'WarehouseScreen',
        redirect: '/dashboard/analysis',
        meta: { hideInMenu: true },
      },
      // 后勤大屏
      {
        path: 'screen/logistics',
        name: 'LogisticsScreen',
        component: () => import('@/views/screen/LogisticsScreen.vue'),
        meta: { title: '后勤大屏', icon: 'Monitor', roles: ['logistics_admin'] },
      },
      {
        path: 'screen/overview',
        redirect: '/dashboard/analysis',
        meta: { hideInMenu: true },
      },
      // 溯源 - 教师、后勤、仓储
      {
        path: 'trace',
        name: 'TraceQuery',
        component: () => import('@/views/trace/TraceQuery.vue'),
        meta: { title: '溯源查询', icon: 'Connection', roles: ['system_admin', 'logistics_admin', 'warehouse_procurement', 'counselor_teacher'] },
      },
      // 预警 - 后勤管理员 + 仓储采购员
      {
        path: 'warning',
        name: 'WarningList',
        component: () => import('@/views/warning/WarningList.vue'),
        meta: { title: '预警中心', icon: 'Warning', roles: ['logistics_admin', 'warehouse_procurement'] },
      },
      // AI 助手 - 所有人
      {
        path: 'ai/chat',
        name: 'AIChat',
        component: () => import('@/views/ai/AIChat.vue'),
        meta: { title: 'AI 助手', icon: 'ChatDotRound', roles: ['system_admin', 'logistics_admin', 'warehouse_procurement', 'campus_supplier', 'counselor_teacher'] },
      },
      {
        path: 'my-applications',
        redirect: (to) => ({ path: '/teacher/personal', query: { ...to.query, tab: 'orders' } }),
        meta: { hideInMenu: true, roles: ['counselor_teacher'] },
      },
      {
        path: 'teacher/service-evaluation',
        redirect: (to) => ({ path: '/teacher/personal', query: { ...to.query, tab: 'orders' } }),
        meta: { hideInMenu: true, roles: ['counselor_teacher'] },
      },
      {
        path: 'teacher/workbench',
        name: 'TeacherWorkbench',
        component: () => import('@/views/teacher/TeacherSmartWorkbench.vue'),
        meta: {
          title: '智能工作台',
          platformTitle: '校园物资供应链健康管理平台',
          icon: 'MagicStick',
          menuGroup: 'teacher',
          roles: ['counselor_teacher'],
        },
      },
      {
        path: 'teacher/schedule',
        name: 'TeacherSchedule',
        component: () => import('@/views/teacher/TeacherSchedule.vue'),
        meta: { title: '日程与规划', icon: 'Calendar', menuGroup: 'teacher', roles: ['counselor_teacher'] },
      },
      {
        path: 'teacher/personal',
        name: 'TeacherPersonal',
        component: () => import('@/views/teacher/TeacherPersonalCenter.vue'),
        meta: { title: '个人中心', icon: 'UserFilled', menuGroup: 'teacher', roles: ['counselor_teacher'] },
      },
      {
        path: 'teacher/personal/order/:orderId',
        name: 'TeacherOrderDetail',
        component: () => import('@/views/teacher/TeacherOrderDetail.vue'),
        meta: { title: '订单详情', hideInMenu: true, menuGroup: 'teacher', roles: ['counselor_teacher'] },
      },
      {
        path: 'teacher/personal/asset/:assetId',
        name: 'TeacherAssetDetail',
        component: () => import('@/views/teacher/TeacherAssetDetail.vue'),
        meta: { title: '领用详情', hideInMenu: true, menuGroup: 'teacher', roles: ['counselor_teacher'] },
      },
      // 校园合作供应商专属 - 我的订单
      {
        path: 'supplier/orders',
        name: 'SupplierOrders',
        component: () => import('@/views/supplier/SupplierOrders.vue'),
        meta: { title: '我的订单', icon: 'List', roles: ['campus_supplier'] },
      },
      // 校园合作供应商专属 - 物流-仓储配送管理
      {
        path: 'supplier/logistics',
        name: 'SupplierLogistics',
        component: () => import('@/views/supplier/SupplierLogistics.vue'),
        meta: { title: '物流-仓储配送管理', icon: 'Van', roles: ['campus_supplier'] },
      },
      {
        path: 'user',
        redirect: '/system/users',
        meta: { hideInMenu: true },
      },
      {
        path: 'system/users',
        name: 'SystemUsers',
        component: () => import('@/views/system/SystemUserIndex.vue'),
        meta: { title: '用户管理', icon: 'User', menuGroup: 'system', roles: ['system_admin'] },
      },
      {
        path: 'system/roles',
        name: 'SystemRoles',
        component: () => import('@/views/system/SystemRoleIndex.vue'),
        meta: { title: '角色管理', icon: 'Key', menuGroup: 'system', roles: ['system_admin'] },
      },
      {
        path: 'supplier',
        name: 'SupplierList',
        component: () => import('@/views/supplier/SupplierList.vue'),
        meta: { title: '供应商管理', icon: 'OfficeBuilding', menuGroup: 'system', roles: ['system_admin'] },
      },
      {
        path: 'system/operation-logs',
        name: 'SystemOperationLogs',
        component: () => import('@/views/system/logs/OperationLog.vue'),
        meta: { title: '操作日志', icon: 'Notebook', menuGroup: 'system', roles: ['system_admin'] },
      },
      {
        path: 'system/login-logs',
        name: 'SystemLoginLogs',
        component: () => import('@/views/system/logs/LoginLog.vue'),
        meta: { title: '登录日志', icon: 'Unlock', menuGroup: 'system', roles: ['system_admin'] },
      },
      {
        path: 'system/files',
        name: 'SystemFileCenter',
        component: () => import('@/views/system/file/FileCenter.vue'),
        meta: { title: '文件中心', icon: 'FolderOpened', menuGroup: 'system', roles: ['system_admin'] },
      },
      {
        path: 'system/positions',
        name: 'SystemPositions',
        component: () => import('@/views/system/position/PositionManage.vue'),
        meta: { title: '岗位管理', icon: 'Briefcase', menuGroup: 'system', roles: ['system_admin'] },
      },
      {
        path: 'system/departments',
        name: 'SystemDepartments',
        component: () => import('@/views/system/department/DepartmentManage.vue'),
        meta: { title: '部门管理', icon: 'Share', menuGroup: 'system', roles: ['system_admin'] },
      },
      {
        path: 'audit',
        redirect: '/system/operation-logs?tab=audit',
        meta: { hideInMenu: true },
      },
      // 安全中心入口：主站不再承载旧 IDS 前端，只保留跳转桥接与后端联动
      {
        path: 'security',
        component: () => import('@/views/security/SecurityCenterLayout.vue'),
        redirect: '/security/ids',
        meta: { title: '安全中心', icon: 'Lock', menuGroup: 'security', roles: ['system_admin'] },
        children: [
          {
            path: 'ids',
            name: 'IDSManage',
            component: () => import('@/views/security/SecurityIDS.vue'),
            meta: { title: '安全中心', hideInMenu: true, roles: ['system_admin'] },
          },
          {
            path: 'situation',
            redirect: '/security/ids',
            meta: { hideInMenu: true, roles: ['system_admin'] },
          },
          {
            path: 'sandbox',
            redirect: '/security/ids',
            meta: { hideInMenu: true, roles: ['system_admin'] },
          },
        ],
      },
      {
        path: 'ids',
        redirect: '/security/ids',
        meta: { hideInMenu: true },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/error/NotFound.vue'),
    meta: { public: true },
  },
]

