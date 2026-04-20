<script setup lang="ts">
import { computed, nextTick, reactive, ref, onMounted, watch, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'
import { useUserStore } from '@/stores/user'
import {
  listIDSEvents,
  getIDSStats,
  getIDSTrend,
  archiveIDSEvent,
  archiveIDSBatch,
  analyzeIDSEventAI,
  updateIDSEventStatus,
  blockIDSEventIp,
  unblockIDSEventIp,
  getIDSEvent,
  getIDSEventReport,
  getIDSEventInsight,
  getIDSHeatboard,
  getIDSNotificationSettings,
  updateIDSNotificationSettings,
  testIDSNotifications,
  listIDSSources,
  createIDSSource,
  updateIDSSource,
  syncIDSSource,
  previewIDSSourcePackage,
  activateIDSSourcePackage,
  listIDSSourcePackages,
} from '@/api/ids'
import type {
  IDSEventItem,
  IDSEventReport,
  IDSStatsResponse,
  IDSSourceItem,
  IDSSourcePackageActivationItem,
  IDSSourcePackageHistoryItem,
  IDSSourceListResponse,
  IDSSourcePackageIntakeItem,
  IDSSourceRegistryPayload,
  IDSMatchedHit,
  IDSRequestPacket,
  IDSDecisionBasis,
  IDSAIStatus,
  IDSUploadTrace,
  IDSSourcePackagePreviewPayload,
  IDSSourcePackagePreviewResponse,
  IDSEventInsightResponse,
  IDSAttackHeatboardResponse,
  IDSNotificationSettings,
} from '@/api/ids'
import type { IDSAlertSoundAssetInfo, IDSAlertSoundSettings, IDSFocusEventDetail } from '@/utils/idsAdminAlert'
import {
  IDS_ALERT_FOCUS_EVENT,
  IDS_ALERT_SOUND_SETTINGS_UPDATED_EVENT,
  clearIdsAlertCustomSound,
  getIdsAlertCustomSoundInfo,
  playIdsAlertSound,
  primeIdsAlertSound,
  readIdsAlertSoundSettings,
  saveIdsAlertCustomSound,
  startIdsAlertAlarm,
  stopIdsAlertAlarm,
  writeIdsAlertSoundSettings,
} from '@/utils/idsAdminAlert'

type SourceFormState = IDSSourceRegistryPayload
type PackagePreviewFormState = IDSSourcePackagePreviewPayload
type PackageActivationFormState = { package_intake_id: number; triggered_by: string; activation_note: string }

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const loading = ref(false)
const trendDays = ref(7)
const trendData = ref<{ dates: string[]; counts: number[] }>({ dates: [], counts: [] })
const stats = ref<IDSStatsResponse | null>(null)
const tableData = ref<IDSEventItem[]>([])
const total = ref(0)
const attackTypeFilter = ref('')
const clientIpFilter = ref('')
const blockedFilter = ref<number | undefined>(undefined)
const archivedFilter = ref<number | undefined>(undefined)
const statusFilter = ref<string>('')
const eventOriginFilter = ref<string>('real')
const sourceClassificationFilter = ref<string>('')
const minScoreFilter = ref<number | undefined>(undefined)
const pageSize = ref(20)
const pageOffset = ref(0)
const selectedIds = ref<number[]>([])
const sourceLoading = ref(false)
const sourceSaving = ref(false)
const sourceDialogVisible = ref(false)
const sourceSyncingId = ref<number | null>(null)
const editingSourceId = ref<number | null>(null)
const packagePreviewing = ref(false)
const packagePreviewDialogVisible = ref(false)
const packageActivationDialogVisible = ref(false)
const packageHistoryDialogVisible = ref(false)
const packageActivating = ref(false)
const packageActivatingSourceId = ref<number | null>(null)
const packageActivationTarget = ref<{
  sourceId: number
  sourceKey: string
  displayName: string
  intake: IDSSourcePackageIntakeItem
} | null>(null)
const packageHistoryLoading = ref(false)
const packageHistory = ref<IDSSourcePackageHistoryItem | null>(null)
const packageHistorySource = ref<IDSSourceItem | null>(null)
const latestPackagePreviewResult = ref<IDSSourcePackagePreviewResponse | null>(null)
const sourceRows = ref<IDSSourceItem[]>([])
const sourceSummary = ref<IDSSourceListResponse['summary']>({
  total: 0,
  healthy_count: 0,
  degraded_count: 0,
  trusted_count: 0,
  demo_test_count: 0,
})
const detailVisible = ref(false)
const currentRow = ref<IDSEventItem | null>(null)
const currentInsight = ref<IDSEventInsightResponse | null>(null)
const insightLoading = ref(false)
const aiAnalyzingId = ref<number | null>(null)
const analysisWorkbenchVisible = ref(false)
const analysisWorkbenchLoading = ref(false)
const reportVisible = ref(false)
const reportLoading = ref(false)
const reportMarkdown = ref('')
const reportData = ref<IDSEventReport | null>(null)
const heatboardLoading = ref(false)
const heatboard = ref<IDSAttackHeatboardResponse | null>(null)
const notificationDialogVisible = ref(false)
const notificationSaving = ref(false)
const notificationTesting = ref(false)
const reportOrderNo = ref('')
const reportMeta = ref<{ reportNo: string; generatedAt: string; title: string; headerSuffix: string }>({
  reportNo: '',
  generatedAt: '',
  title: 'IDS 安全运营中心',
  headerSuffix: '安全事件分析报告',
})
const reportContainerRef = ref<HTMLElement | null>(null)
const aiProcessVisible = ref(false)
const aiProcessText = ref('AI 研判任务已提交，正在等待模型返回分析结果...')
const aiProcessMode = ref<'analysis'>('analysis')
const aiProcessFeed = ref<string[]>([])
const notificationSettings = reactive<IDSNotificationSettings>({
  email: {
    enabled: false,
    smtp_host: '',
    smtp_port: 465,
    username: '',
    password: '',
    password_configured: false,
    from_addr: '',
    to_addrs: '',
    use_tls: false,
    use_ssl: true,
  },
  wecom: {
    enabled: false,
    webhook_url: '',
  },
  webhook: {
    enabled: false,
    url: '',
    secret: '',
    secret_configured: false,
  },
})
const isSystemAdmin = computed(() => userStore.userInfo?.role === 'ids_admin')
const warningAudioInputRef = ref<HTMLInputElement | null>(null)
const idsAlertSoundCardRef = ref<HTMLElement | null>(null)
const idsAlertSoundSettings = reactive<IDSAlertSoundSettings>(readIdsAlertSoundSettings())
const idsAlertCustomSoundInfo = ref<IDSAlertSoundAssetInfo | null>(null)
const IDS_ALERT_POLL_INTERVAL = 10000
const IDS_ALERT_MIN_SCORE = 80
const IDS_ALERT_FETCH_LIMIT = 20
const IDS_ALERT_STATE_KEY = 'ids-standalone-high-risk-alert-v1'
const idsRiskAlertVisible = ref(false)
const idsRiskAlertCurrent = ref<IDSEventItem | null>(null)
const idsRiskAlertQueue = ref<IDSEventItem[]>([])

const idsHudClock = ref('')
let idsHudClockTimer: ReturnType<typeof setInterval> | null = null
let idsAlertPollingTimer: ReturnType<typeof setInterval> | null = null
let idsRiskAlertPendingFocusEventId: number | null = null
const IDS_DESKTOP_NOTIFICATION_KEY = 'ids-desktop-notification-v1'
const browserNotificationPermission = ref(
  typeof Notification === 'undefined' ? 'unsupported' : Notification.permission,
)
const browserNotificationEnabled = ref(readBrowserNotificationEnabled())
function tickIdsHudClock() {
  idsHudClock.value = new Date().toLocaleString('zh-CN', { hour12: false })
}

type IDSAlertState = {
  muted_date: string | null
  watermark_event_id: number
  watermark_created_at: string | null
}

type TableClusterSummary = {
  key: string
  attack_type_label: string
  path: string
  count: number
  first_event_id: number
}

function readBrowserNotificationEnabled() {
  if (typeof window === 'undefined') return true
  return localStorage.getItem(IDS_DESKTOP_NOTIFICATION_KEY) !== '0'
}

function writeBrowserNotificationEnabled(enabled: boolean) {
  browserNotificationEnabled.value = enabled
  if (typeof window === 'undefined') return
  localStorage.setItem(IDS_DESKTOP_NOTIFICATION_KEY, enabled ? '1' : '0')
}

function normalizeIdsPath(path?: string | null) {
  const raw = String(path || '').trim().split('?')[0] || '/'
  const noTrailing = raw.replace(/\/+$/, '') || '/'
  return noTrailing
    .replace(/\/\d+/g, '/:id')
    .replace(/\/[0-9a-f]{8,}/gi, '/:token')
}

const IDS_ATTACK_TYPE_LABELS_ZH: Record<string, string> = {
  sql_injection: 'SQL 注入',
  xss: 'XSS',
  xxe: 'XXE',
  xml_external_entity: 'XXE',
  path_traversal: '路径穿越',
  cmd_injection: '命令注入',
  command_injection: '命令注入',
  scanner: '扫描探测',
  malformed: '异常请求',
  malformed_request: '异常请求',
  jndi_injection: 'JNDI 注入',
  prototype_pollution: '原型污染',
  malware: '恶意文件上传',
  malware_upload: '恶意文件上传',
  recon_finding: '扫描探测',
  recon_port_exposure: '扫描探测',
  recon_nday_candidate: '扫描探测',
  recon_security_header_gap: '扫描探测',
  recon_js_secret_hint: '扫描探测',
  recon_login_surface: '扫描探测',
  recon_sensitive_function: '扫描探测',
  demo_attack_detected: '扫描探测',
  demo_defense_effective: '安全处置',
  suspicious_attack_activity: '扫描探测',
  protective_containment_action: '安全处置',
  unknown: '未知类型',
}

const IDS_GEO_LABELS_ZH: Record<string, string> = {
  China: '中国',
  Changchun: '长春',
  'United States': '美国',
  'New York': '纽约',
  'Los Angeles': '洛杉矶',
  Japan: '日本',
  Tokyo: '东京',
  Germany: '德国',
  Berlin: '柏林',
  Singapore: '新加坡',
}

const IDS_UA_LABELS_ZH: Record<string, string> = {
  Chrome: 'Chrome 浏览器',
  Edge: 'Edge 浏览器',
  Firefox: 'Firefox 浏览器',
  Safari: 'Safari 浏览器',
  Postman: 'Postman',
  'Python Client': 'Python 客户端',
  curl: 'curl',
  Unknown: '未知终端',
}

const IDS_EVENT_STATUS_LABELS_ZH: Record<string, string> = {
  new: '新告警',
  investigating: '调查中',
  mitigated: '已处置',
  false_positive: '误报',
  closed: '已关闭',
}

const IDS_FALSE_POSITIVE_SIGNAL_LABELS_ZH: Record<string, string> = {
  signature: '命中特征',
  path_prefix: '路径特征',
  rule: '命中规则',
  memory: '历史学习',
}

const IDS_FALSE_POSITIVE_SOURCE_LABELS_ZH: Record<string, string> = {
  history: '历史事件',
  memory: '学习记忆',
}

const IDS_BROWSER_PERMISSION_LABELS_ZH: Record<string, string> = {
  granted: '已授权',
  denied: '已拒绝',
  default: '未选择',
  unsupported: '不支持',
}

function localizeAttackTypeLabel(label?: string | null, raw?: string | null) {
  const candidates = [label, raw]
  for (const candidate of candidates) {
    const normalized = String(candidate || '').trim()
    if (!normalized) continue
    if (/[\u4e00-\u9fa5]/.test(normalized)) return normalized
    const key = normalized.toLowerCase().replace(/[\s-]+/g, '_')
    if (IDS_ATTACK_TYPE_LABELS_ZH[key]) return IDS_ATTACK_TYPE_LABELS_ZH[key]
  }
  return String(label || raw || '未知类型').trim() || '未知类型'
}

function localizeGeoLabel(value?: string | null) {
  const normalized = String(value || '').trim()
  if (!normalized) return '-'
  return IDS_GEO_LABELS_ZH[normalized] || normalized
}

function localizeUaFamily(value?: string | null) {
  const normalized = String(value || '').trim()
  if (!normalized) return '-'
  return IDS_UA_LABELS_ZH[normalized] || normalized
}

function eventStatusLabel(value?: string | null) {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return '新告警'
  return IDS_EVENT_STATUS_LABELS_ZH[normalized] || normalized
}

function falsePositiveSignalKindLabel(value?: string | null) {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return '学习信号'
  return IDS_FALSE_POSITIVE_SIGNAL_LABELS_ZH[normalized] || normalized
}

function falsePositiveSignalSourceLabel(value?: string | null) {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return '学习来源'
  return IDS_FALSE_POSITIVE_SOURCE_LABELS_ZH[normalized] || normalized
}

function browserPermissionLabel(value?: string | null) {
  const normalized = String(value || '').trim().toLowerCase()
  if (!normalized) return '未选择'
  return IDS_BROWSER_PERMISSION_LABELS_ZH[normalized] || normalized
}

function clusterSummaryLabel() {
  const cluster = currentInsight.value?.cluster
  const row = currentRow.value
  if (!cluster) return '暂无聚类摘要'
  const attackLabel = localizeAttackTypeLabel(row?.attack_type_label, row?.attack_type)
  const focusPath = normalizeIdsPath(row?.path || cluster.recent_items?.[0]?.path || '/')
  if (!cluster.total) return `${attackLabel} 暂无明显同类聚集`
  return `${attackLabel} 近期有 ${cluster.total} 条相似事件集中出现在 ${focusPath}`
}

function formatProfileTopPaths(items?: Array<{ path: string; count: number }> | null) {
  if (!Array.isArray(items) || !items.length) return '-'
  return items.map((item) => `${item.path}（${item.count}）`).join(' / ')
}

function formatProfileBehaviors(items?: Array<{ label: string; count: number }> | null) {
  if (!Array.isArray(items) || !items.length) return '-'
  return items.map((item) => `${localizeAttackTypeLabel(item.label)}（${item.count}）`).join(' / ')
}

const tableClusters = computed<TableClusterSummary[]>(() => {
  const clusters = new Map<string, TableClusterSummary>()
  for (const row of tableData.value) {
    const key = `${row.attack_type}|${normalizeIdsPath(row.path)}|${row.signature_matched || '-'}`
    const existing = clusters.get(key)
    if (existing) {
      existing.count += 1
      continue
    }
    clusters.set(key, {
      key,
      attack_type_label: localizeAttackTypeLabel(row.attack_type_label, row.attack_type),
      path: normalizeIdsPath(row.path),
      count: 1,
      first_event_id: row.id,
    })
  }
  return Array.from(clusters.values())
    .sort((left, right) => right.count - left.count)
    .slice(0, 6)
})

const heatboardPeak = computed(() => {
  const hourly = heatboard.value?.hourly || []
  return hourly.reduce((peak, item) => Math.max(peak, Number(item.total || 0), Number(item.high_risk || 0)), 1)
})

const heatboardBusyHours = computed(() =>
  (heatboard.value?.hourly || [])
    .filter((item) => Number(item.total || 0) > 0 || Number(item.high_risk || 0) > 0)
    .sort((left, right) => Number(right.total || 0) - Number(left.total || 0) || Number(right.high_risk || 0) - Number(left.high_risk || 0))
    .slice(0, 4),
)

function heatboardBarHeight(cell: { total: number; high_risk: number }) {
  const peak = Math.max(heatboardPeak.value, 1)
  const ratio = Math.max(Number(cell.total || 0), Number(cell.high_risk || 0)) / peak
  return `${Math.max(10, Math.round(ratio * 100))}%`
}

function heatboardBarClass(cell: { total: number; high_risk: number }) {
  if (Number(cell.high_risk || 0) > 0) return 'danger'
  if (Number(cell.total || 0) > 0) return 'active'
  return 'idle'
}

function heatboardHourSummary(cell: { hour: string; total: number; high_risk: number }) {
  return `${cell.hour}:00 · 攻击 ${cell.total} 次 · 高危 ${cell.high_risk} 次`
}

function currentDateKey() {
  const now = new Date()
  const y = now.getFullYear()
  const m = `${now.getMonth() + 1}`.padStart(2, '0')
  const d = `${now.getDate()}`.padStart(2, '0')
  return `${y}-${m}-${d}`
}

function defaultIdsAlertState(): IDSAlertState {
  return {
    muted_date: null,
    watermark_event_id: 0,
    watermark_created_at: null,
  }
}

function readIdsAlertState(): IDSAlertState {
  try {
    const raw = localStorage.getItem(IDS_ALERT_STATE_KEY)
    if (!raw) return defaultIdsAlertState()
    const parsed = JSON.parse(raw) as
      | (Partial<IDSAlertState> & {
          date?: string
          muted_for_today?: boolean
          seen_event_ids?: unknown[]
        })
      | null
    const legacySeenIds = Array.isArray(parsed?.seen_event_ids)
      ? parsed.seen_event_ids
          .map((item) => Number(item))
          .filter((item) => Number.isFinite(item) && item > 0)
      : []
    const legacyWatermark = legacySeenIds.length ? Math.max(...legacySeenIds) : 0
    const watermarkEventId = Math.max(Number(parsed?.watermark_event_id || 0), legacyWatermark)
    const mutedDate =
      typeof parsed?.muted_date === 'string' && parsed.muted_date === currentDateKey()
        ? parsed.muted_date
        : parsed?.muted_for_today && parsed.date === currentDateKey()
          ? currentDateKey()
          : null
    return {
      muted_date: mutedDate,
      watermark_event_id:
        Number.isFinite(watermarkEventId) && watermarkEventId > 0 ? watermarkEventId : 0,
      watermark_created_at:
        typeof parsed?.watermark_created_at === 'string' && parsed.watermark_created_at.trim()
          ? parsed.watermark_created_at
          : null,
    }
  } catch {
    return defaultIdsAlertState()
  }
}

function writeIdsAlertState(state: IDSAlertState) {
  localStorage.setItem(IDS_ALERT_STATE_KEY, JSON.stringify(state))
}

function isIdsAlertMutedToday() {
  return readIdsAlertState().muted_date === currentDateKey()
}

function eventIdOfIdsAlert(item?: IDSEventItem | null) {
  const eventId = Number(item?.id || 0)
  return Number.isFinite(eventId) && eventId > 0 ? eventId : 0
}

function eventCreatedAtMsOfIdsAlert(item?: IDSEventItem | null) {
  const raw = String(item?.created_at || '').trim()
  if (!raw) return 0
  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T')
  const parsed = Date.parse(normalized)
  return Number.isFinite(parsed) ? parsed : 0
}

function watermarkCreatedAtMs(state: IDSAlertState) {
  const raw = String(state.watermark_created_at || '').trim()
  if (!raw) return 0
  const normalized = raw.includes('T') ? raw : raw.replace(' ', 'T')
  const parsed = Date.parse(normalized)
  return Number.isFinite(parsed) ? parsed : 0
}

function isIdsAlertNewerThanWatermark(item: IDSEventItem, state: IDSAlertState) {
  const eventId = eventIdOfIdsAlert(item)
  if (!eventId) return false
  const eventCreatedAtMs = eventCreatedAtMsOfIdsAlert(item)
  const currentWatermarkCreatedAtMs = watermarkCreatedAtMs(state)
  if (currentWatermarkCreatedAtMs > 0 && eventCreatedAtMs > 0) {
    if (eventCreatedAtMs > currentWatermarkCreatedAtMs) return true
    if (eventCreatedAtMs < currentWatermarkCreatedAtMs) return false
  }
  return eventId > state.watermark_event_id
}

function advanceIdsAlertWatermark(items: IDSEventItem[]) {
  if (!items.length) return
  const latestItem = [...items].sort((left, right) => {
    const rightCreatedAtMs = eventCreatedAtMsOfIdsAlert(right)
    const leftCreatedAtMs = eventCreatedAtMsOfIdsAlert(left)
    if (rightCreatedAtMs !== leftCreatedAtMs) return rightCreatedAtMs - leftCreatedAtMs
    return eventIdOfIdsAlert(right) - eventIdOfIdsAlert(left)
  })[0]
  const latestEventId = eventIdOfIdsAlert(latestItem)
  if (!latestEventId) return
  const state = readIdsAlertState()
  const latestCreatedAt = String(latestItem?.created_at || '').trim() || null
  if (
    latestCreatedAt &&
    !isIdsAlertNewerThanWatermark(latestItem, state) &&
    latestEventId === state.watermark_event_id &&
    state.watermark_created_at === latestCreatedAt
  ) {
    return
  }
  if (
    latestCreatedAt &&
    (watermarkCreatedAtMs(state) <= eventCreatedAtMsOfIdsAlert(latestItem) ||
      latestEventId > state.watermark_event_id)
  ) {
    state.watermark_event_id = latestEventId
    state.watermark_created_at = latestCreatedAt
    writeIdsAlertState(state)
    return
  }
  if (latestEventId > state.watermark_event_id) {
    state.watermark_event_id = latestEventId
    writeIdsAlertState(state)
  }
}

function muteIdsAlertsForToday() {
  const state = readIdsAlertState()
  state.muted_date = currentDateKey()
  writeIdsAlertState(state)
}

function idsAlertAttackTitle(item?: IDSEventItem | null) {
  if (!item) return '高危安全事件'
  if (item.alert_profile?.category === 'upload') return '高危样本送检预警'
  if (item.path === '/api/upload' || item.path === '/api/ids/detection/sample-submit' || item.upload_trace) return '高危样本送检预警'
  return localizeAttackTypeLabel(item.attack_type_label, item.attack_type)
}

function idsAlertDetector(item?: IDSEventItem | null) {
  return item?.source_rule_name || item?.detector_name || item?.firewall_rule || '-'
}

function idsAlertEvidence(item?: IDSEventItem | null) {
  return (
    item?.alert_profile?.summary ||
    item?.upload_trace?.decision_basis?.hold_reason_summary ||
    item?.response_detail ||
    item?.review_note ||
    item?.ai_analysis ||
    item?.signature_matched ||
    '-'
  )
}

function isEscalatedIdsPopupAlert(item?: IDSEventItem | null) {
  if (!item) return false
  if (item.alert_profile?.channel) return item.alert_profile.channel === 'modal'
  if (item.path === '/api/upload' || item.path === '/api/ids/detection/sample-submit' || item.upload_trace) return true
  return String(item.attack_type || '').trim().toLowerCase() === 'malware'
}

function stopIdsAlertPolling() {
  if (idsAlertPollingTimer) {
    clearInterval(idsAlertPollingTimer)
    idsAlertPollingTimer = null
  }
}

function showNextIdsAlert() {
  if (!isSystemAdmin.value || isIdsAlertMutedToday()) return
  if (idsRiskAlertVisible.value || idsRiskAlertCurrent.value) return
  if (!idsRiskAlertQueue.value.length) return
  const next = idsRiskAlertQueue.value.shift() || null
  if (!next) return
  idsRiskAlertCurrent.value = next
  idsRiskAlertVisible.value = true
}

function dismissIdsRiskAlert() {
  const focusEventId = idsRiskAlertPendingFocusEventId
  idsRiskAlertPendingFocusEventId = null
  idsRiskAlertCurrent.value = null
  if (focusEventId) {
    void openEventById(focusEventId).finally(() => {
      showNextIdsAlert()
    })
    return
  }
  showNextIdsAlert()
}

function handleIdsRiskAlertClose() {
  idsRiskAlertVisible.value = false
}

function handleIdsRiskAlertJump() {
  idsRiskAlertPendingFocusEventId = idsRiskAlertCurrent.value?.id ?? null
  idsRiskAlertVisible.value = false
}

function handleIdsRiskAlertMuteToday() {
  muteIdsAlertsForToday()
  idsRiskAlertQueue.value = []
  idsRiskAlertVisible.value = false
}

function queueIdsRiskAlerts(items: IDSEventItem[], options?: { silent?: boolean }) {
  if (!isSystemAdmin.value || isIdsAlertMutedToday()) return
  const queuedIds = new Set<number>([
    ...(idsRiskAlertCurrent.value?.id ? [idsRiskAlertCurrent.value.id] : []),
    ...idsRiskAlertQueue.value.map((item) => item.id),
  ])
  const freshItems: IDSEventItem[] = []
  for (const item of items) {
    const eventId = eventIdOfIdsAlert(item)
    if (!eventId || queuedIds.has(eventId)) continue
    queuedIds.add(eventId)
    freshItems.push(item)
  }
  if (!freshItems.length) return

  const popupItems = freshItems.filter((item) => isEscalatedIdsPopupAlert(item))
  const notifyOnlyItems = freshItems.filter((item) => !isEscalatedIdsPopupAlert(item))

  if (popupItems.length) {
    idsRiskAlertQueue.value = [...idsRiskAlertQueue.value, ...popupItems].slice(0, 8)
  }

  if (!options?.silent && notifyOnlyItems.length) {
    const attackTitles = Array.from(
      new Set(
        notifyOnlyItems
          .map((item) => idsAlertAttackTitle(item))
          .filter((item) => String(item || '').trim()),
      ),
    ).slice(0, 3)
    ElNotification({
      title: '站点正在遭受攻击',
      message: attackTitles.length
        ? `新增 ${notifyOnlyItems.length} 条攻击事件：${attackTitles.join('、')}`
        : `新增 ${notifyOnlyItems.length} 条攻击事件，请立即复核`,
      type: 'error',
      duration: 6000,
    })
  }

  if (!options?.silent && popupItems.length && idsRiskAlertVisible.value) {
    ElNotification({
      title: popupItems[0]?.alert_profile?.title || '高危 IDS 风险预警',
      message: `又新增 ${popupItems.length} 条高危攻击，关闭当前弹窗后会继续告警。`,
      type: 'error',
      duration: 4000,
    })
  }

  if (!options?.silent) {
    freshItems.forEach((item) => notifyBrowserForEvent(item))
  }

  if (popupItems.length) {
    showNextIdsAlert()
  }
}

async function refreshAdminIdsRiskAlerts(options?: { silent?: boolean }) {
  if (!isSystemAdmin.value) {
    stopIdsAlertAlarm()
    idsRiskAlertPendingFocusEventId = null
    idsRiskAlertQueue.value = []
    idsRiskAlertVisible.value = false
    idsRiskAlertCurrent.value = null
    return
  }
  try {
    const res: any = await listIDSEvents({
      archived: 0,
      limit: IDS_ALERT_FETCH_LIMIT,
    })
    const items: IDSEventItem[] = Array.isArray(res?.items)
      ? res.items
      : Array.isArray(res?.data?.items)
        ? res.data.items
        : []
    const scopedItems = items.filter((item) => {
      const eventId = eventIdOfIdsAlert(item)
      if (!eventId) return false
      const normalizedStatus = String(item.status || '').trim().toLowerCase()
      return normalizedStatus !== 'false_positive' && normalizedStatus !== 'closed'
    })
    const eventIds = scopedItems.map((item) => eventIdOfIdsAlert(item)).filter((item) => item > 0)
    if (!eventIds.length) return

    const state = readIdsAlertState()
    if (state.watermark_event_id <= 0 && !state.watermark_created_at) {
      advanceIdsAlertWatermark(scopedItems)
      return
    }

    const legacyLooksReset =
      !state.watermark_created_at &&
      state.watermark_event_id > 0 &&
      Math.max(...eventIds) < state.watermark_event_id

    const freshItems = legacyLooksReset
      ? scopedItems
      : scopedItems.filter((item) => isIdsAlertNewerThanWatermark(item, state))

    advanceIdsAlertWatermark(scopedItems)

    if (isIdsAlertMutedToday()) return
    queueIdsRiskAlerts(freshItems, options)
  } catch {
    /* keep silent for ids page polling */
  }
}

function startIdsAlertPolling() {
  stopIdsAlertPolling()
  if (!isSystemAdmin.value) return
  void refreshAdminIdsRiskAlerts({ silent: true })
  idsAlertPollingTimer = window.setInterval(() => {
    void refreshAdminIdsRiskAlerts()
  }, IDS_ALERT_POLL_INTERVAL)
}

function createSourceFormDefaults(): SourceFormState {
  return {
    source_key: '',
    display_name: '',
    trust_classification: 'external_mature',
    detector_family: 'network',
    operational_status: 'enabled',
    freshness_target_hours: 24,
    sync_mode: 'manual',
    sync_endpoint: 'app/data/ids_source_sync/suricata-web-prod.manifest.json',
    provenance_note: '',
  }
}

const sourceForm = reactive<SourceFormState>(createSourceFormDefaults())

function createPackagePreviewFormDefaults(): PackagePreviewFormState {
  return {
    source_key: '',
    package_version: '',
    trust_classification: 'external_mature',
    detector_family: 'network',
    provenance_note: '',
    triggered_by: 'ids_admin',
  }
}

const packagePreviewForm = reactive<PackagePreviewFormState>(createPackagePreviewFormDefaults())

const packageActivationForm = reactive<PackageActivationFormState>({
  package_intake_id: 0,
  triggered_by: 'ids_admin',
  activation_note: '',
})

function resetPackageActivationForm() {
  packageActivationForm.package_intake_id = 0
  packageActivationForm.triggered_by = 'ids_admin'
  packageActivationForm.activation_note = ''
  packageActivationTarget.value = null
  packageActivatingSourceId.value = null
}

function buildStatsFilters() {
  return {
    event_origin: eventOriginFilter.value || undefined,
    source_classification: sourceClassificationFilter.value || undefined,
  }
}

async function fetchStats() {
  try {
    const res: any = await getIDSStats(buildStatsFilters())
    stats.value = res?.data ?? res
    renderPieChart()
  } catch {
    stats.value = null
  }
}

async function fetchTrend() {
  try {
    const res: any = await getIDSTrend(trendDays.value, buildStatsFilters())
    trendData.value = res?.data ?? res ?? { dates: [], counts: [] }
    renderTrendChart()
  } catch {
    trendData.value = { dates: [], counts: [] }
  }
}

let pieChartInstance: echarts.ECharts | null = null
let trendChartInstance: echarts.ECharts | null = null

const PIE_COLORS = ['#ef4444', '#f59e0b', '#10b981', '#3b82f6', '#8b5cf6', '#ec4899']

function renderPieChart() {
  const el = document.getElementById('ids-pie-chart')
  if (!el || !stats.value?.by_type?.length) return
  if (!pieChartInstance) pieChartInstance = echarts.init(el, 'dark')
  pieChartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} ({d}%)',
      backgroundColor: 'rgba(15, 23, 42, 0.96)',
      borderColor: 'rgba(56, 189, 248, 0.35)',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#e2e8f0', fontSize: 14 },
    },
    color: PIE_COLORS,
    legend: {
      type: 'scroll',
      orient: 'vertical',
      right: 14,
      top: 'middle',
      width: 200,
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 10,
      textStyle: { color: 'rgba(255,255,255,0.82)', fontSize: 13 },
      pageTextStyle: { color: 'rgba(255,255,255,0.55)' },
      pageIconColor: 'rgba(255,255,255,0.45)',
      pageIconInactiveColor: 'rgba(255,255,255,0.2)',
    },
    series: [{
      type: 'pie',
      radius: ['40%', '62%'],
      center: ['30%', '50%'],
      data: stats.value.by_type.map((t: { attack_type_label: string; count: number }) => ({
        name: t.attack_type_label,
        value: t.count,
      })),
      label: { show: false },
      labelLine: { show: false },
      emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(59,130,246,0.4)' } },
    }],
  })
}

