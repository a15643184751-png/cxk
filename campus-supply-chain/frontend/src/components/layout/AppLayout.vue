<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import { useMediaQuery } from '@vueuse/core'
import { ElNotification, ElMessageBox, ElMessage } from 'element-plus'
import AppSidebar from './AppSidebar.vue'
import AppHeader from './AppHeader.vue'
import GlobalSearchDialog from './GlobalSearchDialog.vue'
import SettingsDrawer from './SettingsDrawer.vue'
import LockScreen from './LockScreen.vue'
import { useUserStore } from '@/stores/user'
import { useNoticeStore } from '@/stores/notice'
import { getAndClearWarningToLogistics, clearWarningToLogistics } from '@/stores/demo'
import { listPurchases } from '@/api/purchase'
import { listSupplierOrders } from '@/api/supplier'
import { listMyPurchases } from '@/api/purchase'

const route = useRoute()
/** 与「一级子路由」同步 key：安全中心子页等只换内层，避免整页异步组件错层 */
function layoutOutletKey(r: RouteLocationNormalizedLoaded) {
  return r.matched[1]?.path ?? r.fullPath
}
const userStore = useUserStore()
const noticeStore = useNoticeStore()
const sidebarCollapsed = ref(false)
const isMobileLayout = useMediaQuery('(max-width: 900px)')
const mobileDrawerOpen = ref(false)

function toggleSidebar() {
  if (isMobileLayout.value) {
    mobileDrawerOpen.value = !mobileDrawerOpen.value
  } else {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }
}

function closeMobileDrawer() {
  mobileDrawerOpen.value = false
}

watch(isMobileLayout, (v) => {
  if (!v) mobileDrawerOpen.value = false
})

watch(
  () => route.fullPath,
  () => {
    if (isMobileLayout.value) mobileDrawerOpen.value = false
  }
)

/** 数据大屏与侧栏、顶栏统一深色指挥台，避免浅色导航压在霓虹内容上 */
const immersiveScreen = computed(() => {
  const p = route.path || ''
  return p.startsWith('/screen/') || p === '/dashboard/analysis'
})

/** 顶栏主标题：有 platformTitle 时展示平台全称（如教师工作台）；仓储端将分析大屏显示为「仓储大屏」 */
const headerTitle = computed(() => {
  const platform = route.meta?.platformTitle as string | undefined
  if (platform) return platform
  const p = route.path || ''
  if (
    (p === '/dashboard/analysis' || p.startsWith('/dashboard/analysis/')) &&
    userStore.userInfo?.role === 'warehouse_procurement'
  ) {
    return '仓储大屏'
  }
  return (route.meta?.title as string) || ''
})
const teacherWorkbenchLayout = computed(() => (route.path || '').startsWith('/teacher/workbench'))
const teacherSidebarCompact = computed(() => userStore.userInfo?.role === 'counselor_teacher')
const role = computed(() => userStore.userInfo?.role as string)

let pollingTimer: number | null = null
const prevCounts: Record<string, number> = {}
let voiceHotkeyHandler: ((e: KeyboardEvent) => void) | null = null
let hotkeyAudio: HTMLAudioElement | null = null

const POLL_INTERVAL = 25000

function notifyIfIncreased(key: string, count: number, title: string, message: string, type: 'warning' | 'info' | 'success' = 'warning') {
  const prev = prevCounts[key] ?? 0
  prevCounts[key] = count
  if (count > 0 && count > prev) {
    ElNotification({ title, message, type, duration: 5000 })
  }
}

function markSeen(key: string) {
  prevCounts[key] = 0
}

async function refreshPurchaseReminder(options?: { silent?: boolean }) {
  if (role.value !== 'logistics_admin') {
    noticeStore.clearNewPurchaseCount()
    return
  }
  try {
    const res: any = await listPurchases({ status: 'pending' })
    const data = Array.isArray(res) ? res : res?.data ?? []
    const list = data.filter((x: any) => x?.status === 'pending')
    const count = list.length
    noticeStore.setNewPurchaseCount(count)
    if (!options?.silent) notifyIfIncreased('purchase', count, '新申请提醒', `收到 ${count} 条新的待审批申请，请及时处理。`)
  } catch {
    noticeStore.clearNewPurchaseCount()
  }
}

