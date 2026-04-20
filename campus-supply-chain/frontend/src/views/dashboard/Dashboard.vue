<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Box,
  ShoppingCart,
  Warning,
  Upload,
  Connection,
  ChatDotRound,
  List,
  User,
  OfficeBuilding,
  Van,
  Monitor,
  DataAnalysis,
  Edit,
  Key,
  Notebook,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import type { RoleType } from '@/types/role'
import { getDashboard } from '@/api/dashboard'
import type { PendingOutboundDocument, RecentOutboundSlip } from '@/api/dashboard'
import { createStockIn, createStockOut } from '@/api/stock'
import { createDelivery } from '@/api/delivery'
import { getPurchaseTimeline } from '@/api/purchase'
import type { PurchaseTimelineSummary, PurchaseTimelineItem } from '@/api/purchase'
import {
  approvalAlert,
  clearApprovalAlert,
  syncApprovalAlertFromStorage,
  getUnseenMisapprovalIds,
  markMisapprovalSeen,
  readAdminStatOverlay,
  bumpAdminStatOverlay,
  pushApplicantInboxNotice,
  setWarningToLogistics,
} from '@/stores/demo'
import { ElMessage, ElMessageBox } from 'element-plus'
import { isIdsSecurityCenterPath, openIdsSecurityCenter } from '@/utils/openIdsSecurityCenter'
import ConsoleIndex from '@/views/dashboard/console/ConsoleIndex.vue'

const router = useRouter()
const userStore = useUserStore()
const userRole = computed(() => userStore.userInfo?.role as RoleType)
let dashboardVoiceAudio: HTMLAudioElement | null = null

function playDashboardVoice(filename: string) {
  if (!dashboardVoiceAudio) dashboardVoiceAudio = new Audio()
  dashboardVoiceAudio.pause()
  dashboardVoiceAudio.currentTime = 0
  dashboardVoiceAudio.src = `/api/voice/${encodeURIComponent(filename)}`
  void dashboardVoiceAudio.play().catch(() => {
    // 语音文件缺失或浏览器策略限制时，不影响主流程
  })
}

// 真实数据（从 API 拉取）
const stats = ref<{ title: string; value: number; trend: string; trendValue: string; icon: string; path: string }[]>([])
const warnings = ref<{ id: number; time: string; level: string; levelLabel: string; material: string; desc: string }[]>([])
const teacherTodos = ref<{ id: number; time: string; status: string; statusLabel: string; title: string; desc: string }[]>([])
const supplierOrders = ref<{ id: number; time: string; title: string; desc: string }[]>([])
const expiringItems = ref<{ name: string; days: number; count: number }[]>([])
const chartData = ref<{ x: string[]; purchase: number[]; output: number[] }>({ x: [], purchase: [], output: [] })
const todayTodos = ref<{ pendingStockIn: number; pendingStockOut: number; pendingDeliveryCreate: number } | null>(null)
const handoffTasks = ref<{ id: number; order_no: string; status: string; status_label: string; receiver_name: string; destination: string; handoff_code: string }[]>([])
const pendingOutboundDocuments = ref<PendingOutboundDocument[]>([])
const recentOutboundSlips = ref<RecentOutboundSlip[]>([])
const idsSecurity = ref<{ total: number; blockedCount: number; todayCount: number; latest?: { client_ip: string; attack_type: string; created_at: string } } | null>(null)
const loading = ref(true)

// 无真实预警时的占位（与业务口径一致，可演练完整纠偏流程）
const demoAbnormalAlert = {
  orderNo: 'PO-20260318001',
  reason: 'AI 标记异常采购（100 台笔记本电脑，远超常规教学领用规模），已由后勤审批通过',
  applicantName: '李某某',
  applicantCollege: '信息学院',
  createdAt: '2026-03-18 10:00:00',
}

const attackTypeLabels: Record<string, string> = {
  sql_injection: 'SQL 注入',
  xss: 'XSS',
  path_traversal: '路径遍历',
  cmd_injection: '命令注入',
  scanner: '扫描探测',
  malformed: '畸形请求',
}

const showChart = computed(() => userRole.value === 'logistics_admin' || userRole.value === 'warehouse_procurement')

const defaultDynamic = [
  { username: '溯源服务', type: '生成报告', target: '批次 TR-20260312' },
  { username: '仓储', type: '完成入库', target: '办公耗材 PO-088' },
  { username: '后勤', type: '审批通过', target: '教学耗材申请' },
  { username: '配送', type: '已签收', target: '教学楼 A 区' },
  { username: '预警', type: '临期提醒', target: '消毒液 30 天内到期' },
]