function renderTrendChart() {
  const el = document.getElementById('ids-trend-chart')
  if (!el) return
  if (!trendChartInstance) trendChartInstance = echarts.init(el, 'dark')
  const { dates, counts } = trendData.value
  trendChartInstance.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.96)',
      borderColor: 'rgba(56, 189, 248, 0.35)',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#e2e8f0', fontSize: 14 },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 36 },
    xAxis: {
      type: 'category',
      data: dates?.length ? dates.map((d: string) => d.slice(5)) : [],
      axisLine: { lineStyle: { color: 'rgba(255,255,255,0.2)' } },
      axisLabel: { color: 'rgba(255,255,255,0.55)', fontSize: 13 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: 'rgba(255,255,255,0.08)', type: 'dashed' } },
      axisLabel: { color: 'rgba(255,255,255,0.55)', fontSize: 13 },
    },
    series: [{
      type: 'bar',
      data: counts ?? [],
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(59,130,246,0.8)' },
          { offset: 1, color: 'rgba(59,130,246,0.2)' },
        ]),
      },
    }],
  })
}

const idsTableMaxHeight = ref(440)

function refreshIdsTableMaxHeight() {
  idsTableMaxHeight.value = Math.max(300, Math.min(560, Math.round(window.innerHeight - 400)))
}

function handleResize() {
  pieChartInstance?.resize()
  trendChartInstance?.resize()
  refreshIdsTableMaxHeight()
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

async function fetchHeatboard() {
  heatboardLoading.value = true
  try {
    const res: any = await getIDSHeatboard()
    heatboard.value = res?.data ?? res ?? null
  } catch {
    heatboard.value = null
  } finally {
    heatboardLoading.value = false
  }
}

async function loadNotificationSettings() {
  try {
    const res: any = await getIDSNotificationSettings()
    const data = res?.data ?? res
    if (!data) return
    Object.assign(notificationSettings.email, data.email || {})
    Object.assign(notificationSettings.wecom, data.wecom || {})
    Object.assign(notificationSettings.webhook, data.webhook || {})
  } catch {
    /* keep local defaults */
  }
}

async function saveNotificationSettingsForm() {
  notificationSaving.value = true
  try {
    const res: any = await updateIDSNotificationSettings({
      email: notificationSettings.email,
      wecom: notificationSettings.wecom,
      webhook: notificationSettings.webhook,
    })
    const data = res?.data ?? res
    if (data) {
      Object.assign(notificationSettings.email, data.email || {})
      Object.assign(notificationSettings.wecom, data.wecom || {})
      Object.assign(notificationSettings.webhook, data.webhook || {})
    }
    ElMessage.success('IDS 通知设置已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '保存通知设置失败')
  } finally {
    notificationSaving.value = false
  }
}

async function testNotificationDispatch(target?: IDSEventItem | null) {
  notificationTesting.value = true
  try {
    const res: any = await testIDSNotifications(target?.id)
    const data = res?.data ?? res
    const summary = Array.isArray(data?.results)
      ? data.results.map((item: any) => `${item.channel}:${item.status}`).join(' / ')
      : 'test sent'
    ElMessage.success(`通知测试完成 ${summary}`)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '通知测试失败')
  } finally {
    notificationTesting.value = false
  }
}

async function requestBrowserNotificationPermission() {
  if (typeof Notification === 'undefined') {
    ElMessage.warning('当前浏览器不支持桌面通知')
    return
  }
  const permission = await Notification.requestPermission()
  browserNotificationPermission.value = permission
  if (permission === 'granted') {
    writeBrowserNotificationEnabled(true)
    ElMessage.success('桌面通知已开启')
    return
  }
  ElMessage.warning('桌面通知权限未授予')
}

function notifyBrowserForEvent(item: IDSEventItem) {
  if (typeof Notification === 'undefined') return
  browserNotificationPermission.value = Notification.permission
  if (!browserNotificationEnabled.value || Notification.permission !== 'granted') return
  try {
    const notification = new Notification(item.alert_profile?.title || 'IDS 风险预警', {
      body: `${idsAlertAttackTitle(item)} | ${item.client_ip || '-'} | ${item.method} ${item.path || '-'}`,
      tag: `ids-event-${item.id}`,
      requireInteraction: isEscalatedIdsPopupAlert(item) || (item.risk_score || 0) >= IDS_ALERT_MIN_SCORE,
    })
    notification.onclick = () => {
      window.focus()
      void openEventById(item.id)
      analysisWorkbenchVisible.value = true
      notification.close()
    }
  } catch {
    /* keep browser notifications best-effort */
  }
}

async function loadCurrentInsight(eventId: number) {
  insightLoading.value = true
  try {
    const res: any = await getIDSEventInsight(eventId)
    const data = res?.data ?? res
    currentInsight.value = data ?? null
    if (data?.item?.id) {
      currentRow.value = data.item
    }
    return data ?? null
  } catch {
    currentInsight.value = null
    return null
  } finally {
    insightLoading.value = false
  }
}

async function exportEvidencePackage(row?: IDSEventItem | null) {
  const target = row || currentRow.value
  if (!target?.id) {
    ElMessage.warning('当前没有可导出的 IDS 事件')
    return
  }
  try {
    const [insightRes, reportRes] = await Promise.all([
      getIDSEventInsight(target.id),
      getIDSEventReport(target.id, false),
    ])
    const insight = (insightRes as any)?.data ?? insightRes
    const report = (reportRes as any)?.data ?? reportRes
    const payload = {
      exported_at: new Date().toISOString(),
      event: insight?.item ?? target,
      insight: insight ? {
        profile: insight.profile,
        timeline: insight.timeline,
        cluster: insight.cluster,
        false_positive_learning: insight.false_positive_learning,
      } : null,
      report: report?.report ?? null,
      markdown: report?.markdown ?? '',
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], {
      type: 'application/json;charset=utf-8',
    })
    downloadBlob(blob, `ids-evidence-package-${target.id}.json`)
    ElMessage.success('证据包已导出')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '导出证据包失败')
  }
}

function applyTableClusterFocus(cluster: TableClusterSummary) {
  attackTypeFilter.value = tableData.value.find((row) => row.id === cluster.first_event_id)?.attack_type || ''
  pageOffset.value = 0
  void fetchData().then(() => {
    const first = tableData.value.find((row) => row.id === cluster.first_event_id) || tableData.value[0]
    if (first) {
      void openEventById(first.id)
    }
  })
}

async function openAnalysisWorkbench(
  row: IDSEventItem,
  options?: { autoAnalyze?: boolean; skipProcessOverlay?: boolean },
) {
  analysisWorkbenchVisible.value = true
  analysisWorkbenchLoading.value = true
  try {
    if (currentRow.value?.id !== row.id || !currentRow.value?.matched_hits) {
      await openEventById(row.id, { openDetail: false })
    }
    await loadCurrentInsight(row.id)
    if (options?.autoAnalyze) {
      await handleAiAnalyze(currentRow.value || row, { skipProcessOverlay: options?.skipProcessOverlay })
      await loadCurrentInsight(row.id)
    }
  } finally {
    analysisWorkbenchLoading.value = false
  }
}