async function refreshSupplierOrderReminder(options?: { silent?: boolean }) {
  if (role.value !== 'campus_supplier') {
    noticeStore.clearSupplierOrderCount()
    return
  }
  try {
    const res: any = await listSupplierOrders()
    const data = Array.isArray(res) ? res : res?.data ?? []
    const list = data.filter((x: any) => x?.status === 'approved' || x?.status === 'confirmed')
    const count = list.length
    noticeStore.setSupplierOrderCount(count)
    if (!options?.silent) notifyIfIncreased('supplier', count, '待办提醒', `有 ${count} 条待办订单（待接单/待发货），请及时处理。`)
  } catch {
    noticeStore.clearSupplierOrderCount()
  }
}

async function refreshWarehouseReminder(options?: { silent?: boolean }) {
  if (role.value !== 'warehouse_procurement') {
    noticeStore.clearWarehouseCounts()
    return
  }
  try {
    const [inRes, outRes]: any[] = await Promise.all([
      listPurchases(),
      listPurchases({ status: 'stocked_in' }),
    ])
    const inList = Array.isArray(inRes) ? inRes : inRes?.data ?? []
    const outList = Array.isArray(outRes) ? outRes : outRes?.data ?? []
    const inCount = inList.filter(
      (x: any) => (x?.status === 'approved' && !x?.supplier_id) || x?.status === 'shipped'
    ).length
    const outCount = outList.filter((x: any) => x?.status === 'stocked_in').length
    noticeStore.setWarehouseStockInCount(inCount)
    noticeStore.setWarehouseStockOutCount(outCount)
    const total = inCount + outCount
    if (!options?.silent && total > 0) {
      const prev = (prevCounts['warehouse_in'] ?? 0) + (prevCounts['warehouse_out'] ?? 0)
      prevCounts['warehouse_in'] = inCount
      prevCounts['warehouse_out'] = outCount
      if (total > prev) {
        const parts: string[] = []
        if (inCount) parts.push(`${inCount} 条待入库`)
        if (outCount) parts.push(`${outCount} 条待出库`)
        ElNotification({ title: '仓储待办提醒', message: parts.join('，') + '，请及时处理。', type: 'warning', duration: 5000 })
      }
    }
  } catch {
    noticeStore.clearWarehouseCounts()
  }
}

async function refreshDeliveryToCreateReminder(options?: { silent?: boolean }) {
  if (role.value !== 'logistics_admin' && role.value !== 'warehouse_procurement') {
    noticeStore.clearDeliveryToCreateCount()
    return
  }
  try {
    const res: any = await listPurchases({ status: 'stocked_out' })
    const data = Array.isArray(res) ? res : res?.data ?? []
    const list = data.filter((x: any) => x?.status === 'stocked_out')
    const count = list.length
    noticeStore.setDeliveryToCreateCount(count)
    if (!options?.silent) notifyIfIncreased('delivery', count, '待创建配送提醒', `有 ${count} 条出库单待创建配送，请及时处理。`)
  } catch {
    noticeStore.clearDeliveryToCreateCount()
  }
}

async function refreshTeacherReceiveReminder(options?: { silent?: boolean }) {
  if (role.value !== 'counselor_teacher') {
    noticeStore.clearTeacherReceiveCount()
    return
  }
  try {
    const res: any = await listMyPurchases()
    const data = Array.isArray(res) ? res : res?.data ?? []
    const list = data.filter((x: any) => x?.can_confirm_receive === true)
    const count = list.length
    noticeStore.setTeacherReceiveCount(count)
    if (!options?.silent) notifyIfIncreased('teacher', count, '待签收提醒', `有 ${count} 个配送已到达，请及时确认收货。`, 'info')
  } catch {
    noticeStore.clearTeacherReceiveCount()
  }
}

async function refreshAll(options?: { silent?: boolean }) {
  await Promise.all([
    refreshPurchaseReminder(options),
    refreshSupplierOrderReminder(options),
    refreshWarehouseReminder(options),
    refreshDeliveryToCreateReminder(options),
    refreshTeacherReceiveReminder(options),
  ])
}

