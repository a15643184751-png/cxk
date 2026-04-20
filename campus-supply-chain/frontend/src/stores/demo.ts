/** 本地会话：存储 AI 异常单号、误批预警等前端状态 */
import { ref } from 'vue'

const DEMO_ABNORMAL_KEY = 'demo_abnormal_orders'
const DEMO_MISAPPROVAL_KEY = 'demo_misapproval_audit'
const DEMO_APPROVAL_ALERT_KEY = 'demo_approval_alert'
const DEMO_WARNING_TO_LOGISTICS_KEY = 'demo_warning_to_logistics'

function getAbnormalSet(): Set<string> {
  try {
    const raw = localStorage.getItem(DEMO_ABNORMAL_KEY)
    const arr = raw ? JSON.parse(raw) : []
    return new Set(Array.isArray(arr) ? arr : [])
  } catch {
    return new Set()
  }
}

function saveAbnormalSet(set: Set<string>) {
  localStorage.setItem(DEMO_ABNORMAL_KEY, JSON.stringify([...set]))
}

export function addAbnormalOrder(orderNo: string) {
  const set = getAbnormalSet()
  set.add(orderNo)
  saveAbnormalSet(set)
}

export function isAbnormalOrder(orderNo: string, goodsSummary?: string): boolean {
  const set = getAbnormalSet()
  if (set.has(orderNo)) return true
  if (goodsSummary && /笔记本.*100|100.*笔记本/.test(goodsSummary)) return true
  return false
}

// 误批预警（后勤审批了异常单后触发）- 持久化到 localStorage 便于跨 tab / 刷新后管理员可见
export interface ApprovalAlertState {
  orderNo: string
  reason: string
  purchaseId?: number
  applicantName?: string
  applicantCollege?: string
  createdAt?: string
  goodsSummary?: string
}

function loadApprovalAlert(): ApprovalAlertState | null {
  try {
    const raw = localStorage.getItem(DEMO_APPROVAL_ALERT_KEY)
    if (!raw) return null
    return JSON.parse(raw) as ApprovalAlertState
  } catch {
    return null
  }
}

export const approvalAlert = ref<ApprovalAlertState | null>(loadApprovalAlert())

export function setApprovalAlert(
  orderNo: string,
  reason: string,
  purchaseId?: number,
  extra?: Partial<Pick<ApprovalAlertState, 'applicantName' | 'applicantCollege' | 'createdAt' | 'goodsSummary'>>,
) {
  const v: ApprovalAlertState = { orderNo, reason, purchaseId, ...extra }
  approvalAlert.value = v
  try {
    localStorage.setItem(DEMO_APPROVAL_ALERT_KEY, JSON.stringify(v))
  } catch {}
}

export function getApprovalAlert() {
  return approvalAlert.value
}

export function clearApprovalAlert() {
  approvalAlert.value = null
  try {
    localStorage.removeItem(DEMO_APPROVAL_ALERT_KEY)
  } catch {}
}

export function syncApprovalAlertFromStorage() {
  approvalAlert.value = loadApprovalAlert()
}

// 误批审计记录（二次确认通过后写入，管理员可留档/发警告邮件）
export interface MisapprovalRecord {
  id: string
  orderNo: string
  applicantName?: string
  goodsSummary: string
  operatorName: string
  operatorRole: string
  firstConfirmAt: string
  secondConfirmAt: string
  decisionTimeMs: number
  estimatedLoss: string
  intentProbability: string
  report: string
  archived?: boolean
  created_at: string
}