async function fetchData() {
  loading.value = true
  try {
    const res: any = await listIDSEvents({
      attack_type: attackTypeFilter.value || undefined,
      client_ip: clientIpFilter.value || undefined,
      blocked: blockedFilter.value,
      archived: archivedFilter.value,
      status: statusFilter.value || undefined,
      event_origin: eventOriginFilter.value || undefined,
      source_classification: sourceClassificationFilter.value || undefined,
      min_score: minScoreFilter.value,
      limit: pageSize.value,
      offset: pageOffset.value,
    })
    const data = res?.data ?? res
    tableData.value = data?.items ?? []
    total.value = data?.total ?? 0
  } catch {
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function fetchSources() {
  sourceLoading.value = true
  try {
    const res: any = await listIDSSources()
    const data = res?.data ?? res
    sourceRows.value = data?.items ?? []
    sourceSummary.value = data?.summary ?? {
      total: 0,
      healthy_count: 0,
      degraded_count: 0,
      trusted_count: 0,
      demo_test_count: 0,
    }
  } catch {
    sourceRows.value = []
    sourceSummary.value = {
      total: 0,
      healthy_count: 0,
      degraded_count: 0,
      trusted_count: 0,
      demo_test_count: 0,
    }
  } finally {
    sourceLoading.value = false
  }
}

/** 表格中单行展示时间，避免换行导致行高不齐 */
function fmtTableDateTime(v: string | null | undefined): string {
  if (!v) return '-'
  return String(v).trim().replace(/\s+/g, ' ')
}

function fmtConfidencePct(v: number | null | undefined): string {
  const n = v == null || Number.isNaN(Number(v)) ? 0 : Number(v)
  return `${Math.round(n)}%`
}

/** 列表「策略」列：规则名改为固定两字中文，避免 IDS-Block… 被截断 */
function fmtFirewallRuleTable(rule: string | null | undefined): string {
  if (!rule?.trim()) return '-'
  const s = rule.trim()
  if (/IDS[-_]?Block/i.test(s)) return '拦截'
  if (/IDS[-_]?Allow/i.test(s)) return '放行'
  if (/drop|deny|block/i.test(s)) return '拦截'
  if (/pass|accept|allow/i.test(s)) return '放行'
  return '已配'
}

function sourceClassificationLabel(value: string | null | undefined): string {
  if (value === 'external_mature') return '成熟规则源'
  if (value === 'custom_project') return '项目自定义'
  if (value === 'transitional_local') return '过渡本地检测'
  return value?.trim() || '-'
}

function sourceClassificationTagType(value: string | null | undefined): 'success' | 'warning' | 'info' {
  if (value === 'external_mature') return 'success'
  if (value === 'custom_project') return 'warning'
  return 'info'
}

function sourceFreshnessLabel(value: string | null | undefined): string {
  if (value === 'current') return '当前'
  if (value === 'stale') return '待更新'
  if (value === 'unknown') return '未知'
  return value?.trim() || '-'
}

function responseResultLabel(value: string | null | undefined): string {
  if (value === 'success') return '执行成功'
  if (value === 'failed') return '执行失败'
  if (value === 'record_only') return '仅记录'
  return value?.trim() || '-'
}

function responseResultTagType(value: string | null | undefined): 'success' | 'danger' | 'info' {
  if (value === 'success') return 'success'
  if (value === 'failed') return 'danger'
  return 'info'
}

function sourceTrustClassificationLabel(value: string | null | undefined): string {
  if (value === 'external_mature') return '成熟外部规则'
  if (value === 'custom_project') return '项目自定义规则'
  if (value === 'transitional_local') return '过渡本地规则'
  if (value === 'demo_test') return '待核验规则'
  return value?.trim() || '-'
}

function sourceTrustClassificationTagType(value: string | null | undefined): 'success' | 'warning' | 'info' | 'danger' {
  if (value === 'external_mature') return 'success'
  if (value === 'custom_project') return 'warning'
  if (value === 'demo_test') return 'danger'
  return 'info'
}

function sourceHealthLabel(value: string | null | undefined): string {
  if (value === 'healthy') return '健康'
  if (value === 'stale') return '需更新'
  if (value === 'disabled') return '已停用'
  if (value === 'failing') return '异常'
  if (value === 'never_synced') return '未同步'
  return value?.trim() || '-'
}

function sourceHealthTagType(value: string | null | undefined): 'success' | 'warning' | 'info' | 'danger' {
  if (value === 'healthy') return 'success'
  if (value === 'stale') return 'warning'
  if (value === 'failing') return 'danger'
  return 'info'
}

function sourceOperationalStatusLabel(value: string | null | undefined): string {
  if (value === 'enabled') return '启用'
  if (value === 'disabled') return '停用'
  if (value === 'failing') return '异常'
  if (value === 'draft') return '草稿'
  return value?.trim() || '-'
}

function sourceSyncModeLabel(value: string | null | undefined): string {
  if (value === 'manual') return '手动'
  if (value === 'scheduled') return '定时'
  if (value === 'not_applicable') return '不适用'
  return value?.trim() || '-'
}

function sourceSyncResultTagType(value: string | null | undefined): 'success' | 'warning' | 'info' | 'danger' {
  if (value === 'success') return 'success'
  if (value === 'failed') return 'danger'
  if (value === 'skipped') return 'warning'
  return 'info'
}

function sourceSyncResultLabel(value: string | null | undefined): string {
  if (value === 'success') return '成功'
  if (value === 'failed') return '失败'
  if (value === 'skipped') return '已跳过'
  if (value === 'never_synced') return '未同步'
  return value?.trim() || '无记录'
}

function compactSha256(value: string | null | undefined): string {
  const normalized = value?.trim()
  if (!normalized) return '-'
  if (normalized.length <= 16) return normalized
  return `${normalized.slice(0, 8)}...${normalized.slice(-8)}`
}

function formatBytes(value: number | null | undefined): string {
  const size = Number(value || 0)
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(2)} MB`
}

function uploadAuditVerdictLabel(trace?: IDSUploadTrace | null): string {
  const verdict = trace?.audit?.verdict || ''
  if (verdict === 'quarantine') return '已扣留'
  if (verdict === 'review') return '待复核'
  if (verdict === 'pass') return '已放行'
  return verdict || '-'
}

function uploadAuditTagType(trace?: IDSUploadTrace | null): 'success' | 'warning' | 'danger' | 'info' {
  const verdict = trace?.audit?.verdict || ''
  if (verdict === 'quarantine') return 'danger'
  if (verdict === 'review') return 'warning'
  if (verdict === 'pass') return 'success'
  return 'info'
}

function buildUploadTraceMarkdownSection(trace?: IDSUploadTrace | null): string[] {
  if (!trace?.saved_as) return []
  return [
    '## 上传审计链',
    `- 保存名：${trace.saved_as || '-'}`,
    `- 原始文件名：${trace.file_name || '-'}`,
    `- 审计结论：${uploadAuditVerdictLabel(trace)}`,
    `- 审计风险：${trace.audit?.risk_level || '-'}`,
    `- 审计置信度：${trace.audit?.confidence ?? 0}`,
    `- 样本大小：${formatBytes(trace.size)}`,
    `- SHA-256: ${trace.sha256 || '-'}`,
    `- 摘要：${trace.audit?.summary || '-'}`,
    '',
  ]
}

function openSandboxReportFromEvent(row?: IDSEventItem | null) {
  const savedAs = row?.upload_trace?.saved_as?.trim()
  if (!savedAs) {
    ElMessage.info('当前事件没有关联的沙箱样本')
    return
  }
  detailVisible.value = false
  void router.push({
    path: '/sandbox',
    query: { saved_as: savedAs, report: '1' },
  })
}

function appendUploadTraceMarkdown(base: string, trace?: IDSUploadTrace | null): string {
  const lines = buildUploadTraceMarkdownSection(trace)
  if (!lines.length) return base
  const suffix = lines.join('\n')
  return `${base}\n\n${suffix}`
}

function matchedHits(row?: IDSEventItem | null): IDSMatchedHit[] {
  return Array.isArray(row?.matched_hits) ? row!.matched_hits : []
}

function requestPacket(row?: IDSEventItem | null): IDSRequestPacket | null {
  return row?.request_packet || null
}

function decisionBasis(row?: IDSEventItem | null): IDSDecisionBasis | null {
  return row?.decision_basis || null
}

function decisionSourceLabel(source?: string) {
  if (source === 'hybrid') return '静态规则 + AI'
  if (source === 'llm') return 'AI'
  return '静态规则'
}

function reportMatchedHits(): IDSMatchedHit[] {
  return Array.isArray(reportData.value?.matched_hits) ? reportData.value!.matched_hits! : []
}

function reportPacket(): IDSRequestPacket | null {
  return reportData.value?.packet || null
}

function reportDecisionBasis(): IDSDecisionBasis | null {
  return reportData.value?.decision_basis || null
}

function reportAiStatus(): IDSAIStatus | null {
  return reportData.value?.ai_status || null
}

function reportAnalysisModeLabel() {
  return (
    reportAiStatus()?.analysis_mode_label ||
    reportAiStatus()?.analysis_mode ||
    reportDecisionBasis()?.analysis_mode_label ||
    reportDecisionBasis()?.analysis_mode ||
    '-'
  )
}

async function refreshIdsAlertSoundConfig() {
  Object.assign(idsAlertSoundSettings, readIdsAlertSoundSettings())
  const info = await getIdsAlertCustomSoundInfo().catch(() => null)
  idsAlertCustomSoundInfo.value = info
  if (!info && (idsAlertSoundSettings.custom_audio_name || idsAlertSoundSettings.custom_audio_updated_at)) {
    writeIdsAlertSoundSettings({
      custom_audio_name: '',
      custom_audio_updated_at: null,
    })
    Object.assign(idsAlertSoundSettings, readIdsAlertSoundSettings())
  }
}

function persistIdsAlertSoundState(next: Partial<IDSAlertSoundSettings>) {
  Object.assign(idsAlertSoundSettings, writeIdsAlertSoundSettings(next))
}

function triggerWarningAudioPicker() {
  warningAudioInputRef.value?.click()
}

function scrollToIdsAlertSoundCard() {
  idsAlertSoundCardRef.value?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

async function handleWarningAudioFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null
  const file = input?.files?.[0]
  if (!file) return

  const isAudioFile = file.type.startsWith('audio/') || /\.(mp3|wav|ogg|m4a|aac|flac)$/i.test(file.name)
  if (!isAudioFile) {
    ElMessage.error('请选择音频文件作为预警声音')
    if (input) input.value = ''
    return
  }

  if (file.size > 8 * 1024 * 1024) {
    ElMessage.error('预警音频请控制在 8MB 以内')
    if (input) input.value = ''
    return
  }

  try {
    await saveIdsAlertCustomSound(file)
    await refreshIdsAlertSoundConfig()
    await primeIdsAlertSound()
    await playIdsAlertSound({ force: true })
    ElMessage.success(`已启用自定义预警音频：${file.name}`)
  } catch (error: any) {
    ElMessage.error(error?.message || '自定义预警音频保存失败')
  } finally {
    if (input) input.value = ''
  }
}

async function testIdsAlertSound() {
  try {
    await primeIdsAlertSound()
    await playIdsAlertSound({ force: true })
  } catch (error: any) {
    ElMessage.error(error?.message || '当前预警声音播放失败')
  }
}

async function restoreDefaultIdsAlertSound() {
  try {
    await clearIdsAlertCustomSound()
    await refreshIdsAlertSoundConfig()
    await primeIdsAlertSound()
    await playIdsAlertSound({ force: true })
    ElMessage.success('已恢复默认预警声音')
  } catch (error: any) {
    ElMessage.error(error?.message || '默认预警声音恢复失败')
  }
}

async function focusEventFromBroadcast(detail?: IDSFocusEventDetail | null) {
  const eventId = Number(detail?.eventId || 0)
  if (!Number.isFinite(eventId) || eventId <= 0) return
  try {
    await openEventById(eventId, { report: detail?.report === true })
  } catch {
    ElMessage.error('指定 IDS 事件加载失败')
  }
}

function handleIdsFocusEvent(event: Event) {
  const customEvent = event as CustomEvent<IDSFocusEventDetail>
  void focusEventFromBroadcast(customEvent.detail)
}

function handleIdsAlertSoundSettingsUpdated() {
  void refreshIdsAlertSoundConfig()
}

function resetSourceForm() {
  Object.assign(sourceForm, createSourceFormDefaults())
  editingSourceId.value = null
}

function applySourceTrustDefaults(value: string) {
  if (value === 'demo_test') {
    sourceForm.sync_mode = 'not_applicable'
    sourceForm.sync_endpoint = ''
    if (sourceForm.operational_status === 'enabled') {
      sourceForm.operational_status = 'draft'
    }
  } else if (sourceForm.sync_mode === 'not_applicable') {
    sourceForm.sync_mode = 'manual'
    if (!sourceForm.sync_endpoint) {
      sourceForm.sync_endpoint = 'app/data/ids_source_sync/suricata-web-prod.manifest.json'
    }
  }
}

function openSourceCreateDialog() {
  resetSourceForm()
  sourceDialogVisible.value = true
}

function openSourceEditDialog(row: IDSSourceItem) {
  editingSourceId.value = row.id
  Object.assign(sourceForm, {
    source_key: row.source_key,
    display_name: row.display_name,
    trust_classification: row.trust_classification,
    detector_family: row.detector_family,
    operational_status: row.operational_status,
    freshness_target_hours: row.freshness_target_hours,
    sync_mode: row.sync_mode,
    sync_endpoint: row.sync_endpoint || '',
    provenance_note: row.provenance_note || '',
  })
  sourceDialogVisible.value = true
}

async function saveSourceLegacy() {
  sourceSaving.value = true
  try {
    const payload: IDSSourceRegistryPayload = {
      source_key: sourceForm.source_key.trim(),
      display_name: sourceForm.display_name.trim(),
      trust_classification: sourceForm.trust_classification,
      detector_family: sourceForm.detector_family.trim(),
      operational_status: sourceForm.operational_status,
      freshness_target_hours: Number(sourceForm.freshness_target_hours || 0),
      sync_mode: sourceForm.sync_mode,
      sync_endpoint: sourceForm.sync_endpoint?.trim() || '',
      provenance_note: sourceForm.provenance_note?.trim() || '',
    }
    if (editingSourceId.value) {
      await updateIDSSource(editingSourceId.value, payload)
      ElMessage.success('规则源已更新')
    } else {
      await createIDSSource(payload)
      ElMessage.success('规则源已创建')
    }
    sourceDialogVisible.value = false
    resetSourceForm()
    /*
    const versionSummary = data?.package_version ? ` / ${data.package_version}` : ''
    const ruleSummary = data?.rule_count ? ` / ${data.rule_count} rules` : ''
    ElMessage.success(`瑙勫垯婧愬悓姝?{sourceSyncResultLabel(data?.result_status)}锛?{row.display_name}${versionSummary}${ruleSummary}`)
    */
    await fetchSources()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '规则源保存失败')
  } finally {
    sourceSaving.value = false
  }
}

async function saveSource() {
  sourceSaving.value = true
  try {
    const payload: IDSSourceRegistryPayload = {
      source_key: sourceForm.source_key.trim(),
      display_name: sourceForm.display_name.trim(),
      trust_classification: sourceForm.trust_classification,
      detector_family: sourceForm.detector_family.trim(),
      operational_status: sourceForm.operational_status,
      freshness_target_hours: Number(sourceForm.freshness_target_hours || 0),
      sync_mode: sourceForm.sync_mode,
      sync_endpoint: sourceForm.sync_endpoint?.trim() || '',
      provenance_note: sourceForm.provenance_note?.trim() || '',
    }
    if (editingSourceId.value) {
      await updateIDSSource(editingSourceId.value, payload)
      ElMessage.success('规则源已更新')
    } else {
      await createIDSSource(payload)
      ElMessage.success('规则源已创建')
    }
    sourceDialogVisible.value = false
    resetSourceForm()
    await fetchSources()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '规则源保存失败')
  } finally {
    sourceSaving.value = false
  }
}

async function runSourceSyncLegacy(row: IDSSourceItem) {
  sourceSyncingId.value = row.id
  try {
    const res: any = await syncIDSSource(row.id, {
      triggered_by: 'ids_admin',
      reason: `安全中心手动同步（${row.source_key}）`,
    })
    const data = res?.data ?? res
    ElMessage.success(`规则源同步${sourceSyncResultLabel(data?.result_status)}：${row.display_name}`)
    await fetchSources()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '规则源同步失败')
  } finally {
    sourceSyncingId.value = null
  }
}

async function runSourceSync(row: IDSSourceItem) {
  sourceSyncingId.value = row.id
  try {
    const res: any = await syncIDSSource(row.id, {
      triggered_by: 'ids_admin',
      reason: `security-center manual sync for ${row.source_key}`,
    })
    const data = res?.data ?? res
    const versionSummary = data?.package_version ? ` / ${data.package_version}` : ''
    const ruleSummary = data?.rule_count ? ` / ${data.rule_count} rules` : ''
    ElMessage.success(`${sourceSyncResultLabel(data?.result_status)} / ${row.display_name}${versionSummary}${ruleSummary}`)
    await fetchSources()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '规则源同步失败')
  } finally {
    sourceSyncingId.value = null
  }
}

void [formatBytes, saveSourceLegacy, runSourceSyncLegacy]

function resetPackagePreviewForm() {
  Object.assign(packagePreviewForm, createPackagePreviewFormDefaults())
  latestPackagePreviewResult.value = null
}

function openPackagePreviewDialog(row?: IDSSourceItem) {
  resetPackagePreviewForm()
  if (row) {
    packagePreviewForm.source_key = row.source_key
    packagePreviewForm.trust_classification = row.trust_classification
    packagePreviewForm.detector_family = row.detector_family
    packagePreviewForm.provenance_note = row.provenance_note || ''
  }
  packagePreviewDialogVisible.value = true
}

function packageVersionStateLabel(value: string | null | undefined): string {
  if (value === 'newer') return '较新'
  if (value === 'unchanged') return '未变化'
  if (value === 'older') return '较旧'
  if (value === 'conflicting') return '存在冲突'
  return value?.trim() || '-'
}

function packageVersionStateTagType(value: string | null | undefined): 'success' | 'warning' | 'info' | 'danger' {
  if (value === 'newer') return 'success'
  if (value === 'unchanged') return 'info'
  if (value === 'older') return 'warning'
  return 'danger'
}

function packageIntakeResultLabel(value: string | null | undefined): string {
  if (value === 'previewed') return '已预览'
  if (value === 'activated') return '已激活'
  if (value === 'rejected') return '已拒绝'
  if (value === 'failed') return '已失败'
  return value?.trim() || '-'
}

function packageIntakeResultTagType(value: string | null | undefined): 'success' | 'warning' | 'info' | 'danger' {
  if (value === 'activated') return 'success'
  if (value === 'previewed') return 'info'
  if (value === 'rejected') return 'danger'
  return 'warning'
}

function canActivatePackageIntake(intake: IDSSourcePackageIntakeItem | null | undefined): boolean {
  if (!intake) return false
  if (intake.trust_classification === 'demo_test') return false
  return true
}

function packageHistoryStateTagType(
  intake: IDSSourcePackageIntakeItem | null | undefined,
  activation: IDSSourcePackageActivationItem | null | undefined,
): 'success' | 'warning' | 'info' | 'danger' {
  if (activation) return 'success'
  return packageIntakeResultTagType(intake?.intake_result)
}

function packageHistoryStateLabel(
  intake: IDSSourcePackageIntakeItem | null | undefined,
  activation: IDSSourcePackageActivationItem | null | undefined,
): string {
  if (activation) return '已激活'
  return packageIntakeResultLabel(intake?.intake_result)
}

async function submitPackagePreview() {
  packagePreviewing.value = true
  try {
    const payload: IDSSourcePackagePreviewPayload = {
      source_key: packagePreviewForm.source_key.trim(),
      package_version: packagePreviewForm.package_version.trim(),
      trust_classification: packagePreviewForm.trust_classification,
      detector_family: packagePreviewForm.detector_family.trim(),
      provenance_note: packagePreviewForm.provenance_note?.trim() || '',
      triggered_by: packagePreviewForm.triggered_by.trim() || 'ids_admin',
    }
    const res: any = await previewIDSSourcePackage(payload)
    const data = res?.data ?? res
    latestPackagePreviewResult.value = data
    ElMessage.success(`规则包预览${packageIntakeResultLabel(data?.intake_result)}`)
    await fetchSources()
  } catch (e: any) {
    latestPackagePreviewResult.value = null
    ElMessage.error(e?.response?.data?.detail || e?.message || '规则包预览失败')
  } finally {
    packagePreviewing.value = false
  }
}

function openPackageActivationDialog(row: IDSSourceItem) {
  const latestIntake = row.recent_package_intakes?.[0]
  if (!latestIntake) {
    ElMessage.warning('当前没有可激活的规则包预览记录')
    return
  }
  if (latestIntake.trust_classification === 'demo_test') {
    ElMessage.warning('待核验规则包不能直接作为生产受信覆盖激活')
    return
  }
  packageActivationForm.package_intake_id = latestIntake.id
  packageActivationForm.triggered_by = 'ids_admin'
  packageActivationForm.activation_note = ''
  packageActivationTarget.value = {
    sourceId: row.id,
    sourceKey: row.source_key,
    displayName: row.display_name,
    intake: latestIntake,
  }
  packageActivationDialogVisible.value = true
}

function closePackageActivationDialog() {
  packageActivationDialogVisible.value = false
  resetPackageActivationForm()
}

async function openPackageHistoryDialog(row: IDSSourceItem) {
  packageHistoryDialogVisible.value = true
  packageHistoryLoading.value = true
  packageHistory.value = null
  packageHistorySource.value = row
  try {
    const res: any = await listIDSSourcePackages({ source_id: row.id, limit: 5 })
    const data = res?.data ?? res
    packageHistory.value = data?.items?.[0] ?? null
  } catch (e: any) {
    packageHistory.value = null
    ElMessage.error(e?.response?.data?.detail || e?.message || '规则包历史加载失败')
  } finally {
    packageHistoryLoading.value = false
  }
}

async function submitPackageActivation() {
  if (!packageActivationTarget.value) {
    ElMessage.warning('请先选择一个已审阅的规则包再激活')
    return
  }
  packageActivating.value = true
  packageActivatingSourceId.value = packageActivationTarget.value.sourceId
  try {
    const res: any = await activateIDSSourcePackage({
      package_intake_id: packageActivationForm.package_intake_id,
      triggered_by: packageActivationForm.triggered_by.trim() || 'ids_admin',
      activation_note: packageActivationForm.activation_note.trim(),
    })
    const data = res?.data ?? res
    ElMessage.success(`规则包${packageIntakeResultLabel(data?.result_status)}完成`)
    closePackageActivationDialog()
    await fetchSources()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '规则包激活失败')
  } finally {
    packageActivating.value = false
    if (packageActivationDialogVisible.value) {
      packageActivatingSourceId.value = null
    }
  }
}

function handleSearch() {
  pageOffset.value = 0
  fetchData()
  fetchStats()
  fetchTrend()
}

async function handleArchive(row: IDSEventItem) {
  try {
    await archiveIDSEvent(row.id)
    ElMessage.success('已归档')
    await fetchData()
    await fetchStats()
    await fetchHeatboard()
    if (currentRow.value?.id === row.id) {
      await openEventById(row.id)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '归档失败')
  }
}

async function handleBatchArchive() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请选择要归档的事件')
    return
  }
  try {
    await ElMessageBox.confirm(`确定归档选中的 ${selectedIds.value.length} 条记录？`, '批量归档')
    await archiveIDSBatch(selectedIds.value)
    ElMessage.success('批量归档成功')
    selectedIds.value = []
    await fetchData()
    await fetchStats()
    await fetchHeatboard()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || e?.message || '归档失败')
  }
}

function handleSelectionChange(rows: IDSEventItem[]) {
  selectedIds.value = rows.map((r) => r.id)
}

function showDetail(row: IDSEventItem) {
  void openEventById(row.id)
}

async function openEventById(eventId: number, opts?: { report?: boolean; openDetail?: boolean }) {
  const res: any = await getIDSEvent(eventId)
  const data = res?.data ?? res
  const row = data?.item ?? data
  if (!row?.id) {
    throw new Error('IDS event not found')
  }
  currentRow.value = row
  detailVisible.value = opts?.openDetail !== false
  void loadCurrentInsight(eventId)
  if (opts?.report) {
    await openReport(row, true)
  }
}

async function focusEventFromRoute() {
  const raw = typeof route.query.event === 'string' ? route.query.event : ''
  const panel = typeof route.query.panel === 'string' ? route.query.panel : ''
  if (raw) {
    const eventId = Number(raw)
    if (Number.isFinite(eventId) && eventId > 0) {
      try {
        await openEventById(eventId, { report: route.query.report === '1' })
      } catch {
        ElMessage.error('指定 IDS 事件加载失败')
      }
    }
  }

  if (panel === 'sound') {
    await nextTick()
    scrollToIdsAlertSoundCard()
  }

  const nextQuery = { ...route.query }
  delete nextQuery.event
  delete nextQuery.report
  delete nextQuery.panel
  void router.replace({ path: route.path, query: nextQuery })
}

async function handleAiAnalyze(row: IDSEventItem, opts?: { skipProcessOverlay?: boolean }) {
  aiAnalyzingId.value = row.id
  if (!opts?.skipProcessOverlay) {
    startAiProcess('正在等待后端 AI 对当前拦截请求进行真实研判...', [
      '已提交事件 AI 研判请求',
      '后端会基于静态命中规则、攻击包和处置链生成分析结果',
    ])
  }
  try {
    const res: any = await analyzeIDSEventAI(row.id)
    const data = res?.data ?? res
    ElMessage.success(data?.message || 'AI 研判完成')
    if (currentRow.value?.id === row.id) {
      currentRow.value = {
        ...currentRow.value,
        ai_risk_level: data?.ai_risk_level,
        ai_analysis: data?.ai_analysis,
        ai_confidence: data?.ai_confidence,
        ai_analyzed_at: data?.ai_analyzed_at,
      }
    }
    await fetchData()
    if (currentRow.value?.id === row.id) {
      await openEventById(row.id)
      await loadCurrentInsight(row.id)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || 'AI 研判失败')
  } finally {
    aiAnalyzingId.value = null
    if (!opts?.skipProcessOverlay) {
      stopAiProcess()
    }
  }
}

function resolveShortcutAiTarget() {
  if (currentRow.value?.id) return currentRow.value
  const selectedId = selectedIds.value[0]
  if (selectedId) {
    const selectedRow = tableData.value.find((item) => item.id === selectedId)
    if (selectedRow) return selectedRow
  }
  return tableData.value[0] || null
}

async function triggerShortcutAiAnalysis() {
  if (!isSystemAdmin.value || aiAnalyzingId.value) return
  const target = resolveShortcutAiTarget()
  if (!target) {
    ElMessage.warning('当前没有可研判的 IDS 事件')
    return
  }
  try {
    if (currentRow.value?.id !== target.id) {
      await openEventById(target.id, { openDetail: false })
    }
    await openAnalysisWorkbench(currentRow.value?.id === target.id ? currentRow.value || target : target, {
      autoAnalyze: true,
    })
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '快捷 AI 研判失败')
  }
}

function handleIdsShortcutKeydown(event: KeyboardEvent) {
  if (!isSystemAdmin.value) return
  if (event.key !== 'F2' || event.repeat) return
  if (event.altKey || event.ctrlKey || event.metaKey) return
  event.preventDefault()
  void triggerShortcutAiAnalysis()
}

async function handleUpdateStatus(row: IDSEventItem, status: string) {
  try {
    await updateIDSEventStatus(row.id, { status })
    ElMessage.success('状态已更新')
    await fetchData()
    await fetchStats()
    await fetchHeatboard()
    if (currentRow.value?.id === row.id) {
      await openEventById(row.id)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '状态更新失败')
  }
}

/** 操作列「更多」：状态 / 封禁 / 解封 / 归档 */
function handleIdsMoreMenu(row: IDSEventItem, cmd: string | number) {
  const c = String(cmd)
  if (c === 'investigating' || c === 'mitigated' || c === 'false_positive' || c === 'closed') {
    handleUpdateStatus(row, c)
    return
  }
  if (c === 'block') {
    handleManualBlock(row)
    return
  }
  if (c === 'unblock') {
    handleManualUnblock(row)
    return
  }
  if (c === 'archive' && !row.archived) {
    handleArchive(row)
  }
}

async function handleManualBlock(row: IDSEventItem) {
  try {
    const res: any = await blockIDSEventIp(row.id)
    const data = res?.data ?? res
    if (data?.ok === false) {
      ElMessage.error(data?.message || '封禁失败')
    } else {
      ElMessage.success(data?.message || 'IP 已加入封禁名单')
    }
    await fetchData()
    await fetchStats()
    await fetchHeatboard()
    if (currentRow.value?.id === row.id) {
      await openEventById(row.id)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '封禁失败')
  }
}

async function handleManualUnblock(row: IDSEventItem) {
  try {
    const res: any = await unblockIDSEventIp(row.id)
    const data = res?.data ?? res
    if (data?.ok === false) {
      ElMessage.error(data?.message || '解封失败')
    } else {
      ElMessage.success(data?.message || 'IP 已解除封禁')
    }
    await fetchData()
    await fetchStats()
    await fetchHeatboard()
    if (currentRow.value?.id === row.id) {
      await openEventById(row.id)
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '解封失败')
  }
}

function stopAiProcess() {
  aiProcessVisible.value = false
  aiProcessFeed.value = []
  aiProcessMode.value = 'analysis'
}

function startAiProcess(title?: string, feed?: string[]) {
  const initialTitle = title?.trim() ? title : 'AI 研判任务执行中，正在等待后端返回分析结果...'
  aiProcessMode.value = 'analysis'
  aiProcessText.value = initialTitle
  aiProcessVisible.value = true
  aiProcessFeed.value = feed?.length ? feed.slice(0, 4) : [initialTitle]
}

async function exportReport(format: 'md' | 'html' | 'pdf') {
  const content = reportMarkdown.value?.trim()
  if (!content) {
    ElMessage.warning('暂无可导出的报告内容')
    return
  }
  const stamp = new Date().toISOString().replace(/[:.]/g, '-')
  const base = `ids-report-${reportOrderNo.value || 'event'}-${stamp}`
  let blob: Blob
  let filename: string
  if (format === 'pdf') {
    const el = reportContainerRef.value
    if (!el) {
      ElMessage.error('报告容器不可用，无法导出 PDF')
      return
    }
    try {
      const canvas = await html2canvas(el, {
        scale: 2,
        backgroundColor: '#0a0a0a',
        useCORS: true,
      })
      const imgData = canvas.toDataURL('image/png')
      const pdf = new jsPDF('p', 'pt', 'a4')
      const pageW = pdf.internal.pageSize.getWidth()
      const pageH = pdf.internal.pageSize.getHeight()
      const imgW = pageW - 40
      const imgH = (canvas.height * imgW) / canvas.width
      let heightLeft = imgH
      let position = 20
      pdf.addImage(imgData, 'PNG', 20, position, imgW, imgH)
      heightLeft -= (pageH - 40)
      while (heightLeft > 0) {
        position = heightLeft - imgH + 20
        pdf.addPage()
        pdf.addImage(imgData, 'PNG', 20, position, imgW, imgH)
        heightLeft -= (pageH - 40)
      }
      pdf.save(`${base}.pdf`)
      ElMessage.success('PDF 导出成功')
    } catch (e: any) {
      ElMessage.error(e?.message || 'PDF 导出失败')
    }
    return
  } else if (format === 'html') {
    const html = `<!doctype html><html><head><meta charset="utf-8"><title>${base}</title><style>body{font-family:Consolas,monospace;padding:24px;background:#0a0a0a;color:#e5e7eb;white-space:pre-wrap;line-height:1.6}</style></head><body>${content.replace(/&/g, '&amp;').replace(/</g, '&lt;')}</body></html>`
    blob = new Blob([html], { type: 'text/html;charset=utf-8' })
    filename = `${base}.html`
  } else {
    blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    filename = `${base}.md`
  }
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
  ElMessage.success('报告导出成功')
}

function buildProfessionalMarkdown(data: any, eventId: number): string {
  const r = data?.report || {}
  const o = r?.overview || {}
  const s = r?.score || {}
  const e = r?.evidence || {}
  const resp = r?.response || {}
  const reportNo = `SCSP-IDS-${String(eventId).padStart(6, '0')}`
  const generatedAt = r?.generated_at || new Date().toISOString().slice(0, 19).replace('T', ' ')
  const malware =
    (o.attack_type || '') === 'malware' ||
    String(o.attack_type_label || '').includes('木马') ||
    String(o.attack_type_label || '').includes('WebShell')
  reportMeta.value = {
    reportNo,
    generatedAt,
    title: '校园物资供应链安全监测平台',
    headerSuffix: malware ? '木马/WebShell 安全事件分析报告' : '安全事件分析报告',
  }
  return [
    `# ${reportMeta.value.title}`,
    '',
    '## 安全事件分析报告',
    '',
    `- 报告编号：${reportNo}`,
    `- 生成时间：${generatedAt}`,
    `- 事件ID：${eventId}`,
    '',
    '## 一、事件概览',
    `- 事件时间：${o.time || '-'}`,
    `- 来源IP：${o.client_ip || '-'}`,
    `- 攻击类型：${localizeAttackTypeLabel(o.attack_type_label, o.attack_type)} (${o.attack_type || '-'})`,
    `- 请求路径：${o.method || '-'} ${o.path || '-'}`,
    `- 当前处置状态：${eventStatusLabel(o.status)}`,
    '',
    '## 二、风险评估',
    `- 规则风险分：${s.risk_score ?? '-'} / 100`,
    `- 规则置信度：${fmtConfidencePct(s.rule_confidence)}`,
    `- AI风险等级：${riskLevelLabel(s.ai_risk_level)}`,
    `- AI置信度：${fmtConfidencePct(s.ai_confidence)}`,
    '',
    '## 三、关键证据',
    `- 规则签名：${e.signature || '-'}`,
    `- Query片段：${e.query_snippet || '-'}`,
    `- Body片段：${e.body_snippet || '-'}`,
    `- User-Agent：${e.user_agent || '-'}`,
    '',
    '## 四、处置动作',
    `- 是否封禁：${resp.blocked ? '是' : '否'}`,
    `- 防火墙规则：${resp.firewall_rule || '-'}`,
    `- 执行动作：${resp.action_taken || '-'}`,
    `- 复核备注：${resp.review_note || '-'}`,
    '',
    '## 五、AI研判结论',
    data?.report?.ai_analysis || '暂无 AI 研判结果',
    '',
    '---',
    '本报告由 校园物资供应链安全监测平台 自动生成，仅供安全运营与审计留档使用。',
  ].join('\n')
}

async function openReport(
  row: IDSEventItem,
  forceAI = true,
  opts?: { skipProcessOverlay?: boolean },
) {
  reportOrderNo.value = `${row.id}`
  if (forceAI && !opts?.skipProcessOverlay) {
    startAiProcess('正在等待后端生成真实事件报告...', [
      '已提交报告生成请求',
      '若已配置模型密钥，后端会调用 AI 生成研判正文',
    ])
  }
  reportLoading.value = true
  try {
    const res: any = await getIDSEventReport(row.id, forceAI)
    const data = res?.data ?? res
    reportData.value = data?.report || null
    const backendMarkdown = String(data?.markdown || '').trim()
    reportMarkdown.value = backendMarkdown
      ? backendMarkdown
      : appendUploadTraceMarkdown(
          buildProfessionalMarkdown(data, row.id),
          data?.report?.upload_trace,
        )
    reportVisible.value = true
  } catch (e: any) {
    reportData.value = null
    reportMarkdown.value = ''
    ElMessage.error(e?.response?.data?.detail || e?.message || '生成报告失败')
  } finally {
    reportLoading.value = false
    stopAiProcess()
  }
}

function aiRiskTagType(level: string | undefined) {
  const l = (level || '').toLowerCase()
  if (l === 'high' || l === 'critical') return 'danger'
  if (l === 'medium') return 'warning'
  if (l === 'low') return 'success'
  return 'info'
}

/** 列表 AI 列：单字等级，避免 high/medium/low 英文撑破单元格 */
function aiRiskLevelTableLabel(level: string | undefined) {
  const l = (level || '').toLowerCase()
  if (l === 'high' || l === 'critical') return '高'
  if (l === 'medium') return '中'
  if (l === 'low') return '低'
  return '-'
}

function riskLevelLabel(level: string | undefined) {
  const l = (level || '').toLowerCase()
  if (l === 'high') return '高危'
  if (l === 'medium') return '中危'
  if (l === 'low') return '低危'
  return '未评估'
}

function reportConclusionText() {
  const blocked = !!reportData.value?.response?.blocked
  const level = (reportData.value?.score?.ai_risk_level || '').toLowerCase()
  if (blocked && level === 'high') return '已拦截并完成高危处置，建议继续监控同源流量。'
  if (blocked) return '已拦截并完成处置闭环，建议保持封禁策略。'
  if (level === 'high') return '高危事件未封禁，建议立即人工复核并执行阻断。'
  return '事件已记录，建议持续观察并结合上下文复核。'
}

function reportCoverSubtitle() {
  if ((reportData.value?.overview?.attack_type || '') === 'malware') return '木马 / WebShell 安全事件分析报告'
  return '网络安全事件分析报告'
}

function reportFingerprint() {
  const src = `${reportMeta.value.reportNo}|${reportMeta.value.generatedAt}|${reportData.value?.event_id || 0}|${reportData.value?.score?.hit_count || 0}`
  let h = 2166136261
  for (let i = 0; i < src.length; i += 1) {
    h ^= src.charCodeAt(i)
    h = Math.imul(h, 16777619)
  }
  return `EVT-${(h >>> 0).toString(16).toUpperCase().padStart(8, '0')}`
}

onMounted(async () => {
  tickIdsHudClock()
  idsHudClockTimer = setInterval(tickIdsHudClock, 1000)
  refreshIdsTableMaxHeight()
  window.addEventListener('resize', handleResize)
  window.addEventListener(IDS_ALERT_FOCUS_EVENT, handleIdsFocusEvent as EventListener)
  window.addEventListener('keydown', handleIdsShortcutKeydown)
  window.addEventListener(
    IDS_ALERT_SOUND_SETTINGS_UPDATED_EVENT,
    handleIdsAlertSoundSettingsUpdated as EventListener,
  )
  await refreshIdsAlertSoundConfig()
  await Promise.all([fetchSources(), fetchStats(), fetchTrend(), fetchData(), fetchHeatboard(), loadNotificationSettings()])
  await refreshAdminIdsRiskAlerts({ silent: true })
  startIdsAlertPolling()
  await focusEventFromRoute()
})
onBeforeUnmount(() => {
  if (idsHudClockTimer) clearInterval(idsHudClockTimer)
  idsHudClockTimer = null
  stopAiProcess()
  stopIdsAlertPolling()
  stopIdsAlertAlarm()
  window.removeEventListener('resize', handleResize)
  window.removeEventListener(IDS_ALERT_FOCUS_EVENT, handleIdsFocusEvent as EventListener)
  window.removeEventListener('keydown', handleIdsShortcutKeydown)
  window.removeEventListener(
    IDS_ALERT_SOUND_SETTINGS_UPDATED_EVENT,
    handleIdsAlertSoundSettingsUpdated as EventListener,
  )
  pieChartInstance?.dispose()
  trendChartInstance?.dispose()
})
watch([pageOffset, pageSize], fetchData)
watch(trendDays, () => fetchTrend())
watch(
  () => idsAlertSoundSettings.enabled,
  (enabled) => {
    persistIdsAlertSoundState({ enabled })
  },
)
watch(
  () => idsAlertSoundSettings.volume,
  (volume) => {
    persistIdsAlertSoundState({ volume })
  },
)
watch([eventOriginFilter, sourceClassificationFilter], () => {
  pageOffset.value = 0
  fetchStats()
  fetchTrend()
  fetchData()
})
watch(idsRiskAlertVisible, (visible) => {
  if (!visible) {
    stopIdsAlertAlarm()
    return
  }
  void startIdsAlertAlarm().catch(() => undefined)
})
watch(
  () => userStore.userInfo?.id,
  async () => {
    stopIdsAlertPolling()
    stopIdsAlertAlarm()
    idsRiskAlertQueue.value = []
    idsRiskAlertCurrent.value = null
    idsRiskAlertVisible.value = false
    if (!isSystemAdmin.value) return
    await refreshAdminIdsRiskAlerts({ silent: true })
    startIdsAlertPolling()
  },
)
watch(
  () => [route.query.event, route.query.report, route.query.panel],
  async () => {
    if (route.query.event || route.query.report || route.query.panel) {
      await focusEventFromRoute()
    }
  },
)
</script>

<template>
  <div class="security-center-page">
    <header class="sec-header">
      <div class="sec-hud-rail" aria-hidden="true">
        <span class="sec-hud-rail__dot" />
        <span class="sec-hud-rail__brand">旁路流量镜像 · 规则引擎 · 运行态</span>
        <span class="sec-hud-rail__split" />
        <span class="sec-hud-rail__clock">
          <span class="sec-hud-rail__tlab">系统时间</span>
          <span class="sec-hud-rail__tval">{{ idsHudClock }}</span>
        </span>
        <span class="sec-hud-rail__cursor">_</span>
      </div>
      <h1 class="sec-title">IDS 入侵检测</h1>
      <div class="sec-hud-pipeline">
        <span class="sec-hud-pipeline__step">抓包解析</span>
        <span class="sec-hud-pipeline__sep">·</span>
        <span class="sec-hud-pipeline__step">特征匹配（含 Body 抽样）</span>
        <span class="sec-hud-pipeline__sep">·</span>
        <span class="sec-hud-pipeline__step">攻击识别</span>
        <span class="sec-hud-pipeline__sep">·</span>
        <span class="sec-hud-pipeline__step">留痕封禁</span>
        <span class="sec-hud-pipeline__sep">·</span>
        <span class="sec-hud-pipeline__step">LLM 研判</span>
        <span class="sec-hud-pipeline__sep">·</span>
        <span class="sec-hud-pipeline__step">归档管理</span>
      </div>
    </header>

    <main class="sec-main">
      <div v-if="false && isSystemAdmin" class="ids-alert-sound-shortcut sec-card">
        <div class="ids-alert-sound-shortcut__copy">
          <div class="chart-title">管理员预警声音快捷入口</div>
          <div class="ids-alert-sound-shortcut__text">
            首屏就可以直接导入预警音频、试听当前声音，完整开关和音量设置仍保留在下面的完整面板里。
          </div>
          <div class="ids-alert-sound-shortcut__meta">
            <span>当前音源：{{ idsAlertCustomSoundInfo?.name || '默认预警音' }}</span>
            <span>状态：{{ idsAlertSoundSettings.enabled ? '已开启' : '静音' }}</span>
            <span>音量：{{ Math.round(idsAlertSoundSettings.volume * 100) }}%</span>
          </div>
        </div>
        <div class="ids-alert-sound-shortcut__actions">
          <el-button @click="triggerWarningAudioPicker">导入预警音频</el-button>
          <el-button type="primary" @click="testIdsAlertSound">试听当前声音</el-button>
          <el-button @click="scrollToIdsAlertSoundCard">打开完整设置</el-button>
        </div>
      </div>

      <div v-if="stats" class="stats-row">
        <div class="stat-card sec-stat">
          <span class="stat-value">{{ stats.total }}</span>
          <span class="stat-label">检测事件总数</span>
        </div>
        <div class="stat-card sec-stat danger">
          <span class="stat-value">{{ stats.blocked_count }}</span>
          <span class="stat-label">已封禁 IP</span>
        </div>
        <div class="stat-card sec-stat warning">
          <span class="stat-value">{{ stats.high_risk_count || 0 }}</span>
          <span class="stat-label">高风险事件</span>
        </div>
        <div v-for="t in stats.by_type" :key="t.attack_type" class="stat-card sec-stat small">
          <span class="stat-value">{{ t.count }}</span>
          <span class="stat-label">{{ t.attack_type_label }}</span>
        </div>
      </div>

      <div class="chart-row">
        <div class="chart-card sec-card">
          <div class="chart-title">攻击类型分布</div>
          <div id="ids-pie-chart" class="chart-arena" />
        </div>
        <div class="chart-card sec-card chart-card-wide">
          <div class="chart-title">
            事件趋势
            <el-select v-model="trendDays" size="small" class="sec-select">
              <el-option label="近7天" :value="7" />
              <el-option label="近14天" :value="14" />
              <el-option label="近30天" :value="30" />
            </el-select>
          </div>
          <div id="ids-trend-chart" class="chart-arena" />
        </div>
      </div>

      <div class="ids-ops-grid">
        <div class="ids-heatboard-card sec-card" v-loading="heatboardLoading">
          <div class="ids-card-head">
            <div>
              <div class="chart-title">今日攻击热力看板</div>
              <div class="ids-card-subtitle">聚焦今日攻击量、小时热度、类型分布和高危趋势。</div>
            </div>
            <span class="ids-card-stamp">{{ heatboard?.generated_at || '-' }}</span>
          </div>
          <template v-if="heatboard">
            <div class="ids-heatboard-summary">
              <div class="source-summary-tile">
                <span class="source-summary-tile__value">{{ heatboard.today_total }}</span>
                <span class="source-summary-tile__label">今日事件</span>
              </div>
              <div class="source-summary-tile source-summary-tile--warn">
                <span class="source-summary-tile__value">{{ heatboard.today_high_risk_total }}</span>
                <span class="source-summary-tile__label">今日高危</span>
              </div>
              <div class="source-summary-tile source-summary-tile--good">
                <span class="source-summary-tile__value">{{ heatboard.today_blocked_total }}</span>
                <span class="source-summary-tile__label">今日已拦截</span>
              </div>
            </div>
            <div class="ids-heatboard-panel">
              <div class="ids-heatboard-panel__head">
                <div>
                  <div class="ids-mini-card__title">小时攻势带</div>
                  <div class="ids-heatboard-panel__note">横轴是今天 24 小时，柱高表示攻击数，红色标记表示高危事件。</div>
                </div>
                <div class="ids-heatboard-legend">
                  <span><i class="ids-heatboard-legend__dot" /> 普通流量</span>
                  <span><i class="ids-heatboard-legend__dot ids-heatboard-legend__dot--danger" /> 高危流量</span>
                </div>
              </div>
              <div class="ids-heatboard-bars">
                <button
                  v-for="cell in heatboard.hourly"
                  :key="`hour-${cell.hour}`"
                  type="button"
                  class="ids-heatboard-bar"
                  :class="`is-${heatboardBarClass(cell)}`"
                  :title="heatboardHourSummary(cell)"
                >
                  <span class="ids-heatboard-bar__value">{{ cell.total }}</span>
                  <span class="ids-heatboard-bar__track">
                    <span class="ids-heatboard-bar__fill" :style="{ height: heatboardBarHeight(cell) }" />
                    <span v-if="cell.high_risk > 0" class="ids-heatboard-bar__danger">{{ cell.high_risk }}</span>
                  </span>
                  <span class="ids-heatboard-bar__time">{{ cell.hour }}</span>
                </button>
              </div>
              <div class="ids-heatboard-focus">
                <span class="ids-heatboard-focus__label">高热时段</span>
                <div v-if="heatboardBusyHours.length" class="ids-heatboard-focus__list">
                  <span v-for="cell in heatboardBusyHours" :key="`busy-${cell.hour}`" class="ids-heatboard-focus__chip">
                    {{ heatboardHourSummary(cell) }}
                  </span>
                </div>
                <div v-else class="timeline-empty">今天还没有出现明显攻击高峰</div>
              </div>
            </div>
            <div class="ids-mini-columns">
              <div class="ids-mini-card">
                <div class="ids-mini-card__title">今日类型分布</div>
                <div v-if="heatboard.by_type?.length" class="ids-mini-list">
                  <div v-for="item in heatboard.by_type" :key="`heat-type-${item.attack_type_label}`" class="ids-mini-list__row">
                    <span>{{ localizeAttackTypeLabel(item.attack_type_label) }}</span>
                    <strong>{{ item.count }}</strong>
                  </div>
                </div>
                <div v-else class="timeline-empty">今日暂无攻击类型数据</div>
              </div>
              <div class="ids-mini-card">
                <div class="ids-mini-card__title">近 7 天高危趋势</div>
                <div v-if="heatboard.high_risk_trend?.length" class="ids-mini-list">
                  <div v-for="item in heatboard.high_risk_trend" :key="`heat-trend-${item.date}`" class="ids-mini-list__row">
                    <span>{{ item.date.slice(5) }}</span>
                    <strong>{{ item.count }}</strong>
                  </div>
                </div>
                <div v-else class="timeline-empty">暂无高危趋势数据</div>
              </div>
              <div class="ids-mini-card">
                <div class="ids-mini-card__title">今日热点 IP</div>
                <div v-if="heatboard.hot_ips?.length" class="ids-mini-list">
                  <div v-for="item in heatboard.hot_ips" :key="`hot-ip-${item.client_ip}`" class="ids-mini-list__row">
                    <span class="cell-mono">{{ item.client_ip }}</span>
                    <strong>{{ item.count }}</strong>
                  </div>
                </div>
                <div v-else class="timeline-empty">暂无热点 IP</div>
              </div>
            </div>
          </template>
        </div>

        <div class="ids-notification-card sec-card">
          <div class="ids-card-head">
            <div>
              <div class="chart-title">联动通知中心</div>
              <div class="ids-card-subtitle">页面弹窗之外，支持桌面通知、邮件、企业微信和 Webhook。</div>
            </div>
          </div>
          <div class="ids-notification-grid">
            <div class="detail-item">
              <span class="detail-label">桌面通知</span>
              <span class="detail-value">
                {{ browserNotificationEnabled ? '已开启' : '已关闭' }} / 权限 {{ browserPermissionLabel(browserNotificationPermission) }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">邮件通知</span>
              <span class="detail-value">
                {{ notificationSettings.email.enabled ? '已启用' : '未启用' }}
                / {{ notificationSettings.email.password_configured ? '已配置凭据' : '未配置凭据' }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">企业微信</span>
              <span class="detail-value">{{ notificationSettings.wecom.enabled ? '已启用' : '未启用' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">Webhook</span>
              <span class="detail-value">
                {{ notificationSettings.webhook.enabled ? '已启用' : '未启用' }}
                / {{ notificationSettings.webhook.secret_configured ? '已配置密钥' : '无密钥' }}
              </span>
            </div>
          </div>
          <div class="ids-notification-actions">
            <el-switch
              :model-value="browserNotificationEnabled"
              inline-prompt
              active-text="桌面通知"
              inactive-text="静默"
              @change="(value: boolean) => writeBrowserNotificationEnabled(value)"
            />
            <el-button @click="requestBrowserNotificationPermission">申请桌面权限</el-button>
            <el-button @click="testNotificationDispatch(currentRow)">测试通知</el-button>
            <el-button type="primary" @click="notificationDialogVisible = true">通知配置</el-button>
          </div>
        </div>
      </div>

      <div v-if="false && isSystemAdmin" ref="idsAlertSoundCardRef" class="ids-alert-sound-card sec-card">
        <div class="ids-alert-sound-card__header">
          <div>
            <div class="chart-title">管理员预警声音完整设置</div>
            <div class="ids-alert-sound-card__subtitle">
              每次新的高危攻击弹窗出现时都会播放预警声音。你可以在这里开关声音、调整音量、导入自定义音频并立即试听。
            </div>
          </div>
          <el-switch
            v-model="idsAlertSoundSettings.enabled"
            inline-prompt
            active-text="开启"
            inactive-text="静音"
          />
        </div>

        <div class="ids-alert-sound-card__grid">
          <div class="ids-alert-sound-card__panel">
            <div class="ids-alert-sound-card__label">当前音源</div>
            <div class="ids-alert-sound-card__value">
              {{ idsAlertCustomSoundInfo?.name || '默认预警音' }}
            </div>
            <div class="ids-alert-sound-card__meta">
              <span>{{ idsAlertCustomSoundInfo ? '自定义音频' : '系统默认音效' }}</span>
              <span v-if="idsAlertCustomSoundInfo">{{ formatBytes(idsAlertCustomSoundInfo?.size) }}</span>
              <span v-if="idsAlertCustomSoundInfo?.updatedAt">{{ fmtTableDateTime(idsAlertCustomSoundInfo?.updatedAt) }}</span>
            </div>
          </div>

          <div class="ids-alert-sound-card__panel">
            <div class="ids-alert-sound-card__label">音量</div>
            <div class="ids-alert-sound-card__slider">
              <el-slider v-model="idsAlertSoundSettings.volume" :min="0" :max="1" :step="0.05" />
              <span class="ids-alert-sound-card__value">{{ Math.round(idsAlertSoundSettings.volume * 100) }}%</span>
            </div>
          </div>
        </div>

        <div class="ids-alert-sound-card__actions">
          <input
            ref="warningAudioInputRef"
            type="file"
            accept="audio/*,.mp3,.wav,.ogg,.m4a,.aac,.flac"
            class="ids-alert-sound-card__input"
            @change="handleWarningAudioFileChange"
          />
          <el-button @click="triggerWarningAudioPicker">导入音频</el-button>
          <el-button type="primary" @click="testIdsAlertSound">试听当前声音</el-button>
          <el-button :disabled="!idsAlertCustomSoundInfo" @click="restoreDefaultIdsAlertSound">恢复默认音</el-button>
        </div>
      </div>

      <div class="source-ops-card sec-card">
        <div class="source-ops-card__header">
          <div>
            <div class="chart-title">受信规则源运营</div>
            <div class="source-ops-card__subtitle">
              聚焦规则源健康度、同步留痕和运行态覆盖，让规则包变更能被看见、被追溯。
            </div>
          </div>
          <div class="source-ops-card__actions">
            <el-button @click="openPackagePreviewDialog()">预览规则包</el-button>
            <el-button type="primary" @click="openSourceCreateDialog">新增规则源</el-button>
          </div>
        </div>

        <div class="source-summary-grid">
          <div class="source-summary-tile">
            <span class="source-summary-tile__value">{{ sourceSummary.total }}</span>
            <span class="source-summary-tile__label">规则源总数</span>
          </div>
          <div class="source-summary-tile source-summary-tile--good">
            <span class="source-summary-tile__value">{{ sourceSummary.healthy_count }}</span>
            <span class="source-summary-tile__label">健康规则源</span>
          </div>
          <div class="source-summary-tile source-summary-tile--warn">
            <span class="source-summary-tile__value">{{ sourceSummary.degraded_count }}</span>
            <span class="source-summary-tile__label">待复核规则源</span>
          </div>
          <div class="source-summary-tile">
            <span class="source-summary-tile__value">{{ sourceSummary.trusted_count }}</span>
            <span class="source-summary-tile__label">受信生产规则</span>
          </div>
        </div>

        <el-table :data="sourceRows" v-loading="sourceLoading" class="sec-table source-ops-table" style="width: 100%">
          <el-table-column label="规则源" min-width="200">
            <template #default="{ row }">
              <div class="cell-stack">
                <span class="cell-ellipsis">{{ row.display_name }}</span>
                <span class="cell-sub cell-mono">{{ row.source_key }}</span>
                <span v-if="row.sync_endpoint" class="cell-sub cell-mono" :title="row.sync_endpoint">
                  {{ row.sync_endpoint }}
                </span>
                <span v-if="row.active_package_version" class="cell-sub">
                  当前激活包：{{ row.active_package_version }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="信任级别" width="168">
            <template #default="{ row }">
              <div class="cell-stack">
                <el-tag size="small" :type="sourceTrustClassificationTagType(row.trust_classification)">
                  {{ sourceTrustClassificationLabel(row.trust_classification) }}
                </el-tag>
                <span class="cell-sub">{{ sourceOperationalStatusLabel(row.operational_status) }} / {{ sourceSyncModeLabel(row.sync_mode) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="健康状态" width="170">
            <template #default="{ row }">
              <div class="cell-stack">
                <el-tag size="small" :type="sourceHealthTagType(row.health_state)">
                  {{ sourceHealthLabel(row.health_state) }}
                </el-tag>
                <span class="cell-sub" :title="row.visible_warning || '-'">{{ row.visible_warning || '当前无额外告警' }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="近期活动" width="144" align="center">
            <template #default="{ row }">
              <div class="cell-stack source-ops-table__metric">
                <span>{{ row.recent_incident_count }}</span>
                <span class="cell-sub">{{ fmtTableDateTime(row.recent_incident_last_seen_at) }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="最近同步" min-width="240">
            <template #default="{ row }">
              <div class="cell-stack">
                <div class="source-sync-line">
                  <el-tag size="small" :type="sourceSyncResultTagType(row.latest_sync_attempt?.result_status || row.last_sync_status)">
                    {{ sourceSyncResultLabel(row.latest_sync_attempt?.result_status || row.last_sync_status) }}
                  </el-tag>
                  <span class="cell-sub">{{ fmtTableDateTime(row.last_synced_at || row.latest_sync_attempt?.started_at) }}</span>
                </div>
                <span v-if="row.latest_sync_attempt?.package_version || row.latest_sync_attempt?.resolved_sync_endpoint" class="cell-sub">
                  {{ row.latest_sync_attempt?.package_version || 'pending-package' }} / {{ row.latest_sync_attempt?.resolved_sync_endpoint || row.sync_endpoint || '-' }}
                </span>
                <span class="cell-sub" :title="row.latest_sync_attempt?.detail || row.last_sync_detail || '-'">
                  {{ row.latest_sync_attempt?.detail || row.last_sync_detail || '等待首次同步' }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="规则包预览" min-width="220">
            <template #default="{ row }">
              <div class="cell-stack">
                <div class="source-sync-line" v-if="row.latest_package_preview">
                  <el-tag size="small" :type="packageVersionStateTagType(row.latest_package_preview.version_change_state)">
                    {{ packageVersionStateLabel(row.latest_package_preview.version_change_state) }}
                  </el-tag>
                  <span class="cell-sub">{{ row.latest_package_preview.package_version || '-' }}</span>
                </div>
                <div v-if="row.recent_package_intakes?.length" class="source-sync-line">
                  <el-tag size="small" :type="packageIntakeResultTagType(row.recent_package_intakes[0].intake_result)">
                    {{ packageIntakeResultLabel(row.recent_package_intakes[0].intake_result) }}
                  </el-tag>
                  <el-tag
                    size="small"
                    :type="sourceTrustClassificationTagType(row.recent_package_intakes[0].trust_classification)"
                  >
                    {{ sourceTrustClassificationLabel(row.recent_package_intakes[0].trust_classification) }}
                  </el-tag>
                </div>
                <span class="cell-sub" :title="row.latest_package_preview?.visible_warning || '-'">
                  {{ row.latest_package_preview?.visible_warning || '暂无新的规则包预览告警' }}
                </span>
                <span
                  v-if="row.recent_package_intakes?.[0]?.artifact_sha256 || row.recent_package_intakes?.[0]?.rule_count"
                  class="cell-sub"
                >
                  rules={{ row.recent_package_intakes?.[0]?.rule_count || 0 }} / {{ compactSha256(row.recent_package_intakes?.[0]?.artifact_sha256) }}
                </span>
                <span
                  v-if="row.recent_package_intakes?.[0]?.trust_classification === 'demo_test'"
                  class="cell-sub"
                >
                  待核验规则包仅保留留痕记录，不允许直接作为受信覆盖激活。
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="228" align="center">
            <template #default="{ row }">
              <div class="ids-ops ids-ops--row">
                <button type="button" class="ids-act ids-act--primary" @click="openSourceEditDialog(row)">编辑</button>
                <span class="ids-ops__sep" aria-hidden="true">|</span>
                <button type="button" class="ids-act" @click="openPackagePreviewDialog(row)">预览</button>
                <span class="ids-ops__sep" aria-hidden="true">|</span>
                <button type="button" class="ids-act ids-act--muted" @click="openPackageHistoryDialog(row)">历史</button>
                <span class="ids-ops__sep" aria-hidden="true">|</span>
                <button
                  type="button"
                  class="ids-act ids-act--ok"
                  :disabled="!canActivatePackageIntake(row.recent_package_intakes?.[0]) || (packageActivating && packageActivatingSourceId === row.id)"
                  @click="openPackageActivationDialog(row)"
                >
                  {{ packageActivating && packageActivatingSourceId === row.id ? '激活中...' : '激活' }}
                </button>
                <span class="ids-ops__sep" aria-hidden="true">|</span>
                <button
                  type="button"
                  class="ids-act"
                  :disabled="sourceSyncingId === row.id || (!row.sync_endpoint && row.sync_mode !== 'not_applicable')"
                  @click="runSourceSync(row)"
                >
                  {{ sourceSyncingId === row.id ? '同步中...' : '执行同步' }}
                </button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="tableClusters.length" class="ids-cluster-strip sec-card">
        <div class="ids-card-head">
          <div>
            <div class="chart-title">相似事件聚类</div>
            <div class="ids-card-subtitle">将当前页相似攻击聚成簇，减少列表分散感。</div>
          </div>
        </div>
        <div class="ids-cluster-strip__list">
          <button
            v-for="cluster in tableClusters"
            :key="cluster.key"
            type="button"
            class="ids-cluster-chip"
            @click="applyTableClusterFocus(cluster)"
          >
            <span>{{ cluster.attack_type_label }}</span>
            <span class="cell-mono">{{ cluster.path }}</span>
            <strong>{{ cluster.count }}</strong>
          </button>
        </div>
      </div>

      <div class="filter-bar">
        <el-input v-model="clientIpFilter" placeholder="来源 IP" clearable class="sec-input" />
        <el-select v-model="eventOriginFilter" placeholder="事件范围" clearable class="sec-select">
          <el-option label="真实事件" value="real" />
          <el-option label="测试事件" value="test" />
          <el-option label="全部事件" value="" />
        </el-select>
        <el-select v-model="attackTypeFilter" placeholder="攻击类型" clearable class="sec-select">
          <el-option label="SQL 注入" value="sql_injection" />
          <el-option label="XSS" value="xss" />
          <el-option label="XXE" value="xxe" />
          <el-option label="路径遍历" value="path_traversal" />
          <el-option label="命令注入" value="cmd_injection" />
          <el-option label="扫描器" value="scanner" />
          <el-option label="畸形请求" value="malformed" />
          <el-option label="JNDI 类" value="jndi_injection" />
          <el-option label="原型链污染" value="prototype_pollution" />
        </el-select>
        <el-select v-model="sourceClassificationFilter" placeholder="检测来源" clearable class="sec-select">
          <el-option label="成熟规则源" value="external_mature" />
          <el-option label="项目自定义" value="custom_project" />
          <el-option label="过渡本地检测" value="transitional_local" />
        </el-select>
        <el-select v-model="blockedFilter" placeholder="封禁状态" clearable class="sec-select">
          <el-option label="已封禁" :value="1" />
          <el-option label="仅记录" :value="0" />
        </el-select>
        <el-select v-model="archivedFilter" placeholder="归档状态" clearable class="sec-select">
          <el-option label="未归档" :value="0" />
          <el-option label="已归档" :value="1" />
        </el-select>
        <el-select v-model="statusFilter" placeholder="处置状态" clearable class="sec-select">
          <el-option label="新事件" value="new" />
          <el-option label="调查中" value="investigating" />
          <el-option label="已缓解" value="mitigated" />
          <el-option label="误报" value="false_positive" />
          <el-option label="已关闭" value="closed" />
        </el-select>
        <el-select v-model="minScoreFilter" placeholder="最低风险分" clearable class="sec-select">
          <el-option label="≥40" :value="40" />
          <el-option label="≥60" :value="60" />
          <el-option label="≥70" :value="70" />
          <el-option label="≥85" :value="85" />
        </el-select>
        <el-button type="primary" @click="handleSearch">查询</el-button>
        <el-button type="success" :disabled="!selectedIds.length" @click="handleBatchArchive">
          批量归档 ({{ selectedIds.length }})
        </el-button>
      </div>

      <div class="table-card sec-card ids-table-shell">
        <el-table
          :data="tableData"
          v-loading="loading"
          class="sec-table"
          style="width: 100%"
          :max-height="idsTableMaxHeight"
          @selection-change="handleSelectionChange"
        >
          <el-table-column type="selection" width="40" align="center" />
          <el-table-column label="时间" width="154" min-width="148">
            <template #default="{ row }">
              <span class="cell-ellipsis cell-time">{{ fmtTableDateTime(row.created_at) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="client_ip" label="源 IP" width="148" min-width="132">
            <template #default="{ row }">
              <span class="cell-ellipsis cell-mono">{{ row.client_ip }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="attack_type_label" label="类型" width="124" min-width="118" align="center">
            <template #default="{ row }">
              <el-tag :type="['sql_injection', 'xss', 'xxe', 'path_traversal', 'cmd_injection', 'command_injection', 'jndi_injection', 'malware'].includes(String(row.attack_type || '').trim().toLowerCase()) ? 'danger' : 'warning'" size="small" class="ids-table-tag ids-table-tag--clip">
                {{ localizeAttackTypeLabel(row.attack_type_label, row.attack_type) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="168" min-width="156">
            <template #default="{ row }">
              <div class="cell-stack">
                <span class="cell-ellipsis">{{ row.event_origin_label || '未标注' }}</span>
                <span class="cell-sub" :title="row.detector_name || sourceClassificationLabel(row.source_classification)">
                  {{ row.detector_name || sourceClassificationLabel(row.source_classification) }}
                </span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="method" label="方法" width="78" min-width="72" align="center">
            <template #default="{ row }">
              <span class="cell-ellipsis cell-mono">{{ row.method }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="path" label="路径" min-width="72">
            <template #default="{ row }">
              <span class="cell-path-ellipsis cell-mono">{{ row.path }}</span>
            </template>
          </el-table-column>
          <el-table-column label="风险" width="56" min-width="52" align="center" header-align="center">
            <template #default="{ row }">
              <span class="cell-ellipsis cell-mono">{{ row.risk_score ?? 0 }}</span>
            </template>
          </el-table-column>
          <el-table-column label="置信" width="64" min-width="58" align="center" header-align="center">
            <template #default="{ row }">
              <span class="cell-ellipsis cell-mono">{{ fmtConfidencePct(row.confidence) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="blocked" label="封禁" width="80" min-width="76" align="center">
            <template #default="{ row }">
              <el-tag :type="row.blocked ? 'success' : 'info'" size="small" class="ids-table-tag">
                {{ row.blocked ? '已封禁' : '仅记录' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="策略" width="64" min-width="56" align="center" header-align="center">
            <template #default="{ row }">
              <span class="ids-fw-cn">{{ fmtFirewallRuleTable(row.firewall_rule) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="84" min-width="80" align="center">
            <template #default="{ row }">
              <el-tag
                size="small"
                class="ids-table-tag"
                :type="row.status === 'closed' ? 'info' : row.status === 'false_positive' ? 'warning' : row.status === 'mitigated' ? 'success' : 'primary'"
              >
                {{
                  row.status === 'new'
                    ? '新事件'
                    : row.status === 'investigating'
                      ? '调查中'
                      : row.status === 'mitigated'
                        ? '已缓解'
                        : row.status === 'false_positive'
                          ? '误报'
                          : row.status === 'closed'
                            ? '已关闭'
                            : row.status || '-'
                }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="AI" width="52" min-width="48" align="center">
            <template #default="{ row }">
              <el-tag
                v-if="row.ai_risk_level"
                :type="aiRiskTagType(row.ai_risk_level) as any"
                size="small"
                class="ids-table-tag ids-table-tag--ai ids-table-tag--ai-cn"
              >
                {{ aiRiskLevelTableLabel(row.ai_risk_level) }}
              </el-tag>
              <span v-else class="muted-ai">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="248" min-width="232" align="center" header-align="center" fixed="right">
            <template #default="{ row }">
              <div class="ids-ops ids-ops--row">
                <button type="button" class="ids-act ids-act--primary" @click="showDetail(row)">查看</button>
                <span class="ids-ops__sep" aria-hidden="true">|</span>
                <button
                  type="button"
                  class="ids-act ids-act--warn"
                  :disabled="aiAnalyzingId === row.id"
                  @click="openAnalysisWorkbench(row, { autoAnalyze: true })"
                >
                  <span class="ai-btn-label">
                    研判
                    <span v-if="aiAnalyzingId === row.id" class="mini-orbit" />
                  </span>
                </button>
                <span class="ids-ops__sep" aria-hidden="true">|</span>
                <button type="button" class="ids-act ids-act--primary" @click="openReport(row)">报告</button>
                <span class="ids-ops__sep" aria-hidden="true">|</span>
                <el-dropdown trigger="click" @command="(cmd: string | number) => handleIdsMoreMenu(row, cmd)">
                  <button type="button" class="ids-act ids-act--muted">更多</button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="investigating">状态 → 调查中</el-dropdown-item>
                      <el-dropdown-item command="mitigated">状态 → 已缓解</el-dropdown-item>
                      <el-dropdown-item command="false_positive">状态 → 误报</el-dropdown-item>
                      <el-dropdown-item command="closed">状态 → 已关闭</el-dropdown-item>
                      <el-dropdown-item divided command="block">封禁 IP</el-dropdown-item>
                      <el-dropdown-item command="unblock">解封 IP</el-dropdown-item>
                      <el-dropdown-item v-if="!row.archived" divided command="archive">归档本条</el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </div>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          :current-page="Math.floor(pageOffset / pageSize) + 1"
          class="sec-pagination"
          @current-change="(p: number) => { pageOffset = (p - 1) * pageSize; fetchData() }"
        />
      </div>
    </main>

    <el-dialog
      v-model="packagePreviewDialogVisible"
      title="预览受信规则包"
      width="640px"
      destroy-on-close
    >
      <el-form label-width="160px" class="source-form-grid">
        <el-form-item label="规则源标识">
          <el-input v-model="packagePreviewForm.source_key" placeholder="suricata-web-prod" />
        </el-form-item>
        <el-form-item label="规则包版本">
          <el-input v-model="packagePreviewForm.package_version" placeholder="2026.04" />
        </el-form-item>
        <el-form-item label="信任级别">
          <el-select v-model="packagePreviewForm.trust_classification" class="sec-select">
            <el-option label="成熟外部规则" value="external_mature" />
            <el-option label="项目自定义规则" value="custom_project" />
            <el-option label="过渡本地规则" value="transitional_local" />
          </el-select>
        </el-form-item>
        <el-form-item label="检测家族">
          <el-select v-model="packagePreviewForm.detector_family" class="sec-select">
            <el-option label="网络" value="network" />
            <el-option label="网页" value="web" />
            <el-option label="文件" value="file" />
            <el-option label="日志" value="log" />
          </el-select>
        </el-form-item>
        <el-form-item label="触发人">
          <el-input v-model="packagePreviewForm.triggered_by" placeholder="ids_admin" />
        </el-form-item>
        <el-form-item label="来源说明">
          <el-input
            v-model="packagePreviewForm.provenance_note"
            type="textarea"
            :rows="4"
            placeholder="填写规则包来源、审阅说明或可信依据。"
          />
        </el-form-item>
      </el-form>
      <div v-if="latestPackagePreviewResult" class="detail-section">
        <div class="detail-section__title">最新预览结果</div>
        <div class="detail-tags">
          <el-tag size="small" :type="packageVersionStateTagType(latestPackagePreviewResult.version_change_state)">
            {{ packageVersionStateLabel(latestPackagePreviewResult.version_change_state) }}
          </el-tag>
          <el-tag size="small" type="info">{{ latestPackagePreviewResult.package_version }}</el-tag>
        </div>
        <div class="detail-grid">
          <div class="detail-item">
            <span class="detail-label">规则源标识</span>
            <span class="detail-value detail-value--mono">{{ latestPackagePreviewResult.source_key }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">变更字段</span>
            <span class="detail-value">{{ latestPackagePreviewResult.changed_fields?.join('、') || '无' }}</span>
          </div>
          <div class="detail-item detail-item--full">
            <span class="detail-label">风险提示</span>
            <span class="detail-value">{{ latestPackagePreviewResult.visible_warning || '暂无额外提示' }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="packagePreviewDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="packagePreviewing" @click="submitPackagePreview">执行预览</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="sourceDialogVisible"
      :title="editingSourceId ? '编辑规则源' : '新增规则源'"
      width="640px"
      destroy-on-close
    >
      <el-form label-width="160px" class="source-form-grid">
        <el-form-item label="规则源标识">
          <el-input v-model="sourceForm.source_key" placeholder="suricata-web-prod" />
        </el-form-item>
        <el-form-item label="显示名称">
            <el-input v-model="sourceForm.display_name" placeholder="Suricata Web 规则" />
        </el-form-item>
        <el-form-item label="信任级别">
          <el-select v-model="sourceForm.trust_classification" class="sec-select" @change="applySourceTrustDefaults">
            <el-option label="成熟外部规则" value="external_mature" />
            <el-option label="项目自定义规则" value="custom_project" />
            <el-option label="过渡本地规则" value="transitional_local" />
          </el-select>
        </el-form-item>
        <el-form-item label="检测家族">
          <el-select v-model="sourceForm.detector_family" class="sec-select">
            <el-option label="网络" value="network" />
            <el-option label="网页" value="web" />
            <el-option label="文件" value="file" />
            <el-option label="日志" value="log" />
          </el-select>
        </el-form-item>
        <el-form-item label="运行状态">
          <el-select v-model="sourceForm.operational_status" class="sec-select">
            <el-option label="启用" value="enabled" />
            <el-option label="停用" value="disabled" />
            <el-option label="异常" value="failing" />
            <el-option label="草稿" value="draft" />
          </el-select>
        </el-form-item>
        <el-form-item label="新鲜度目标（小时）">
          <el-input-number v-model="sourceForm.freshness_target_hours" :min="1" :max="720" />
        </el-form-item>
        <el-form-item label="同步方式">
          <el-select v-model="sourceForm.sync_mode" class="sec-select">
            <el-option label="手动" value="manual" />
            <el-option label="定时" value="scheduled" />
            <el-option label="不适用" value="not_applicable" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源说明">
          <el-input v-model="sourceForm.provenance_note" type="textarea" :rows="4" placeholder="说明该规则源为何可信，以及如何进入运行态覆盖。" />
        </el-form-item>
        <el-form-item label="Sync Endpoint">
          <el-input
            v-model="sourceForm.sync_endpoint"
            :disabled="sourceForm.sync_mode === 'not_applicable'"
            placeholder="app/data/ids_source_sync/suricata-web-prod.manifest.json"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sourceDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="sourceSaving" @click="saveSource">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="packageActivationDialogVisible"
      title="激活已审阅规则包"
      width="560px"
      destroy-on-close
      @closed="resetPackageActivationForm"
    >
      <el-form label-width="160px" class="source-form-grid">
        <div v-if="packageActivationTarget" class="detail-section">
          <div class="detail-section__title">本次激活对象</div>
          <div class="detail-tags">
            <el-tag size="small" :type="packageIntakeResultTagType(packageActivationTarget.intake.intake_result)">
              {{ packageIntakeResultLabel(packageActivationTarget.intake.intake_result) }}
            </el-tag>
            <el-tag size="small" :type="sourceTrustClassificationTagType(packageActivationTarget.intake.trust_classification)">
              {{ sourceTrustClassificationLabel(packageActivationTarget.intake.trust_classification) }}
            </el-tag>
            <el-tag size="small" type="info">{{ packageActivationTarget.intake.package_version }}</el-tag>
          </div>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">规则源</span>
              <span class="detail-value">{{ packageActivationTarget.displayName }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">规则源标识</span>
              <span class="detail-value detail-value--mono">{{ packageActivationTarget.sourceKey }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">预览时间</span>
              <span class="detail-value">{{ fmtTableDateTime(packageActivationTarget.intake.created_at) }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">预览说明</span>
              <span class="detail-value">{{ packageActivationTarget.intake.intake_detail || '暂无预览说明' }}</span>
            </div>
          </div>
        </div>
        <el-form-item label="规则包记录 ID">
          <el-input v-model="packageActivationForm.package_intake_id" disabled />
        </el-form-item>
        <el-form-item label="触发人">
          <el-input v-model="packageActivationForm.triggered_by" placeholder="ids_admin" />
        </el-form-item>
        <el-form-item label="激活说明">
          <el-input
            v-model="packageActivationForm.activation_note"
            type="textarea"
            :rows="4"
            placeholder="填写本次激活依据，例如：审阅通过后激活。"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="closePackageActivationDialog">取消</el-button>
        <el-button type="primary" :loading="packageActivating" @click="submitPackageActivation">确认激活</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="packageHistoryDialogVisible"
      title="规则包历史"
      width="760px"
      destroy-on-close
    >
      <div v-loading="packageHistoryLoading">
        <template v-if="packageHistory">
          <div class="detail-section">
            <div class="detail-section__title">当前规则包状态</div>
            <div class="detail-tags">
              <el-tag size="small" :type="sourceTrustClassificationTagType(packageHistory.source?.trust_classification)">
                {{ sourceTrustClassificationLabel(packageHistory.source?.trust_classification) }}
              </el-tag>
              <el-tag size="small" type="info">
                {{ packageHistory.active_package_version || '暂无激活规则包' }}
              </el-tag>
            </div>
            <div class="detail-grid">
              <div class="detail-item">
                <span class="detail-label">规则源</span>
                <span class="detail-value">{{ packageHistory.source?.display_name || packageHistory.source_key }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">规则源标识</span>
                <span class="detail-value detail-value--mono">{{ packageHistory.source_key }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">最近激活时间</span>
                <span class="detail-value">{{ fmtTableDateTime(packageHistory.active_package_activated_at) }}</span>
              </div>
              <div class="detail-item">
                <span class="detail-label">最近激活人</span>
                <span class="detail-value">{{ packageHistory.active_package_activated_by || '-' }}</span>
              </div>
            </div>
          </div>

          <div class="detail-section">
            <div class="detail-section__title">近期规则包接入记录</div>
            <div class="detail-section" v-if="packageHistorySource">
              <div class="detail-section__title">Sync Audit</div>
              <el-table :data="packageHistorySource.recent_sync_attempts || []" size="small" style="width: 100%">
                <el-table-column label="Result" width="132">
                  <template #default="{ row }">
                    <div class="cell-stack">
                      <el-tag size="small" :type="sourceSyncResultTagType(row.result_status)">
                        {{ sourceSyncResultLabel(row.result_status) }}
                      </el-tag>
                      <span class="cell-sub">{{ fmtTableDateTime(row.started_at) }}</span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="Package" min-width="168">
                  <template #default="{ row }">
                    <div class="cell-stack">
                      <span class="cell-mono">{{ row.package_version || '-' }}</span>
                      <span class="cell-sub cell-mono">{{ row.resolved_sync_endpoint || packageHistorySource?.sync_endpoint || '-' }}</span>
                    </div>
                  </template>
                </el-table-column>
                <el-table-column label="Operator" width="128">
                  <template #default="{ row }">
                    <span>{{ row.triggered_by || '-' }}</span>
                  </template>
                </el-table-column>
                <el-table-column label="Detail" min-width="260">
                  <template #default="{ row }">
                    <span class="cell-sub">{{ row.detail || '-' }}</span>
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <el-table :data="packageHistory.recent_intakes" size="small" style="width: 100%">
              <el-table-column label="版本" min-width="128">
                <template #default="{ row }">
                  <div class="cell-stack">
                    <span class="cell-mono">{{ row.package_version || '-' }}</span>
                    <span class="cell-sub">{{ fmtTableDateTime(row.created_at) }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="144">
                <template #default="{ row }">
                  <div class="cell-stack">
                    <el-tag size="small" :type="packageHistoryStateTagType(row, null)">
                      {{ packageHistoryStateLabel(row, null) }}
                    </el-tag>
                    <el-tag size="small" :type="sourceTrustClassificationTagType(row.trust_classification)">
                      {{ sourceTrustClassificationLabel(row.trust_classification) }}
                    </el-tag>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="操作人" width="128">
                <template #default="{ row }">
                  <span>{{ row.triggered_by || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="说明" min-width="260">
                <template #default="{ row }">
                  <span class="cell-sub">{{ row.intake_detail || '暂无接入说明' }}</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="detail-section">
            <div class="detail-section__title">近期激活记录</div>
            <el-table :data="packageHistory.recent_activations" size="small" style="width: 100%">
              <el-table-column label="版本" min-width="128">
                <template #default="{ row }">
                  <div class="cell-stack">
                    <span class="cell-mono">{{ row.package_version || '-' }}</span>
                    <span class="cell-sub">{{ fmtTableDateTime(row.activated_at) }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="120">
                <template #default="{ row }">
                  <el-tag size="small" :type="packageHistoryStateTagType(null, row)">
                    {{ packageHistoryStateLabel(null, row) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作人" width="128">
                <template #default="{ row }">
                  <span>{{ row.activated_by || '-' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="说明" min-width="260">
                <template #default="{ row }">
                  <span class="cell-sub">{{ row.activation_detail || '暂无激活说明' }}</span>
                </template>
              </el-table-column>
            </el-table>
            <div v-if="!packageHistory.recent_activations.length" class="detail-value">
              暂无激活历史记录。
            </div>
          </div>
        </template>
        <div v-else class="detail-value">
          当前规则源暂无规则包历史。
        </div>
      </div>
      <template #footer>
        <el-button @click="packageHistoryDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="idsRiskAlertVisible"
      :title="idsRiskAlertCurrent?.alert_profile?.title || '高危 IDS 风险预警'"
      width="640px"
      class="ids-risk-alert-dialog"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      append-to-body
      @closed="dismissIdsRiskAlert"
    >
      <template v-if="idsRiskAlertCurrent">
        <div class="ids-risk-alert">
          <div class="ids-risk-alert__headline">
            <span class="ids-risk-alert__badge">HIGH</span>
            <div>
              <div class="ids-risk-alert__title">{{ idsAlertAttackTitle(idsRiskAlertCurrent) }}</div>
              <div class="ids-risk-alert__subtitle">
                事件 #{{ idsRiskAlertCurrent.id }}，风险分 {{ idsRiskAlertCurrent.risk_score ?? '-' }}，来源 {{ idsAlertDetector(idsRiskAlertCurrent) }}
              </div>
            </div>
          </div>

          <div class="ids-risk-alert__grid">
            <div class="ids-risk-alert__item">
              <span class="ids-risk-alert__label">客户端 IP</span>
              <span class="ids-risk-alert__value">{{ idsRiskAlertCurrent.client_ip || '-' }}</span>
            </div>
            <div class="ids-risk-alert__item">
              <span class="ids-risk-alert__label">事件时间</span>
              <span class="ids-risk-alert__value">{{ idsRiskAlertCurrent.created_at || '-' }}</span>
            </div>
            <div class="ids-risk-alert__item ids-risk-alert__item--full">
              <span class="ids-risk-alert__label">请求目标</span>
              <span class="ids-risk-alert__value">{{ idsRiskAlertCurrent.method }} {{ idsRiskAlertCurrent.path || '-' }}</span>
            </div>
            <div class="ids-risk-alert__item ids-risk-alert__item--full">
              <span class="ids-risk-alert__label">拦截依据</span>
              <span class="ids-risk-alert__value ids-risk-alert__value--multiline">{{ idsAlertEvidence(idsRiskAlertCurrent) }}</span>
            </div>
          </div>

          <div class="ids-risk-alert__hint">
            {{ idsRiskAlertQueue.length ? `队列中还有 ${idsRiskAlertQueue.length} 条高危事件，关闭当前弹窗后会继续告警。` : '这是当前最新的一条待处理高危事件。' }}
          </div>
        </div>
      </template>

      <template #footer>
        <div class="ids-risk-alert__actions">
          <el-button @click="handleIdsRiskAlertClose">关闭</el-button>
          <el-button @click="handleIdsRiskAlertMuteToday">今日不再弹出</el-button>
          <el-button type="danger" @click="handleIdsRiskAlertJump">定位当前事件</el-button>
        </div>
      </template>
    </el-dialog>

    <el-drawer v-model="detailVisible" title="事件详情" size="480" class="sec-drawer">
      <template v-if="currentRow">
        <p><strong>时间：</strong>{{ currentRow.created_at }}</p>
        <p><strong>来源 IP：</strong>{{ currentRow.client_ip }}</p>
        <p><strong>攻击类型：</strong>{{ currentRow.attack_type_label }}</p>
        <p><strong>匹配特征：</strong>{{ currentRow.signature_matched }}</p>
        <p><strong>方法：</strong>{{ currentRow.method }}</p>
        <p><strong>路径：</strong>{{ currentRow.path }}</p>
        <p><strong>Query 片段：</strong>{{ currentRow.query_snippet || '-' }}</p>
        <p><strong>Body 片段：</strong>{{ currentRow.body_snippet || '-' }}</p>
        <p><strong>User-Agent：</strong>{{ currentRow.user_agent || '-' }}</p>
        <p><strong>封禁：</strong>{{ currentRow.blocked ? '是' : '否' }}</p>
        <p><strong>防火墙规则：</strong>{{ currentRow.firewall_rule || '-' }}</p>
        <p><strong>风险评分：</strong>{{ currentRow.risk_score || 0 }} / 100（置信度 {{ fmtConfidencePct(currentRow.confidence) }}）</p>
        <p><strong>命中数量：</strong>{{ currentRow.hit_count || 0 }}</p>
        <p><strong>处置状态：</strong>{{ currentRow.status || 'new' }}</p>
        <p><strong>处置备注：</strong>{{ currentRow.review_note || '-' }}</p>
        <div v-if="decisionBasis(currentRow)" class="detail-section">
          <div class="detail-section__title">研判来源</div>
          <div class="detail-tags">
            <el-tag size="small" type="warning">
              {{ decisionSourceLabel(decisionBasis(currentRow)?.final_source) }}
            </el-tag>
            <el-tag size="small" type="info">
              {{ decisionBasis(currentRow)?.static_source_label || '-' }}
            </el-tag>
            <el-tag size="small" type="info">
              {{ decisionBasis(currentRow)?.analysis_mode_label || decisionBasis(currentRow)?.analysis_mode || '-' }}
            </el-tag>
          </div>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">静态风险分</span>
              <span class="detail-value">{{ decisionBasis(currentRow)?.static_risk_score ?? '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">阻断阈值</span>
              <span class="detail-value">{{ decisionBasis(currentRow)?.block_threshold ?? '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">规则置信度</span>
              <span class="detail-value">{{ decisionBasis(currentRow)?.rule_confidence ?? '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">LLM 已调用 / AI 可用</span>
              <span class="detail-value">
                {{ decisionBasis(currentRow)?.llm_used ? '是' : '否' }} / {{ decisionBasis(currentRow)?.ai_available ? '是' : '否' }}
              </span>
            </div>
          </div>
        </div>
        <div v-if="requestPacket(currentRow)" class="detail-section">
          <div class="detail-section__title">攻击请求包</div>
          <div class="detail-grid">
            <div class="detail-item detail-item--full">
              <span class="detail-label">请求行</span>
              <span class="detail-value detail-value--mono">{{ requestPacket(currentRow)?.request_line || '-' }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">请求头摘要</span>
              <span class="detail-value">{{ requestPacket(currentRow)?.headers_snippet || currentRow.headers_snippet || '-' }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">原始请求</span>
              <pre class="ai-text">{{ requestPacket(currentRow)?.raw_request || '-' }}</pre>
            </div>
          </div>
        </div>
        <div v-if="matchedHits(currentRow).length" class="detail-section">
          <div class="detail-section__title">命中静态规则</div>
          <div
            v-for="hit in matchedHits(currentRow)"
            :key="`${currentRow.id}-${hit.id || hit.source_rule_id || hit.signature_matched}`"
            class="detail-item detail-item--full"
          >
            <span class="detail-label">
              {{ hit.source_rule_id || '-' }} / {{ hit.source_rule_name || '-' }} ({{ hit.detector_name || '-' }} {{ hit.source_version || '-' }})
            </span>
            <span class="detail-value">{{ hit.signature_matched || hit.pattern || '-' }}</span>
            <span class="detail-value">命中位置 {{ hit.matched_part || 'request' }} => {{ hit.matched_value || '-' }}</span>
          </div>
        </div>
        <div class="detail-section">
          <div class="detail-section__title">来源与响应</div>
          <div class="detail-tags">
            <el-tag size="small" type="info">{{ currentRow.event_origin_label || '-' }}</el-tag>
            <el-tag size="small" :type="sourceClassificationTagType(currentRow.source_classification)">
              {{ sourceClassificationLabel(currentRow.source_classification) }}
            </el-tag>
            <el-tag size="small" type="info">{{ sourceFreshnessLabel(currentRow.source_freshness) }}</el-tag>
            <el-tag size="small" :type="responseResultTagType(currentRow.response_result)">
              {{ responseResultLabel(currentRow.response_result) }}
            </el-tag>
          </div>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">检测器</span>
              <span class="detail-value">{{ currentRow.detector_name || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">检测家族</span>
              <span class="detail-value">{{ currentRow.detector_family || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">规则 ID</span>
              <span class="detail-value detail-value--mono">{{ currentRow.source_rule_id || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">规则版本</span>
              <span class="detail-value">{{ currentRow.source_version || '-' }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">响应说明</span>
              <span class="detail-value">{{ currentRow.response_detail || '-' }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">事件指纹</span>
              <span class="detail-value detail-value--mono">{{ currentRow.event_fingerprint || '-' }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">关联键</span>
              <span class="detail-value detail-value--mono">{{ currentRow.correlation_key || '-' }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">指标口径</span>
              <span class="detail-value">{{ currentRow.counted_in_real_metrics ? '计入真实指标' : '不计入真实指标' }}</span>
            </div>
          </div>
        </div>
        <div v-if="currentRow.upload_trace" class="detail-section">
          <div class="detail-section__title">上传审计链</div>
          <div class="detail-tags">
            <el-tag size="small" :type="uploadAuditTagType(currentRow.upload_trace)">
              {{ uploadAuditVerdictLabel(currentRow.upload_trace) }}
            </el-tag>
            <el-tag size="small" type="warning">
              {{ currentRow.upload_trace.audit?.risk_level || '-' }}
            </el-tag>
            <el-tag size="small" type="info">
              {{ formatBytes(currentRow.upload_trace.size) }}
            </el-tag>
          </div>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">保存名</span>
              <span class="detail-value detail-value--mono">{{ currentRow.upload_trace.saved_as || '-' }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">原始文件名</span>
              <span class="detail-value">{{ currentRow.upload_trace.file_name || '-' }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">SHA-256</span>
              <span class="detail-value detail-value--mono">{{ currentRow.upload_trace.sha256 || '-' }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">审计摘要</span>
              <span class="detail-value">{{ currentRow.upload_trace.audit?.summary || '-' }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">审计模式</span>
              <span class="detail-value">
                {{ currentRow.upload_trace.audit?.analysis_mode_label || currentRow.upload_trace.audit?.analysis_mode || '-' }}
                / LLM {{ currentRow.upload_trace.audit?.llm_used ? '是' : '否' }}
                / AI {{ currentRow.upload_trace.audit?.ai_available ? '是' : '否' }}
              </span>
            </div>
            <div
              v-if="currentRow.upload_trace.indicators?.length"
              class="detail-item detail-item--full"
            >
              <span class="detail-label">命中指标</span>
              <div
                v-for="indicator in currentRow.upload_trace.indicators"
                :key="`${currentRow.id}-${indicator.code}-${indicator.detail}`"
                class="detail-value"
              >
                {{ indicator.code }}: {{ indicator.detail || '-' }}
              </div>
            </div>
          </div>
          <div class="detail-actions">
            <el-button size="small" type="warning" @click="openSandboxReportFromEvent(currentRow)">
              打开沙箱报告
            </el-button>
          </div>
        </div>
        <div v-if="currentInsight?.profile" class="detail-section">
          <div class="detail-section__title">攻击画像卡</div>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">来源地</span>
              <span class="detail-value">
                {{ localizeGeoLabel(currentInsight.profile.source_location.country) }} / {{ localizeGeoLabel(currentInsight.profile.source_location.city) }}
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">UA 家族</span>
              <span class="detail-value">{{ localizeUaFamily(currentInsight.profile.user_agent_family) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">同源历史事件</span>
              <span class="detail-value">{{ currentInsight.profile.total_events_from_ip }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">同源高危事件</span>
              <span class="detail-value">{{ currentInsight.profile.high_risk_events_from_ip }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">UA 样本</span>
              <span class="detail-value">{{ currentInsight.profile.user_agent_sample || '-' }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">高频路径</span>
              <span class="detail-value">{{ formatProfileTopPaths(currentInsight.profile.top_paths) }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">历史行为</span>
              <span class="detail-value">{{ formatProfileBehaviors(currentInsight.profile.historical_behaviors) }}</span>
            </div>
          </div>
        </div>

        <div v-if="currentInsight?.timeline" class="detail-section">
          <div class="detail-section__title">攻击链时间线</div>
          <div class="timeline-loading-note">
            关联方式：{{ currentInsight.timeline.basis === 'correlation_key' ? '同一事件链路' : '同一来源 IP' }}
          </div>
          <div class="timeline-container">
            <div v-if="!currentInsight.timeline.items.length" class="timeline-empty">暂无攻击链时间线</div>
            <div v-for="item in currentInsight.timeline.items" :key="`timeline-${item.id}`" class="chain-card">
              <div class="chain-card__head">
                <strong>#{{ item.id }} {{ localizeAttackTypeLabel(item.attack_type_label, item.attack_type) }}</strong>
                <span>{{ item.created_at || '-' }}</span>
              </div>
              <div class="chain-card__meta">
                <span>{{ item.method }} {{ item.path }}</span>
                <span>风险 {{ item.risk_score }}</span>
                <span>{{ eventStatusLabel(item.status) }}</span>
              </div>
              <div class="chain-card__body">{{ item.response_detail || item.signature_matched || '-' }}</div>
            </div>
          </div>
        </div>

        <div v-if="currentInsight?.cluster" class="detail-section">
          <div class="detail-section__title">相似事件聚类</div>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">聚类总数</span>
              <span class="detail-value">{{ currentInsight.cluster.total }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">同类攻击</span>
              <span class="detail-value">{{ currentInsight.cluster.same_attack_type_total }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">同签名</span>
              <span class="detail-value">{{ currentInsight.cluster.same_signature_total }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">同路径</span>
              <span class="detail-value">{{ currentInsight.cluster.same_path_total }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">聚类摘要</span>
              <span class="detail-value">{{ clusterSummaryLabel() }}</span>
            </div>
          </div>
        </div>

        <div v-if="currentInsight?.false_positive_learning" class="detail-section">
          <div class="detail-section__title">误报学习</div>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">匹配学习记录</span>
              <span class="detail-value">{{ currentInsight.false_positive_learning.matched_learning_events }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">最近学习时间</span>
              <span class="detail-value">{{ currentInsight.false_positive_learning.last_learned_at || '-' }}</span>
            </div>
            <div class="detail-item detail-item--full">
              <span class="detail-label">建议</span>
              <span class="detail-value">{{ currentInsight.false_positive_learning.recommendation }}</span>
            </div>
            <div
              v-for="signal in currentInsight.false_positive_learning.signals"
              :key="`fp-${signal.kind}-${signal.pattern}`"
              class="detail-item detail-item--full"
            >
              <span class="detail-label">{{ falsePositiveSignalKindLabel(signal.kind) }} / {{ falsePositiveSignalSourceLabel(signal.source) }}</span>
              <span class="detail-value">{{ signal.pattern }} ({{ signal.count }}) - {{ signal.recommendation }}</span>
            </div>
          </div>
          <div class="detail-actions">
            <el-button size="small" type="warning" @click="handleUpdateStatus(currentRow, 'false_positive')">
              标记为误报并沉淀经验
            </el-button>
          </div>
        </div>

        <div class="detail-section">
          <div class="detail-section__title">处置建议卡</div>
          <div class="detail-actions">
            <el-button size="small" type="danger" @click="currentRow.blocked ? handleManualUnblock(currentRow) : handleManualBlock(currentRow)">
              {{ currentRow.blocked ? '解除封禁 IP' : '封禁 IP' }}
            </el-button>
            <el-button size="small" @click="handleArchive(currentRow)">
              归档事件
            </el-button>
            <el-button size="small" @click="openReport(currentRow, true)">导出报告</el-button>
            <el-button size="small" @click="exportEvidencePackage(currentRow)">导出证据包</el-button>
            <el-button size="small" type="primary" @click="openAnalysisWorkbench(currentRow, { autoAnalyze: true })">
              F2 分析工作台
            </el-button>
          </div>
        </div>

        <div class="ai-block">
          <p class="ai-head">
            <strong>AI 研判</strong>
            <el-tag v-if="currentRow.ai_risk_level" :type="aiRiskTagType(currentRow.ai_risk_level) as any" size="small">
              {{ currentRow.ai_risk_level }}
            </el-tag>
            <span class="ai-time">置信度 {{ fmtConfidencePct(currentRow.ai_confidence) }}</span>
            <span v-if="currentRow.ai_analyzed_at" class="ai-time">{{ currentRow.ai_analyzed_at }}</span>
          </p>
          <pre v-if="currentRow.ai_analysis" class="ai-text">{{ currentRow.ai_analysis }}</pre>
          <p v-else class="ai-empty">暂未生成 AI 研判，可手动触发分析；未配置 LLM 时将仅展示静态证据结果。</p>
          <el-button type="primary" size="small" :loading="aiAnalyzingId === currentRow.id" @click="handleAiAnalyze(currentRow)">
            重新研判
          </el-button>
          <el-button size="small" @click="openReport(currentRow, true)">生成报告（强制AI）</el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog
      v-model="analysisWorkbenchVisible"
      width="980px"
      class="timeline-modal"
      modal-class="timeline-modal-overlay"
    >
      <template #header>
        <div class="report-header">
          <span>F2 攻击分析工作台</span>
          <div class="report-actions">
            <el-button size="small" @click="exportEvidencePackage(currentRow)">导出证据包</el-button>
            <el-button size="small" @click="testNotificationDispatch(currentRow)">发送通知</el-button>
            <el-button
              type="primary"
              size="small"
              :loading="aiAnalyzingId === currentRow?.id"
              @click="currentRow && handleAiAnalyze(currentRow, { skipProcessOverlay: true })"
            >
              重新研判
            </el-button>
          </div>
        </div>
      </template>
      <div v-loading="analysisWorkbenchLoading || insightLoading">
        <template v-if="currentRow">
          <div class="ids-analysis-hero">
            <div class="ids-analysis-hero__badge">实时分析</div>
            <h3>{{ idsAlertAttackTitle(currentRow) }}</h3>
            <p>事件 #{{ currentRow.id }} / 风险分 {{ currentRow.risk_score || 0 }} / {{ currentRow.method }} {{ currentRow.path }}</p>
          </div>
          <div class="ids-analysis-steps">
            <div class="ids-analysis-step active">
              <strong>1. 攻击识别</strong>
              <span>{{ localizeAttackTypeLabel(currentRow.attack_type_label, currentRow.attack_type) }}</span>
            </div>
            <div class="ids-analysis-step active">
              <strong>2. 证据提取</strong>
              <span>{{ currentRow.signature_matched || currentRow.response_detail || '-' }}</span>
            </div>
            <div class="ids-analysis-step active">
              <strong>3. 处置判断</strong>
              <span>{{ currentRow.blocked ? '已拦截' : '仅记录' }} / {{ eventStatusLabel(currentRow.status) }}</span>
            </div>
            <div class="ids-analysis-step" :class="{ active: !!currentRow.ai_analysis }">
              <strong>4. AI 结论</strong>
              <span>{{ riskLevelLabel(currentRow.ai_risk_level) }}</span>
            </div>
          </div>
          <div class="ids-analysis-grid">
            <div class="ids-analysis-card">
              <div class="ids-analysis-card__title">攻击画像</div>
              <p>来源 IP: {{ currentRow.client_ip }}</p>
              <p>地理位置: {{ localizeGeoLabel(currentInsight?.profile?.source_location?.country) }} / {{ localizeGeoLabel(currentInsight?.profile?.source_location?.city) }}</p>
              <p>UA: {{ localizeUaFamily(currentInsight?.profile?.user_agent_family) }}</p>
              <p>历史行为: {{ formatProfileBehaviors(currentInsight?.profile?.historical_behaviors) }}</p>
            </div>
            <div class="ids-analysis-card">
              <div class="ids-analysis-card__title">聚类摘要</div>
              <p>{{ clusterSummaryLabel() }}</p>
              <p>聚类事件: {{ currentInsight?.cluster?.total || 0 }}</p>
              <p>同签名: {{ currentInsight?.cluster?.same_signature_total || 0 }}</p>
              <p>同路径: {{ currentInsight?.cluster?.same_path_total || 0 }}</p>
            </div>
            <div class="ids-analysis-card ids-analysis-card--wide">
              <div class="ids-analysis-card__title">攻击链时间线</div>
              <div v-if="currentInsight?.timeline?.items?.length" class="ids-analysis-timeline">
                <div v-for="item in currentInsight.timeline.items" :key="`awb-${item.id}`" class="ids-analysis-timeline__item">
                  <strong>#{{ item.id }}</strong>
                  <span>{{ item.created_at || '-' }}</span>
                  <span>{{ localizeAttackTypeLabel(item.attack_type_label, item.attack_type) }}</span>
                  <span>{{ item.method }} {{ item.path }}</span>
                </div>
              </div>
              <div v-else class="timeline-empty">暂无时间线</div>
            </div>
            <div class="ids-analysis-card ids-analysis-card--wide">
              <div class="ids-analysis-card__title">误报学习与处置建议</div>
              <p>{{ currentInsight?.false_positive_learning?.recommendation || '暂无误报学习建议' }}</p>
              <div v-if="currentInsight?.false_positive_learning?.signals?.length" class="ids-mini-list">
                <div
                  v-for="signal in currentInsight.false_positive_learning.signals"
                  :key="`awb-signal-${signal.kind}-${signal.pattern}`"
                  class="ids-mini-list__row"
                >
                  <span>{{ falsePositiveSignalKindLabel(signal.kind) }} / {{ signal.pattern }}</span>
                  <strong>{{ signal.count }}</strong>
                </div>
              </div>
              <div class="detail-actions">
                <el-button size="small" type="danger" @click="currentRow.blocked ? handleManualUnblock(currentRow) : handleManualBlock(currentRow)">
                  {{ currentRow.blocked ? '解除封禁 IP' : '封禁 IP' }}
                </el-button>
                <el-button size="small" type="warning" @click="handleUpdateStatus(currentRow, 'false_positive')">标记误报</el-button>
                <el-button size="small" @click="handleArchive(currentRow)">归档</el-button>
                <el-button size="small" @click="openReport(currentRow, true)">导出报告</el-button>
              </div>
            </div>
            <div class="ids-analysis-card ids-analysis-card--wide">
              <div class="ids-analysis-card__title">AI 结论</div>
              <pre class="ai-text">{{ currentRow.ai_analysis || '当前尚未生成 AI 研判，工作台已展示规则命中、请求包与关联证据。' }}</pre>
            </div>
          </div>
        </template>
      </div>
    </el-dialog>

    <el-dialog
      v-model="notificationDialogVisible"
      title="IDS 联动通知配置"
      width="720px"
      class="notification-config-modal"
      destroy-on-close
    >
      <div class="detail-grid">
        <div class="detail-item detail-item--full">
          <span class="detail-label">邮件 SMTP</span>
          <el-switch v-model="notificationSettings.email.enabled" inline-prompt active-text="开" inactive-text="关" />
        </div>
        <div class="detail-item">
          <span class="detail-label">SMTP 地址</span>
          <el-input v-model="notificationSettings.email.smtp_host" placeholder="smtp.example.com" />
        </div>
        <div class="detail-item">
          <span class="detail-label">SMTP 端口</span>
          <el-input-number v-model="notificationSettings.email.smtp_port" :min="1" :max="65535" />
        </div>
        <div class="detail-item">
          <span class="detail-label">用户名</span>
          <el-input v-model="notificationSettings.email.username" placeholder="ids@example.com" />
        </div>
        <div class="detail-item">
          <span class="detail-label">密码</span>
          <el-input v-model="notificationSettings.email.password" type="password" placeholder="留空则保留已有密码" show-password />
        </div>
        <div class="detail-item">
          <span class="detail-label">发件人</span>
          <el-input v-model="notificationSettings.email.from_addr" placeholder="ids@example.com" />
        </div>
        <div class="detail-item">
          <span class="detail-label">收件人</span>
          <el-input v-model="notificationSettings.email.to_addrs" placeholder="a@example.com,b@example.com" />
        </div>
        <div class="detail-item">
          <span class="detail-label">企业微信机器人</span>
          <el-switch v-model="notificationSettings.wecom.enabled" inline-prompt active-text="开" inactive-text="关" />
        </div>
        <div class="detail-item detail-item--full">
          <span class="detail-label">企业微信 Webhook</span>
          <el-input v-model="notificationSettings.wecom.webhook_url" placeholder="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=..." />
        </div>
        <div class="detail-item">
          <span class="detail-label">Webhook</span>
          <el-switch v-model="notificationSettings.webhook.enabled" inline-prompt active-text="开" inactive-text="关" />
        </div>
        <div class="detail-item detail-item--full">
          <span class="detail-label">Webhook 地址</span>
          <el-input v-model="notificationSettings.webhook.url" placeholder="https://example.com/ids-hook" />
        </div>
        <div class="detail-item detail-item--full">
          <span class="detail-label">Webhook 密钥</span>
          <el-input v-model="notificationSettings.webhook.secret" type="password" placeholder="留空则保留已有密钥" show-password />
        </div>
      </div>
      <template #footer>
        <el-button @click="testNotificationDispatch(currentRow)">测试通知</el-button>
        <el-button @click="notificationDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="notificationSaving" @click="saveNotificationSettingsForm">保存配置</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="reportVisible"
      title="安全事件分析报告"
      width="860px"
      class="report-modal"
      modal-class="report-modal-overlay"
    >
      <template #header>
        <div class="report-header">
          <span>{{ reportMeta.title }} · {{ reportMeta.headerSuffix }}</span>
          <div class="report-actions">
            <el-button size="small" @click="exportReport('md')">导出 MD</el-button>
            <el-button size="small" @click="exportReport('html')">导出 HTML</el-button>
            <el-button type="primary" size="small" @click="exportReport('pdf')">导出 PDF</el-button>
          </div>
        </div>
      </template>
      <div ref="reportContainerRef" class="report-panel">
        <div v-if="reportData" class="report-cover">
          <div class="report-cover-title">校园物资供应链安全监测平台</div>
          <div class="report-cover-subtitle">{{ reportCoverSubtitle() }}</div>
          <div class="report-cover-badges">
            <el-tag :type="aiRiskTagType(reportData?.score?.ai_risk_level) as any" effect="dark" size="small">
              {{ riskLevelLabel(reportData?.score?.ai_risk_level) }}
            </el-tag>
            <el-tag type="info" effect="plain" size="small">事件指纹 {{ reportFingerprint() }}</el-tag>
          </div>
          <div class="report-kv">
            <span>报告编号：{{ reportMeta.reportNo || '-' }}</span>
            <span>生成时间：{{ reportMeta.generatedAt || '-' }}</span>
            <span>事件ID：{{ reportData?.event_id || '-' }}</span>
            <span>风险分：{{ reportData?.score?.risk_score ?? '-' }} / 100</span>
          </div>
          <div class="report-conclusion">
            <strong>处置结论：</strong>{{ reportConclusionText() }}
          </div>
        </div>
        <div v-if="reportData" class="report-grid">
          <div class="report-card">
            <h4>事件概览</h4>
            <p>时间：{{ reportData?.overview?.time || '-' }}</p>
            <p>来源IP：{{ reportData?.overview?.client_ip || '-' }}</p>
            <p>类型：{{ reportData?.overview?.attack_type_label || '-' }}</p>
            <p>路径：{{ reportData?.overview?.method || '-' }} {{ reportData?.overview?.path || '-' }}</p>
          </div>
          <div class="report-card">
            <h4>风险评估</h4>
            <p>规则风险分：{{ reportData?.score?.risk_score ?? '-' }}</p>
            <p>规则置信度：{{ reportData?.score?.rule_confidence ?? '-' }}</p>
            <p>AI风险等级：{{ riskLevelLabel(reportData?.score?.ai_risk_level) }}</p>
            <p>AI置信度：{{ reportData?.score?.ai_confidence ?? '-' }}</p>
          </div>
          <div class="report-card report-card-full">
            <h4>关键证据与处置</h4>
            <p>特征：{{ reportData?.evidence?.signature || '-' }}</p>
            <p>处置动作：{{ reportData?.response?.action_taken || '-' }}</p>
            <p>封禁状态：{{ reportData?.response?.blocked ? '已封禁' : '仅记录' }}</p>
          </div>
        </div>
        <pre class="ai-text report-text">{{ reportMarkdown || '暂无报告内容' }}</pre>
        <div v-if="reportData" class="report-grid">
          <div class="report-card report-card-full">
            <h4>静态规则证据</h4>
            <p>研判来源：{{ decisionSourceLabel(reportDecisionBasis()?.final_source) }}</p>
            <p>静态来源：{{ reportDecisionBasis()?.static_source_label || reportDecisionBasis()?.static_source_mode || '-' }}</p>
            <p>静态分值 / 阈值：{{ reportDecisionBasis()?.static_risk_score ?? '-' }} / {{ reportDecisionBasis()?.block_threshold ?? '-' }}</p>
            <div v-if="reportMatchedHits().length" class="report-list-block">
              <ul>
                <li
                  v-for="hit in reportMatchedHits()"
                  :key="`report-hit-${hit.id || hit.source_rule_id || hit.signature_matched}`"
                >
                  {{
                    `${hit.source_rule_id || '-'} ${hit.source_rule_name || '-'} | ${hit.signature_matched || hit.pattern || '-'} | ${hit.matched_part || 'request'}: ${hit.matched_value || '-'}`
                  }}
                </li>
              </ul>
            </div>
            <p v-else>后端未返回更详细的静态命中内容。</p>
          </div>
          <div class="report-card report-card-full">
            <h4>AI 研判</h4>
            <p>分析模式：{{ reportAnalysisModeLabel() }}</p>
            <p>AI 状态：LLM {{ reportAiStatus()?.llm_used ? '已启用' : '未启用' }} / AI {{ reportAiStatus()?.ai_available ? '可用' : '不可用' }}</p>
            <p>AI 风险 / 置信度：{{ riskLevelLabel(reportAiStatus()?.ai_risk_level || reportData?.score?.ai_risk_level) }} / {{ reportAiStatus()?.ai_confidence ?? reportData?.score?.ai_confidence ?? '-' }}</p>
            <pre class="ai-text report-text report-text--inline">{{ reportData?.ai_analysis || '后端尚未返回 AI 研判正文。' }}</pre>
          </div>
          <div v-if="reportPacket()" class="report-card report-card-full">
            <h4>请求包</h4>
            <p>请求行：{{ reportPacket()?.request_line || '-' }}</p>
            <p>请求头摘要：{{ reportPacket()?.headers_snippet || '-' }}</p>
          </div>
        </div>
        <div class="report-footer-sign">
          <span>平台签章：校园物资供应链安全监测平台</span>
          <span>审计用途：答辩留档 / 安全复盘</span>
        </div>
      </div>
    </el-dialog>
    <el-dialog
      v-model="aiProcessVisible"
      width="760px"
      :show-close="false"
      :close-on-click-modal="false"
      :close-on-press-escape="false"
      class="ai-process-modal"
      modal-class="ai-process-overlay"
    >
      <div class="ai-process-wrap" :class="`mode-${aiProcessMode}`">
        <div class="ai-process-bg-grid" />
        <div class="ai-process-bg-beam" />
        <div class="ai-process-core">
          <div class="pulse pulse-1" />
          <div class="pulse pulse-2" />
          <div class="pulse pulse-3" />
          <div class="core-dot" />
        </div>
        <div class="ai-process-title">
          AI 研判执行中
        </div>
        <div class="ai-process-progress ai-process-progress--indeterminate">
          <div class="ai-process-progress-bar ai-process-progress-bar--indeterminate" />
        </div>
        <div class="ai-process-desc">{{ aiProcessText }}</div>
        <div class="ai-process-note">这里只表示后端请求仍在执行，不再模拟阶段进度。</div>
        <div class="ai-feed">
          <div v-for="(line, idx) in aiProcessFeed" :key="`${idx}-${line}`" class="ai-feed-line">
            <span class="dot" />
            <span>{{ line }}</span>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.security-center-page {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: var(--sec-hud-page-bg);
  color: #fff;
  padding: 24px 28px;
  color-scheme: dark;
}
.sec-header {
  margin-bottom: 24px;
  padding-bottom: 20px;
  border-bottom: 1px solid rgba(34, 211, 238, 0.14);
}
.sec-hud-rail {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
  font-size: 15px;
  color: rgba(34, 211, 238, 0.78);
  letter-spacing: 0.06em;
}
.sec-hud-rail__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--sec-hud-cyan);
  box-shadow: 0 0 12px var(--sec-hud-cyan);
  animation: sec-hud-pulse 2s ease-in-out infinite;
}
@keyframes sec-hud-pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.55;
    transform: scale(0.88);
  }
}
.sec-hud-rail__brand {
  font-family:
    'Segoe UI',
    'PingFang SC',
    'Microsoft YaHei',
    system-ui,
    sans-serif;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: rgba(207, 250, 254, 0.95);
  text-shadow:
    0 0 18px rgba(34, 211, 238, 0.22),
    0 0 1px rgba(255, 255, 255, 0.08);
}
.sec-hud-rail__split {
  width: 1px;
  height: 14px;
  background: rgba(34, 211, 238, 0.28);
  margin: 0 2px;
}
.sec-hud-rail__clock {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  color: rgba(226, 232, 240, 0.92);
  font-weight: 600;
}
.sec-hud-rail__tlab {
  font-family:
    'Segoe UI',
    'PingFang SC',
    system-ui,
    sans-serif;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.1em;
  color: rgba(148, 163, 184, 0.88);
}
.sec-hud-rail__tval {
  font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
  font-size: 14px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: rgba(226, 232, 240, 0.95);
}
.sec-hud-rail__cursor {
  animation: sec-hud-blink 1.1s step-end infinite;
  color: var(--sec-hud-cyan);
  font-family: ui-monospace, monospace;
}
@keyframes sec-hud-blink {
  50% {
    opacity: 0;
  }
}
.sec-title {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: 0.2em;
  margin: 0 0 10px 0;
  background: linear-gradient(to bottom, #fff 40%, #94a3b8 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  text-shadow: 0 0 28px rgba(34, 211, 238, 0.18);
  cursor: pointer;
  user-select: none;
}
.sec-hud-pipeline {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.2em 0.35em;
  margin: 0;
  cursor: pointer;
  user-select: none;
  line-height: 1.65;
}
.sec-hud-pipeline:focus-visible {
  outline: 2px solid rgba(34, 211, 238, 0.5);
  outline-offset: 4px;
  border-radius: 4px;
}
.sec-hud-pipeline__step {
  font-size: 16px;
  font-weight: 650;
  font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
  letter-spacing: 0.06em;
  color: #a5f3fc;
  text-shadow:
    0 0 18px rgba(34, 211, 238, 0.45),
    0 0 2px rgba(255, 255, 255, 0.15);
  transition: color 0.15s, text-shadow 0.15s;
}
.sec-hud-pipeline:hover .sec-hud-pipeline__step {
  color: #ecfeff;
  text-shadow:
    0 0 22px rgba(34, 211, 238, 0.65),
    0 0 3px rgba(255, 255, 255, 0.2);
}
.sec-hud-pipeline__sep {
  color: rgba(34, 211, 238, 0.35);
  font-weight: 300;
  font-size: 18px;
  user-select: none;
  padding: 0 0.08em;
}
.sec-main { padding: 0; }

.stats-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: stretch;
  margin-bottom: 24px;
}
.stat-card.sec-stat {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  padding: 18px 20px;
  background: rgba(10, 14, 22, 0.92);
  border: 1px solid rgba(34, 211, 238, 0.12);
  border-radius: 16px;
  min-width: 140px;
  min-height: 104px;
  box-sizing: border-box;
  transition: border-color 0.2s;
  &:hover { border-color: rgba(255,255,255,0.1); }
  &.danger .stat-value { color: #ef4444; }
  &.warning .stat-value { color: #f59e0b; }
  &.small .stat-value { font-size: 26px; }
}
.stat-card .stat-value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: #3b82f6;
  font-family: monospace;
  line-height: 1.1;
  min-height: 1.1em;
}
.stat-card .stat-label {
  display: block;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.55);
  letter-spacing: 0.04em;
  margin-top: 10px;
  line-height: 1.35;
  max-width: 168px;
}

.chart-row {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 24px;
}
.chart-card.sec-card {
  flex: 0 0 320px;
  padding: 20px;
  background: rgba(10, 14, 22, 0.92);
  border: 1px solid rgba(34, 211, 238, 0.12);
  border-radius: 16px;
  &.chart-card-wide { flex: 1; min-width: 360px; }
}
.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: rgba(165, 243, 252, 0.92);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
  letter-spacing: 0.04em;
  text-shadow: 0 0 14px rgba(34, 211, 238, 0.2);
}
.chart-arena { height: 220px; }
.sec-select { width: 120px; margin-left: 8px; }

.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
  align-items: center;
}

:deep(.filter-bar .el-button) {
  font-size: 15px;
  padding: 10px 18px;
}
.sec-input { width: 140px; }
.sec-select { width: 140px; }

.table-card.sec-card {
  padding: 20px;
  background: rgba(10, 14, 22, 0.92);
  border: 1px solid rgba(34, 211, 238, 0.12);
  border-radius: 16px;
}
/* 不再强制 min-width / table-layout:fixed，避免表头与表体列宽错位、防火墙列「盖住」封禁 */
.ids-table-shell {
  min-width: 0;
  width: 100%;
}
:deep(.ids-table-shell .sec-table .el-table__body-wrapper),
:deep(.ids-table-shell .sec-table .el-table__header-wrapper) {
  width: 100% !important;
}
.sec-pagination {
  margin-top: 16px;
}

:deep(.sec-pagination) {
  font-size: 15px;
  --el-pagination-font-size: 15px;
}
.demo-clear-area {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}
.demo-clear-logo {
  box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.28) inset;
}
.demo-clear-logo.armed {
  animation: clear-armed-pulse 0.9s ease-in-out infinite;
}
@keyframes clear-armed-pulse {
  0% { box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.28) inset, 0 0 0 rgba(239, 68, 68, 0.15); }
  50% { box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.45) inset, 0 0 14px rgba(239, 68, 68, 0.35); }
  100% { box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.28) inset, 0 0 0 rgba(239, 68, 68, 0.15); }
}

/* 统一暗色科技风：表格、选择器、输入框、标签、分页、抽屉 */
:deep(.sec-table),
:deep(.sec-table .el-table),
:deep(.sec-table .el-table__inner-wrapper) {
  --el-table-bg-color: rgba(10, 14, 22, 0.98);
  --el-table-tr-bg-color: rgba(10, 14, 22, 0.98);
  --el-table-header-bg-color: rgba(34, 211, 238, 0.06);
  --el-table-row-hover-bg-color: rgba(34, 211, 238, 0.07);
  --el-table-border-color: rgba(34, 211, 238, 0.1);
  --el-table-text-color: rgba(255, 255, 255, 0.9);
  background: rgba(10, 14, 22, 0.98) !important;
}
:deep(.sec-table .el-table__body tr) { background: rgba(10, 14, 22, 0.98) !important; }
:deep(.sec-table .el-table__body tr.el-table__row--striped) { background: rgba(255,255,255,0.02) !important; }
/* 主表体与右侧固定区行悬停背景一致，避免出现半截透明蒙层 */
:deep(.sec-table .el-table__body tr.hover-row > td.el-table__cell) {
  background-color: var(--el-table-row-hover-bg-color) !important;
}
:deep(.sec-table .el-table__fixed-right .el-table__body tr.hover-row > td.el-table__cell) {
  background-color: var(--el-table-row-hover-bg-color) !important;
}
/* 右侧固定区：与左侧滚动区清晰分界，避免仅靠阴影造成「盖住」错觉 */
:deep(.sec-table .el-table__fixed-right::before),
:deep(.sec-table .el-table__fixed-right::after) {
  box-shadow: none !important;
}
:deep(.sec-table .el-table__fixed-right-patch) {
  background-color: rgba(10, 14, 22, 0.98) !important;
}
:deep(.sec-table .el-table__fixed-right) {
  background: rgba(10, 14, 22, 0.98);
  border-left: 1px solid rgba(34, 211, 238, 0.15);
}
:deep(.sec-table .el-table__fixed-right .el-table__cell) {
  background: rgba(10, 14, 22, 0.98) !important;
}
:deep(.sec-table .el-table__fixed-right .el-table__header-wrapper th.el-table__cell) {
  background: rgba(255, 255, 255, 0.04) !important;
}
:deep(.sec-table th.el-table__cell) {
  background: rgba(34, 211, 238, 0.07) !important;
  color: rgba(226, 254, 255, 0.9);
  font-size: 13px;
  font-weight: 600;
  vertical-align: middle;
  padding: 8px 6px !important;
}
:deep(.sec-table th.el-table__cell .cell) {
  white-space: nowrap !important;
  line-height: 1.35 !important;
  word-break: keep-all;
}
:deep(.sec-table td.el-table__cell) {
  vertical-align: middle;
  font-size: 14px;
  padding: 8px 6px !important;
}
:deep(.sec-table .cell) {
  line-height: 1.45;
}
:deep(.sec-drawer) {
  --el-drawer-bg-color: #0a0a0a;
  --el-text-color-primary: rgba(255,255,255,0.9);
  background: #0a0a0a !important;
}
:deep(.el-pagination) {
  --el-pagination-button-bg-color: transparent;
  --el-pagination-button-color: rgba(255,255,255,0.7);
  --el-pagination-hover-color: #3b82f6;
}
:deep(.sec-input .el-input__wrapper),
:deep(.sec-select .el-select__wrapper) {
  background: rgba(255,255,255,0.06) !important;
  box-shadow: 0 0 0 1px rgba(255,255,255,0.08);
  color: rgba(255,255,255,0.9);
}
:deep(.sec-input .el-input__inner),
:deep(.sec-select .el-select__input) {
  color: rgba(255, 255, 255, 0.9);
  font-size: 15px;
}
:deep(.sec-select .el-select__selected-item) {
  font-size: 15px;
}
:deep(.sec-input .el-input__wrapper:hover),
:deep(.sec-select .el-select__wrapper:hover) { background: rgba(255,255,255,0.08) !important; }
:deep(.el-select-dropdown) { --el-bg-color: #0f172a !important; --el-text-color-primary: rgba(255,255,255,0.9); }
:deep(.el-tag) { --el-tag-bg-color: rgba(255,255,255,0.08); --el-tag-text-color: rgba(255,255,255,0.8); }
:deep(.el-tag--danger) { --el-tag-bg-color: rgba(239,68,68,0.2); --el-tag-text-color: #f87171; }
:deep(.el-tag--warning) { --el-tag-bg-color: rgba(245,158,11,0.2); --el-tag-text-color: #fbbf24; }
:deep(.el-tag--success) { --el-tag-bg-color: rgba(16,185,129,0.2); --el-tag-text-color: #34d399; }
:deep(.el-tag--info) { --el-tag-bg-color: rgba(255,255,255,0.06); --el-tag-text-color: rgba(255,255,255,0.6); }

:deep(.sec-table .el-tag) {
  font-size: 12px;
  height: auto;
  line-height: 1.35;
  padding: 3px 8px;
  max-width: 100%;
}
:deep(.sec-table .ids-table-tag--clip) {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  vertical-align: middle;
}

:deep(.sec-table .ids-table-tag--ai.el-tag) {
  max-width: 100%;
  min-width: 0;
  box-sizing: border-box;
  overflow: hidden;
  vertical-align: middle;
}
:deep(.sec-table .ids-table-tag--ai .el-tag__content) {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

:deep(.sec-table .ids-table-tag--ai-cn.el-tag) {
  padding: 2px 7px !important;
  max-width: 2.25em;
}
:deep(.sec-table .ids-table-tag--ai-cn .el-tag__content) {
  text-align: center;
  font-weight: 700;
  font-size: 13px;
}

.ids-fw-cn {
  font-size: 13px;
  font-weight: 600;
  color: rgba(226, 254, 255, 0.9);
  letter-spacing: 0.04em;
}

.cell-nowrap {
  white-space: nowrap;
}

.cell-ellipsis,
.cell-path-ellipsis {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell-time,
.cell-mono {
  font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
  font-variant-numeric: tabular-nums;
}

/* 仅表体：避免与表头 .cell 规则不一致导致列对不齐；表头走 Element Plus 默认 */
.cell-stack {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.cell-sub {
  font-size: 12px;
  color: rgba(255, 255, 255, 0.52);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-section {
  margin-bottom: 16px;
  padding: 12px;
  border: 1px solid rgba(56, 189, 248, 0.14);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.45);
}

.detail-section__title {
  margin-bottom: 10px;
  font-size: 13px;
  font-weight: 700;
  color: #67e8f9;
  letter-spacing: 0.04em;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.detail-item--full {
  grid-column: 1 / -1;
}

.detail-label {
  font-size: 12px;
  color: rgba(148, 163, 184, 0.9);
}

.detail-value {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.88);
  line-height: 1.5;
  word-break: break-word;
}

.detail-value--mono {
  font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
  font-variant-numeric: tabular-nums;
}

.detail-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

:deep(
    .sec-table .el-table__body-wrapper .el-table__body tr > td:nth-child(2) .cell,
    .sec-table .el-table__body-wrapper .el-table__body tr > td:nth-child(3) .cell,
    .sec-table .el-table__body-wrapper .el-table__body tr > td:nth-child(5) .cell,
    .sec-table .el-table__body-wrapper .el-table__body tr > td:nth-child(7) .cell,
    .sec-table .el-table__body-wrapper .el-table__body tr > td:nth-child(8) .cell
  ) {
  white-space: nowrap !important;
}
/* 下拉触发器外层默认带可聚焦盒子，悬停时像透明浮层盖住文字 */
:deep(.sec-table .ids-ops .el-dropdown),
:deep(.sec-table .ids-ops .el-dropdown .el-tooltip__trigger) {
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
}
:deep(.sec-table .ids-ops .el-dropdown .el-tooltip__trigger) {
  outline: none !important;
  box-shadow: none !important;
  background: transparent !important;
}
:deep(.sec-table .ids-ops .el-dropdown:focus-visible .el-tooltip__trigger) {
  outline: 2px solid rgba(59, 130, 246, 0.45) !important;
  outline-offset: 2px;
  border-radius: 2px;
}

.ids-ops {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  width: 100%;
  max-width: 100%;
}
.ids-ops--row {
  flex-direction: row;
  flex-wrap: nowrap;
}
.ids-ops__sep {
  color: rgba(255, 255, 255, 0.14);
  font-size: 11px;
  user-select: none;
  padding: 0 1px;
  flex-shrink: 0;
}

.ids-act {
  margin: 0;
  padding: 2px 5px;
  border: none;
  border-radius: 2px;
  background: transparent !important;
  box-shadow: none !important;
  font-size: 13px;
  font-family: ui-monospace, Consolas, monospace;
  letter-spacing: 0.02em;
  line-height: 1.4;
  cursor: pointer;
  color: rgba(103, 232, 249, 0.88);
  white-space: nowrap;
  transition: color 0.15s, text-shadow 0.15s, background 0.15s;
}

.ids-act:hover:not(:disabled) {
  color: #ecfeff;
  text-shadow: 0 0 12px rgba(34, 211, 238, 0.45);
  background: rgba(34, 211, 238, 0.07) !important;
  text-decoration: none;
}

.ids-act:focus-visible {
  outline: 2px solid rgba(59, 130, 246, 0.65);
  outline-offset: 2px;
  border-radius: 2px;
}

.ids-act:disabled {
  opacity: 0.55;
  cursor: wait;
}

.ids-act--warn {
  color: #fbbf24;
}

.ids-act--warn:hover:not(:disabled) {
  color: #fde68a;
}

.ids-act--danger {
  color: #f87171;
}

.ids-act--danger:hover:not(:disabled) {
  color: #fecaca;
}

.ids-act--ok {
  color: #4ade80;
}

.ids-act--ok:hover:not(:disabled) {
  color: #bbf7d0;
}

.ids-act--muted {
  color: #94a3b8;
}

.ids-act--muted:hover:not(:disabled) {
  color: #cbd5e1;
}

.ids-alert-sound-shortcut {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
  border: 1px solid rgba(248, 113, 113, 0.22);
  background:
    radial-gradient(circle at top left, rgba(248, 113, 113, 0.08), transparent 38%),
    linear-gradient(180deg, rgba(7, 14, 28, 0.94), rgba(6, 12, 24, 0.82));
  box-shadow: inset 0 1px 0 rgba(248, 250, 252, 0.04);
}

.ids-alert-sound-shortcut__copy {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
}

.ids-alert-sound-shortcut__text {
  font-size: 13px;
  line-height: 1.7;
  color: rgba(226, 232, 240, 0.82);
}

.ids-alert-sound-shortcut__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 12px;
  color: rgba(148, 163, 184, 0.94);
}

.ids-alert-sound-shortcut__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.ids-alert-sound-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 18px;
  border: 1px solid rgba(248, 113, 113, 0.22);
  background:
    radial-gradient(circle at top right, rgba(248, 113, 113, 0.08), transparent 38%),
    linear-gradient(180deg, rgba(7, 14, 28, 0.92), rgba(6, 12, 24, 0.78));
  box-shadow: inset 0 1px 0 rgba(248, 250, 252, 0.04);
}

.ids-alert-sound-card__header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.ids-alert-sound-card__subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.6;
  max-width: 760px;
  color: rgba(226, 232, 240, 0.76);
}

.ids-alert-sound-card__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(260px, 1fr);
  gap: 12px;
}

.ids-alert-sound-card__panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 0;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(248, 113, 113, 0.16);
  background: rgba(15, 23, 42, 0.58);
}

.ids-alert-sound-card__label {
  font-size: 12px;
  letter-spacing: 0.05em;
  color: rgba(148, 163, 184, 0.92);
}

.ids-alert-sound-card__value {
  font-size: 15px;
  font-weight: 600;
  color: #f8fafc;
  word-break: break-word;
}

.ids-alert-sound-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  font-size: 12px;
  color: rgba(191, 219, 254, 0.7);
}

.ids-alert-sound-card__slider {
  display: flex;
  align-items: center;
  gap: 16px;
}

.ids-alert-sound-card__slider :deep(.el-slider) {
  flex: 1;
}

.ids-alert-sound-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.ids-alert-sound-card__input {
  display: none;
}

:deep(.ids-risk-alert-dialog) {
  .el-dialog {
    border: 1px solid rgba(255, 107, 107, 0.32);
    background:
      radial-gradient(circle at top right, rgba(255, 107, 107, 0.18), transparent 38%),
      linear-gradient(180deg, rgba(10, 20, 38, 0.98), rgba(7, 12, 25, 0.98));
    box-shadow:
      0 22px 60px rgba(0, 0, 0, 0.45),
      0 0 0 1px rgba(255, 255, 255, 0.04) inset;
    color: #ecf4ff;
  }

  .el-dialog__header {
    margin-right: 0;
    padding: 18px 22px 0;
  }

  .el-dialog__title {
    color: #f8fbff;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 0.02em;
  }

  .el-dialog__headerbtn .el-dialog__close {
    color: rgba(236, 244, 255, 0.72);
  }

  .el-dialog__body {
    padding: 18px 22px 10px;
  }

  .el-dialog__footer {
    padding: 8px 22px 22px;
  }
}

.ids-risk-alert {
  display: grid;
  gap: 18px;
}

.ids-risk-alert__headline {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  padding: 16px 18px;
  border-radius: 18px;
  background: linear-gradient(135deg, rgba(135, 16, 16, 0.42), rgba(61, 14, 18, 0.84));
  border: 1px solid rgba(255, 129, 129, 0.22);
}

.ids-risk-alert__badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 64px;
  height: 32px;
  border-radius: 999px;
  background: linear-gradient(135deg, #ff6b6b, #ff8748);
  color: #fff9f6;
  font-size: 13px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.ids-risk-alert__title {
  color: #fdfefe;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.25;
}

.ids-risk-alert__subtitle {
  margin-top: 6px;
  color: rgba(236, 244, 255, 0.78);
  font-size: 13px;
  line-height: 1.6;
}

.ids-risk-alert__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.ids-risk-alert__item {
  display: flex;
  flex-direction: column;
  gap: 7px;
  min-width: 0;
  padding: 14px 15px;
  border-radius: 16px;
  background: rgba(12, 20, 36, 0.88);
  border: 1px solid rgba(150, 177, 216, 0.16);
}

.ids-risk-alert__item--full {
  grid-column: 1 / -1;
}

.ids-risk-alert__label {
  color: rgba(168, 188, 214, 0.82);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.ids-risk-alert__value {
  color: #f4f8ff;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.6;
  word-break: break-word;
}

.ids-risk-alert__value--multiline {
  white-space: pre-wrap;
}

.ids-risk-alert__hint {
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(68, 84, 117, 0.2);
  color: rgba(211, 223, 240, 0.92);
  font-size: 13px;
  line-height: 1.7;
}

.ids-risk-alert__actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
}

.source-ops-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 18px;
  border: 1px solid rgba(56, 189, 248, 0.22);
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.08), transparent 38%),
    linear-gradient(180deg, rgba(7, 14, 28, 0.92), rgba(6, 12, 24, 0.78));
  box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.08);
}

.source-ops-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.source-ops-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.source-ops-card__subtitle {
  margin-top: 6px;
  font-size: 13px;
  line-height: 1.5;
  max-width: 520px;
  color: rgba(226, 232, 240, 0.76);
}

.source-summary-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.source-summary-tile {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 14px 16px;
  border: 1px solid rgba(34, 211, 238, 0.12);
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.72), rgba(15, 23, 42, 0.46));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.source-summary-tile--good {
  border-color: rgba(74, 222, 128, 0.2);
}

.source-summary-tile--warn {
  border-color: rgba(245, 158, 11, 0.22);
}

.source-summary-tile--demo {
  border-color: rgba(248, 113, 113, 0.18);
}

.source-summary-tile__value {
  font-size: 24px;
  font-weight: 700;
  color: #f8fafc;
}

.source-summary-tile__label {
  font-size: 12px;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.52);
}

.source-ops-table__metric {
  align-items: center;
}

.source-sync-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.source-form-grid :deep(.el-form-item) {
  margin-bottom: 18px;
}

.source-form-grid :deep(.el-input-number) {
  width: 100%;
}

@media (max-width: 1280px) {
  .ids-ops-grid {
    grid-template-columns: 1fr;
  }

  .ids-mini-columns {
    grid-template-columns: 1fr;
  }

  .ids-analysis-steps {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ids-analysis-grid {
    grid-template-columns: 1fr;
  }

  .ids-alert-sound-shortcut {
    flex-direction: column;
    align-items: stretch;
  }

  .ids-alert-sound-card__grid {
    grid-template-columns: 1fr;
  }

  .source-summary-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .ids-heatboard-panel__head {
    flex-direction: column;
  }

  .ids-heatboard-bars {
    grid-template-columns: repeat(12, minmax(24px, 1fr));
  }

  .ids-notification-grid {
    grid-template-columns: 1fr;
  }

  .ids-analysis-timeline__item {
    grid-template-columns: 1fr;
  }

  .ids-alert-sound-shortcut__actions {
    justify-content: flex-start;
  }

  .ids-alert-sound-card__header {
    flex-direction: column;
  }

  .source-ops-card__header {
    flex-direction: column;
  }

  .source-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .ids-heatboard-summary {
    grid-template-columns: 1fr;
  }

  .ids-heatboard-bars {
    grid-template-columns: repeat(8, minmax(24px, 1fr));
    overflow-x: auto;
    padding-bottom: 6px;
  }

  .ids-heatboard-bar__track {
    min-height: 104px;
  }

  .ids-cluster-chip {
    width: 100%;
    justify-content: space-between;
  }

  .ids-analysis-steps {
    grid-template-columns: 1fr;
  }

  .ids-alert-sound-shortcut__actions :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }

  .ids-alert-sound-card__slider {
    flex-direction: column;
    align-items: stretch;
  }

  .ids-alert-sound-card__actions :deep(.el-button) {
    width: 100%;
    margin-left: 0;
  }

  .source-summary-grid {
    grid-template-columns: 1fr;
  }
}

.muted-ai {
  color: rgba(255, 255, 255, 0.35);
  font-size: 15px;
}
.ai-block {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid rgba(255,255,255,0.08);
}
.ai-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.ai-time {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.55);
}
.ai-text {
  margin: 0 0 12px 0;
  padding: 12px;
  background: rgba(0, 0, 0, 0.35);
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  color: rgba(255, 255, 255, 0.85);
  max-height: 280px;
  overflow-y: auto;
}
.ai-empty {
  font-size: 14px;
  color: rgba(255, 255, 255, 0.45);
  margin: 0 0 12px 0;
}
.report-text { max-height: 460px; }

.ai-btn-label { display: inline-flex; align-items: center; gap: 6px; }
.mini-orbit {
  width: 10px;
  height: 10px;
  border: 2px solid rgba(59, 130, 246, 0.75);
  border-top-color: transparent;
  border-radius: 50%;
  display: inline-block;
  animation: spin-mini 0.8s linear infinite;
}

.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.report-actions { display: flex; gap: 8px; }
.ids-ops-grid {
  display: grid;
  grid-template-columns: 1.5fr 1fr;
  gap: 18px;
  margin: 18px 0;
}
.ids-card-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 14px;
}
.ids-card-subtitle {
  margin-top: 6px;
  color: rgba(148, 163, 184, 0.9);
  font-size: 13px;
  line-height: 1.5;
}
.ids-card-stamp {
  color: rgba(148, 163, 184, 0.82);
  font-size: 12px;
  letter-spacing: 0.04em;
}
.ids-heatboard-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}
.ids-heatboard-panel {
  border: 1px solid rgba(56, 189, 248, 0.16);
  background:
    linear-gradient(180deg, rgba(8, 15, 28, 0.94), rgba(8, 15, 28, 0.72)),
    radial-gradient(circle at top, rgba(56, 189, 248, 0.08), transparent 48%);
  border-radius: 18px;
  padding: 16px;
}
.ids-heatboard-panel__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 14px;
}
.ids-heatboard-panel__note {
  margin-top: 6px;
  color: rgba(148, 163, 184, 0.88);
  font-size: 12px;
  line-height: 1.6;
}
.ids-heatboard-legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 12px;
  color: rgba(191, 219, 254, 0.82);
  font-size: 12px;
}
.ids-heatboard-legend span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.ids-heatboard-legend__dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #38bdf8;
  box-shadow: 0 0 10px rgba(56, 189, 248, 0.45);
}
.ids-heatboard-legend__dot--danger {
  background: #fb7185;
  box-shadow: 0 0 10px rgba(251, 113, 133, 0.45);
}
.ids-heatboard-bars {
  display: grid;
  grid-template-columns: repeat(24, minmax(20px, 1fr));
  gap: 8px;
  align-items: end;
}
.ids-heatboard-bar {
  appearance: none;
  border: none;
  background: transparent;
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  color: rgba(226, 232, 240, 0.92);
}
.ids-heatboard-bar__value {
  font-size: 12px;
  color: rgba(226, 232, 240, 0.86);
}
.ids-heatboard-bar__track {
  position: relative;
  width: 100%;
  min-height: 124px;
  border-radius: 999px;
  border: 1px solid rgba(71, 85, 105, 0.3);
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.26), rgba(15, 23, 42, 0.92));
  overflow: hidden;
}
.ids-heatboard-bar__fill {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  border-radius: 999px;
  background: linear-gradient(180deg, rgba(34, 211, 238, 0.95), rgba(14, 165, 233, 0.65));
  box-shadow: 0 0 18px rgba(34, 211, 238, 0.2);
}
.ids-heatboard-bar__danger {
  position: absolute;
  top: 8px;
  left: 50%;
  transform: translateX(-50%);
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  border-radius: 999px;
  background: rgba(127, 29, 29, 0.88);
  color: #fee2e2;
  font-size: 11px;
  line-height: 18px;
  text-align: center;
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.26);
}
.ids-heatboard-bar__time {
  font-size: 11px;
  color: rgba(148, 163, 184, 0.88);
}
.ids-heatboard-bar.is-active .ids-heatboard-bar__track {
  border-color: rgba(56, 189, 248, 0.3);
}
.ids-heatboard-bar.is-danger .ids-heatboard-bar__track {
  border-color: rgba(248, 113, 113, 0.36);
  box-shadow: inset 0 0 0 1px rgba(248, 113, 113, 0.08);
}
.ids-heatboard-bar.is-danger .ids-heatboard-bar__fill {
  background: linear-gradient(180deg, rgba(251, 113, 133, 0.98), rgba(239, 68, 68, 0.72));
  box-shadow: 0 0 18px rgba(248, 113, 113, 0.24);
}
.ids-heatboard-focus {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid rgba(56, 189, 248, 0.12);
}
.ids-heatboard-focus__label {
  display: inline-block;
  margin-bottom: 10px;
  font-size: 12px;
  color: rgba(125, 211, 252, 0.96);
  letter-spacing: 0.08em;
}
.ids-heatboard-focus__list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.ids-heatboard-focus__chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.84);
  border: 1px solid rgba(56, 189, 248, 0.16);
  color: rgba(226, 232, 240, 0.92);
  font-size: 12px;
}
.ids-mini-columns {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}
.ids-mini-card {
  border: 1px solid rgba(56, 189, 248, 0.16);
  background: rgba(8, 15, 28, 0.78);
  border-radius: 14px;
  padding: 14px;
}
.ids-mini-card__title {
  font-size: 13px;
  letter-spacing: 0.06em;
  color: rgba(148, 163, 184, 0.9);
  margin-bottom: 10px;
}
.ids-mini-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ids-mini-list__row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  color: rgba(226, 232, 240, 0.9);
}
.ids-notification-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.ids-notification-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}
.ids-cluster-strip {
  margin-bottom: 14px;
}
.ids-cluster-strip__list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.ids-cluster-chip {
  border: 1px solid rgba(56, 189, 248, 0.22);
  background: rgba(15, 23, 42, 0.85);
  border-radius: 999px;
  color: rgba(226, 232, 240, 0.94);
  padding: 10px 14px;
  display: inline-flex;
  gap: 10px;
  align-items: center;
}
.ids-analysis-hero {
  position: relative;
  overflow: hidden;
  padding: 22px 24px;
  border-radius: 20px;
  border: 1px solid rgba(56, 189, 248, 0.2);
  background:
    radial-gradient(circle at 85% 15%, rgba(14, 165, 233, 0.16), transparent 28%),
    linear-gradient(135deg, rgba(8, 15, 28, 0.96), rgba(15, 23, 42, 0.9));
  margin-bottom: 14px;
}
.ids-analysis-hero::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, rgba(56, 189, 248, 0.06), transparent 32%);
  pointer-events: none;
}
.ids-analysis-hero__badge {
  position: relative;
  display: inline-flex;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(248, 113, 113, 0.16);
  color: #fecaca;
  font-size: 12px;
  letter-spacing: 0.08em;
  margin-bottom: 10px;
}
.ids-analysis-hero h3 {
  position: relative;
  margin: 0 0 8px;
  font-size: 24px;
}
.ids-analysis-hero p {
  position: relative;
  margin: 0;
  color: rgba(226, 232, 240, 0.8);
}
.ids-analysis-steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}
.ids-analysis-step {
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.78);
  border-radius: 14px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: rgba(148, 163, 184, 0.85);
}
.ids-analysis-step.active {
  border-color: rgba(56, 189, 248, 0.35);
  color: rgba(226, 232, 240, 0.94);
}
.ids-analysis-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}
.ids-analysis-card {
  border: 1px solid rgba(56, 189, 248, 0.16);
  background: linear-gradient(180deg, rgba(8, 15, 28, 0.86), rgba(8, 15, 28, 0.72));
  border-radius: 16px;
  padding: 16px;
}
.ids-analysis-card--wide {
  grid-column: 1 / -1;
}
.ids-analysis-card__title {
  font-size: 14px;
  letter-spacing: 0.06em;
  color: rgba(147, 197, 253, 0.95);
  margin-bottom: 10px;
}
.ids-analysis-card p {
  margin: 0 0 8px;
  color: rgba(226, 232, 240, 0.88);
}
.ids-analysis-timeline {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ids-analysis-timeline__item {
  display: grid;
  grid-template-columns: 72px 150px 1fr 1.6fr;
  gap: 10px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 12px;
  padding: 10px 12px;
  color: rgba(226, 232, 240, 0.88);
  font-size: 13px;
}
.timeline-toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}
.timeline-loading-note {
  margin-bottom: 10px;
  color: #93c5fd;
  font-size: 12px;
  letter-spacing: 0.08em;
}
.timeline-container {
  max-height: 600px;
  overflow-y: auto;
  padding-right: 4px;
}
.timeline-empty {
  padding: 18px;
  text-align: center;
  color: rgba(148, 163, 184, 0.9);
}
.chain-card {
  border: 1px solid rgba(56, 189, 248, 0.2);
  background: rgba(15, 23, 42, 0.55);
  border-radius: 10px;
  padding: 12px;
  margin-bottom: 10px;
}
.chain-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.chain-title {
  color: #e2e8f0;
  font-size: 13px;
  font-weight: 700;
}
.chain-meta {
  color: #94a3b8;
  font-size: 12px;
}
.chain-attack-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
}
.chain-node {
  display: flex;
  gap: 10px;
  padding: 8px 0;
  border-left: 1px dashed rgba(148, 163, 184, 0.3);
  margin-left: 7px;
  padding-left: 14px;
}
.chain-node:last-child {
  border-left-color: transparent;
}
.chain-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  margin-left: -20px;
  margin-top: 5px;
  flex: 0 0 auto;
}
.chain-dot.state-info { background: #38bdf8; box-shadow: 0 0 8px rgba(56, 189, 248, 0.55); }
.chain-dot.state-warning { background: #f59e0b; box-shadow: 0 0 8px rgba(245, 158, 11, 0.55); }
.chain-dot.state-danger { background: #ef4444; box-shadow: 0 0 8px rgba(239, 68, 68, 0.55); }
.chain-dot.state-success { background: #22c55e; box-shadow: 0 0 8px rgba(34, 197, 94, 0.55); }
.chain-node-title {
  color: #e2e8f0;
  font-size: 12px;
  font-weight: 600;
}
.chain-node-detail {
  margin-top: 2px;
  color: #94a3b8;
  font-size: 12px;
}
.report-panel {
  position: relative;
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.95), rgba(3, 7, 18, 0.98));
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 12px;
  padding: 14px;
}
.report-panel::after {
  content: "IDS Platform";
  position: absolute;
  right: 18px;
  bottom: 12px;
  font-size: 12px;
  color: rgba(148, 163, 184, 0.14);
  letter-spacing: 0.08em;
  pointer-events: none;
}
.report-cover {
  border: 1px solid rgba(56, 189, 248, 0.25);
  border-radius: 10px;
  padding: 12px 14px;
  background: rgba(15, 23, 42, 0.65);
  margin-bottom: 12px;
}
.report-cover-title {
  font-size: 16px;
  font-weight: 700;
  color: #e2e8f0;
}
.report-cover-subtitle {
  margin-top: 2px;
  font-size: 12px;
  color: #93c5fd;
  letter-spacing: 0.08em;
}
.report-cover-badges {
  margin-top: 8px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.report-kv {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 18px;
  color: #cbd5e1;
  font-size: 12px;
}
.report-conclusion {
  margin-top: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid rgba(56, 189, 248, 0.25);
  background: rgba(2, 132, 199, 0.08);
  color: #e2e8f0;
  font-size: 12px;
}
.report-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 12px;
}
.report-card {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.25);
  background: rgba(15, 23, 42, 0.55);
  color: #dbeafe;
  h4 {
    margin: 0 0 8px 0;
    font-size: 13px;
    color: #67e8f9;
  }
  p {
    margin: 4px 0;
    font-size: 12px;
    color: #cbd5e1;
  }
}
.report-card-full { grid-column: 1 / -1; }
.report-vector-table {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid rgba(56, 189, 248, 0.22);
  background: rgba(15, 23, 42, 0.45);
  overflow-x: auto;
}
.report-json-block {
  margin-bottom: 12px;
}
.report-json-pre {
  margin: 0;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(56, 189, 248, 0.25);
  background: rgba(2, 6, 23, 0.92);
  color: #a5f3fc;
  font-size: 11px;
  line-height: 1.45;
  overflow-x: auto;
  max-height: 320px;
  font-family: ui-monospace, Consolas, monospace;
}
.report-vector-head {
  font-size: 13px;
  font-weight: 600;
  color: #67e8f9;
  margin-bottom: 8px;
}
.report-vec-tbl {
  width: 100%;
  border-collapse: collapse;
  font-size: 11px;
  color: #cbd5e1;
}
.report-vec-tbl th,
.report-vec-tbl td {
  border: 1px solid rgba(148, 163, 184, 0.2);
  padding: 6px 8px;
  text-align: left;
}
.report-vec-tbl th {
  color: #94a3b8;
  font-weight: 600;
}
.report-vec-path {
  max-width: 220px;
  word-break: break-all;
}
.report-footer-sign {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: rgba(148, 163, 184, 0.9);
  border-top: 1px dashed rgba(148, 163, 184, 0.3);
  padding-top: 8px;
}

.ai-loading-fx {
  position: relative;
  height: 92px;
  margin-bottom: 10px;
  border: 1px dashed rgba(59,130,246,0.25);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  color: rgba(191, 219, 254, 0.92);
  font-size: 12px;
  letter-spacing: 0.08em;
  background: radial-gradient(circle at center, rgba(37,99,235,0.08), rgba(0,0,0,0));
}
.ring {
  width: 26px;
  height: 26px;
  border: 2px solid rgba(59,130,246,0.65);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1.4s linear infinite;
}
.ring-2 { width: 18px; height: 18px; border-color: rgba(147,197,253,0.72); border-top-color: transparent; animation-duration: 1s; }
.ring-3 { width: 10px; height: 10px; border-color: rgba(96,165,250,0.9); border-top-color: transparent; animation-duration: 0.7s; }

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes spin-mini {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

:global(.ai-process-modal .el-dialog),
:global(.el-dialog.ai-process-modal) {
  --el-dialog-bg-color: #020617 !important;
  background: radial-gradient(circle at 50% 35%, rgba(30, 64, 175, 0.26), rgba(2, 6, 23, 0.98)) !important;
  border: 1px solid rgba(56, 189, 248, 0.42);
  border-radius: 16px;
  box-shadow: 0 20px 56px rgba(2, 6, 23, 0.75), 0 0 24px rgba(14, 165, 233, 0.2);
}
:global(.ai-process-modal .el-dialog__body),
:global(.el-dialog.ai-process-modal .el-dialog__body) {
  padding: 0;
  background: transparent !important;
}
:global(.ai-process-modal .el-dialog__header),
:global(.el-dialog.ai-process-modal .el-dialog__header) { display: none; }
:global(.ai-process-overlay) {
  background: rgba(1, 3, 10, 0.72) !important;
  backdrop-filter: blur(2px);
}
.ai-process-wrap {
  position: relative;
  overflow: hidden;
  padding: 28px 22px 24px;
  text-align: center;
}
.ai-process-wrap.mode-phase2 {
  box-shadow: inset 0 0 0 1px rgba(248, 113, 113, 0.22);
}
.ai-process-wrap.mode-phase2 .ai-process-bg-beam {
  background: linear-gradient(120deg, transparent 42%, rgba(248, 113, 113, 0.22) 50%, transparent 58%);
}
.ai-process-wrap.mode-phase2 .ai-process-progress-bar {
  background: linear-gradient(90deg, #ef4444, #f97316 52%, #f43f5e);
  box-shadow: 0 0 16px rgba(248, 113, 113, 0.45);
}
.ai-process-wrap.mode-phase2 .ai-process-title {
  text-shadow: 0 0 14px rgba(248, 113, 113, 0.42);
}
.ai-process-bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(56, 189, 248, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(56, 189, 248, 0.06) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: radial-gradient(circle at 50% 42%, #000 40%, transparent 90%);
  pointer-events: none;
}
.ai-process-bg-beam {
  position: absolute;
  top: -35%;
  left: -20%;
  width: 140%;
  height: 200%;
  background: linear-gradient(120deg, transparent 42%, rgba(56, 189, 248, 0.14) 50%, transparent 58%);
  transform: rotate(8deg);
  animation: beam-scan 2.8s linear infinite;
  pointer-events: none;
}
.ai-process-core {
  position: relative;
  width: 140px;
  height: 140px;
  margin: 0 auto 14px;
}
.pulse {
  position: absolute;
  inset: 0;
  border: 2px solid rgba(59,130,246,0.45);
  border-radius: 50%;
  animation: pulse 1.8s ease-out infinite;
}
.pulse-2 { animation-delay: 0.35s; border-color: rgba(96,165,250,0.45); }
.pulse-3 { animation-delay: 0.7s; border-color: rgba(147,197,253,0.45); }
.core-dot {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 22px;
  height: 22px;
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: #60a5fa;
  box-shadow: 0 0 22px rgba(96,165,250,0.9);
}
.ai-process-title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #f8fafc;
  text-shadow: 0 0 14px rgba(56, 189, 248, 0.36);
}
.ai-process-stage {
  margin-top: 6px;
  color: #dbeafe;
  font-size: 13px;
  letter-spacing: 0.18em;
}
.ai-process-progress {
  width: 88%;
  height: 8px;
  margin: 14px auto 0;
  border-radius: 99px;
  background: rgba(15, 23, 42, 0.9);
  border: 1px solid rgba(125, 211, 252, 0.22);
  overflow: hidden;
}

.ai-process-progress--indeterminate {
  position: relative;
}

.ai-process-progress-bar {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0ea5e9, #38bdf8 52%, #22d3ee);
  box-shadow: 0 0 16px rgba(56, 189, 248, 0.5);
  transition: width 0.45s ease;
}

.ai-process-progress-bar--indeterminate {
  width: 38%;
  animation: ai-progress-scan 1.15s ease-in-out infinite;
}

.ai-process-desc {
  margin-top: 14px;
  color: #f1f5f9;
  font-size: 15px;
  font-weight: 600;
}

.ai-process-note {
  margin-top: 8px;
  color: rgba(191, 219, 254, 0.78);
  font-size: 12px;
}
.ai-feed {
  margin: 16px auto 0;
  width: 88%;
  text-align: left;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(56, 189, 248, 0.35);
  background: rgba(15, 23, 42, 0.78);
}
.ai-feed-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #e2e8f0;
  line-height: 1.7;
}
.ai-feed-line .dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22d3ee;
  box-shadow: 0 0 8px rgba(34, 211, 238, 0.75);
}
@keyframes pulse {
  0% { transform: scale(0.45); opacity: 0.9; }
  70% { transform: scale(1); opacity: 0.15; }
  100% { transform: scale(1.08); opacity: 0; }
}
@keyframes beam-scan {
  0% { transform: translateX(-12%) rotate(8deg); opacity: 0.2; }
  50% { transform: translateX(8%) rotate(8deg); opacity: 0.5; }
  100% { transform: translateX(24%) rotate(8deg); opacity: 0.2; }
}
@keyframes ai-progress-scan {
  0% { transform: translateX(-110%); }
  50% { transform: translateX(95%); }
  100% { transform: translateX(-110%); }
}
</style>

<style lang="scss">
/* Teleport 到 body 的 Dialog 全局样式（非 scoped） */
.el-dialog.ai-process-modal,
.ai-process-modal .el-dialog {
  background: radial-gradient(circle at 50% 35%, rgba(30, 64, 175, 0.26), rgba(2, 6, 23, 0.98)) !important;
  border: 1px solid rgba(56, 189, 248, 0.42) !important;
  box-shadow: 0 20px 56px rgba(2, 6, 23, 0.75), 0 0 24px rgba(14, 165, 233, 0.2) !important;
}

.el-dialog.ai-process-modal .el-dialog__body,
.ai-process-modal .el-dialog__body {
  background: transparent !important;
}

.ai-process-overlay {
  background: rgba(1, 3, 10, 0.72) !important;
  backdrop-filter: blur(2px);
}

.el-dialog.report-modal,
.report-modal .el-dialog {
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.98), rgba(3, 7, 18, 0.98)) !important;
  border: 1px solid rgba(56, 189, 248, 0.28) !important;
  box-shadow: 0 24px 64px rgba(2, 6, 23, 0.75) !important;
}

.el-dialog.report-modal .el-dialog__header,
.report-modal .el-dialog__header {
  border-bottom: 1px solid rgba(56, 189, 248, 0.2);
  margin-right: 0 !important;
}

.el-dialog.report-modal .el-dialog__title,
.report-modal .el-dialog__title {
  color: #e2e8f0 !important;
  font-weight: 700;
}

.el-dialog.report-modal .el-dialog__body,
.report-modal .el-dialog__body {
  background: transparent !important;
}

.report-modal-overlay {
  background: rgba(1, 3, 10, 0.7) !important;
  backdrop-filter: blur(2px);
}

.el-dialog.notification-config-modal,
.notification-config-modal .el-dialog {
  background:
    radial-gradient(circle at top right, rgba(56, 189, 248, 0.16), transparent 34%),
    linear-gradient(180deg, rgba(5, 12, 24, 0.98), rgba(8, 15, 28, 0.99)) !important;
  border: 1px solid rgba(56, 189, 248, 0.24) !important;
  box-shadow: 0 24px 64px rgba(2, 6, 23, 0.76) !important;
}

.el-dialog.notification-config-modal .el-dialog__header,
.notification-config-modal .el-dialog__header {
  border-bottom: 1px solid rgba(125, 211, 252, 0.12);
  margin-right: 0 !important;
}

.el-dialog.notification-config-modal .el-dialog__title,
.notification-config-modal .el-dialog__title {
  color: #f8fafc !important;
  font-weight: 700;
  text-shadow: 0 2px 10px rgba(15, 23, 42, 0.35);
}

.el-dialog.notification-config-modal .detail-label,
.notification-config-modal .detail-label {
  color: #eaf2ff;
  font-weight: 600;
}

.el-dialog.notification-config-modal .el-input__wrapper,
.notification-config-modal .el-input__wrapper,
.el-dialog.notification-config-modal .el-textarea__inner,
.notification-config-modal .el-textarea__inner,
.el-dialog.notification-config-modal .el-input-number,
.notification-config-modal .el-input-number {
  background: rgba(9, 17, 32, 0.96) !important;
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.2) inset !important;
  border-radius: 12px !important;
}

.el-dialog.notification-config-modal .el-input__inner,
.notification-config-modal .el-input__inner,
.el-dialog.notification-config-modal .el-textarea__inner,
.notification-config-modal .el-textarea__inner {
  color: #f8fafc !important;
  -webkit-text-fill-color: #f8fafc !important;
  font-weight: 600;
  font-size: 14px;
  opacity: 1;
  caret-color: #f8fafc;
}

.el-dialog.notification-config-modal .el-input__inner::placeholder,
.notification-config-modal .el-input__inner::placeholder,
.el-dialog.notification-config-modal .el-textarea__inner::placeholder,
.notification-config-modal .el-textarea__inner::placeholder {
  color: rgba(219, 234, 254, 0.8) !important;
  -webkit-text-fill-color: rgba(219, 234, 254, 0.8) !important;
  opacity: 1 !important;
}

.el-dialog.notification-config-modal .el-input__inner:-webkit-autofill,
.notification-config-modal .el-input__inner:-webkit-autofill,
.el-dialog.notification-config-modal .el-input__inner:-webkit-autofill:hover,
.notification-config-modal .el-input__inner:-webkit-autofill:hover,
.el-dialog.notification-config-modal .el-input__inner:-webkit-autofill:focus,
.notification-config-modal .el-input__inner:-webkit-autofill:focus,
.el-dialog.notification-config-modal .el-textarea__inner:-webkit-autofill,
.notification-config-modal .el-textarea__inner:-webkit-autofill,
.el-dialog.notification-config-modal .el-textarea__inner:-webkit-autofill:hover,
.notification-config-modal .el-textarea__inner:-webkit-autofill:hover,
.el-dialog.notification-config-modal .el-textarea__inner:-webkit-autofill:focus,
.notification-config-modal .el-textarea__inner:-webkit-autofill:focus {
  -webkit-text-fill-color: #f8fafc !important;
  caret-color: #f8fafc !important;
  box-shadow: 0 0 0 1000px rgba(9, 17, 32, 0.98) inset !important;
  -webkit-box-shadow: 0 0 0 1000px rgba(9, 17, 32, 0.98) inset !important;
  transition: background-color 9999s ease-out 0s;
}

.el-dialog.notification-config-modal .el-input-number__increase,
.notification-config-modal .el-input-number__increase,
.el-dialog.notification-config-modal .el-input-number__decrease,
.notification-config-modal .el-input-number__decrease {
  background: rgba(15, 23, 42, 0.98) !important;
  color: #f8fafc !important;
  border-left: 1px solid rgba(148, 163, 184, 0.18);
}

.el-dialog.notification-config-modal .el-input__wrapper:hover,
.notification-config-modal .el-input__wrapper:hover,
.el-dialog.notification-config-modal .el-textarea__inner:hover,
.notification-config-modal .el-textarea__inner:hover,
.el-dialog.notification-config-modal .el-input-number:hover,
.notification-config-modal .el-input-number:hover {
  box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.3) inset !important;
}

.el-dialog.notification-config-modal .el-input__wrapper.is-focus,
.notification-config-modal .el-input__wrapper.is-focus,
.el-dialog.notification-config-modal .el-textarea__inner:focus,
.notification-config-modal .el-textarea__inner:focus,
.el-dialog.notification-config-modal .el-input-number.is-controls-right .el-input__wrapper.is-focus,
.notification-config-modal .el-input-number.is-controls-right .el-input__wrapper.is-focus {
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.58) inset, 0 0 0 4px rgba(56, 189, 248, 0.12) !important;
}

.el-dialog.notification-config-modal .el-input-number .el-input__inner,
.notification-config-modal .el-input-number .el-input__inner,
.el-dialog.notification-config-modal .el-switch__label,
.notification-config-modal .el-switch__label {
  color: #f8fafc !important;
  -webkit-text-fill-color: #f8fafc !important;
}

.el-dialog.timeline-modal,
.timeline-modal .el-dialog {
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.98), rgba(3, 7, 18, 0.98)) !important;
  border: 1px solid rgba(56, 189, 248, 0.25) !important;
  box-shadow: 0 24px 64px rgba(2, 6, 23, 0.75) !important;
}

.el-dialog.timeline-modal .el-dialog__title,
.timeline-modal .el-dialog__title {
  color: #e2e8f0 !important;
  font-weight: 700;
}

.el-dialog.timeline-modal .el-dialog__body,
.timeline-modal .el-dialog__body {
  background: transparent !important;
}

.el-dialog.timeline-modal .el-loading-mask,
.timeline-modal .el-loading-mask {
  background: rgba(2, 6, 23, 0.72) !important;
  backdrop-filter: blur(3px);
}

.el-dialog.timeline-modal .el-loading-spinner .path,
.timeline-modal .el-loading-spinner .path {
  stroke: #38bdf8 !important;
}

.el-dialog.timeline-modal .el-loading-spinner .el-loading-text,
.timeline-modal .el-loading-spinner .el-loading-text {
  color: #dbeafe !important;
}

.timeline-modal-overlay {
  background: rgba(1, 3, 10, 0.72) !important;
  backdrop-filter: blur(2px);
}
</style>

