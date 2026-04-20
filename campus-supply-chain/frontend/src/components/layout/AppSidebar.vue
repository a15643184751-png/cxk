<script setup lang="ts">
import { computed } from 'vue'
import { isNavigationFailure, NavigationFailureType, useRoute, useRouter } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { routes, type RouteMetaRole } from '@/router/routes'
import { useUserStore } from '@/stores/user'
import { useNoticeStore } from '@/stores/notice'
import type { RoleType } from '@/types/role'
import {
  Odometer,
  Box,
  OfficeBuilding,
  ShoppingCart,
  Edit,
  Upload,
  Download,
  Van,
  Connection,
  Warning,
  ChatDotRound,
  User,
  DArrowLeft,
  DArrowRight,
  Close,
  Document,
  List,
  Monitor,
  Location,
  Lock,
  Star,
  Sunny,
  Moon,
  Setting,
  Key,
  DataLine,
  Notebook,
  Unlock,
  FolderOpened,
  Briefcase,
  Share,
  MagicStick,
  Calendar,
  UserFilled,
} from '@element-plus/icons-vue'
import { useUiSettingsStore } from '@/stores/uiSettings'
import { openSettingsBus } from '@/utils/layoutBus'
import { isIdsSecurityCenterPath, openIdsSecurityCenter } from '@/utils/openIdsSecurityCenter'
import { themeAnimation } from '@/utils/themeAnimation'
import UserMenuPopover from './UserMenuPopover.vue'

const props = defineProps<{
  collapsed: boolean
  immersive?: boolean
  mobile?: boolean
  mobileOpen?: boolean
}>()
const emit = defineEmits<{
  (e: 'update:collapsed', v: boolean): void
  (e: 'close-drawer'): void
}>()

function onFooterClick() {
  if (props.mobile) emit('close-drawer')
  else emit('update:collapsed', !props.collapsed)
}

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const noticeStore = useNoticeStore()
const uiSettings = useUiSettingsStore()

function openSettings() {
  openSettingsBus.emit()
}

function onThemeClick(e: MouseEvent) {
  themeAnimation(e)
}

const iconMap: Record<string, object> = {
  Odometer,
  Box,
  Lock,
  OfficeBuilding,
  ShoppingCart,
  Edit,
  Upload,
  Download,
  Van,
  Connection,
  Warning,
  ChatDotRound,
  User,
  Document,
  List,
  Monitor,
  Location,
  Star,
  Key,
  DataLine,
  Notebook,
  Unlock,
  FolderOpened,
  Briefcase,
  Share,
  MagicStick,
  Calendar,
  UserFilled,
}

const userRole = computed(() => userStore.userInfo?.role as RoleType | undefined)

const menuItems = computed(() => {
  const children = routes.find((r) => r.path === '/')?.children || []
  return children.filter((r) => !r.meta?.hideInMenu && !r.meta?.public)
})

function canAccess(item: (typeof menuItems.value)[0]): boolean {
  const roles = (item.meta as RouteMetaRole)?.roles
  if (!roles?.length) return true
  return userRole.value ? roles.includes(userRole.value) : false
}

const teacherItems = computed(() =>
  menuItems.value.filter((r) => r.meta?.menuGroup === 'teacher' && canAccess(r))
)

/** 教师端侧栏顺序：工作台 → 采购申请 → 溯源 → 日程 → 个人中心 */
const TEACHER_NAV_PATHS = ['/teacher/workbench', '/purchase/apply', '/trace', '/teacher/schedule', '/teacher/personal']

const teacherNavDisplay = computed(() => {
  if (userRole.value !== 'counselor_teacher') return teacherItems.value
  return TEACHER_NAV_PATHS.map((path) =>
    menuItems.value.find((r) => normalizePath(r.path as string) === path)
  ).filter((x): x is (typeof menuItems.value)[0] => !!x)
})
const dashboardItems = computed(() =>
  menuItems.value.filter((r) => r.meta?.menuGroup === 'dashboard' && canAccess(r))
)
const stockItems = computed(() =>
  menuItems.value.filter((r) => r.meta?.menuGroup === 'stock' && canAccess(r))
)
const securityItems = computed(() =>
  menuItems.value.filter((r) => r.meta?.menuGroup === 'security' && canAccess(r))
)
const systemItems = computed(() =>
  menuItems.value.filter((r) => r.meta?.menuGroup === 'system' && canAccess(r))
)
function hideFromTeacherMenu(item: (typeof menuItems.value)[0]): boolean {
  if (userRole.value !== 'counselor_teacher') return false
  const p = normalizePath(item.path as string)
  if (p === '/ai/chat') return true
  if (p === '/purchase/apply' || p === '/trace') return true
  return false
}