/** 管理员端工作台：高密度动态摘要 */
const supplyAdminDynamics = [
  { username: '北区仓', type: '入库完成', target: 'PO-20260308-112 医用口罩 1200 件' },
  { username: '后勤处', type: '审批通过', target: '实验耗材集中采购计划' },
  { username: '供应商-康源', type: '发货确认', target: 'SO-77821 预计 18:00 到校' },
  { username: '配送班组', type: '在途', target: '车辆 #粤B·D0921 → 图书馆卸货点' },
  { username: '溯源引擎', type: '批次归档', target: 'BATCH-2026-Q1-009 已上链' },
  { username: '南区仓', type: '库存调整', target: '消毒液实盘 +36 瓶' },
  { username: 'IDS', type: '拦截', target: '192.168.x.x 路径遍历尝试' },
  { username: '辅导员办', type: '提交申请', target: '春季劳保用品' },
  { username: '预警中心', type: '低库存', target: 'A4 打印纸 安全库存以下' },
  { username: '供应商-晨光', type: '接单', target: 'PO-20260310-03 文具包' },
  { username: '仓储大屏', type: '刷新指标', target: '当日出库件数 +12%' },
  { username: '仓储大屏', type: '同步', target: '供应链 KPI 看板' },
  { username: '财务', type: '对账完成', target: '2 月后勤采购结算单' },
  { username: '质检', type: '抽检合格', target: '批次 TR-20260228-01' },
  { username: 'AI 助手', type: '解析意图', target: '自然语言 → 采购草稿' },
  { username: '安全审计', type: '标记关注', target: '敏感操作 purchase_reject ×3' },
  { username: '车队', type: '路线优化', target: '合并 2 单同校区配送' },
  { username: '信息中心', type: '角色变更', target: '账号权限复核' },
  { username: '供应商-联创', type: '延期申请', target: '到货顺延 1 工作日' },
  { username: '北区仓', type: '出库复核', target: '教学点 B 教材包' },
  { username: '后勤处', type: '驳回', target: '单价异常申请' },
  { username: '配送', type: '签收异常', target: '收件人电话未接通，已留言' },
  { username: '仓储', type: '盘点任务', target: 'Q1 固定资产抽盘' },
  { username: '供应商门户', type: '对账单', target: '已推送 3 月对账 PDF' },
  { username: '溯源', type: '扫码查询', target: '师生端查询 +86 次' },
  { username: '预警', type: '临期', target: '洗手液 45 天内到期' },
  { username: '南区仓', type: '退货入库', target: 'RMA-009 包装破损' },
  { username: '系统', type: '定时任务', target: '库存快照备份成功' },
]

const adminStatOverlay = ref(readAdminStatOverlay())

const displayStats = computed(() =>
  stats.value.map((s) => {
    const base = {
      ...s,
      trendValue:
        s.trendValue ||
        (s.trend === 'up' ? '+11.6%' : s.trend === 'down' ? '-3.8%' : '—'),
    }
    if (userRole.value !== 'system_admin') return base
    const o = adminStatOverlay.value
    const v = Number(s.value) || 0
    if (s.title === '审计日志') return { ...base, value: v + o.audit }
    if (s.title === '敏感操作') return { ...base, value: v + o.sensitive }
    return base
  })
)

const showDemoAbnormalCard = computed(() => userRole.value === 'system_admin' && !approvalAlert.value)

const timelineSummary = ref<PurchaseTimelineSummary | null>(null)
const timelineItems = ref<PurchaseTimelineItem[]>([])

const quickRejectDialogVisible = ref(false)
const punishDialogVisible = ref(false)
const traceDrawerVisible = ref(false)
const resolveSummaryReason = ref('')
const teacherRejectNotice = ref('')
const logisticsWarningNotice = ref('')
const quickRejectWithWarning = ref(true)
const punishType = ref<'oral' | 'suspend' | 'blacklist'>('oral')
const punishmentDetail = ref('')

async function refreshAbnormalTimeline() {
  const id = approvalAlert.value?.purchaseId
  if (!id) {
    timelineSummary.value = null
    timelineItems.value = []
    return
  }
  try {
    const res: any = await getPurchaseTimeline(id)
    const d = res?.data ?? res
    timelineSummary.value = d.summary ?? null
    timelineItems.value = d.timeline ?? []
  } catch {
    timelineSummary.value = null
    timelineItems.value = []
  }
}

watch(approvalAlert, () => {
  void refreshAbnormalTimeline()
})