function getMisapprovalList(): MisapprovalRecord[] {
  try {
    const raw = localStorage.getItem(DEMO_MISAPPROVAL_KEY)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

function saveMisapprovalList(list: MisapprovalRecord[]) {
  localStorage.setItem(DEMO_MISAPPROVAL_KEY, JSON.stringify(list))
}

export const misapprovalRecords = ref<MisapprovalRecord[]>(getMisapprovalList())

export function addMisapprovalRecord(rec: Omit<MisapprovalRecord, 'id' | 'created_at'>) {
  const list = getMisapprovalList()
  const newRec: MisapprovalRecord = {
    ...rec,
    id: `MIS-${Date.now()}`,
    created_at: new Date().toISOString(),
  }
  list.unshift(newRec)
  saveMisapprovalList(list)
  misapprovalRecords.value = list
}

export function archiveMisapproval(id: string) {
  const list = getMisapprovalList().map((r) => (r.id === id ? { ...r, archived: true } : r))
  saveMisapprovalList(list)
  misapprovalRecords.value = list
}

export function syncMisapprovalFromStorage() {
  misapprovalRecords.value = getMisapprovalList()
}

// 管理员发起警告后，后勤端需弹窗接收
export interface WarningToLogistics {
  id: string
  orderNo: string
  subject: string
  body: string
  sentAt: string
}

function loadWarningToLogistics(): WarningToLogistics | null {
  try {
    const raw = localStorage.getItem(DEMO_WARNING_TO_LOGISTICS_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function setWarningToLogistics(w: Omit<WarningToLogistics, 'id' | 'sentAt'>) {
  const v: WarningToLogistics = {
    ...w,
    id: `WARN-${Date.now()}`,
    sentAt: new Date().toISOString(),
  }
  try {
    localStorage.setItem(DEMO_WARNING_TO_LOGISTICS_KEY, JSON.stringify(v))
  } catch {}
}

export function getAndClearWarningToLogistics(): WarningToLogistics | null {
  const v = loadWarningToLogistics()
  try { localStorage.removeItem(DEMO_WARNING_TO_LOGISTICS_KEY) } catch {}
  return v
}

export function clearWarningToLogistics() {
  try { localStorage.removeItem(DEMO_WARNING_TO_LOGISTICS_KEY) } catch {}
}

// 异常操作（误批）弹窗告警 - 管理员进入审计页时如有未读误批则弹窗
const DEMO_MISAPPROVAL_SEEN_KEY = 'demo_misapproval_seen_ids'

export function getUnseenMisapprovalIds(): string[] {
  let seen = new Set<string>()
  try {
    const raw = localStorage.getItem(DEMO_MISAPPROVAL_SEEN_KEY)
    if (raw) seen = new Set(JSON.parse(raw))
  } catch {}
  const all = getMisapprovalList()
  return all.filter((r) => !seen.has(r.id)).map((r) => r.id)
}

export function markMisapprovalSeen(id: string) {
  try {
    const raw = localStorage.getItem(DEMO_MISAPPROVAL_SEEN_KEY)
    const arr = raw ? JSON.parse(raw) : []
    const set = new Set(arr)
    set.add(id)
    localStorage.setItem(DEMO_MISAPPROVAL_SEEN_KEY, JSON.stringify([...set]))
  } catch {}
}

const ADMIN_STAT_OVERLAY_KEY = 'admin_dashboard_stat_overlay'
const INBOX_KEY = 'campus_notice_inbox_v1'

export function readAdminStatOverlay(): { audit: number; sensitive: number } {
  try {
    const o = JSON.parse(localStorage.getItem(ADMIN_STAT_OVERLAY_KEY) || '{"audit":0,"sensitive":0}')
    return { audit: Number(o.audit) || 0, sensitive: Number(o.sensitive) || 0 }
  } catch {
    return { audit: 0, sensitive: 0 }
  }
}

/** 管理员纠偏操作后，工作台「审计日志」「敏感操作」卡片数字叠加（与后端审计异步一致） */
export function bumpAdminStatOverlay(kind: 'warn' | 'penalty') {
  const cur = readAdminStatOverlay()
  cur.audit += 1
  if (kind === 'penalty') cur.sensitive += 1
  try {
    localStorage.setItem(ADMIN_STAT_OVERLAY_KEY, JSON.stringify(cur))
  } catch {}
}

export interface InboxNotice {
  id: string
  applicant_id: number
  title: string
  body: string
  created_at: string
}

function loadInbox(): InboxNotice[] {
  try {
    const raw = localStorage.getItem(INBOX_KEY)
    const arr = raw ? JSON.parse(raw) : []
    return Array.isArray(arr) ? arr : []
  } catch {
    return []
  }
}

export function pushApplicantInboxNotice(applicantId: number, title: string, body: string) {
  if (!applicantId) return
  const list = loadInbox()
  list.unshift({
    id: `N-${Date.now()}`,
    applicant_id: applicantId,
    title,
    body,
    created_at: new Date().toISOString(),
  })
  try {
    localStorage.setItem(INBOX_KEY, JSON.stringify(list.slice(0, 200)))
  } catch {}
}

export function listInboxForApplicant(applicantId: number): InboxNotice[] {
  return loadInbox().filter((n) => n.applicant_id === applicantId)
}

const DEMO_ABNORMAL_DISMISS_KEY = 'demo_abnormal_placeholder_dismissed'

export function isDemoAbnormalPlaceholderDismissed(): boolean {
  try {
    return localStorage.getItem(DEMO_ABNORMAL_DISMISS_KEY) === '1'
  } catch {
    return false
  }
}

export function dismissDemoAbnormalPlaceholder() {
  try {
    localStorage.setItem(DEMO_ABNORMAL_DISMISS_KEY, '1')
  } catch {}
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (e) => {
    if (e.key === DEMO_APPROVAL_ALERT_KEY) approvalAlert.value = loadApprovalAlert()
    if (e.key === DEMO_MISAPPROVAL_KEY) misapprovalRecords.value = getMisapprovalList()
    if (e.key === DEMO_WARNING_TO_LOGISTICS_KEY && e.newValue) {
      try {
        const w = JSON.parse(e.newValue) as WarningToLogistics
        window.dispatchEvent(new CustomEvent('demo-logistics-warning', { detail: w }))
      } catch {}
    }
  })
}