const otherItems = computed(() =>
  menuItems.value.filter(
    (r) =>
      r.meta?.menuGroup !== 'dashboard' &&
      r.meta?.menuGroup !== 'stock' &&
      r.meta?.menuGroup !== 'security' &&
      r.meta?.menuGroup !== 'system' &&
      r.meta?.menuGroup !== 'teacher' &&
      canAccess(r) &&
      !hideFromTeacherMenu(r)
  )
)

function isActive(path: string) {
  const normalizedPath = normalizePath(path)
  if (normalizedPath === '/dashboard') {
    return route.path === '/dashboard' || route.path === '/dashboard/'
  }
  if (normalizedPath === '/dashboard/analysis') {
    return route.path === '/dashboard/analysis' || route.path.startsWith('/dashboard/analysis/')
  }
  return route.path === normalizedPath || route.path.startsWith(normalizedPath + '/')
}

function navigate(target: RouteRecordRaw | string) {
  const normalizedPath =
    typeof target === 'string'
      ? normalizePath(target)
      : normalizePath((target.path as string) || '')

  if (isIdsSecurityCenterPath(normalizedPath)) {
    if (props.mobile) emit('close-drawer')
    void openIdsSecurityCenter()
    return
  }

  const loc =
    typeof target === 'string'
      ? normalizedPath
      : target.name != null
        ? { name: target.name }
        : normalizedPath
  void router.push(loc).catch((failure) => {
    if (isNavigationFailure(failure, NavigationFailureType.duplicated)) return
    throw failure
  })
}

function normalizePath(path: string) {
  if (!path) return '/'
  return path.startsWith('/') ? path : `/${path}`
}

function getIcon(name: string) {
  return iconMap[name] || Box
}

function getBadgeCount(path: string) {
  return noticeStore.getBadgeForPath(normalizePath(path))
}

/** 仓储端：原「全景大屏」路由展示为「仓储大屏」 */
function menuTitle(item: (typeof menuItems.value)[0]): string {
  const p = normalizePath(item.path as string)
  if (p === '/dashboard/analysis' && userRole.value === 'warehouse_procurement') {
    return '仓储大屏'
  }
  return (item.meta?.title as string) || ''
}
</script>