function inferResponsibleLogisticsName() {
  for (let i = timelineItems.value.length - 1; i >= 0; i--) {
    const t = timelineItems.value[i]
    if (t.stage !== '审批') continue
    if (!/审批通过/.test(t.content || '')) continue
    const m = (t.content || '').match(/审批人\s*([^\s（(]+)/)
    if (m?.[1]) return m[1]
  }
  return '后勤管理员'
}

function currentAbnormalMeta() {
  if (approvalAlert.value) {
    return {
      orderNo: approvalAlert.value.orderNo,
      reason: approvalAlert.value.reason,
      applicantName: approvalAlert.value.applicantName || timelineSummary.value?.applicant_name || '—',
      college: approvalAlert.value.applicantCollege || timelineSummary.value?.destination || '—',
      createdAt:
        approvalAlert.value.createdAt ||
        timelineSummary.value?.created_at ||
        '—',
      purchaseId: approvalAlert.value.purchaseId,
    }
  }
  return {
    orderNo: demoAbnormalAlert.orderNo,
    reason: demoAbnormalAlert.reason,
    applicantName: demoAbnormalAlert.applicantName,
    college: demoAbnormalAlert.applicantCollege,
    createdAt: demoAbnormalAlert.createdAt,
    purchaseId: undefined as number | undefined,
  }
}

function openQuickRejectDialog() {
  const meta = currentAbnormalMeta()
  const owner = inferResponsibleLogisticsName()
  resolveSummaryReason.value = meta.reason
  teacherRejectNotice.value = `您的申请单 ${meta.orderNo} 已由系统管理员驳回。原因：${meta.reason}。如有疑问请联系后勤处复核。`
  logisticsWarningNotice.value = `责任人 ${owner} 在 AI 已判定异常的情况下强行通过审批，已触发管理警告并记入审计。`
  quickRejectWithWarning.value = true
  quickRejectDialogVisible.value = true
}

function openPunishDialog() {
  const meta = currentAbnormalMeta()
  const owner = inferResponsibleLogisticsName()
  resolveSummaryReason.value = meta.reason
  logisticsWarningNotice.value = `责任人 ${owner} 在 AI 已判定异常的情况下强行通过审批，已触发管理警告并记入审计。`
  punishType.value = 'oral'
  punishmentDetail.value = '经核查，该申请采购数量远超教学需求，违反校园采购管理规定，予以驳回并通报批评。'
  punishDialogVisible.value = true
}

function buildDecisionDoc(): string {
  const meta = currentAbnormalMeta()
  const owner = inferResponsibleLogisticsName()
  const t = new Date().toISOString().slice(0, 19).replace('T', ' ')
  return [
    '异常审批处置单',
    '',
    `异常单号：${meta.orderNo}`,
    `申请人：${meta.applicantName}（${meta.college}）`,
    `驳回原因：${resolveSummaryReason.value.trim() || meta.reason}`,
    `教师通知：${teacherRejectNotice.value.trim()}`,
    `后勤责任人：${owner}`,
    `责任警告：${logisticsWarningNotice.value.trim()}`,
    `后勤责任警告：${logisticsWarningNotice.value.trim()}`,
    `处罚类型：${{ oral: '口头警告（全院通报）', suspend: '暂停部门采购权限 1 个月', blacklist: '列入采购黑名单' }[punishType.value]}`,
    `处罚说明：${punishmentDetail.value.trim() || '未填写'}`,
    `生效时间（UTC）：${t}`,
    '处理链路：管理员纠偏驳回 → 通知申请教师 → 警告后勤责任人',
    '',
    '（本文件为系统生成留痕，可打印归档）',
  ].join('\n')
}

function downloadDecisionDoc() {
  const blob = new Blob([buildDecisionDoc()], { type: 'text/plain;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `异常审批处置单_${currentAbnormalMeta().orderNo}.txt`
  a.click()
  URL.revokeObjectURL(url)
}

async function submitResolveDialog() {
  if (quickRejectWithWarning.value && logisticsWarningNotice.value.trim().length < 4) {
    ElMessage.warning('请选择“仅驳回”或填写有效的后勤警告内容')
    return
  }
  const meta = currentAbnormalMeta()
  const logisticsBody = quickRejectWithWarning.value
    ? logisticsWarningNotice.value.trim()
    : '管理员已执行驳回纠偏，本次不追加责任警告。'
  const aid = timelineSummary.value?.applicant_id
  if (aid) {
    pushApplicantInboxNotice(
      Number(aid),
      `申请驳回通知 · ${meta.orderNo}`,
      teacherRejectNotice.value.trim() || `您的申请单 ${meta.orderNo} 已被管理员驳回。`,
    )
  }
  if (quickRejectWithWarning.value) {
    setWarningToLogistics({
      orderNo: meta.orderNo,
      subject: `异常审批责任提醒 · ${inferResponsibleLogisticsName()}`,
      body: logisticsBody,
    })
  }
  clearApprovalAlert()
  bumpAdminStatOverlay('warn')
  adminStatOverlay.value = readAdminStatOverlay()
  quickRejectDialogVisible.value = false
  playDashboardVoice('驳回申请语音.mp3')
  ElMessage.success(`已完成驳回${quickRejectWithWarning.value ? '并下发责任警告' : ''}`)
  await loadDashboard()
}

async function submitPunishDialog() {
  if (punishmentDetail.value.trim().length < 4) {
    ElMessage.warning('请填写处罚说明（至少 4 个字符）')
    return
  }
  const meta = currentAbnormalMeta()
  const punishTextMap = {
    oral: '口头警告（全院通报）',
    suspend: '暂停部门采购权限 1 个月',
    blacklist: '列入采购黑名单',
  } as const
  const aid = timelineSummary.value?.applicant_id
  if (aid) {
    pushApplicantInboxNotice(
      Number(aid),
      `申请驳回通知 · ${meta.orderNo}`,
      teacherRejectNotice.value.trim() || `您的申请单 ${meta.orderNo} 已被管理员驳回。`,
    )
  }
  setWarningToLogistics({
    orderNo: meta.orderNo,
    subject: `处罚决定 · ${inferResponsibleLogisticsName()}`,
    body: `${logisticsWarningNotice.value.trim()}\n处罚类型：${punishTextMap[punishType.value]}\n处罚说明：${punishmentDetail.value.trim()}`,
  })
  clearApprovalAlert()
  bumpAdminStatOverlay('penalty')
  adminStatOverlay.value = readAdminStatOverlay()
  punishDialogVisible.value = false
  downloadDecisionDoc()
  playDashboardVoice('驳回申请语音.mp3')
  ElMessage.success('已执行处罚并完成前端留痕（已导出处置单）')
  await loadDashboard()
}

const consoleDynamicItems = computed(() => {
  const r = userRole.value
  if (r === 'system_admin') return supplyAdminDynamics
  if (r === 'logistics_admin' && warnings.value.length) {
    return warnings.value.slice(0, 14).map((w) => ({
      username: w.time,
      type: w.levelLabel,
      target: `${w.material} ${w.desc}`.trim(),
    }))
  }
  if (r === 'counselor_teacher' && teacherTodos.value.length) {
    return teacherTodos.value.slice(0, 14).map((a) => ({
      username: a.time,
      type: a.statusLabel,
      target: `${a.title} ${a.desc}`.trim(),
    }))
  }
  if (r === 'campus_supplier' && supplierOrders.value.length) {
    return supplierOrders.value.slice(0, 14).map((o) => ({
      username: o.time,
      type: '待接单',
      target: `${o.title} ${o.desc}`.trim(),
    }))
  }
  return defaultDynamic
})

// 快捷入口
const shortcuts = computed(() => {
  const logisticsBase = [
    { icon: ChatDotRound, label: 'AI 助手', path: '/ai/chat' },
    { icon: Connection, label: '溯源查询', path: '/trace' },
    { icon: ShoppingCart, label: '审批台', path: '/purchase' },
    { icon: Warning, label: '预警中心', path: '/warning' },
    { icon: Monitor, label: '后勤大屏', path: '/screen/logistics' },
    { icon: DataAnalysis, label: '全景大屏', path: '/dashboard/analysis' },
  ]
  const warehouseBase = [
    { icon: ChatDotRound, label: 'AI 助手', path: '/ai/chat' },
    { icon: Connection, label: '溯源查询', path: '/trace' },
    { icon: Upload, label: '入库管理', path: '/stock/in' },
    { icon: Box, label: '物资与库存', path: '/goods' },
    { icon: Van, label: '配送管理', path: '/delivery' },
    { icon: DataAnalysis, label: '仓储大屏', path: '/dashboard/analysis' },
  ]
  const adminBase = [
    { icon: User, label: '用户管理', path: '/system/users' },
    { icon: Key, label: '角色管理', path: '/system/roles' },
    { icon: OfficeBuilding, label: '供应商管理', path: '/supplier' },
    { icon: Notebook, label: '操作日志与审计', path: '/system/operation-logs' },
    { icon: Connection, label: '溯源查询', path: '/trace' },
    { icon: DataAnalysis, label: '全景大屏', path: '/dashboard/analysis' },
  ]
  if (userRole.value === 'counselor_teacher') {
    return [
      { icon: ChatDotRound, label: '智能工作台', path: '/teacher/workbench' },
      { icon: Edit, label: '采购申请', path: '/purchase/apply' },
      { icon: User, label: '个人中心', path: '/teacher/personal' },
      { icon: Connection, label: '溯源', path: '/trace' },
    ]
  }
  if (userRole.value === 'system_admin') return adminBase
  if (userRole.value === 'warehouse_procurement') return warehouseBase
  if (userRole.value === 'campus_supplier') {
    return [
      { icon: List, label: '我的订单', path: '/supplier/orders' },
      { icon: DataAnalysis, label: '全景大屏', path: '/dashboard/analysis' },
    ]
  }
  return logisticsBase
})

async function loadDashboard() {
  loading.value = true
  try {
    const res = await getDashboard()
    const d = res as any
    stats.value = d.stats || []
    chartData.value = d.chartData || { x: [], purchase: [], output: [] }
    expiringItems.value = d.expiringItems || []
    todayTodos.value = d.todayTodos || null
    handoffTasks.value = d.handoffTasks || []
    pendingOutboundDocuments.value = d.pendingOutboundDocuments || []
    recentOutboundSlips.value = d.recentOutboundSlips || []
    idsSecurity.value = d.idsSecurity || null

    if (userRole.value === 'counselor_teacher') {
      teacherTodos.value = d.warningList || []
    } else if (userRole.value === 'campus_supplier') {
      supplierOrders.value = d.warningList || []
    } else {
      warnings.value = d.warnings || d.warningList || []
    }
  } catch (_) {
    stats.value = []
    chartData.value = { x: [], purchase: [], output: [] }
    pendingOutboundDocuments.value = []
    recentOutboundSlips.value = []
  } finally {
    loading.value = false
  }
}

async function quickStockIn(task: { id: number }) {
  try {
    await createStockIn({ purchase_id: task.id })
    ElMessage.success('入库成功')
    loadDashboard()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '入库失败')
  }
}

async function quickStockOut(task: { id: number }) {
  try {
    await createStockOut({ purchase_id: task.id })
    ElMessage.success('出库成功')
    loadDashboard()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '出库失败')
  }
}

async function quickCreateDelivery(task: { id: number; destination?: string; receiver_name?: string }) {
  try {
    await createDelivery({
      purchase_id: task.id,
      destination: task.destination || '',
      receiver_name: task.receiver_name || '',
    })
    ElMessage.success('配送单已创建')
    loadDashboard()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '创建失败')
  }
}