async function markCurrentAsSeen() {
  const path = route.path
  if (path.startsWith('/purchase') && role.value === 'logistics_admin') {
    markSeen('purchase')
    noticeStore.clearNewPurchaseCount()
  }
  if (path.startsWith('/supplier/orders') && role.value === 'campus_supplier') {
    markSeen('supplier')
    noticeStore.clearSupplierOrderCount()
  }
  if ((path.startsWith('/stock/in') || path.startsWith('/stock/out')) && role.value === 'warehouse_procurement') {
    markSeen('warehouse_in')
    markSeen('warehouse_out')
    noticeStore.clearWarehouseCounts()
  }
  if (path.startsWith('/delivery') && (role.value === 'logistics_admin' || role.value === 'warehouse_procurement')) {
    markSeen('delivery')
    noticeStore.clearDeliveryToCreateCount()
  }
  if (
    (path.startsWith('/my-applications') || path.startsWith('/teacher/personal')) &&
    role.value === 'counselor_teacher'
  ) {
    markSeen('teacher')
    noticeStore.clearTeacherReceiveCount()
  }
}

function startPolling() {
  if (pollingTimer) clearInterval(pollingTimer)
  pollingTimer = window.setInterval(() => refreshAll(), POLL_INTERVAL)
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

function showLogisticsWarning(warn: { subject: string; body: string }) {
  ElMessageBox.alert(
    `【审计警告】\n\n${warn.subject}\n\n${warn.body}`,
    '管理员已向您发起警告',
    { type: 'warning', confirmButtonText: '已知晓' }
  )
}

function initLogisticsWarningCheck() {
  if (role.value !== 'logistics_admin') return
  const warn = getAndClearWarningToLogistics()
  if (warn) showLogisticsWarning(warn)
  const handler = (e: CustomEvent) => {
    showLogisticsWarning(e.detail)
    clearWarningToLogistics()
  }
  window.addEventListener('demo-logistics-warning', handler as EventListener)
  onBeforeUnmount(() => {
    window.removeEventListener('demo-logistics-warning', handler as EventListener)
  })
}

function syncImmersiveBodyClass(on: boolean) {
  if (typeof document === 'undefined') return
  document.body.classList.toggle('layout-immersive', on)
}

function canPlayTeacherHotkey(): boolean {
  return role.value === 'counselor_teacher' && (route.path || '').startsWith('/teacher/')
}

function canPlayLogisticsHotkey(): boolean {
  return (
    (role.value === 'logistics_admin' || role.value === 'warehouse_procurement') &&
    (route.path || '').startsWith('/')
  )
}

function playVoiceHotkey(fileName: string) {
  if (!hotkeyAudio) hotkeyAudio = new Audio()
  hotkeyAudio.pause()
  hotkeyAudio.src = `/api/voice/${encodeURIComponent(fileName)}`
  hotkeyAudio.currentTime = 0
  void hotkeyAudio.play().catch(() => {
    ElMessage.warning(`语音播放失败：${fileName}`)
  })
}

function notifyNewMaterialApproval() {
  ElNotification({
    title: '审批提醒',
    message: '你有一个新的物资申请，请及时审批。',
    type: 'warning',
    position: 'top-right',
    duration: 4500,
  })
}

function initVoiceHotkeys() {
  if (voiceHotkeyHandler) window.removeEventListener('keydown', voiceHotkeyHandler)
  voiceHotkeyHandler = (e: KeyboardEvent) => {
    if (e.repeat) return
    if (e.key === 'F2' && canPlayTeacherHotkey()) {
      e.preventDefault()
      playVoiceHotkey('采购信息提交语音.mp3')
      return
    }
    if (e.key === 'F3' && canPlayTeacherHotkey()) {
      e.preventDefault()
      playVoiceHotkey('采购信息判定异常语音.mp3')
      return
    }
    if (e.key === 'F4' && canPlayLogisticsHotkey()) {
      e.preventDefault()
      playVoiceHotkey('采购待审批语音.mp3')
      if (role.value === 'logistics_admin') notifyNewMaterialApproval()
    }
  }
  window.addEventListener('keydown', voiceHotkeyHandler)
}

watch(
  immersiveScreen,
  (v) => {
    syncImmersiveBodyClass(v)
  },
  { immediate: true }
)

onMounted(async () => {
  await refreshAll({ silent: true })
  await markCurrentAsSeen()
  startPolling()
  initLogisticsWarningCheck()
  initVoiceHotkeys()
})

watch(
  () => route.path,
  async () => {
    await markCurrentAsSeen()
  }
)

watch(
  () => userStore.userInfo?.id,
  async () => {
    await refreshAll({ silent: true })
    startPolling()
  }
)

onBeforeUnmount(() => {
  stopPolling()
  syncImmersiveBodyClass(false)
  if (voiceHotkeyHandler) {
    window.removeEventListener('keydown', voiceHotkeyHandler)
    voiceHotkeyHandler = null
  }
  if (hotkeyAudio) {
    hotkeyAudio.pause()
    hotkeyAudio = null
  }
})
</script>

<template>
  <div
    class="app-layout"
    :class="{
      'app-layout--immersive': immersiveScreen,
      'app-layout--mobile': isMobileLayout,
      'app-layout--teacher-sidebar': teacherSidebarCompact,
    }"
  >
    <Transition name="fade">
      <div
        v-if="isMobileLayout && mobileDrawerOpen"
        class="sidebar-backdrop"
        aria-hidden="true"
        @click="closeMobileDrawer"
      />
    </Transition>
    <AppSidebar
      v-model:collapsed="sidebarCollapsed"
      :immersive="immersiveScreen"
      :mobile="isMobileLayout"
      :mobile-open="mobileDrawerOpen"
      @close-drawer="closeMobileDrawer"
    />
    <div
      class="main-wrapper"
      :class="{
        'sidebar-collapsed': sidebarCollapsed && !isMobileLayout,
        'main-wrapper--immersive': immersiveScreen,
        'main-wrapper--mobile': isMobileLayout,
      }"
    >
      <AppHeader
        :title="headerTitle"
        :sidebar-expanded="isMobileLayout ? mobileDrawerOpen : !sidebarCollapsed"
        :immersive="immersiveScreen"
        :platform-brand="!!route.meta?.platformTitle"
        @toggle="toggleSidebar"
      />
      <main
        class="main-content"
        :class="{
          'main-content--immersive': immersiveScreen,
          'main-content--teacher-wb': teacherWorkbenchLayout,
        }"
      >
        <div class="router-outlet">
          <router-view v-slot="{ Component, route: r }">
            <!-- 不用带位移的 page 过渡：离开节点仍占位时，新页面会被排到视口下方，出现「URL/标题已变但内容仍是上一页」 -->
            <component v-if="Component" :is="Component" :key="layoutOutletKey(r)" />
          </router-view>
        </div>
      </main>
    </div>

    <GlobalSearchDialog />
    <SettingsDrawer />
    <LockScreen />
  </div>