<template>
  <aside
    class="sidebar"
    :class="{
      collapsed: collapsed && !mobile,
      immersive: immersive,
      'sidebar--mobile': mobile,
      'sidebar--mobile-open': mobile && mobileOpen,
      'sidebar--teacher': userRole === 'counselor_teacher',
    }"
  >
    <div class="logo">
      <div class="logo-icon">
        <span class="icon-text">链</span>
      </div>
      <span v-show="!collapsed" class="logo-text">供应链平台</span>
    </div>

    <nav class="nav">
      <div v-if="teacherNavDisplay.length" class="nav-group nav-group--teacher">
        <div class="nav-group-title" :class="{ collapsed }">
          <el-icon><MagicStick /></el-icon>
          <span v-show="!collapsed">教师工作台</span>
        </div>
        <div
          v-for="item in teacherNavDisplay"
          :key="item.path"
          class="nav-item nested"
          :class="{ active: isActive(item.path as string) }"
          @click="navigate(item)"
        >
          <el-badge
            class="nav-icon-badge"
            :is-dot="collapsed && getBadgeCount(item.path as string) > 0"
            :hidden="!(collapsed && getBadgeCount(item.path as string) > 0)"
          >
            <span class="nav-icon-wrap">
              <el-icon class="nav-icon">
                <component :is="getIcon(item.meta?.icon as string)" />
              </el-icon>
            </span>
          </el-badge>
          <el-badge
            :value="getBadgeCount(item.path as string)"
            :hidden="collapsed || getBadgeCount(item.path as string) <= 0"
            type="danger"
          >
            <span v-show="!collapsed" class="nav-label">{{ menuTitle(item) }}</span>
          </el-badge>
        </div>
      </div>

      <div v-if="dashboardItems.length" class="nav-group nav-group--dashboard">
        <div
          v-for="item in dashboardItems"
          :key="item.path"
          class="nav-item"
          :class="{ active: isActive(item.path as string) }"
          @click="navigate(item)"
        >
          <el-badge
            class="nav-icon-badge"
            :is-dot="collapsed && getBadgeCount(item.path as string) > 0"
            :hidden="!(collapsed && getBadgeCount(item.path as string) > 0)"
          >
            <span class="nav-icon-wrap">
              <el-icon class="nav-icon">
                <component :is="getIcon(item.meta?.icon as string)" />
              </el-icon>
            </span>
          </el-badge>
          <el-badge
            :value="getBadgeCount(item.path as string)"
            :hidden="collapsed || getBadgeCount(item.path as string) <= 0"
            type="danger"
          >
            <span v-show="!collapsed" class="nav-label">{{ menuTitle(item) }}</span>
          </el-badge>
        </div>
      </div>

      <template v-for="item in otherItems" :key="item.path">
        <div
          class="nav-item"
          :class="{ active: isActive(item.path as string) }"
          @click="navigate(item)"
        >
          <el-badge
            class="nav-icon-badge"
            :is-dot="collapsed && getBadgeCount(item.path as string) > 0"
            :hidden="!(collapsed && getBadgeCount(item.path as string) > 0)"
          >
            <span class="nav-icon-wrap">
              <el-icon class="nav-icon">
                <component :is="getIcon(item.meta?.icon as string)" />
              </el-icon>
            </span>
          </el-badge>
          <el-badge
            :value="getBadgeCount(item.path as string)"
            :hidden="collapsed || getBadgeCount(item.path as string) <= 0"
            type="danger"
          >
            <span v-show="!collapsed" class="nav-label">{{ menuTitle(item) }}</span>
          </el-badge>
        </div>
      </template>

      <div v-if="systemItems.length" class="nav-group">
        <div class="nav-group-title" :class="{ collapsed }">
          <el-icon><Setting /></el-icon>
          <span v-show="!collapsed">系统管理</span>
        </div>
        <div
          v-for="item in systemItems"
          :key="item.path"
          class="nav-item nested"
          :class="{ active: isActive(item.path as string) }"
          @click="navigate(item)"
        >
          <el-badge
            class="nav-icon-badge"
            :is-dot="collapsed && getBadgeCount(item.path as string) > 0"
            :hidden="!(collapsed && getBadgeCount(item.path as string) > 0)"
          >
            <span class="nav-icon-wrap">
              <el-icon class="nav-icon">
                <component :is="getIcon(item.meta?.icon as string)" />
              </el-icon>
            </span>
          </el-badge>
          <el-badge
            :value="getBadgeCount(item.path as string)"
            :hidden="collapsed || getBadgeCount(item.path as string) <= 0"
            type="danger"
          >
            <span v-show="!collapsed" class="nav-label">{{ menuTitle(item) }}</span>
          </el-badge>
        </div>
      </div>

      <div v-if="stockItems.length" class="nav-group">
        <div class="nav-group-title" :class="{ collapsed }">
          <el-icon><Box /></el-icon>
          <span v-show="!collapsed">仓储管理</span>
        </div>
        <div
          v-for="item in stockItems"
          :key="item.path"
          class="nav-item nested"
          :class="{ active: isActive(item.path as string) }"
          @click="navigate(item)"
        >
          <el-badge
            class="nav-icon-badge"
            :is-dot="collapsed && getBadgeCount(item.path as string) > 0"
            :hidden="!(collapsed && getBadgeCount(item.path as string) > 0)"
          >
            <span class="nav-icon-wrap">
              <el-icon class="nav-icon">
                <component :is="getIcon(item.meta?.icon as string)" />
              </el-icon>
            </span>
          </el-badge>
          <el-badge
            :value="getBadgeCount(item.path as string)"
            :hidden="collapsed || getBadgeCount(item.path as string) <= 0"
            type="danger"
          >
            <span v-show="!collapsed" class="nav-label">{{ menuTitle(item) }}</span>
          </el-badge>
        </div>
      </div>
      <div
        v-if="securityItems.length"
        class="nav-item"
        :class="{ active: route.path.startsWith('/security') }"
        @click="navigate('/security')"
      >
        <span class="nav-icon-wrap">
          <el-icon class="nav-icon"><Lock /></el-icon>
        </span>
        <span v-show="!collapsed" class="nav-label">安全中心</span>
      </div>
    </nav>

    <div class="sidebar-dock">
      <el-tooltip content="明暗主题" placement="right" :disabled="!collapsed && !mobile">
        <div
          class="dock-btn"
          :class="{ immersive }"
          @click="onThemeClick($event)"
        >
          <transition name="theme-ico" mode="out-in">
            <el-icon v-if="uiSettings.isDark" key="sun" :size="20"><Sunny /></el-icon>
            <el-icon v-else key="moon" :size="20"><Moon /></el-icon>
          </transition>
        </div>
      </el-tooltip>
      <el-tooltip content="设置" placement="right" :disabled="!collapsed && !mobile">
        <div class="dock-btn" :class="{ immersive }" @click="openSettings">
          <el-icon :size="20"><Setting /></el-icon>
        </div>
      </el-tooltip>
      <UserMenuPopover
        class="dock-user-wrap"
        :immersive="immersive"
        trigger="click"
        compact
      />
    </div>

    <div class="sidebar-footer">
      <div class="collapse-btn" :title="mobile ? '收起菜单' : collapsed ? '展开侧栏' : '收起侧栏'" @click="onFooterClick">
        <transition name="collapse-ico" mode="out-in">
          <el-icon v-if="mobile" key="m-close" :size="20"><Close /></el-icon>
          <el-icon v-else-if="!collapsed" key="expand" :size="20"><DArrowLeft /></el-icon>
          <el-icon v-else key="collapse" :size="20"><DArrowRight /></el-icon>
        </transition>
      </div>
    </div>
  </aside>