function navigate(path: string) {
  if (!path) return
  if (isIdsSecurityCenterPath(path)) {
    void openIdsSecurityCenter()
    return
  }
  router.push(path.startsWith('/') ? path : `/${path}`)
}

onMounted(async () => {
  syncApprovalAlertFromStorage()
  adminStatOverlay.value = readAdminStatOverlay()
  await loadDashboard()
  if (userRole.value === 'system_admin') {
    await refreshAbnormalTimeline()
    const unseen = getUnseenMisapprovalIds()
    if (unseen.length) {
      ElMessageBox.alert(
        `发现 ${unseen.length} 条异常操作（误批）待审查，请前往「操作日志」中的审计页签处理。`,
        '异常操作告警',
        { type: 'warning', confirmButtonText: '前往查看' }
      ).then(() => {
        unseen.forEach(markMisapprovalSeen)
        router.push({ path: '/system/operation-logs', query: { tab: 'audit' } })
      })
    }
  }
})
</script>

<template>
  <div class="dashboard" v-loading="loading">
    <!-- 异常预警 · 误批提醒（管理员） -->
    <div v-if="userRole === 'system_admin' && (approvalAlert || showDemoAbnormalCard)" class="abnormal-alert-section">
      <h3 class="section-title">异常预警</h3>
      <div class="abnormal-card" :class="{ 'is-demo': !approvalAlert }" role="button" tabindex="0" @click="traceDrawerVisible = true" @keydown.enter.prevent="traceDrawerVisible = true">
        <div class="abnormal-main">
          <div class="abnormal-main__title">
            <span class="abnormal-risk-badge">高风险异常</span>
            <span class="abnormal-order">{{ currentAbnormalMeta().orderNo }}</span>
            <span class="abnormal-title-text">AI 标记异常采购</span>
          </div>
          <div class="abnormal-main__meta">
            <span>申请人：{{ currentAbnormalMeta().applicantName }}</span>
            <span>单位：{{ currentAbnormalMeta().college }}</span>
            <span>申请时间：{{ currentAbnormalMeta().createdAt }}</span>
          </div>
          <div class="abnormal-main__reason">
            <span class="abnormal-main__reason-text">异常原因：{{ currentAbnormalMeta().reason }}</span>
            <span class="ai-tag">AI 智能识别</span>
          </div>
          <div class="abnormal-main__hint">点击卡片展开完整申请与溯源时间线</div>
        </div>
        <div class="abnormal-actions" @click.stop>
          <el-dropdown split-button type="danger" size="small" trigger="click" @click="openQuickRejectDialog" @command="(c: string) => (c === 'punish' ? openPunishDialog() : openQuickRejectDialog())">
            驳回并处置
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="warn">驳回并警告</el-dropdown-item>
                <el-dropdown-item command="punish" divided>下发处罚</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-button type="primary" plain size="small" class="abnormal-actions__detail" @click.stop="traceDrawerVisible = true">查看详情</el-button>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="quickRejectDialogVisible"
      title="确认驳回异常申请"
      width="600px"
      destroy-on-close
      align-center
      class="abnormal-dialog"
    >
      <div class="ab-dialog-block">
        <h4>异常订单核心信息</h4>
        <ul class="ab-dialog-facts">
          <li>异常单号：{{ currentAbnormalMeta().orderNo }}</li>
          <li>申请人：{{ currentAbnormalMeta().applicantName }}（{{ currentAbnormalMeta().college }}）</li>
          <li>异常原因：{{ currentAbnormalMeta().reason }}</li>
          <li>申请时间：{{ currentAbnormalMeta().createdAt }}</li>
          <li>责任后勤：{{ inferResponsibleLogisticsName() }}（AI 已判异常仍强行通过）</li>
        </ul>
      </div>
      <div class="ab-dialog-block">
        <h4>处置选项</h4>
        <el-checkbox v-model="quickRejectWithWarning">驳回并下发责任警告</el-checkbox>
        <el-input v-model="resolveSummaryReason" class="ab-mt" type="textarea" :rows="2" placeholder="驳回摘要（写入审计）" />
        <el-input v-model="teacherRejectNotice" class="ab-mt" type="textarea" :rows="2" placeholder="教师驳回通知内容" />
        <el-input v-if="quickRejectWithWarning" v-model="logisticsWarningNotice" class="ab-mt" type="textarea" :rows="2" placeholder="后勤责任人警告内容" />
      </div>
      <template #footer>
        <el-button @click="quickRejectDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="submitResolveDialog">确认驳回</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="punishDialogVisible" title="异常采购处罚决定书" width="620px" destroy-on-close align-center class="abnormal-dialog">
      <div class="ab-dialog-block">
        <h4>违规事实</h4>
        <p class="ab-muted">信息学院 {{ currentAbnormalMeta().applicantName }} 提交异常采购，AI 已标记异常，但被后勤责任人强行审批通过。</p>
      </div>
      <div class="ab-dialog-block">
        <h4>处罚类型</h4>
        <el-radio-group v-model="punishType" class="ab-radio-col">
          <el-radio label="oral">🟢 口头警告（全院通报）</el-radio>
          <el-radio label="suspend">🟡 暂停部门采购权限 1 个月</el-radio>
          <el-radio label="blacklist">🔴 列入采购黑名单</el-radio>
        </el-radio-group>
      </div>
      <div class="ab-dialog-block">
        <h4>处罚说明</h4>
        <el-input v-model="punishmentDetail" type="textarea" :rows="4" maxlength="800" show-word-limit placeholder="经核查，该申请采购数量远超教学需求，违反校园采购管理规定，予以驳回并通报批评" />
      </div>
      <template #footer>
        <el-button @click="punishDialogVisible = false">取消</el-button>
        <el-button type="danger" @click="submitPunishDialog">确认执行</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="traceDrawerVisible" size="620px" title="异常申请全链路溯源" direction="rtl" :destroy-on-close="false">
      <div class="ab-drawer">
        <div class="ab-dialog-block">
          <h4>申请详情</h4>
          <ul class="ab-dialog-facts">
            <li>单号：{{ currentAbnormalMeta().orderNo }}</li>
            <li>申请人：{{ currentAbnormalMeta().applicantName }}</li>
            <li>申请时间：{{ currentAbnormalMeta().createdAt }}</li>
          </ul>
        </div>
        <div class="ab-dialog-block">
          <h4>时间线可视化</h4>
          <el-timeline>
            <el-timeline-item v-for="(ev, i) in timelineItems.length ? timelineItems : [{ stage: '申请提交', content: '暂无可用时间线数据（可在溯源查询中检索）', time: '' }]" :key="i" :timestamp="ev.time">
              <span class="tl-stage">{{ ev.stage }}</span>{{ ev.content }}
            </el-timeline-item>
          </el-timeline>
        </div>
        <div class="ab-drawer__foot">
          <el-button @click="traceDrawerVisible = false">关闭</el-button>
          <el-button type="primary" @click="downloadDecisionDoc">导出溯源报告（mock）</el-button>
        </div>
      </div>
    </el-drawer>

    <!-- 安全拦截 · 攻击发生立刻知道（管理员） -->
    <div v-if="userRole === 'system_admin' && idsSecurity" class="ids-security-section">
      <h3 class="section-title">🛡️ 安全拦截 · 攻击发生立刻知道</h3>
      <div class="ids-security-grid">
        <div class="ids-stat">
          <span class="ids-value">{{ idsSecurity.total }}</span>
          <span class="ids-label">累计检测</span>
        </div>
        <div class="ids-stat">
          <span class="ids-value highlight">{{ idsSecurity.blockedCount }}</span>
          <span class="ids-label">已封禁 IP</span>
        </div>
        <div class="ids-stat">
          <span class="ids-value">{{ idsSecurity.todayCount }}</span>
          <span class="ids-label">今日拦截</span>
        </div>
      </div>
      <div v-if="idsSecurity.latest" class="ids-latest">
        <span class="ids-latest-label">最近一条：</span>
        <span>{{ idsSecurity.latest.created_at }} 拦截 {{ idsSecurity.latest.client_ip }} 的 {{ attackTypeLabels[idsSecurity.latest.attack_type] || idsSecurity.latest.attack_type }} 攻击</span>
      </div>
      <el-button type="primary" link size="small" @click="navigate('/ids')">查看详情</el-button>
    </div>

    <!-- 今日待办 · 做完一个少一个（仅仓储） -->
    <div v-if="userRole === 'warehouse_procurement' && todayTodos" class="today-todos-section">
      <h3 class="section-title">今日待办 · 做完一个少一个</h3>
      <div class="today-todos-grid">
        <div class="todo-block" @click="navigate('/stock/in')">
          <span class="todo-value">{{ todayTodos.pendingStockIn }}</span>
          <span class="todo-label">待入库</span>
        </div>
        <div class="todo-block" @click="navigate('/stock/out')">
          <span class="todo-value">{{ todayTodos.pendingStockOut }}</span>
          <span class="todo-label">待出库</span>
        </div>
        <div class="todo-block" @click="navigate('/purchase')">
          <span class="todo-value">{{ todayTodos.pendingDeliveryCreate }}</span>
          <span class="todo-label">待创建配送</span>
        </div>
      </div>
      <div v-if="handoffTasks.length" class="handoff-task-list">
        <div v-for="t in handoffTasks" :key="t.id" class="handoff-task-item">
          <span class="task-no">{{ t.order_no }}</span>
          <span class="task-dest">{{ t.destination }}</span>
          <span class="task-action">
            <el-button
              v-if="t.status === 'shipped' || t.status === 'approved'"
              type="primary"
              size="small"
              @click.stop="quickStockIn(t)"
            >
              入库
            </el-button>
            <el-button v-if="t.status === 'stocked_in'" type="success" size="small" @click.stop="quickStockOut(t)">
              出库
            </el-button>
            <el-button v-if="t.status === 'stocked_out'" type="warning" size="small" @click.stop="quickCreateDelivery(t)">
              创建配送
            </el-button>
          </span>
        </div>
      </div>
    </div>

    <!-- 教师申领出库单：待出库备货 + 已开出库回执（与仓储大屏同源接口数据） -->
    <div
      v-if="userRole === 'warehouse_procurement' && (pendingOutboundDocuments.length || recentOutboundSlips.length)"
      class="outbound-slip-section"
    >
      <div class="outbound-slip-section__hd">
        <h3 class="section-title">教师申领 · 出库单</h3>
        <p class="outbound-slip-section__sub">
          申领经审批、入库完成后在此生成备货明细；确认出库后生成下方「已开出库单」，与仓储大屏待办数字一致联动。
        </p>
      </div>
      <div v-if="pendingOutboundDocuments.length" class="outbound-slip-grid">
        <article v-for="doc in pendingOutboundDocuments" :key="doc.purchase_id" class="outbound-slip outbound-slip--pending">
          <header class="outbound-slip__hd">
            <span class="outbound-slip__badge">出库备货单</span>
            <span class="outbound-slip__no">{{ doc.order_no }}</span>
            <el-button type="success" size="small" class="outbound-slip__go" @click="quickStockOut({ id: doc.purchase_id })">
              确认出库
            </el-button>
          </header>
          <dl class="outbound-slip__meta">
            <div><dt>申领人</dt><dd>{{ doc.applicant_name }}</dd></div>
            <div><dt>收货人</dt><dd>{{ doc.receiver_name || '—' }}</dd></div>
            <div><dt>目的地</dt><dd>{{ doc.destination || '—' }}</dd></div>
            <div v-if="doc.material_type"><dt>类型</dt><dd>{{ doc.material_type }}</dd></div>
          </dl>
          <table class="outbound-slip__table">
            <thead>
              <tr><th>物资</th><th class="num">数量</th><th>单位</th></tr>
            </thead>
            <tbody>
              <tr v-for="(ln, idx) in doc.lines" :key="idx">
                <td>{{ ln.goods_name }}</td>
                <td class="num">{{ ln.quantity }}</td>
                <td>{{ ln.unit }}</td>
              </tr>
            </tbody>
          </table>
        </article>
      </div>
      <p v-else class="outbound-slip-empty">当前无待出库备货单；教师新提交且完成入库后将出现在此。</p>

      <h4 v-if="recentOutboundSlips.length" class="outbound-slip-recent-title">近期已开出库单</h4>
      <div v-if="recentOutboundSlips.length" class="outbound-slip-grid outbound-slip-grid--recent">
        <article v-for="slip in recentOutboundSlips" :key="slip.stock_out_order_no" class="outbound-slip outbound-slip--done">
          <header class="outbound-slip__hd">
            <span class="outbound-slip__badge outbound-slip__badge--done">已出库</span>
            <span class="outbound-slip__no">{{ slip.stock_out_order_no }}</span>
            <span class="outbound-slip__po">关联 {{ slip.purchase_order_no || '—' }}</span>
          </header>
          <dl class="outbound-slip__meta outbound-slip__meta--compact">
            <div><dt>交接码</dt><dd>{{ slip.handoff_code || '—' }}</dd></div>
            <div><dt>时间</dt><dd>{{ slip.created_at }}</dd></div>
            <div><dt>目的地</dt><dd>{{ slip.destination || '—' }}</dd></div>
          </dl>
          <ul class="outbound-slip__lines">
            <li v-for="(ln, idx) in slip.lines.slice(0, 6)" :key="idx">
              {{ ln.goods_name }} <strong>{{ ln.quantity }}{{ ln.unit }}</strong>
            </li>
            <li v-if="slip.lines.length > 6" class="outbound-slip__more">等 {{ slip.lines.length }} 条明细…</li>
          </ul>
          <el-button link type="primary" size="small" @click="navigate('/stock/out')">出库记录</el-button>
        </article>
      </div>
    </div>

    <ConsoleIndex
      :stat-cards="displayStats"
      :chart-data="chartData"
      :show-purchase-chart="showChart"
      :dynamic-items="consoleDynamicItems"
      :shortcuts="shortcuts"
      :expiring-items="expiringItems"
      :show-expiring="userRole === 'warehouse_procurement'"
      :admin-console="userRole === 'system_admin'"
    />
  </div>