</template>

<style lang="scss" scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background: var(--bg-base);
}

.sidebar-backdrop {
  position: fixed;
  inset: 0;
  z-index: 90;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(2px);
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.28s cubic-bezier(0.25, 0.1, 0.25, 1);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.main-wrapper {
  flex: 1;
  margin-left: 220px;
  transition: margin-left 0.32s cubic-bezier(0.25, 0.1, 0.25, 1);
  display: flex;
  flex-direction: column;
  min-width: 0;

  &.sidebar-collapsed {
    margin-left: 68px;
  }

  &.main-wrapper--mobile {
    margin-left: 0;
  }
}

.main-content {
  flex: 1;
  padding: 24px;
  overflow-y: auto;
  min-height: 0;
}

.router-outlet {
  min-height: 0;
}

.main-content--teacher-wb {
  padding: 0;
  display: flex;
  flex-direction: column;
  min-height: 0;
  /* 工作台内部自管滚动（对话区 + 沉底输入栏），避免整页滚动破坏 Gemini 式布局 */
  overflow: hidden;
}
.main-content--teacher-wb .router-outlet {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.app-layout--teacher-sidebar :deep(.sidebar:not(.sidebar--mobile)) {
  width: 200px;
}
.app-layout--teacher-sidebar .main-wrapper:not(.main-wrapper--mobile) {
  margin-left: 200px;
}
.app-layout--teacher-sidebar .main-wrapper.sidebar-collapsed:not(.main-wrapper--mobile) {
  margin-left: 68px;
}

.app-layout--immersive {
  background: var(--screen-bg-mid);
}

.main-wrapper--immersive {
  background: transparent;
}

.main-content--immersive {
  padding: 0;
  overflow-x: hidden;
  overflow-y: auto;
  background: transparent;
}

</style>