</template>

<style lang="scss" scoped>
.sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: 220px;
  background: var(--bg-elevated);
  border-right: 1px solid var(--border-subtle);
  box-shadow: 1px 0 4px rgba(0, 0, 0, 0.03);
  display: flex;
  flex-direction: column;
  z-index: 100;
  transition:
    width 0.32s cubic-bezier(0.25, 0.1, 0.25, 1),
    transform 0.32s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.32s ease;
  will-change: width, transform;

  &.sidebar--mobile {
    width: min(280px, 86vw);
    transform: translate3d(-104%, 0, 0);
    box-shadow: none;
    border-right: 1px solid var(--border-subtle);

    &.sidebar--mobile-open {
      transform: translate3d(0, 0, 0);
      box-shadow: 8px 0 40px rgba(15, 23, 42, 0.18);
    }
  }

  &.immersive {
    background: linear-gradient(180deg, #1a2456 0%, #16214d 100%);
    border-right: 1px solid rgba(129, 140, 248, 0.24);
    box-shadow: 8px 0 24px rgba(30, 41, 95, 0.28);

    .logo {
      border-bottom-color: rgba(129, 140, 248, 0.2);
    }

    .logo-text {
      color: #eef2ff;
    }

    .nav-item {
      color: rgba(214, 223, 255, 0.82);

      &::before {
        background: #9aa7ff;
        pointer-events: none;
      }

      &:hover {
        background: rgba(129, 140, 248, 0.2);
        color: #c7d2fe;
      }

      &.active {
        background: rgba(129, 140, 248, 0.26);
        color: #f1f5ff;
        box-shadow: none;
      }

      &.active .nav-icon {
        transform: scale(1.02);
        color: #d9e1ff;
      }
    }

    .nav-group-title {
      color: rgba(177, 192, 240, 0.78);
    }

    .sidebar-dock {
      border-top-color: rgba(129, 140, 248, 0.2);
    }

    .sidebar-footer {
      border-top-color: rgba(129, 140, 248, 0.2);
    }

    .collapse-btn {
      color: rgba(200, 210, 248, 0.9);

      &:hover {
        background: rgba(129, 140, 248, 0.18);
        color: #dbe4ff;
      }
    }

    :deep(.el-badge__content) {
      border-color: #1a2456;
    }
  }

  &.collapsed {
    width: 68px;

    .nav-item .nav-label,
    .logo-text {
      opacity: 0;
      max-width: 0;
      margin: 0;
      overflow: hidden;
      pointer-events: none;
    }
  }
}

.logo {
  height: 64px;
  padding: 0 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--border-subtle);

  &:hover .logo-icon {
    transform: scale(1.05);
  }
}