</template>

<style lang="scss" scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.abnormal-alert-section {
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  padding: 18px 20px;
}
.abnormal-alert-section .section-title {
  font-size: 15px;
  color: #111827;
  margin: 0 0 14px 0;
  font-weight: 700;
}
.abnormal-item { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
.abnormal-item .abnormal-order { font-weight: 600; color: var(--el-color-danger); }
.abnormal-item .abnormal-reason { flex: 1; font-size: 13px; color: var(--text-secondary); }
.abnormal-item.demo .abnormal-order { color: var(--text-muted); }

.abnormal-card {
  background: #ffffff;
  border: 1px solid #f3d2d5;
  border-radius: 10px;
  padding: 14px 16px;
  cursor: pointer;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
  display: flex;
  align-items: flex-start;
  gap: 16px;
}
.abnormal-card:hover {
  border-color: #eab2b9;
  box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
}
.abnormal-card.is-demo {
  opacity: 0.96;
  border-style: dashed;
}
.abnormal-main {
  flex: 1;
  min-width: 260px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 6px;
}
.abnormal-main__title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.abnormal-risk-badge {
  display: inline-flex;
  align-items: center;
  border-radius: 999px;
  border: 1px solid #fca5a5;
  background: #fff1f2;
  color: #b91c1c;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
}
.abnormal-main__title .abnormal-order {
  font-size: 17px;
  font-weight: 800;
  color: #b91c1c;
}
.abnormal-title-text {
  font-size: 16px;
  font-weight: 700;
  color: #991b1b;
}
.abnormal-main__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  font-size: 12px;
  color: #6b7280;
}
.abnormal-main__reason {
  font-size: 13px;
  color: #374151;
  line-height: 1.5;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
}
.abnormal-main__reason-text {
  flex: 1;
  min-width: 0;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.ai-tag {
  font-size: 11px;
  font-weight: 600;
  color: #1e3a8a;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  border-radius: 999px;
  padding: 2px 8px;
}
.abnormal-main__hint {
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
}
.abnormal-actions {
  width: 168px;
  flex-shrink: 0;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  padding: 10px;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  gap: 8px;
}
.abnormal-actions :deep(.el-dropdown) {
  display: block;
  width: 100%;
}
.abnormal-actions :deep(.el-button-group) {
  display: flex;
  width: 100%;
}
.abnormal-actions :deep(.el-button-group > .el-dropdown__main-button) {
  flex: 1 1 auto;
  min-width: 0;
}
.abnormal-actions :deep(.el-button-group > .el-dropdown__caret-button) {
  flex: 0 0 36px;
  width: 36px;
}
.abnormal-actions__detail {
  width: 100%;
}
.abnormal-actions :deep(.el-button) {
  font-weight: 600;
}
.abnormal-actions :deep(.el-button--danger) {
  border-radius: 8px;
}
.abnormal-actions :deep(.el-button-group > .el-dropdown__main-button) {
  border-top-right-radius: 0;
  border-bottom-right-radius: 0;
}
.abnormal-actions :deep(.el-button-group > .el-dropdown__caret-button) {
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
}
.tl-stage {
  font-weight: 600;
  color: #b45309;
  margin-right: 6px;
}
.ab-muted {
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
}

.ab-dialog-block h4 {
  margin: 0 0 10px 0;
  font-size: 13px;
  color: #0f172a;
}
.ab-dialog-facts {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-secondary);
}
.ab-radio-col {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
}
.ab-radio-col :deep(.el-radio) {
  margin-right: 0;
  height: auto;
  white-space: normal;
  align-items: flex-start;
}
.ab-mt {
  margin-top: 10px;
}
.ab-drawer {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ab-drawer__foot {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 8px;
}
@media (max-width: 980px) {
  .abnormal-card {
    flex-direction: column;
  }
  .abnormal-actions {
    width: 100%;
  }
  .abnormal-main {
    min-width: 0;
  }
}

.ids-security-section {
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 100%);
  border: 1px solid #fcd34d;
  border-radius: 12px;
  padding: 20px 24px;
}
.ids-security-section .section-title {
  font-size: 14px;
  color: #92400e;
  margin: 0 0 12px 0;
  font-weight: 600;
}
.ids-security-grid {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
}
.ids-stat {
  .ids-value { font-size: 24px; font-weight: 700; color: #78350f; }
  .ids-value.highlight { color: #dc2626; }
  .ids-label { display: block; font-size: 12px; color: #92400e; }
}
.ids-latest {
  font-size: 13px; color: #78350f; margin-bottom: 8px;
  .ids-latest-label { font-weight: 600; }
}
/* 黄底上的「查看详情」：深蓝字 + 白底条，避免主色 link 在黄底上发糊 */
.ids-security-section :deep(.el-button.is-link.el-button--primary) {
  color: #1e3a8a !important;
  font-weight: 600;
  padding: 6px 12px !important;
  border-radius: 8px !important;
  background: rgba(255, 255, 255, 0.92) !important;
  border: 1px solid rgba(30, 58, 138, 0.2) !important;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06) !important;
}
.ids-security-section :deep(.el-button.is-link.el-button--primary:hover) {
  color: #172554 !important;
  background: #ffffff !important;
  border-color: rgba(30, 58, 138, 0.35) !important;
}

.today-todos-section {
  background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
  border: 1px solid #93c5fd;
  border-radius: 12px;
  padding: 20px 24px;
}
.today-todos-section .section-title {
  font-size: 14px;
  color: #1e40af;
  margin: 0 0 16px 0;
  font-weight: 600;
}
.today-todos-grid {
  display: flex;
  gap: 24px;
  margin-bottom: 16px;
}
.todo-block {
  flex: 1;
  text-align: center;
  padding: 16px;
  background: #fff;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid #bfdbfe;
}
.todo-block:hover {
  border-color: #3b82f6;
  box-shadow: 0 2px 12px rgba(59, 130, 246, 0.2);
}
.todo-block .todo-value {
  display: block;
  font-size: 28px;
  font-weight: 700;
  color: #1d4ed8;
  margin-bottom: 4px;
}
.todo-block .todo-label {
  font-size: 13px;
  color: #64748b;
}
.handoff-task-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.handoff-task-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #fff;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
}
.handoff-task-item .task-no {
  font-weight: 600;
  color: #1e40af;
  min-width: 140px;
}
.handoff-task-item .task-dest {
  flex: 1;
  font-size: 13px;
  color: #64748b;
}
.handoff-task-item .task-action {
  flex-shrink: 0;
}

.outbound-slip-section {
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  border: 1px solid #6ee7b7;
  border-radius: 12px;
  padding: 20px 24px;
}
.outbound-slip-section__hd {
  margin-bottom: 16px;
}
.outbound-slip-section__hd .section-title {
  font-size: 14px;
  color: #065f46;
  margin: 0 0 8px 0;
  font-weight: 600;
}
.outbound-slip-section__sub {
  margin: 0;
  font-size: 12px;
  color: #047857;
  line-height: 1.55;
  max-width: 920px;
}
.outbound-slip-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  margin-bottom: 8px;
}
.outbound-slip-grid--recent {
  margin-top: 8px;
}
.outbound-slip-recent-title {
  margin: 20px 0 10px 0;
  font-size: 13px;
  font-weight: 600;
  color: #065f46;
}
.outbound-slip-empty {
  margin: 0 0 12px 0;
  font-size: 13px;
  color: #059669;
}
.outbound-slip {
  background: #fff;
  border-radius: 10px;
  border: 1px solid #a7f3d0;
  padding: 14px 16px;
  box-shadow: 0 1px 3px rgba(6, 95, 70, 0.08);
}
.outbound-slip--done {
  border-color: #cbd5e1;
  background: #f8fafc;
}
.outbound-slip__hd {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}
.outbound-slip__badge {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  border-radius: 4px;
  background: #059669;
  color: #fff;
}
.outbound-slip__badge--done {
  background: #64748b;
}
.outbound-slip__no {
  font-weight: 700;
  font-size: 14px;
  color: #0f172a;
  flex: 1;
  min-width: 0;
}
.outbound-slip__po {
  font-size: 12px;
  color: #64748b;
}
.outbound-slip__go {
  margin-left: auto;
}
.outbound-slip__meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px 12px;
  margin: 0 0 10px 0;
  font-size: 12px;
}
.outbound-slip__meta--compact {
  grid-template-columns: repeat(3, 1fr);
}
.outbound-slip__meta dt {
  margin: 0;
  color: #64748b;
  font-weight: 500;
}
.outbound-slip__meta dd {
  margin: 0;
  color: #0f172a;
  font-weight: 600;
}
.outbound-slip__table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}
.outbound-slip__table th,
.outbound-slip__table td {
  padding: 6px 8px;
  text-align: left;
  border-bottom: 1px solid #e2e8f0;
}
.outbound-slip__table th {
  color: #64748b;
  font-weight: 600;
}
.outbound-slip__table .num {
  text-align: right;
  width: 64px;
}
.outbound-slip__lines {
  margin: 0 0 8px 0;
  padding-left: 18px;
  font-size: 12px;
  color: #334155;
}
.outbound-slip__lines li {
  margin-bottom: 4px;
}
.outbound-slip__more {
  list-style: none;
  margin-left: -18px;
  color: #64748b;
  font-size: 11px;
}
</style>