.logo-icon {
  width: 38px;
  height: 38px;
  border-radius: 10px;
  background: var(--gradient-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px rgba(79, 70, 229, 0.25);
  transition: transform var(--transition-fast);
}

.icon-text {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
}

.logo-text {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  max-width: 200px;
  transition:
    opacity 0.26s cubic-bezier(0.25, 0.1, 0.25, 1),
    max-width 0.32s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.nav {
  flex: 1;
  padding: 16px 12px;
  overflow-y: auto;
}

.nav-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 12px;
  cursor: pointer;
  color: var(--text-secondary);
  transition:
    background 0.28s cubic-bezier(0.22, 1, 0.36, 1),
    color 0.28s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.28s ease,
    transform 0.28s cubic-bezier(0.22, 1, 0.36, 1);
  margin-bottom: 4px;

  &::before {
    content: '';
    position: absolute;
    left: 10px;
    top: 50%;
    width: 3px;
    height: 0;
    border-radius: 2px;
    background: var(--primary);
    transform: translateY(-50%) scaleY(0);
    opacity: 0;
    pointer-events: none;
    transition:
      height 0.32s cubic-bezier(0.22, 1, 0.36, 1),
      opacity 0.24s ease,
      transform 0.32s cubic-bezier(0.22, 1, 0.36, 1);
  }

  &.active::before {
    height: 26px;
    opacity: 1;
    transform: translateY(-50%) scaleY(1);
  }

  &:hover {
    background: var(--primary-muted);
    color: var(--primary);
    transform: translateX(3px);
  }

  &.active {
    /* 低饱和底 + 深色字，避免与侧栏紫条/图标融在一起 */
    background: rgba(79, 70, 229, 0.09);
    color: #3730a3;
    font-weight: 600;
    box-shadow: none;
  }

  &.nested {
    padding-left: 44px;
    &::before {
      left: 22px;
    }
  }
}

.nav-icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.nav-item .nav-icon {
  transition:
    transform 0.34s cubic-bezier(0.34, 1.25, 0.64, 1),
    color 0.28s ease;
}

.nav-item.active .nav-icon {
  transform: scale(1.02);
  color: #4338ca;
}

.nav-icon {
  font-size: 20px;
  flex-shrink: 0;
}

.nav-icon-badge {
  display: inline-flex;
}

.nav-label {
  white-space: nowrap;
  max-width: 200px;
  transition:
    opacity 0.26s cubic-bezier(0.25, 0.1, 0.25, 1),
    max-width 0.32s cubic-bezier(0.25, 0.1, 0.25, 1);
}

.nav-group {
  margin-top: 8px;
}

.nav-group-title {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;

  .el-icon {
    font-size: 16px;
  }
}

.sidebar-dock {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 12px 12px 10px;
  border-top: 1px solid var(--border-subtle);
  flex-shrink: 0;
}

.dock-btn {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-muted);
  transition:
    background 0.2s ease,
    color 0.2s ease,
    transform 0.2s ease;
  &:hover {
    background: var(--primary-muted);
    color: var(--primary);
    transform: scale(1.05);
  }
  &.immersive {
    color: rgba(200, 210, 248, 0.88);
    &:hover {
      background: rgba(129, 140, 248, 0.18);
      color: #dbe4ff;
    }
  }
}

.dock-user-wrap {
  display: flex;
  align-items: center;
}

.sidebar-footer {
  padding: 12px 16px 16px;
  border-top: 1px solid var(--border-subtle);
}

.collapse-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text-muted);
  transition: all var(--transition-fast);

  &:hover {
    background: var(--bg-hover);
    color: var(--primary);
  }
}

.theme-ico-enter-active,
.theme-ico-leave-active,
.collapse-ico-enter-active,
.collapse-ico-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.28s cubic-bezier(0.34, 1.25, 0.64, 1);
}

.theme-ico-enter-from,
.collapse-ico-enter-from {
  opacity: 0;
  transform: rotate(-85deg) scale(0.45);
}

.theme-ico-leave-to,
.collapse-ico-leave-to {
  opacity: 0;
  transform: rotate(85deg) scale(0.45);
}

/* 暗色主题：激活项用浅色字，避免紫底吞没图标 */
:global(html.dark) .sidebar .nav-item.active {
  background: rgba(129, 140, 248, 0.14);
  color: #e0e7ff;
  box-shadow: none;
}
:global(html.dark) .sidebar .nav-item.active .nav-icon {
  color: #c7d2fe;
}
</style>
