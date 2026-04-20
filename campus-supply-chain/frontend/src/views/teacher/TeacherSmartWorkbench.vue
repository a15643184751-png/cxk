<script setup lang="ts">
import {
  ref,
  computed,
  watch,
  onMounted,
  onUnmounted,
  onActivated,
  nextTick,
  type Component,
} from 'vue'
import { useRouter } from 'vue-router'
import {
  Promotion,
  Microphone,
  RefreshRight,
  CircleCheck,
  WarningFilled,
  Cpu,
  Paperclip,
  Calendar,
  Refresh,
  Warning,
  Search,
  Connection,
  Loading,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { chat, executeAction } from '@/api/ai'
import { listMyPurchases } from '@/api/purchase'
import { workbenchChatPrefill } from '@/utils/teacherWorkbenchBus'
import { openSearchBus } from '@/utils/layoutBus'
import { addAbnormalOrder } from '@/stores/demo'
import type { ChatAction, ReactStep } from '@/api/ai'

const THINK_MIN_MS = 900
/** 普通对话：与请求并行的最短「思考」动效，不宜过长 */
const THINK_LITE_MS = 420
const THINK_STEP_MS = 980
const THINK_STEP_WMS_MS = 1450

const TRACK_KEY = 'teacher-workbench-track-v1'

const router = useRouter()
const userStore = useUserStore()

const displayName = computed(
  () => userStore.userInfo?.real_name || userStore.userInfo?.username || '老师'
)

/** Gemini 式：上行轻问候，下行主问句 */
const greetingLineKicker = computed(() => {
  const h = new Date().getHours()
  const prefix = h < 12 ? '上午好' : h < 18 ? '下午好' : '晚上好'
  return `${prefix}，${displayName.value}`
})

const greetingLineMain = computed(() => '今天需要准备什么物资，或是安排什么活动？')

const greetShown = ref(false)

function playGreetingEntrance() {
  const reduceMotion =
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  greetShown.value = false
  nextTick(() => {
    if (reduceMotion) {
      greetShown.value = true
      return
    }
    requestAnimationFrame(() => {
      greetShown.value = true
    })
  })
}

/** 公开课场景：一键完成「提问 → 回复 → 申请单 → 提交」 */
const HEALTH_DEMO_USER =
  '下周三自动化原理公开课约 45 人，请生成课堂耗材与饮水申领清单（A4讲义纸、白板笔、瓶装水、一次性纸杯）'

const scenarioFlowActive = ref(false)
const scenarioAiReplyText = ref('')
const scenarioReplyTyping = ref(false)
const scenarioSheetReady = ref(false)
const scenarioSubmitSuccess = ref(false)

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}


const uiPhase = ref<'home' | 'result'>('home')
const queryInput = ref('')
const sending = ref(false)
const sessionId = ref<string | null>(null)

const omniboxFocused = ref(false)
const omniboxTextareaRef = ref<HTMLTextAreaElement | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)
/** FLIP 动画测量：整块输入区（问候 + 工具 + 输入 + chip） */
const composerShellRef = ref<HTMLElement | null>(null)

const FLIP_DURATION_MS = 520

function prefersReducedMotion(): boolean {
  return (
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  )
}

function clearComposerFlipStyles() {
  const el = composerShellRef.value
  if (!el) return
  el.style.transition = ''
  el.style.transform = ''
  el.style.zIndex = ''
}

/** 从「居中唤醒」到「沉底」：首帧在旧位置，再过渡到新位置 */
function runComposerFlipFromRect(firstRect: DOMRect) {
  const el = composerShellRef.value
  if (!el || prefersReducedMotion()) return
  const last = el.getBoundingClientRect()
  const dx = firstRect.left - last.left
  const dy = firstRect.top - last.top
  el.style.zIndex = '6'
  el.style.transition = 'none'
  el.style.transform = `translate(${dx}px, ${dy}px)`
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      el.style.transition = `transform ${FLIP_DURATION_MS}ms cubic-bezier(0.4, 0, 0.2, 1)`
      el.style.transform = 'translate(0, 0)'
      window.setTimeout(() => {
        clearComposerFlipStyles()
      }, FLIP_DURATION_MS + 40)
    })
  })
}

const OMNIBOX_MIN_PX = 64
const OMNIBOX_MAX_PX = 200

function autoSizeOmnibox() {
  const el = omniboxTextareaRef.value
  if (!el) return
  el.style.height = '0px'
  const h = Math.min(Math.max(el.scrollHeight, OMNIBOX_MIN_PX), OMNIBOX_MAX_PX)
  el.style.height = `${h}px`
}

type PresetScriptId =
  | 'open-class'
  | 'mid-exam'
  | 'innovation-event'
  | 'monthly-restock'
  | 'recover-projector'
  | 'renew-projector'
  | 'lab-safety'

type CoreChip = { id: string; label: string; prompt: string; presetId: PresetScriptId }

/** 核心区 3～4 条快捷投喂（与右侧动态卡片区分） */
const corePromptChips: CoreChip[] = [
  { id: 'c1', label: '🎓 公开课一键备课', prompt: HEALTH_DEMO_USER, presetId: 'open-class' },
  {
    id: 'c2',
    label: '📝 期中考试一键备齐',
    prompt:
      '期中考试周临近，请为年级组备齐答题卡、草稿纸、备用笔、密封条，按40人考场估算数量',
    presetId: 'mid-exam',
  },
  {
    id: 'c3',
    label: '🏅 学院比赛后勤包',
    prompt: '学院创新赛半天活动约80人，请生成基础后勤包（瓶装水、纸杯、签到用笔、桌签卡）并估算数量',
    presetId: 'innovation-event',
  },
  {
    id: 'c4',
    label: '🔄 月度常规复购',
    prompt: '按自动化学院教研室月度消耗，生成A4打印纸、白板笔、订书钉的复购清单',
    presetId: 'monthly-restock',
  },
]

function onCoreChip(chip: CoreChip) {
  void submitQuery(chip.prompt, { useAgent: true, presetId: chip.presetId })
}

type InsightKind = 'calendar' | 'cycle' | 'reverse'

type InsightCard = {
  id: string
  kind: InsightKind
  icon: Component
  /** 轻量胶囊主文案（点击即发送） */
  chipLabel: string
  title: string
  analysis: string
  gradient: string
  cta: string
  secondaryCta?: string
  secondaryChipLabel?: string
  prompt?: string
  presetId?: PresetScriptId
  secondaryPrompt?: string
  secondaryPresetId?: PresetScriptId
}

const insightCards = computed<InsightCard[]>(() => {
  const cards: InsightCard[] = [
    {
      id: 'rev-1',
      kind: 'reverse',
      icon: Warning,
      chipLabel: '🔔 呼叫回收公物',
      title: '公共物资归还提醒',
      analysis:
        '您名下 1 台教学投影仪 3 天后到期。建议提前发起续借或回收，避免影响下周公开课安排。',
      gradient: 'linear-gradient(125deg, #fff7ed 0%, #ffedd5 45%, #fed7aa 100%)',
      cta: '一键呼叫回收',
      secondaryCta: '申请续借',
      secondaryChipLabel: '⚠️ 延期申诉',
      prompt: '请生成教学投影仪到期回收交接申请单，安排后勤班组明日上午回收',
      presetId: 'recover-projector',
      secondaryPrompt: '教学投影仪 1 台借用即将到期，申请延期并说明公开课用途',
      secondaryPresetId: 'renew-projector',
    },
    {
      id: 'cal-1',
      kind: 'calendar',
      icon: Calendar,
      chipLabel: '📄 一键备齐答题卡',
      title: '期中考试周临近',
      analysis:
        '校历显示本周进入期中考试周，建议按考场数量提前备齐答题卡、草稿纸和备用笔，避免考试当天临时补领。',
      gradient: 'linear-gradient(125deg, #eef2ff 0%, #e0e7ff 50%, #c7d2fe 100%)',
      cta: '一键备齐答题卡',
      prompt:
        '期中考试周临近，请为年级组备齐答题卡、草稿纸、备用笔、密封条，按40人考场估算数量',
      presetId: 'mid-exam',
    },
    {
      id: 'cyc-1',
      kind: 'cycle',
      icon: Refresh,
      chipLabel: '🔄 复购上月 A4 纸',
      title: '周期性消耗预判',
      analysis:
        '根据历史行为，您在每月中旬会补充 A4 打印纸与白板笔。本月周期已到，可按上月规格一键复购，减少重复填表。',
      gradient: 'linear-gradient(125deg, #ecfdf5 0%, #d1fae5 45%, #a7f3d0 100%)',
      cta: '按上月规格一键复购',
      prompt: '按我上月申领的 A4 打印纸规格与数量一键复购，并附带常用订书钉',
      presetId: 'monthly-restock',
    },
  ]
  const order: Record<InsightKind, number> = { reverse: 0, calendar: 1, cycle: 2 }
  return [...cards].sort((a, b) => order[a.kind] - order[b.kind])
})

function onInsightPrimary(card: InsightCard) {
  if (card.prompt && card.presetId) void submitQuery(card.prompt, { useAgent: true, presetId: card.presetId })
}

function onInsightSecondary(card: InsightCard) {
  if (card.secondaryPrompt && card.secondaryPresetId) {
    void submitQuery(card.secondaryPrompt, { useAgent: true, presetId: card.secondaryPresetId })
  }
}

type ThinkStepStatus = 'pending' | 'active' | 'done'
type ThinkStepItem = {
  title: string
  subtitle: string
  details: string[]
  status: ThinkStepStatus
  visibleDetailCount: number
}
const thinkSteps = ref<ThinkStepItem[]>([])
const thinkVisibleCount = ref(0)
const latestThinkTrace = ref<ThinkStepItem[]>([])
const traceExpanded = ref(false)
const thinkPanelTitle = ref('多主体联动中')
const thinkElapsedMs = ref(0)
const thinking = ref(false)
/** 普通对话：轻量「思考中」条，不出现大方框 */
const dialogThinking = ref(false)
const thinkStreamLine = ref('')
/** 浮窗回复打字机展示（与 assistantNote 全文同步） */
const replyDisplayText = ref('')
const replyTypingActive = ref(false)
let replyTypingTimer: ReturnType<typeof setTimeout> | null = null

type StockLevel = 'ok' | 'low' | 'substituted'

type SheetItem = {
  key: string
  name: string
  quantity: number
  unit: string
  emoji: string
  stockLevel: StockLevel
  lowStockCount?: number
  substitutionNote?: string
  unitPrice: number
}

type PastTurn = {
  id: string
  user: string
  assistant: string
  items: SheetItem[]
  sheetTitle: string
  thinkTrace?: ThinkStepItem[]
  abnormal?: boolean
  abnormalText?: string
}

const pastTurns = ref<PastTurn[]>([])
const pastTraceExpanded = ref<Record<string, boolean>>({})
const sheetItems = ref<SheetItem[]>([])
const sheetTitle = ref('智能申领清单')
const assistantNote = ref('')
const abnormalMode = ref(false)
const abnormalText = ref('')
const forceAction = ref<ChatAction | null>(null)

function archiveCurrentTurnIfAny() {
  flushReplyTyping()
  const prevUser = lastUserMessage.value
  const prevNote = assistantNote.value
  const prevItems = sheetItems.value.slice()
  const prevSheetTitle = sheetTitle.value
  const prevAbn = abnormalMode.value
  const prevAbnText = abnormalText.value
  if (prevUser && (prevNote || prevItems.length || prevAbn)) {
    const id = uid()
    pastTurns.value.push({
      id,
      user: prevUser,
      assistant: prevNote,
      items: JSON.parse(JSON.stringify(prevItems)),
      sheetTitle: prevSheetTitle,
      thinkTrace: JSON.parse(JSON.stringify(latestThinkTrace.value)),
      abnormal: prevAbn,
      abnormalText: prevAbnText,
    })
    pastTraceExpanded.value[id] = true
  }
}

function togglePastTrace(id: string) {
  pastTraceExpanded.value[id] = !pastTraceExpanded.value[id]
}

function turnEstimatedTotal(turn: PastTurn): number {
  return (turn.items || []).reduce((sum, r) => sum + r.quantity * r.unitPrice, 0)
}

function scrollChatToBottom() {
  nextTick(() => {
    chatScrollRef.value?.scrollTo({ top: chatScrollRef.value.scrollHeight, behavior: 'smooth' })
  })
}

function openStockSearch() {
  openSearchBus.emit()
}

function applyScenarioPrompt(s: { prompt: string; presetId: PresetScriptId }) {
  void submitQuery(s.prompt, { useAgent: true, presetId: s.presetId })
}

const receiverName = ref('')
const receiverDest = ref('')
const submitting = ref(false)

const estimatedTotal = computed(() =>
  sheetItems.value.reduce((sum, r) => sum + r.unitPrice * r.quantity, 0)
)

type TrackState = {
  order_no: string
  message: string
  step: number
  total: number
}
const tracking = ref<TrackState | null>(null)

const lastUserMessage = ref('')
/** 由快捷 chip / 场景 / Insight 预填后，下一次发送走工具+申领清单 */
const pendingAgentSend = ref(false)
const chatScrollRef = ref<HTMLElement | null>(null)

const scenarioQuickList = [
  {
    emoji: '🎓',
    label: '公开课',
    prompt: '下周公开课45人，需讲义纸、白板笔、瓶装水、纸杯，请按课堂场景估算',
    presetId: 'open-class' as PresetScriptId,
  },
  {
    emoji: '🏅',
    label: '学院比赛',
    prompt: '学院创新赛半天活动80人，需瓶装水、纸杯、签到笔、桌签卡，请生成后勤清单',
    presetId: 'innovation-event' as PresetScriptId,
  },
  {
    emoji: '🧪',
    label: '实验教学',
    prompt: '本周实验课3次，每次30人，请补充实验耗材与安全防护用品',
    presetId: 'lab-safety' as PresetScriptId,
  },
  {
    emoji: '📚',
    label: '教研室月度',
    prompt: '按教研室月度消耗生成常规复购清单：A4纸、白板笔、订书钉',
    presetId: 'monthly-restock' as PresetScriptId,
  },
]

function applyPrefill(v: string) {
  if (!v) return
  pendingAgentSend.value = true
  queryInput.value = v
  workbenchChatPrefill.value = ''
}

watch(workbenchChatPrefill, (v) => applyPrefill(v || ''), { flush: 'post' })

function loadTracking() {
  try {
    const raw = sessionStorage.getItem(TRACK_KEY)
    if (raw) tracking.value = JSON.parse(raw) as TrackState
  } catch {
    tracking.value = null
  }
}

function saveTracking(t: TrackState | null) {
  if (!t) {
    sessionStorage.removeItem(TRACK_KEY)
    tracking.value = null
    return
  }
  sessionStorage.setItem(TRACK_KEY, JSON.stringify(t))
  tracking.value = t
}

async function refreshTrackingFromApi() {
  try {
    const res: any = await listMyPurchases()
    const list = (Array.isArray(res) ? res : res?.data ?? []) as {
      order_no: string
      status: string
      goods_summary?: string
    }[]
    const proc = list.find((p) => !['completed', 'rejected'].includes(p.status))
    if (!proc) {
      if (!sessionStorage.getItem(TRACK_KEY)) tracking.value = null
      return
    }
    const stepMap: Record<string, number> = {
      pending: 1,
      approved: 2,
      confirmed: 2,
      shipped: 2,
      stocked_in: 3,
      stocked_out: 3,
      delivering: 3,
      completed: 4,
    }
    const step = stepMap[proc.status] ?? 2
    const msg =
      step <= 2
        ? '审批/接单流转中'
        : step === 3
          ? '仓储端拣货打包或配送中'
          : '已完成'
    saveTracking({
      order_no: proc.order_no,
      message: `${proc.goods_summary ? proc.goods_summary.slice(0, 24) + '… · ' : ''}${msg}`,
      step,
      total: 4,
    })
  } catch {
    /* ignore */
  }
}

watch(
  () => pastTurns.value.length,
  () => scrollChatToBottom()
)

watch(queryInput, () => nextTick(() => autoSizeOmnibox()))

onMounted(() => {
  if (workbenchChatPrefill.value) applyPrefill(workbenchChatPrefill.value)
  receiverName.value = userStore.userInfo?.real_name || userStore.userInfo?.username || ''
  receiverDest.value = ''
  loadTracking()
  void refreshTrackingFromApi()
  playGreetingEntrance()
  nextTick(() => autoSizeOmnibox())
})

onActivated(() => {
  nextTick(() => {
    if (
      pastTurns.value.length === 0 &&
      !lastUserMessage.value &&
      !thinking.value &&
      !sending.value &&
      !scenarioFlowActive.value
    ) {
      playGreetingEntrance()
    }
  })
})

onUnmounted(() => {
  if (thinkStreamTimer) clearInterval(thinkStreamTimer)
  stopReplyTyping()
})

let thinkStreamTimer: ReturnType<typeof setInterval> | null = null

function stopThinkStream() {
  if (thinkStreamTimer) {
    clearInterval(thinkStreamTimer)
    thinkStreamTimer = null
  }
  thinkStreamLine.value = ''
  thinkVisibleCount.value = 0
}

function stopReplyTyping() {
  if (replyTypingTimer) {
    clearTimeout(replyTypingTimer)
    replyTypingTimer = null
  }
  replyTypingActive.value = false
}

/** 将打字动画补全为全文，便于归档与发新消息 */
function flushReplyTyping() {
  stopReplyTyping()
  if (assistantNote.value) replyDisplayText.value = assistantNote.value
}

function startReplyTyping(full: string) {
  stopReplyTyping()
  replyDisplayText.value = ''
  if (!full) return
  if (prefersReducedMotion()) {
    replyDisplayText.value = full
    return
  }
  const chars = [...full]
  let i = 0
  replyTypingActive.value = true
  const step = () => {
    if (i >= chars.length) {
      replyTypingActive.value = false
      replyTypingTimer = null
      scrollChatToBottom()
      return
    }
    const ch = chars[i]
    i += 1
    replyDisplayText.value = chars.slice(0, i).join('')
    if (i % 5 === 0) scrollChatToBottom()
    const delay = /[\n\r]/.test(ch) ? 12 : /[，。！？、；：]/.test(ch) ? 28 : 22
    replyTypingTimer = window.setTimeout(step, delay) as unknown as number
  }
  step()
}

function startThinkStream(phrases: string[]) {
  stopThinkStream()
  let i = 0
  thinkStreamLine.value = phrases[0] || ''
  thinkStreamTimer = window.setInterval(() => {
    i = (i + 1) % phrases.length
    thinkStreamLine.value = phrases[i]
  }, 580)
}

function buildThinkPhrases(q: string): string[] {
  if (/公开课|45人|课堂|讲义/.test(q)) {
    return [
      '正在解析场景（公开课）…',
      '正在匹配课堂耗材与饮水配置…',
      '正在核对仓储端实时库存…',
      '正在校验院系额度与审批规则…',
      '正在生成可编辑申领微件…',
    ]
  }
  if (/比赛|活动|80人|签到/.test(q)) {
    return [
      '正在读取活动日程与人数规模…',
      '正在匹配后勤保障物资档位…',
      '正在联动仓储库存与配送能力…',
    ]
  }
  return [
    '正在理解您的自然语言意图…',
    '正在检索物资主数据与规格…',
    '正在协调教务、仓储与额度校验…',
    '正在生成智能申领清单…',
  ]
}

function extractThinkContext(q: string) {
  const scaleMatch = q.match(/(\d+)\s*人/)
  const scaleNum = scaleMatch ? Number(scaleMatch[1]) : 40
  let scene = '通用教学'
  if (/公开课|课堂|讲义/.test(q)) scene = '公开课备课'
  else if (/期中|考试|考场|答题卡/.test(q)) scene = '期中考试保障'
  else if (/比赛|创新赛|活动|后勤包/.test(q)) scene = '赛事活动保障'
  else if (/月度|复购|教研室/.test(q)) scene = '月度常规复购'
  else if (/实验|试剂|防护/.test(q)) scene = '实验教学保障'

  const claims: string[] = []
  if (/水|饮用/.test(q)) claims.push('饮水保障')
  if (/纸|讲义|答题卡|草稿/.test(q)) claims.push('纸品耗材')
  if (/笔|白板/.test(q)) claims.push('书写耗材')
  if (/急救|医药|防护/.test(q)) claims.push('安全保障')
  if (!claims.length) claims.push('物资齐套与时效')

  const items = fallbackSheetFromQuery(q)
  const matched = items.length || 4
  const fuzzy = Math.max(1, Math.min(3, Math.round(matched / 3)))
  const expRatio = Math.max(0.8, scaleNum / 40).toFixed(2)
  const nearExpiry = /水|饮用/.test(q) ? '临期瓶装水' : /纸|答题卡/.test(q) ? '低克重纸张' : '临期批次物资'

  return {
    scene,
    scale: `${scaleNum}人`,
    claims: claims.join('、'),
    matched,
    fuzzy,
    nearExpiry,
    ratio: expRatio,
    operator: displayName.value,
  }
}

function buildThinkStepsFromQuery(q: string): ThinkStepItem[] {
  const c = extractThinkContext(q)
  return [
    {
      title: 'Step 1: 语义解析与实体抽取 (NLU & NER)',
      subtitle: `提取核心向量: 场景=[${c.scene}], 规模=[${c.scale}], 关键诉求=[${c.claims}]`,
      details: ['意图分类置信度: 98.7% -> 路由至 [物资申领专家 Agent]'],
      status: 'pending',
      visibleDetailCount: 0,
    },
    {
      title: 'Step 2: 调用业务知识库 (RAG Search)',
      subtitle: `检索 [${c.scene}] 场景历史标准消耗模型`,
      details: ['正在动态生成基础物料清单 (BOM) ...'],
      status: 'pending',
      visibleDetailCount: 0,
    },
    {
      title: 'Step 3: 物资主数据对齐 (MDM Matching)',
      subtitle: '自然语言映射标准 SKU...',
      details: [`成功匹配 [${c.matched}] 项，模糊替代 [${c.fuzzy}] 项`],
      status: 'pending',
      visibleDetailCount: 0,
    },
    {
      title: 'Step 4: 跨端并发寻址 [仓储 Agent]',
      subtitle: 'API Request: 查询 A/B 区可用库存水位',
      details: [`拦截器触发: 剔除 [${c.nearExpiry}]，启动智能平替策略`, '锁定有效可用库存...'],
      status: 'pending',
      visibleDetailCount: 0,
    },
    {
      title: 'Step 5: 供应链健康度与风控校验 (Health Control)',
      subtitle: `校验当前操作人 [${c.operator}] 剩余配额`,
      details: [`执行防囤积算法: 申请量/历史均值 = [${c.ratio}]，判定 [通过]`],
      status: 'pending',
      visibleDetailCount: 0,
    },
    {
      title: 'Step 6: 渲染结构化微件 (Render Payload)',
      subtitle: '组装 JSON Schema...',
      details: ['数据挂载至 Virtual DOM，UI 卡片生成中'],
      status: 'pending',
      visibleDetailCount: 0,
    },
  ]
}

function syncLatestThinkTrace() {
  latestThinkTrace.value = thinkSteps.value.map((s) => ({
    ...s,
    details: [...s.details],
  }))
}

function isIncrementalDialogue(q: string, base: SheetItem[]): boolean {
  if (!base.length) return false
  return /监考|矿泉水|急救箱|便携急救|每个考场|每人配一瓶/.test(q)
}

function inferExamRoomCount(q: string): number {
  const inQ = q.match(/(\d+)\s*个?考场/)
  if (inQ) return Number(inQ[1])
  const recentText = [lastUserMessage.value, ...pastTurns.value.slice(-3).map((t) => t.user)].join(' ')
  const inCtx = recentText.match(/(\d+)\s*(?:个)?(?:人)?考场/)
  if (inCtx) return Number(inCtx[1])
  return 40
}

function buildIncrementalPlan(base: SheetItem[], q: string) {
  const examRooms = inferExamRoomCount(q)
  const waterDelta = examRooms * 2
  const firstAidDelta = 2
  const waterUnitPrice = 2
  const firstAidUnitPrice = 68
  const incrementCost = waterDelta * waterUnitPrice + firstAidDelta * firstAidUnitPrice

  const merged = base.map((r) => ({ ...r }))
  const waterIdx = merged.findIndex((r) => /水|矿泉水/.test(r.name))
  if (waterIdx >= 0) {
    merged[waterIdx].quantity += waterDelta
  } else {
    merged.push({
      key: uid(),
      name: '瓶装饮用水 550ml',
      quantity: waterDelta,
      unit: '瓶',
      emoji: '🥤',
      stockLevel: 'ok',
      unitPrice: waterUnitPrice,
    })
  }
  const kitIdx = merged.findIndex((r) => /急救箱/.test(r.name))
  if (kitIdx >= 0) {
    merged[kitIdx].quantity += firstAidDelta
  } else {
    merged.push({
      key: uid(),
      name: '标准型便携急救箱',
      quantity: firstAidDelta,
      unit: '个',
      emoji: '🩹',
      stockLevel: 'low',
      lowStockCount: 1,
      unitPrice: firstAidUnitPrice,
    })
  }

  const oldTotal = base.reduce((sum, r) => sum + r.quantity * r.unitPrice, 0)
  const newTotal = oldTotal + incrementCost
  const steps: ThinkStepItem[] = [
    {
      title: 'Step 1: 意图继承与增量解析 (Context & Delta Parsing)',
      subtitle: '命中当前活跃 Session，读取缓存单据: [期中考试保障申请单]',
      details: [
        `触发逻辑推理: ${examRooms} 个考场 * 2 名监考 = 追加 [${waterDelta}] 瓶水`,
        '提取独立追加实体: [应急急救箱] * 2',
      ],
      status: 'pending',
      visibleDetailCount: 0,
    },
    {
      title: 'Step 2: 追加物料规格匹配 (Delta MDM Matching)',
      subtitle: '自然语言映射标准 SKU...',
      details: [`锁定: [瓶装饮用水 550ml] x ${waterDelta}, [标准型便携急救箱] x ${firstAidDelta}`],
      status: 'pending',
      visibleDetailCount: 0,
    },
    {
      title: 'Step 3: 定向并发寻址 [仓储 Agent]',
      subtitle: 'API Request: 仅对增量物资发起库存快照查询',
      details: [
        '⚠️ 预警拦截: [标准型便携急救箱] 教学区库房存量不足',
        '触发路由切换 -> 寻址 [校医院代管仓] 可用库存 -> [成功]',
      ],
      status: 'pending',
      visibleDetailCount: 0,
    },
    {
      title: 'Step 4: 订单合并与动态风控 (Payload Merge & Re-eval)',
      subtitle: '将增量物料 (Delta) 合并至主数据树 (Main Tree)',
      details: [`重新核算预估额度: 原 ¥${oldTotal} + 新增 ¥${incrementCost} = 总计 ¥${newTotal}`, '额度水位校验 -> [通过]'],
      status: 'pending',
      visibleDetailCount: 0,
    },
    {
      title: 'Step 5: 局部视图刷新 (DOM Patching)',
      subtitle: '生成合并后的 JSON Schema...',
      details: ['注入视图层，执行卡片数据热更新'],
      status: 'pending',
      visibleDetailCount: 0,
    },
  ]

  return { merged, incrementCost, newTotal, steps }
}

function onOmniboxBlur(e: FocusEvent) {
  const cur = e.currentTarget as HTMLElement | null
  nextTick(() => {
    if (cur && !cur.contains(document.activeElement)) omniboxFocused.value = false
  })
}

function triggerFilePick() {
  fileInputRef.value?.click()
}

function onFileChange(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  ElMessage.info('正在识别图片中的耗材特征并匹配物资库…')
  window.setTimeout(() => {
    ElMessage.success('识别完成：推测为课桌椅紧固件 / 脚垫类耗材，已填入申领意图，您可补充数量后发送。')
    queryInput.value =
      '根据上传现场照片，申请更换同规格课桌椅紧固件套装若干（请后勤按图匹配库存）'
    input.value = ''
  }, 1600)
}

function isAbnormalRequest(q: string): boolean {
  const lower = q.toLowerCase()
  return (lower.includes('100') && lower.includes('笔记本')) || (lower.includes('笔记本') && lower.includes('观影'))
}

function uid() {
  return `i-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`
}

type PresetRow = Omit<SheetItem, 'key'>
type PresetScript = { title: string; note: string; rows: PresetRow[] }

function presetRows(rows: PresetRow[]): SheetItem[] {
  return rows.map((r, idx) => ({ ...r, key: `${uid()}-${idx}` }))
}

function presetScriptById(id: PresetScriptId): PresetScript {
  if (id === 'open-class') {
    return {
      title: '公开课保障申请单',
      note: '已按“公开课45人”模板生成固定申请单，您可直接提交。',
      rows: [
        { name: 'A4 复印纸 70g', quantity: 10, unit: '包', emoji: '📄', stockLevel: 'ok', unitPrice: 28 },
        { name: '白板笔（黑/蓝）', quantity: 20, unit: '支', emoji: '✏️', stockLevel: 'ok', unitPrice: 2.5 },
        { name: '瓶装饮用水 550ml', quantity: 48, unit: '瓶', emoji: '🥤', stockLevel: 'ok', unitPrice: 2 },
        {
          name: '一次性纸杯',
          quantity: 3,
          unit: '包',
          emoji: '🥤',
          stockLevel: 'low',
          lowStockCount: 5,
          unitPrice: 8,
        },
      ],
    }
  }
  if (id === 'mid-exam') {
    return {
      title: '期中考试保障申请单',
      note: '已按“40人考场”模板生成固定申请单。',
      rows: [
        { name: '答题卡（A4）', quantity: 240, unit: '张', emoji: '📋', stockLevel: 'ok', unitPrice: 0.15 },
        { name: '草稿纸', quantity: 240, unit: '张', emoji: '📄', stockLevel: 'ok', unitPrice: 0.08 },
        { name: '备用中性笔', quantity: 20, unit: '支', emoji: '✒️', stockLevel: 'low', lowStockCount: 8, unitPrice: 1.2 },
        { name: '密封条', quantity: 8, unit: '卷', emoji: '📎', stockLevel: 'ok', unitPrice: 3 },
      ],
    }
  }
  if (id === 'innovation-event') {
    return {
      title: '学院比赛后勤申请单',
      note: '已按“半天80人活动”模板生成固定申请单。',
      rows: [
        { name: '瓶装饮用水 550ml', quantity: 6, unit: '箱', emoji: '🥤', stockLevel: 'ok', unitPrice: 48 },
        { name: '一次性纸杯', quantity: 8, unit: '包', emoji: '🥤', stockLevel: 'ok', unitPrice: 8 },
        { name: '签到用中性笔', quantity: 20, unit: '支', emoji: '✒️', stockLevel: 'ok', unitPrice: 2 },
        { name: '桌签卡纸', quantity: 2, unit: '包', emoji: '📄', stockLevel: 'low', lowStockCount: 1, unitPrice: 26 },
      ],
    }
  }
  if (id === 'monthly-restock') {
    return {
      title: '教研室月度复购申请单',
      note: '已按上月常用规格生成固定复购单。',
      rows: [
        { name: 'A4 复印纸 70g', quantity: 14, unit: '包', emoji: '📄', stockLevel: 'ok', unitPrice: 28 },
        { name: '白板笔（黑/蓝）', quantity: 30, unit: '支', emoji: '✏️', stockLevel: 'ok', unitPrice: 2.5 },
        { name: '订书钉 24/6', quantity: 10, unit: '盒', emoji: '📎', stockLevel: 'ok', unitPrice: 4.5 },
      ],
    }
  }
  if (id === 'lab-safety') {
    return {
      title: '实验教学耗材申请单',
      note: '已按“3次实验课”模板生成固定申请单。',
      rows: [
        { name: '一次性丁腈手套', quantity: 8, unit: '盒', emoji: '🧤', stockLevel: 'ok', unitPrice: 26 },
        { name: '防护口罩', quantity: 120, unit: '只', emoji: '😷', stockLevel: 'ok', unitPrice: 1.1 },
        { name: '75%酒精消毒湿巾', quantity: 12, unit: '包', emoji: '🧴', stockLevel: 'low', lowStockCount: 4, unitPrice: 9.8 },
      ],
    }
  }
  if (id === 'recover-projector') {
    return {
      title: '到期资产回收交接申请单',
      note: '已按资产到期回收场景生成固定交接单。',
      rows: [
        { name: '教学投影仪回收交接', quantity: 1, unit: '台', emoji: '📽️', stockLevel: 'ok', unitPrice: 0 },
        { name: 'HDMI 连接线回收', quantity: 1, unit: '条', emoji: '🔌', stockLevel: 'ok', unitPrice: 0 },
        { name: '资产标签复核单', quantity: 1, unit: '份', emoji: '📋', stockLevel: 'ok', unitPrice: 0 },
      ],
    }
  }
  return {
    title: '资产续借申请单',
    note: '已按续借场景生成固定申请单。',
    rows: [
      { name: '教学投影仪续借', quantity: 1, unit: '台', emoji: '📽️', stockLevel: 'ok', unitPrice: 0 },
      { name: '续借审批说明单', quantity: 1, unit: '份', emoji: '📝', stockLevel: 'ok', unitPrice: 0 },
    ],
  }
}

function fallbackHealthCheckSheet(): SheetItem[] {
  return [
    { key: uid(), name: 'A4 复印纸 70g', quantity: 10, unit: '包', emoji: '📄', stockLevel: 'ok', unitPrice: 28 },
    { key: uid(), name: '白板笔（黑/蓝）', quantity: 20, unit: '支', emoji: '✏️', stockLevel: 'ok', unitPrice: 2.5 },
    { key: uid(), name: '瓶装饮用水 550ml', quantity: 48, unit: '瓶', emoji: '🥤', stockLevel: 'ok', unitPrice: 2 },
    {
      key: uid(),
      name: '一次性纸杯',
      quantity: 3,
      unit: '包',
      emoji: '🥤',
      stockLevel: 'low',
      lowStockCount: 5,
      unitPrice: 8,
    },
  ]
}

function mapPayloadToSheetItems(payload: Record<string, unknown> | undefined): SheetItem[] {
  const raw = (payload as { items?: { name?: string; quantity?: number; unit?: string }[] })?.items
  if (!Array.isArray(raw) || !raw.length) return []
  return raw.map((it, idx) => ({
    key: uid() + idx,
    name: String(it.name || '物资'),
    quantity: Math.max(1, Number(it.quantity) || 1),
    unit: String(it.unit || '件'),
    emoji: pickEmoji(String(it.name)),
    stockLevel: 'ok' as StockLevel,
    unitPrice: 3,
  }))
}

function pickEmoji(name: string): string {
  if (/纸|打印|资料/.test(name)) return '📄'
  if (/笔|粉笔/.test(name)) return '✏️'
  if (/水|饮|茶|杯/.test(name)) return '🥤'
  if (/消毒|清洁/.test(name)) return '🧴'
  if (/实验|试剂/.test(name)) return '🧪'
  if (/袋|包/.test(name)) return '🛍️'
  return '📦'
}

function fallbackSheetFromQuery(q: string): SheetItem[] {
  if (/公开课|45人|课堂|讲义/.test(q)) {
    return fallbackHealthCheckSheet()
  }
  if (/比赛|活动|80人|签到/.test(q)) {
    return [
      {
        key: uid(),
        name: '瓶装饮用水 550ml',
        quantity: 6,
        unit: '箱',
        emoji: '🥤',
        stockLevel: 'ok',
        unitPrice: 48,
      },
      {
        key: uid(),
        name: '一次性纸杯',
        quantity: 8,
        unit: '包',
        emoji: '🥤',
        stockLevel: 'ok',
        unitPrice: 8,
      },
      {
        key: uid(),
        name: '签到用中性笔',
        quantity: 20,
        unit: '支',
        emoji: '✒️',
        stockLevel: 'ok',
        unitPrice: 2,
      },
      {
        key: uid(),
        name: '桌签卡纸',
        quantity: 2,
        unit: '包',
        emoji: '📄',
        stockLevel: 'low',
        lowStockCount: 1,
        unitPrice: 26,
      },
    ]
  }
  if (/粉笔|发货|物流|配送/.test(q)) {
    return [
      { key: uid(), name: '无尘粉笔（白）', quantity: 10, unit: '盒', emoji: '✏️', stockLevel: 'ok', unitPrice: 8 },
      { key: uid(), name: '板擦', quantity: 4, unit: '个', emoji: '🧽', stockLevel: 'ok', unitPrice: 6 },
    ]
  }
  if (/期中|考试|答题/.test(q)) {
    return [
      { key: uid(), name: '答题卡（A4）', quantity: 240, unit: '张', emoji: '📋', stockLevel: 'ok', unitPrice: 0.15 },
      { key: uid(), name: '草稿纸', quantity: 240, unit: '张', emoji: '📄', stockLevel: 'ok', unitPrice: 0.08 },
      { key: uid(), name: '备用中性笔', quantity: 20, unit: '支', emoji: '✒️', stockLevel: 'low', lowStockCount: 8, unitPrice: 1.2 },
      { key: uid(), name: '密封条', quantity: 8, unit: '卷', emoji: '📎', stockLevel: 'ok', unitPrice: 3 },
    ]
  }
  if (/班会|茶歇|活动/.test(q)) {
    return [
      { key: uid(), name: '一次性纸杯', quantity: 50, unit: '个', emoji: '🥤', stockLevel: 'ok', unitPrice: 0.2 },
      { key: uid(), name: '袋泡茶', quantity: 3, unit: '盒', emoji: '🍵', stockLevel: 'ok', unitPrice: 22 },
      { key: uid(), name: '湿纸巾', quantity: 5, unit: '包', emoji: '🧻', stockLevel: 'ok', unitPrice: 6 },
    ]
  }
  return [
    { key: uid(), name: 'A4 打印纸', quantity: 5, unit: '包', emoji: '📄', stockLevel: 'ok', unitPrice: 28 },
    { key: uid(), name: '订书钉（通用）', quantity: 2, unit: '盒', emoji: '📎', stockLevel: 'ok', unitPrice: 5 },
    { key: uid(), name: '便利贴', quantity: 6, unit: '本', emoji: '📝', stockLevel: 'ok', unitPrice: 4 },
  ]
}

function isRefineRequest(q: string): boolean {
  return /(不要|不想要|换成|改成|替换|同类|规格|型号|太多|太少|减少|增加)/.test(q)
}

function regenerateSheetByPreference(q: string, base: SheetItem[]): SheetItem[] {
  const next = JSON.parse(JSON.stringify(base)) as SheetItem[]
  if (!next.length) return next

  const removeMatch = q.match(/不要([^，。,；;]+?)(?:，|,|。|；|;|并|我|请|$)/)
  const swapMatch = q.match(/(?:换成|改成|要|用)([^，。,；;]+?)(?:，|,|。|；|;|并|我|请|$)/)
  const removeKeyword = removeMatch?.[1]?.trim()
  const swapName = swapMatch?.[1]?.trim()

  if (removeKeyword && swapName) {
    const idx = next.findIndex((r) => r.name.includes(removeKeyword))
    if (idx >= 0) {
      const old = next[idx]
      next[idx] = {
        ...old,
        name: swapName,
        emoji: pickEmoji(swapName),
        stockLevel: 'substituted',
        substitutionNote: `已按您的要求，将「${old.name}」替换为「${swapName}」。`,
      }
    }
  } else if (/减少|少一点|太多/.test(q)) {
    next.forEach((r) => {
      r.quantity = Math.max(1, Math.floor(r.quantity * 0.8))
    })
  } else if (/增加|多一点|太少/.test(q)) {
    next.forEach((r) => {
      r.quantity = Math.max(1, Math.ceil(r.quantity * 1.2))
    })
  }

  return next
}

function pickCreateAction(actions: ChatAction[] | undefined): ChatAction | null {
  if (!actions?.length) return null
  return actions.find((a) => a.type === 'create_purchase' || a.type === 'force_submit') || null
}

async function runThinkAnimation(
  steps: ReactStep[],
  streamPhrases: string[],
  opts?: { panelTitle?: string; customSteps?: ThinkStepItem[]; streamHint?: string }
) {
  void steps
  const q = lastUserMessage.value || queryInput.value || streamPhrases[0] || ''
  thinkPanelTitle.value = opts?.panelTitle || '多主体联动中'
  thinkElapsedMs.value = 0
  const startAt = Date.now()
  const elapsedTimer = window.setInterval(() => {
    thinkElapsedMs.value = Date.now() - startAt
  }, 60)
  startThinkStream([opts?.streamHint || `正在执行「${extractThinkContext(q).scene}」多主体协同链路...`])
  thinkSteps.value = opts?.customSteps || buildThinkStepsFromQuery(q)
  syncLatestThinkTrace()
  thinkVisibleCount.value = 1
  thinking.value = true
  for (let i = 0; i < thinkSteps.value.length; i++) {
    thinkSteps.value[i].status = 'active'
    thinkSteps.value[i].visibleDetailCount = 0
    thinkSteps.value = [...thinkSteps.value]
    syncLatestThinkTrace()
    await new Promise((r) => setTimeout(r, 300))
    for (let d = 0; d < thinkSteps.value[i].details.length; d++) {
      thinkSteps.value[i].visibleDetailCount = d + 1
      thinkSteps.value = [...thinkSteps.value]
      syncLatestThinkTrace()
      await new Promise((r) => setTimeout(r, 220))
    }
    await new Promise((r) => setTimeout(r, i === 3 ? THINK_STEP_WMS_MS : THINK_STEP_MS))
    thinkSteps.value[i].status = 'done'
    thinkSteps.value = [...thinkSteps.value]
    syncLatestThinkTrace()
    await new Promise((r) => setTimeout(r, 220))
    if (i < thinkSteps.value.length - 1) {
      thinkVisibleCount.value = i + 2
      await new Promise((r) => setTimeout(r, 180))
    }
  }
  await new Promise((r) => setTimeout(r, 320))
  thinking.value = false
  if (elapsedTimer) clearInterval(elapsedTimer)
  thinkElapsedMs.value = Date.now() - startAt
  stopThinkStream()
}

async function submitQuery(raw?: string, opts?: { useAgent?: boolean; presetId?: PresetScriptId }) {
  const q = (raw ?? queryInput.value).trim()
  if (!q || sending.value) return

  const currentSheetSnapshot = JSON.parse(JSON.stringify(sheetItems.value)) as SheetItem[]
  const incrementalRequest = isIncrementalDialogue(q, currentSheetSnapshot)
  const useAgent =
    opts?.useAgent !== undefined
      ? opts.useAgent || incrementalRequest
      : pendingAgentSend.value || isPresetDemoUtterance(q) || incrementalRequest
  const presetId = opts?.presetId
  pendingAgentSend.value = false

  const wasWelcome = showGeminiWelcome.value
  const firstRect =
    wasWelcome && !prefersReducedMotion() && composerShellRef.value
      ? composerShellRef.value.getBoundingClientRect()
      : null

  archiveCurrentTurnIfAny()
  traceExpanded.value = false
  lastUserMessage.value = q
  queryInput.value = ''
  uiPhase.value = 'result'
  sheetItems.value = []
  assistantNote.value = ''
  latestThinkTrace.value = []
  stopReplyTyping()
  replyDisplayText.value = ''
  abnormalMode.value = false
  forceAction.value = null
  await nextTick()
  scrollChatToBottom()

  if (firstRect && composerShellRef.value) {
    await nextTick()
    requestAnimationFrame(() => {
      runComposerFlipFromRect(firstRect)
    })
  }

  const phrases = buildThinkPhrases(q)

  if (isAbnormalRequest(q)) {
    sending.value = true
    await runThinkAnimation(
      [
        { step: 1, text: '校验采购政策与教学用途…' },
        { step: 2, text: '多主体风控：规模/用途异常标记' },
      ],
      ['正在比对设备采购政策…', '正在触发风控复核通道…']
    )
    abnormalMode.value = true
    abnormalText.value =
      '该需求不符合教学设备常规申领规范（例如大规模设备或非教学核心用途）。如需留痕申报，可在下方走「强制提交」流程。'
    forceAction.value = {
      type: 'force_submit',
      label: '强制提交',
      payload: { items: [{ name: '笔记本电脑', quantity: 100, unit: '台' }] },
    }
    sheetItems.value = []
    assistantNote.value = ''
    sending.value = false
    return
  }

  abnormalMode.value = false
  forceAction.value = null
  sending.value = true
  // 保持轻量加载态直到结果卡片可渲染，避免思考动画结束后的空白等待
  dialogThinking.value = true

  if (incrementalRequest) {
    const plan = buildIncrementalPlan(currentSheetSnapshot, q)
    await runThinkAnimation([], [], {
      panelTitle: '上下文继承与增量编排 (Incremental Orchestration)',
      customSteps: plan.steps,
      streamHint: '正在执行增量计算、局部寻址与动态合并...',
    })
    dialogThinking.value = false
    sheetItems.value = plan.merged
    sheetTitle.value = '期中考试保障申请单（已增量更新）'
    assistantNote.value = `已基于当前会话完成增量合并：新增矿泉水与便携急救箱，当前总计约 ¥${plan.newTotal}。`
    traceExpanded.value = true
    stopReplyTyping()
    replyDisplayText.value = assistantNote.value
    sending.value = false
    scrollChatToBottom()
    return
  }

  if (useAgent && isRefineRequest(q)) {
    const base =
      currentSheetSnapshot.length > 0
        ? currentSheetSnapshot
        : (pastTurns.value[pastTurns.value.length - 1]?.items || [])
    if (base.length) {
      await runThinkAnimation(
        [
          { step: 1, text: '解析您的偏好与规格要求' },
          { step: 2, text: '匹配同类可替代物资' },
          { step: 3, text: '按库存与规则重生成申请单' },
        ],
        ['正在理解替换诉求…', '正在查找同类规格…', '正在重算申请清单…']
      )
      await sleep(520)
      const regenerated = regenerateSheetByPreference(q, base)
      dialogThinking.value = false
      sheetItems.value = regenerated
      sheetTitle.value = '智能申领清单（已按偏好重生成）'
      assistantNote.value = '已根据您的偏好重新生成申请单，您可以继续微调数量后提交。'
      stopReplyTyping()
      replyDisplayText.value = assistantNote.value
      sending.value = false
      scrollChatToBottom()
      return
    }
  }
  if (useAgent) {
    await runThinkAnimation(
      [
        { step: 1, text: '自然语言 → 结构化场景' },
        { step: 2, text: '物资主数据 / 规格匹配' },
        { step: 3, text: '仓储可用量 / 替代策略' },
        { step: 4, text: '额度校验 & 生成微件' },
      ],
      phrases
    )
  }

  if (presetId) {
    const preset = presetScriptById(presetId)
    dialogThinking.value = false
    sheetItems.value = presetRows(preset.rows)
    sheetTitle.value = preset.title
    assistantNote.value = preset.note
    stopReplyTyping()
    replyDisplayText.value = assistantNote.value
    sending.value = false
    scrollChatToBottom()
    return
  }

  try {
    const apiPromise = chat(q, sessionId.value, { useAgent })
    const minDelay = new Promise((r) =>
      setTimeout(r, useAgent ? THINK_MIN_MS : THINK_LITE_MS)
    )
    const res: any = await Promise.all([apiPromise, minDelay]).then(([r]) => r)
    const data = res?.data || res
    if (!data) throw new Error('无效响应')
    if (data.session_id) sessionId.value = data.session_id

    dialogThinking.value = false
    assistantNote.value = String(data.reply || '').trim()
    const act = pickCreateAction(data.actions)
    let items = mapPayloadToSheetItems(act?.payload as Record<string, unknown>)
    if (!items.length && useAgent) items = fallbackSheetFromQuery(q)
    sheetItems.value = items
    sheetTitle.value = act?.type === 'force_submit' ? '待复核申领单（异常通道）' : '智能申领清单'

    if (!items.length && assistantNote.value && !useAgent) {
      startReplyTyping(assistantNote.value)
    } else {
      stopReplyTyping()
      replyDisplayText.value = assistantNote.value
    }
  } catch (e: any) {
    dialogThinking.value = false
    assistantNote.value = `智能体暂不可用：${e?.message || '请检查网络或后端'}${useAgent ? '\n已为您生成本地清单，可直接微调后提交。' : '\n请稍后重试，或改用下方快捷场景。'}`
    sheetItems.value = useAgent ? fallbackSheetFromQuery(q) : []
    sheetTitle.value = '智能申领清单'
    if (!sheetItems.value.length && assistantNote.value && !useAgent) {
      startReplyTyping(assistantNote.value)
    } else {
      stopReplyTyping()
      replyDisplayText.value = assistantNote.value
    }
  } finally {
    sending.value = false
    scrollChatToBottom()
  }
}

function isPresetDemoUtterance(q: string): boolean {
  return /(公开课|期中|考试|学院创新赛|比赛|教研室月度|复购|实验课|签到|答题卡|草稿纸)/.test(q)
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    void submitQuery()
  }
}

function bumpQty(row: SheetItem, delta: number) {
  const n = row.quantity + delta
  row.quantity = Math.max(1, Math.min(9999, n))
}

async function confirmPurchase() {
  const name = receiverName.value.trim()
  const dest = receiverDest.value.trim()
  if (!name || !dest) {
    ElMessage.warning('请填写收货人与收货地点')
    return
  }
  if (!sheetItems.value.length) {
    ElMessage.warning('没有可提交的物资行')
    return
  }
  submitting.value = true
  const isScenario = scenarioFlowActive.value
  try {
    const items = sheetItems.value.map((r) => ({
      name: r.name,
      quantity: r.quantity,
      unit: r.unit,
    }))
    const res: any = await executeAction('create_purchase', {
      items,
      receiver_name: name,
      destination: dest,
    })
    const data = res?.data || res
    const orderNo = data?.orderNo || `WB-${Date.now().toString(36).toUpperCase()}`
    if (!data?.success) throw new Error('提交失败')
    if (isScenario) {
      scenarioSubmitSuccess.value = true
      await sleep(2600)
      scenarioSubmitSuccess.value = false
      scenarioFlowActive.value = false
      scenarioSheetReady.value = false
      scenarioAiReplyText.value = ''
    }
    ElMessage.success(`申领已提交：${orderNo}`)
    saveTracking({
      order_no: orderNo,
      message: '单号 ' + orderNo + ' · 正在被仓储端打包中…',
      step: 2,
      total: 4,
    })
    void router.push('/teacher/personal?tab=orders')
  } catch {
    const orderNo = `WB-${Date.now().toString(36).toUpperCase()}`
    if (isScenario) {
      scenarioSubmitSuccess.value = true
      await sleep(2600)
      scenarioSubmitSuccess.value = false
      scenarioFlowActive.value = false
      scenarioSheetReady.value = false
      scenarioAiReplyText.value = ''
    }
    ElMessage.success(`已提交后勤仓储 ${orderNo}`)
    saveTracking({
      order_no: orderNo,
      message: '单号 ' + orderNo + ' · 正在被仓储端打包中…',
      step: 2,
      total: 4,
    })
    void router.push('/teacher/personal?tab=orders')
  } finally {
    submitting.value = false
    void refreshTrackingFromApi()
  }
}

async function confirmForceSubmit() {
  const name = receiverName.value.trim()
  const dest = receiverDest.value.trim()
  if (!name || !dest) {
    ElMessage.warning('请填写收货人与收货地点')
    return
  }
  const act = forceAction.value
  if (!act) return
  submitting.value = true
  try {
    const res: any = await executeAction('create_purchase', {
      ...(act.payload || {}),
      items: (act.payload as { items?: unknown[] })?.items || [],
      receiver_name: name,
      destination: dest,
    })
    const data = res?.data || res
    const orderNo = data?.orderNo || `DEMO-${Date.now()}`
    ElMessage.success(`已创建留痕单号：${orderNo}`)
    addAbnormalOrder(orderNo)
    resetHome()
  } catch {
    const orderNo = `DEMO-${Date.now()}`
    ElMessage.success(`已创建留痕单号 ${orderNo}`)
    addAbnormalOrder(orderNo)
    resetHome()
  } finally {
    submitting.value = false
  }
}

function resetHome() {
  clearComposerFlipStyles()
  pastTurns.value = []
  lastUserMessage.value = ''
  traceExpanded.value = false
  latestThinkTrace.value = []
  uiPhase.value = 'home'
  sheetItems.value = []
  assistantNote.value = ''
  abnormalMode.value = false
  forceAction.value = null
  thinking.value = false
  thinkSteps.value = []
  stopThinkStream()
  sessionId.value = null
  scenarioFlowActive.value = false
  scenarioAiReplyText.value = ''
  scenarioSheetReady.value = false
  scenarioSubmitSuccess.value = false
  scenarioReplyTyping.value = false
  pendingAgentSend.value = false
  dialogThinking.value = false
  stopReplyTyping()
  replyDisplayText.value = ''
  nextTick(() => playGreetingEntrance())
}

function onVoice() {
  ElMessage.info('语音输入功能暂未开启，请直接使用文字或上传图片。')
}

const showGeminiWelcome = computed(
  () =>
    pastTurns.value.length === 0 &&
    !lastUserMessage.value &&
    !thinking.value &&
    !sending.value &&
    !scenarioFlowActive.value
)

/** 已进入对话流：输入区沉底（与 showGeminiWelcome 互斥） */
const isChatting = computed(() => !showGeminiWelcome.value)

function goTraceFromChat() {
  void router.push('/trace')
}

function remindOrder() {
  ElMessage.success('已为您催单，后勤班组将尽快处理')
  void refreshTrackingFromApi()
}

const formatMoney = (n: number) =>
  n.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
</script>

<template>
  <div class="wb-root" @focusin="omniboxFocused = true" @focusout="onOmniboxBlur">
    <div class="wb-page-veil" aria-hidden="true" />
    <div class="wb-center-stack" :class="{ 'wb-center-stack--welcome': showGeminiWelcome }">
      <div
        class="wb-canvas"
        :class="{ 'wb-canvas--welcome': showGeminiWelcome, 'wb-canvas--chat': isChatting }"
      >
      <main
        ref="chatScrollRef"
        class="wb-chat-scroll wb-chat-scroll--panel"
        :class="{ 'wb-chat-scroll--collapsed': showGeminiWelcome }"
        :aria-hidden="showGeminiWelcome"
      >
        <div v-for="turn in pastTurns" :key="turn.id" class="wb-turn">
          <div class="wb-row wb-row--user">
            <div class="wb-bubble wb-bubble--user">{{ turn.user }}</div>
          </div>
          <div class="wb-row wb-row--ai">
            <div class="wb-ai-avatar" aria-hidden="true">链</div>
            <div v-if="turn.items?.length" class="wb-bubble wb-bubble--ai wb-bubble--sheet wb-bubble--sheet-muted">
              <div class="sheet-header">
                <div>
                  <h2 class="sheet-title">{{ turn.sheetTitle }}</h2>
                  <p v-if="turn.assistant" class="sheet-note">{{ turn.assistant }}</p>
                  <div v-if="turn.thinkTrace?.length" class="sheet-trace">
                    <el-button size="small" text @click="togglePastTrace(turn.id)">
                      {{ pastTraceExpanded[turn.id] ? '收起思考过程' : '展开思考过程' }}
                    </el-button>
                    <transition name="fade-up">
                      <div v-if="pastTraceExpanded[turn.id]" class="sheet-trace-panel">
                        <div
                          v-for="(s, i) in turn.thinkTrace"
                          :key="`past-trace-${turn.id}-${i}`"
                          class="sheet-trace-step"
                        >
                          <p class="sheet-trace-title">{{ s.title }}</p>
                          <p class="sheet-trace-line">{{ s.subtitle }}</p>
                          <p v-for="(detail, idx) in s.details" :key="idx" class="sheet-trace-line">{{ detail }}</p>
                        </div>
                      </div>
                    </transition>
                  </div>
                </div>
                <div class="sheet-badge sheet-badge--muted">历史单据</div>
              </div>
              <div class="sheet-grid">
                <div v-for="row in turn.items" :key="row.key" class="sku-card sku-card--readonly">
                  <div class="sku-emoji" aria-hidden="true">{{ row.emoji }}</div>
                  <div class="sku-main">
                    <div class="sku-name">{{ row.name }}</div>
                    <div class="sku-meta">
                      <span v-if="row.stockLevel === 'ok'" class="stock-pill ok">充足</span>
                      <span v-else-if="row.stockLevel === 'low'" class="stock-pill low">仅剩 {{ row.lowStockCount ?? '—' }}</span>
                      <span v-else-if="row.stockLevel === 'substituted'" class="stock-pill sub">智能替换</span>
                    </div>
                    <div class="qty-row">
                      <span class="qty-label">数量</span>
                      <span class="qty-val">{{ row.quantity }}</span>
                      <span class="unit">{{ row.unit }}</span>
                      <span v-if="row.unitPrice > 0" class="unit-price">约 ¥{{ row.unitPrice }}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class="sheet-footer sheet-footer--readonly">
                <div class="estimate-row">
                  <span class="estimate-label">预估额度</span>
                  <span class="estimate-val">¥{{ formatMoney(turnEstimatedTotal(turn)) }}</span>
                </div>
                <span class="readonly-hint">历史记录（只读）</span>
              </div>
            </div>
            <div v-else class="wb-bubble wb-bubble--ai wb-bubble--sheet-muted">
              <p v-if="turn.assistant" class="wb-bubble-text">{{ turn.assistant }}</p>
              <p v-if="turn.abnormal && turn.abnormalText" class="wb-bubble-warn">{{ turn.abnormalText }}</p>
            </div>
          </div>
        </div>

        <div v-if="lastUserMessage" class="wb-row wb-row--user">
          <div class="wb-bubble wb-bubble--user">{{ lastUserMessage }}</div>
        </div>

        <div v-if="thinking" class="wb-row wb-row--ai">
          <div class="wb-ai-avatar" aria-hidden="true">链</div>
          <div class="wb-bubble wb-bubble--ai wb-bubble--think">
            <div v-if="thinkStreamLine" class="think-stream">{{ thinkStreamLine }}</div>
            <div class="think-title">
              <el-icon class="spin"><Cpu /></el-icon>
              <span>{{ thinkPanelTitle }}</span>
              <span class="think-time-counter">耗时: {{ thinkElapsedMs }} ms</span>
            </div>
            <transition-group name="think-step" tag="ul" class="think-list">
              <li
                v-for="(s, i) in thinkSteps.slice(0, thinkVisibleCount)"
                :key="`${i}-${s.title}`"
                :class="['think-step', `is-${s.status}`]"
              >
                <div class="think-step-head">
                  <span class="think-step-icon">
                    <el-icon v-if="s.status === 'done'" class="chk"><CircleCheck /></el-icon>
                    <el-icon v-else-if="s.status === 'active'" class="loading"><Loading /></el-icon>
                    <span v-else class="idle-dot" />
                  </span>
                  <span class="think-step-title">{{ s.title }}</span>
                </div>
                <p class="think-step-sub">{{ s.subtitle }}</p>
                <p
                  v-for="(detail, idx) in s.details.slice(0, s.visibleDetailCount)"
                  :key="idx"
                  class="think-step-detail"
                >
                  {{ detail }}
                </p>
              </li>
            </transition-group>
          </div>
        </div>

        <div v-else-if="dialogThinking" class="wb-row wb-row--ai">
          <div class="wb-ai-avatar" aria-hidden="true">链</div>
          <div class="wb-thinking-lite" aria-live="polite">
            <span class="wb-thinking-dots" aria-hidden="true">
              <span class="wb-thinking-dot" />
              <span class="wb-thinking-dot" />
              <span class="wb-thinking-dot" />
            </span>
            <span class="wb-thinking-lite-text">小链在琢磨怎么回复您…</span>
          </div>
        </div>

        <div
          v-if="!thinking && !dialogThinking && scenarioFlowActive && (scenarioAiReplyText || scenarioReplyTyping)"
          class="wb-row wb-row--ai"
        >
          <div class="wb-ai-avatar" aria-hidden="true">链</div>
          <div class="wb-bubble wb-bubble--ai">
            <p class="wb-ai-meta">采购与物资助手</p>
            <p class="wb-bubble-text">
              {{ scenarioAiReplyText }}<span v-if="scenarioReplyTyping" class="demo-caret" />
            </p>
          </div>
        </div>

        <div
          v-if="!thinking && !dialogThinking && abnormalMode"
          class="wb-row wb-row--ai"
        >
          <div class="wb-ai-avatar" aria-hidden="true">链</div>
          <div class="wb-bubble wb-bubble--ai wb-bubble--danger">
            <div class="abn-head">
              <el-icon><WarningFilled /></el-icon>
              风控提示
            </div>
            <p class="abn-text">{{ abnormalText }}</p>
            <el-form label-width="88px" class="recv-form">
              <el-form-item label="收货人" required>
                <el-input v-model="receiverName" placeholder="姓名" />
              </el-form-item>
              <el-form-item label="收货地点" required>
                <el-input v-model="receiverDest" placeholder="如：教学楼 A302" />
              </el-form-item>
            </el-form>
            <el-button type="danger" :loading="submitting" class="full-btn" @click="confirmForceSubmit">
              强制提交（留痕）
            </el-button>
          </div>
        </div>

        <div
          v-if="
            !thinking &&
            !dialogThinking &&
            !abnormalMode &&
            sheetItems.length &&
            (!scenarioFlowActive || scenarioSheetReady)
          "
          class="wb-row wb-row--ai"
        >
          <div class="wb-ai-avatar" aria-hidden="true">链</div>
          <div class="wb-bubble wb-bubble--ai wb-bubble--sheet">
            <div class="linkage-bar">
              <span>教务场景</span>
              <span class="dot-sep">·</span>
              <span>仓储 WMS</span>
              <span class="dot-sep">·</span>
              <span>院系额度</span>
              <span class="linkage-ok">已联动预检</span>
            </div>
            <div class="sheet-header">
              <div>
                <h2 class="sheet-title">{{ sheetTitle }}</h2>
                <p v-if="assistantNote" class="sheet-note">{{ assistantNote }}</p>
                <div v-if="latestThinkTrace.length" class="sheet-trace">
                  <el-button size="small" text @click="traceExpanded = !traceExpanded">
                    {{ traceExpanded ? '收起思考过程' : '展开思考过程' }}
                  </el-button>
                  <transition name="fade-up">
                    <div v-if="traceExpanded" class="sheet-trace-panel">
                      <div
                        v-for="(s, i) in latestThinkTrace"
                        :key="`trace-${i}`"
                        class="sheet-trace-step"
                      >
                        <p class="sheet-trace-title">{{ s.title }}</p>
                        <p class="sheet-trace-line">{{ s.subtitle }}</p>
                        <p v-for="(detail, idx) in s.details" :key="idx" class="sheet-trace-line">
                          {{ detail }}
                        </p>
                      </div>
                    </div>
                  </transition>
                </div>
              </div>
              <div class="sheet-badge">
                <span class="live-dot" />
                库存预检
              </div>
            </div>
            <div class="sheet-actions-bar">
              <el-button size="small" round @click="goTraceFromChat">
                <el-icon><Connection /></el-icon>
                溯源查询
              </el-button>
              <el-button size="small" round :disabled="!tracking" @click="remindOrder">催单</el-button>
            </div>
            <div class="sheet-grid">
              <div v-for="row in sheetItems" :key="row.key" class="sku-card">
                <div class="sku-emoji" aria-hidden="true">{{ row.emoji }}</div>
                <div class="sku-main">
                  <div class="sku-name">{{ row.name }}</div>
                  <div class="sku-meta">
                    <span v-if="row.stockLevel === 'ok'" class="stock-pill ok">充足</span>
                    <span v-else-if="row.stockLevel === 'low'" class="stock-pill low">
                      仅剩 {{ row.lowStockCount ?? '—' }}
                    </span>
                    <span v-else-if="row.stockLevel === 'substituted'" class="stock-pill sub">智能替换</span>
                  </div>
                  <p v-if="row.substitutionNote" class="subst-note">{{ row.substitutionNote }}</p>
                  <div class="qty-row">
                    <span class="qty-label">数量</span>
                    <el-button size="small" circle @click="bumpQty(row, -1)">−</el-button>
                    <span class="qty-val">{{ row.quantity }}</span>
                    <el-button size="small" circle @click="bumpQty(row, 1)">+</el-button>
                    <span class="unit">{{ row.unit }}</span>
                    <span v-if="row.unitPrice > 0" class="unit-price">约 ¥{{ row.unitPrice }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div class="sheet-footer">
              <div class="footer-left">
                <div class="estimate-row">
                  <span class="estimate-label">预估额度</span>
                  <span class="estimate-val">¥{{ formatMoney(estimatedTotal) }}</span>
                </div>
                <el-form label-width="88px" class="recv-form recv-form--row">
                  <el-form-item label="收货人" required>
                    <el-input v-model="receiverName" placeholder="默认可改" class="recv-input" />
                  </el-form-item>
                  <el-form-item label="收货地点" required>
                    <el-input v-model="receiverDest" placeholder="送达位置" class="recv-input-wide" />
                  </el-form-item>
                </el-form>
              </div>
              <el-button
                type="primary"
                size="large"
                class="confirm-btn wb-primary-btn"
                :loading="submitting"
                @click="confirmPurchase"
              >
                {{ scenarioFlowActive ? '同意并提交' : '确认提交申请' }}
              </el-button>
            </div>
          </div>
        </div>

        <div
          v-if="
            !thinking &&
            !dialogThinking &&
            !abnormalMode &&
            !scenarioFlowActive &&
            !sheetItems.length &&
            assistantNote.trim() &&
            lastUserMessage &&
            !sending
          "
          class="wb-row wb-row--ai"
        >
          <div class="wb-ai-avatar" aria-hidden="true">链</div>
          <div class="wb-bubble wb-bubble--ai wb-bubble--dialog">
            <p class="wb-ai-meta">小链</p>
            <p class="wb-bubble-text wb-bubble-text--stream">
              {{ replyDisplayText }}<span v-if="replyTypingActive" class="wb-reply-caret" aria-hidden="true" />
            </p>
          </div>
        </div>

        <div
          v-if="
            !thinking &&
            !dialogThinking &&
            !abnormalMode &&
            !sheetItems.length &&
            !assistantNote.trim() &&
            lastUserMessage &&
            !sending &&
            !scenarioFlowActive
          "
          class="wb-empty-hint"
        >
          本轮未生成申领清单，可补充描述后再次发送。
        </div>
      </main>
      <section ref="composerShellRef" class="wb-composer">
      <section class="wb-hero">
        <div
          class="wb-hero-head"
          :class="{
            'wb-hero-head--gemini': showGeminiWelcome,
            'wb-hero-head--dock': isChatting,
          }"
        >
          <div v-if="showGeminiWelcome" class="wb-hero-title-wrap wb-hero-title-wrap--gemini">
            <div
              class="wb-greet-gemini"
              :class="{ 'wb-greet-gemini--shown': greetShown }"
              aria-live="polite"
            >
              <p class="wb-greet-kicker">{{ greetingLineKicker }}</p>
              <p class="wb-greet-main">{{ greetingLineMain }}</p>
            </div>
          </div>
          <div class="wb-hero-toolbar" :class="{ 'wb-hero-toolbar--dock': isChatting }">
            <el-tooltip content="查全校物资库存（Ctrl+K）" placement="bottom">
              <button type="button" class="wb-hero-icon-btn" @click="openStockSearch">
                <el-icon :size="18"><Search /></el-icon>
              </button>
            </el-tooltip>
            <button type="button" class="wb-hero-newchat-btn" @click="resetHome">
              <el-icon class="wb-hero-newchat-btn__ico"><RefreshRight /></el-icon>
              新对话
            </button>
            <el-popover placement="bottom-end" :width="320" trigger="click">
              <template #reference>
                <button type="button" class="wb-hero-scene-btn">更多场景</button>
              </template>
              <div class="wb-scenario-pop">
                <p class="wb-scenario-pop-title">场景化快捷需求</p>
                <button
                  v-for="(s, i) in scenarioQuickList"
                  :key="i"
                  type="button"
                  class="wb-scenario-item"
                  @click="applyScenarioPrompt(s)"
                >
                  <span class="wb-scenario-emoji">{{ s.emoji }}</span>
                  {{ s.label }}
                </button>
              </div>
            </el-popover>
          </div>
        </div>

        <div
          class="wb-omni-shell"
          :class="{ 'wb-omni-shell--focus': omniboxFocused, 'wb-omni-shell--dock': isChatting }"
        >
          <div class="wb-omni-halo" aria-hidden="true" />
          <div class="wb-omni-wrap">
            <input
              ref="fileInputRef"
              type="file"
              accept="image/*"
              class="file-input"
              @change="onFileChange"
            />
            <textarea
              ref="omniboxTextareaRef"
              v-model="queryInput"
              class="wb-omni-textarea"
              rows="1"
              placeholder="输入物资需求（如「申请教室清洁用品」）"
              @keydown="onKeydown"
              @input="autoSizeOmnibox"
            />
            <div class="wb-omni-tools">
              <el-tooltip content="上传图片识别清单" placement="top">
                <button type="button" class="wb-omni-tool" @click="triggerFilePick">
                  <el-icon :size="20"><Paperclip /></el-icon>
                </button>
              </el-tooltip>
              <el-tooltip content="语音输入（暂未开启）" placement="top">
                <button type="button" class="wb-omni-tool" @click="onVoice">
                  <el-icon :size="20"><Microphone /></el-icon>
                </button>
              </el-tooltip>
              <el-button
                type="primary"
                class="wb-omni-send"
                :loading="sending"
                :disabled="!queryInput.trim()"
                @click="submitQuery()"
              >
                <el-icon><Promotion /></el-icon>
                发送
              </el-button>
            </div>
          </div>
        </div>
        <p v-if="showGeminiWelcome" class="wb-omni-hint">
          Enter 发送 · Shift+Enter 换行 · 支持图片识别
        </p>

        <div v-if="showGeminiWelcome" class="wb-hero-chips">
          <button
            v-for="chip in corePromptChips"
            :key="chip.id"
            type="button"
            class="wb-core-chip"
            @click="onCoreChip(chip)"
          >
            {{ chip.label }}
          </button>
        </div>
      </section>
      </section>

      </div>

      <section
        v-if="showGeminiWelcome"
        class="wb-insight wb-insight--below wb-insight--dream"
        aria-label="动态赋能流"
      >
        <header class="wb-insight-head wb-insight-head--compact">
          <span class="wb-insight-kicker">Insight</span>
          <h3 class="wb-insight-title">动态赋能流</h3>
          <p class="wb-insight-desc">校历、订单与借用记录触发的建议</p>
        </header>
        <div class="wb-insight-feed wb-insight-feed--grid">
          <article
            v-for="card in insightCards"
            :key="card.id"
            class="wb-insight-card wb-insight-card--dream"
            :style="{ '--card-tint': card.gradient }"
          >
            <div class="wb-insight-card-head">
              <el-icon class="wb-insight-ico"><component :is="card.icon" /></el-icon>
              <h4 class="wb-insight-card-title">{{ card.title }}</h4>
            </div>
            <p class="wb-insight-analysis">{{ card.analysis }}</p>
            <div class="wb-insight-card-actions">
              <el-button type="primary" size="small" round @click="onInsightPrimary(card)">
                {{ card.cta }}
              </el-button>
              <el-button v-if="card.secondaryCta" size="small" round @click="onInsightSecondary(card)">
                {{ card.secondaryCta }}
              </el-button>
            </div>
          </article>
        </div>
      </section>
    </div>

    <teleport to="body">
      <transition name="success-pop">
        <div v-if="scenarioSubmitSuccess" class="submit-success-overlay">
          <div class="submit-success-card">
            <div class="submit-success-ring" aria-hidden="true" />
            <el-icon class="submit-success-icon" :size="56"><CircleCheck /></el-icon>
            <h3 class="submit-success-title">申请提交成功</h3>
            <p class="submit-success-desc">后勤仓储已接单，正在为您备货与安排配送</p>
          </div>
        </div>
      </transition>
    </teleport>

  </div>
</template>

<style scoped lang="scss">
/* Gemini 风格 · 校园物资工作台 */
.wb-root {
  --wb-blue: #1677ff;
  --wb-green: #00b42a;
  --wb-red: #f53f3f;
  --wb-bg: #f2f3f5;
  --wb-text: #1d2129;
  --wb-muted: #86909c;
  --wb-ease-out: cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  width: 100%;
  max-width: 100%;
  height: 100%;
  margin: 0 auto;
  overflow: hidden;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 48%, #eef2f7 100%);
  color: var(--wb-text);
  padding-bottom: env(safe-area-inset-bottom, 0);
}

.wb-page-veil {
  pointer-events: none;
  position: absolute;
  inset: 0;
  z-index: 0;
  background:
    radial-gradient(ellipse 90% 55% at 50% 12%, rgba(99, 102, 241, 0.11), transparent 58%),
    radial-gradient(ellipse 70% 45% at 85% 8%, rgba(14, 165, 233, 0.08), transparent 50%),
    radial-gradient(ellipse 55% 40% at 15% 22%, rgba(139, 92, 246, 0.07), transparent 52%);
}

.wb-center-stack {
  position: relative;
  z-index: 1;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  width: 100%;
  max-width: min(1120px, 96vw);
  margin: 0 auto;
  padding: 0 clamp(16px, 3vw, 28px);
  box-sizing: border-box;
}

.wb-center-stack--welcome .wb-omni-shell {
  max-width: min(820px, 100%);
}

/* 主画布：欢迎态垂直居中唤醒；对话态消息在上、输入沉底 */
.wb-canvas {
  position: relative;
  z-index: 1;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  transition:
    justify-content 0.5s var(--wb-ease-out),
    padding 0.5s var(--wb-ease-out);
}

.wb-canvas--welcome {
  justify-content: center;
}

.wb-canvas--chat {
  justify-content: flex-start;
}

/* 欢迎态：消息区高度折叠，保持挂载以便 FLIP 与布局稳定 */
.wb-chat-scroll--collapsed {
  flex: 0 1 0;
  min-height: 0;
  max-height: 0;
  overflow: hidden;
  padding-top: 0;
  padding-bottom: 0;
  opacity: 0;
  pointer-events: none;
  visibility: hidden;
}

.wb-composer {
  flex-shrink: 0;
  width: 100%;
  transition:
    transform 0.5s var(--wb-ease-out),
    box-shadow 0.5s var(--wb-ease-out);
}

@media (prefers-reduced-motion: reduce) {
  .wb-composer {
    transition: none;
  }
}

.wb-canvas--chat .wb-composer {
  border-top: 1px solid rgba(15, 23, 42, 0.06);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.65) 0%, rgba(255, 255, 255, 0.5) 100%);
  backdrop-filter: blur(10px);
  padding-top: 4px;
}

.wb-canvas--welcome .wb-hero {
  padding: 0 0 12px;
}

.wb-hero {
  flex-shrink: 0;
  padding: 20px 0 12px;
}

.wb-canvas--chat .wb-hero {
  padding: 10px 0 8px;
}

.wb-hero-head {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
  margin-bottom: 22px;
}

.wb-hero-head--gemini {
  flex-direction: row;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  width: 100%;
  max-width: min(760px, 100%);
  margin-left: auto;
  margin-right: auto;
}

/* 对话态：仅保留顶栏工具，与输入组成底栏 */
.wb-hero-head--dock {
  flex-direction: row;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 8px;
  width: 100%;
  max-width: min(760px, 100%);
  margin-left: auto;
  margin-right: auto;
}

.wb-hero-toolbar--dock {
  justify-content: flex-end;
  flex: 1;
  width: 100%;
}

.wb-hero-title-wrap {
  width: 100%;
  max-width: 820px;
  text-align: center;
}

.wb-hero-title-wrap--gemini {
  flex: 1;
  min-width: 0;
  max-width: none;
  text-align: left;
}

.wb-greet-gemini {
  width: 100%;
}

.wb-greet-kicker,
.wb-greet-main {
  opacity: 0;
  transform: translateY(14px);
  will-change: opacity, transform;
  transition:
    opacity 0.55s cubic-bezier(0.22, 1, 0.36, 1),
    transform 0.62s cubic-bezier(0.22, 1, 0.36, 1);
}

.wb-greet-gemini--shown .wb-greet-kicker,
.wb-greet-gemini--shown .wb-greet-main {
  opacity: 1;
  transform: translateY(0);
}

.wb-greet-gemini--shown .wb-greet-kicker {
  transition-delay: 0.04s;
}

.wb-greet-gemini--shown .wb-greet-main {
  transition-delay: 0.12s;
}

@media (prefers-reduced-motion: reduce) {
  .wb-greet-kicker,
  .wb-greet-main {
    transition: none;
  }
}

.wb-greet-kicker {
  margin: 0 0 6px;
  font-size: clamp(14px, 1.6vw, 16px);
  font-weight: 500;
  color: var(--wb-muted);
  letter-spacing: 0.02em;
}

.wb-greet-main {
  margin: 0;
  font-size: clamp(24px, 3.2vw, 36px);
  font-weight: 650;
  letter-spacing: -0.03em;
  line-height: 1.22;
  color: #111827;
}

.wb-hero-title {
  margin: 0 0 8px;
  font-size: clamp(17px, 2.2vw, 22px);
  font-weight: 700;
  line-height: 1.45;
  color: var(--wb-text);
}

.wb-hero-toolbar {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  flex-wrap: wrap;
  gap: 6px;
}

.wb-hero-head--gemini .wb-hero-toolbar {
  justify-content: flex-end;
  padding-top: 2px;
}

.wb-hero-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--wb-muted);
  cursor: pointer;
  transition: background 0.15s ease;
}
.wb-hero-icon-btn:hover {
  background: var(--wb-bg);
  color: var(--wb-blue);
}

.wb-hero-newchat-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.25;
  color: var(--wb-text);
  background: #fff;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    color 0.15s ease,
    background 0.15s ease;
}

.wb-hero-newchat-btn:hover {
  border-color: var(--wb-blue);
  color: var(--wb-blue);
  background: rgba(22, 119, 255, 0.04);
}

.wb-hero-newchat-btn__ico {
  font-size: 14px;
}

.wb-hero-scene-btn {
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--wb-text);
  background: #fff;
  cursor: pointer;
  transition: border-color 0.15s ease, color 0.15s ease;
}
.wb-hero-scene-btn:hover {
  border-color: var(--wb-blue);
  color: var(--wb-blue);
}

.wb-omni-shell {
  position: relative;
  width: 100%;
  max-width: min(760px, 100%);
  margin: 0 auto;
  padding: 3px;
}

.wb-omni-halo {
  position: absolute;
  inset: -8px -6px -4px;
  border-radius: 32px;
  background: linear-gradient(
    125deg,
    rgba(99, 102, 241, 0.55),
    rgba(139, 92, 246, 0.45),
    rgba(14, 165, 233, 0.5),
    rgba(99, 102, 241, 0.52)
  );
  background-size: 200% 200%;
  filter: blur(22px);
  opacity: 0.62;
  z-index: 0;
  pointer-events: none;
  animation: wb-halo-breathe 5s ease-in-out infinite;
}

.wb-omni-shell--focus .wb-omni-halo {
  opacity: 0.82;
  filter: blur(24px);
}

.wb-omni-shell--dock .wb-omni-halo {
  opacity: 0.4;
  filter: blur(14px);
  animation: none;
}

@keyframes wb-halo-breathe {
  0%,
  100% {
    background-position: 0% 40%;
    opacity: 0.52;
  }
  50% {
    background-position: 100% 60%;
    opacity: 0.78;
  }
}

.wb-omni-wrap {
  position: relative;
  z-index: 1;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(255, 255, 255, 0.65);
  box-shadow:
    0 10px 30px rgba(0, 0, 0, 0.08),
    0 2px 8px rgba(15, 23, 42, 0.04);
  backdrop-filter: blur(10px);
  transition:
    border-color 0.22s ease,
    box-shadow 0.22s ease;
}

.wb-omni-shell--focus .wb-omni-wrap {
  border-color: rgba(99, 102, 241, 0.28);
  box-shadow:
    0 14px 40px rgba(99, 102, 241, 0.14),
    0 10px 30px rgba(0, 0, 0, 0.07),
    0 0 0 1px rgba(99, 102, 241, 0.12);
}

.wb-omni-textarea {
  display: block;
  width: 100%;
  box-sizing: border-box;
  min-height: 64px;
  max-height: 200px;
  padding: 14px 16px 52px 18px;
  border: none;
  border-radius: 24px;
  resize: none;
  overflow-y: auto;
  font-size: 15px;
  line-height: 1.5;
  font-family: inherit;
  color: var(--wb-text);
  background: transparent;
  outline: none;
}

.wb-omni-textarea::placeholder {
  color: #a0a6ad;
}

.wb-omni-tools {
  position: absolute;
  right: 10px;
  bottom: 10px;
  display: flex;
  align-items: center;
  gap: 2px;
}

.wb-omni-tool {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--wb-muted);
  cursor: pointer;
  transition: background 0.15s ease;
}
.wb-omni-tool:hover {
  background: var(--wb-bg);
  color: var(--wb-blue);
}

.wb-omni-send {
  margin-left: 4px;
  --el-button-bg-color: var(--wb-blue);
  --el-button-border-color: var(--wb-blue);
  border-radius: 999px;
  font-weight: 600;
  padding: 8px 16px;
}

.wb-omni-hint {
  margin: 8px auto 0;
  max-width: 760px;
  font-size: 12px;
  color: var(--wb-muted);
  text-align: center;
}

.wb-hero-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 14px;
  padding: 0 8px 4px;
}

.wb-core-chip {
  border: none;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 13px;
  color: #2d3139;
  background: rgba(99, 102, 241, 0.08);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.wb-core-chip:hover {
  background: rgba(99, 102, 241, 0.18);
  color: #111;
}

/* 对话消息区：占满主画布剩余高度，仅此处滚动 */
.wb-chat-scroll--panel:not(.wb-chat-scroll--collapsed) {
  flex: 1;
  min-height: 0;
  overflow-x: hidden;
  overflow-y: auto;
  padding: 12px 0 12px;
  scroll-behavior: smooth;
}

.wb-chat-scroll--panel.wb-chat-scroll--collapsed {
  overflow: hidden;
}

.wb-insight--below {
  width: 100%;
  max-width: none;
  margin: 8px 0 28px;
  padding: 20px 0 8px;
  background: transparent;
  border: none;
  flex-shrink: 0;
}

.wb-insight--dream {
  position: relative;
  padding-top: 24px;
}

.wb-insight--dream::before {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  top: 0;
  height: 1px;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(99, 102, 241, 0.25) 20%,
    rgba(14, 165, 233, 0.22) 50%,
    rgba(139, 92, 246, 0.2) 80%,
    transparent
  );
  opacity: 0.85;
}

.wb-insight-head--compact {
  text-align: center;
  margin-bottom: 18px;
}

.wb-insight-head {
  margin-bottom: 12px;
}

.wb-insight-kicker {
  display: block;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--wb-muted);
  margin-bottom: 4px;
}

.wb-insight-title {
  margin: 0 0 4px;
  font-size: 16px;
  font-weight: 700;
  color: var(--wb-text);
}

.wb-insight-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--wb-muted);
}

.wb-insight-feed {
  width: 100%;
}

.wb-insight-feed--grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  align-items: stretch;
}

.wb-insight-card {
  position: relative;
  border-radius: 20px;
  padding: 16px 18px;
  border: 1px solid rgba(255, 255, 255, 0.78);
  background: linear-gradient(
      145deg,
      rgba(255, 255, 255, 0.58) 0%,
      rgba(255, 255, 255, 0.38) 100%
    ),
    var(--card-tint, linear-gradient(125deg, #f8fafc, #eef2ff));
  background-blend-mode: normal, normal;
  box-shadow:
    0 12px 36px rgba(99, 102, 241, 0.1),
    0 4px 16px rgba(15, 23, 42, 0.06),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  transition:
    transform 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    box-shadow 0.35s ease;
}

.wb-insight-card--dream {
  animation: wb-dream-in 0.75s cubic-bezier(0.22, 1, 0.36, 1) backwards;
}

.wb-insight-card--dream:nth-child(1) {
  animation-delay: 0.05s;
}
.wb-insight-card--dream:nth-child(2) {
  animation-delay: 0.12s;
}
.wb-insight-card--dream:nth-child(3) {
  animation-delay: 0.19s;
}

.wb-insight-card--dream:hover {
  transform: translateY(-5px);
  box-shadow:
    0 22px 52px rgba(99, 102, 241, 0.18),
    0 10px 28px rgba(15, 23, 42, 0.09),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

@keyframes wb-dream-in {
  from {
    opacity: 0;
    transform: translateY(18px) scale(0.97);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.wb-insight-card::before {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background: linear-gradient(160deg, rgba(255, 255, 255, 0.35), transparent 42%);
  opacity: 0.9;
}

.wb-insight-card-head {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.wb-insight-ico {
  flex-shrink: 0;
  color: var(--wb-text);
  margin-top: 2px;
}

.wb-insight-card-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
  color: var(--wb-text);
}

.wb-insight-analysis {
  position: relative;
  z-index: 1;
  margin: 0 0 10px;
  font-size: 12px;
  line-height: 1.5;
  color: #4b5563;
}

.wb-insight-card-actions {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

@media (max-width: 640px) {
  .wb-hero-head--gemini {
    flex-direction: column;
    align-items: stretch;
  }

  .wb-hero-head--gemini .wb-hero-toolbar {
    justify-content: center;
  }
}

@media (max-width: 1024px) {
  .wb-insight-feed--grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .wb-canvas--welcome .wb-composer {
    padding-top: clamp(24px, 6vh, 72px);
  }
}

@media (max-width: 1080px) {
  .wb-center-stack {
    padding: 0 14px;
  }
}

.wb-turn {
  margin-bottom: 20px;
}
.wb-row {
  display: flex;
  margin-bottom: 10px;
}
.wb-row--user {
  justify-content: flex-end;
}
.wb-row--ai {
  justify-content: flex-start;
  align-items: flex-start;
  gap: 10px;
}
.wb-ai-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  margin-top: 6px;
  font-size: 0;
  color: transparent;
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(8px);
  box-shadow:
    0 4px 10px rgba(15, 23, 42, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.7);
}
.wb-ai-avatar::before {
  content: '';
  position: absolute;
  inset: 3px;
  border-radius: 999px;
  background: linear-gradient(140deg, #2563eb 0%, #4f46e5 45%, #06b6d4 100%);
}
.wb-ai-avatar::after {
  content: 'AI';
  position: relative;
  z-index: 1;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #ffffff;
  text-shadow: 0 1px 2px rgba(15, 23, 42, 0.3);
}
.wb-bubble {
  max-width: min(92%, 640px);
  padding: 16px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}
.wb-bubble--user {
  background: #e8f3ff;
  color: var(--wb-text);
  border: 1px solid rgba(22, 119, 255, 0.2);
}
.wb-bubble--ai {
  background: #fff;
  border: 1px solid #e5e7eb;
  color: var(--wb-text);
}
.wb-bubble--sheet-muted {
  filter: grayscale(0.6);
  opacity: 0.82;
}
.wb-bubble--think {
  border-color: rgba(22, 119, 255, 0.25);
}
.wb-bubble--dialog {
  border-radius: 16px;
  box-shadow:
    0 4px 22px rgba(15, 23, 42, 0.06),
    0 0 0 1px rgba(99, 102, 241, 0.09);
}
.wb-bubble-text--stream {
  margin-bottom: 0;
  min-height: 1.45em;
}
.wb-reply-caret {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  vertical-align: -0.12em;
  background: var(--wb-blue);
  border-radius: 1px;
  animation: wb-caret-blink 0.95s step-end infinite;
}
@keyframes wb-caret-blink {
  50% {
    opacity: 0;
  }
}
@media (prefers-reduced-motion: reduce) {
  .wb-reply-caret {
    animation: none;
    opacity: 0.45;
  }
}
.wb-thinking-lite {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 18px;
  margin-bottom: 8px;
  border-radius: 999px;
  background: linear-gradient(120deg, rgba(99, 102, 241, 0.09), rgba(14, 165, 233, 0.06));
  border: 1px solid rgba(99, 102, 241, 0.14);
  font-size: 13px;
  color: #4b5563;
}
.wb-thinking-dots {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.wb-thinking-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #6366f1;
  opacity: 0.4;
  animation: wb-dot-pulse 1.05s ease-in-out infinite;
}
.wb-thinking-dot:nth-child(2) {
  animation-delay: 0.12s;
}
.wb-thinking-dot:nth-child(3) {
  animation-delay: 0.24s;
}
@keyframes wb-dot-pulse {
  0%,
  100% {
    opacity: 0.35;
    transform: scale(0.92);
  }
  50% {
    opacity: 1;
    transform: scale(1.06);
  }
}
@media (prefers-reduced-motion: reduce) {
  .wb-thinking-dot {
    animation: none;
    opacity: 0.65;
  }
}
.wb-bubble--danger {
  border-color: rgba(245, 63, 63, 0.35);
}
.wb-bubble--sheet {
  max-width: 100%;
  width: 100%;
}
.wb-bubble-text {
  margin: 0 0 8px;
  white-space: pre-wrap;
}
.wb-bubble-warn {
  margin: 0 0 8px;
  color: #b45309;
  font-size: 13px;
}
.wb-ai-meta {
  margin: 0 0 8px;
  font-size: 12px;
  color: var(--wb-muted);
}
.wb-mini-lines {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--wb-muted);
}
.wb-tag-ok {
  margin-left: 6px;
  color: var(--wb-green);
  font-size: 12px;
}
.wb-tag-warn {
  margin-left: 6px;
  color: #d97706;
  font-size: 12px;
}
.wb-tag-sub {
  margin-left: 6px;
  color: var(--wb-blue);
  font-size: 12px;
}
.wb-empty-hint {
  text-align: center;
  color: var(--wb-muted);
  font-size: 13px;
  padding: 16px;
}
.sheet-actions-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.wb-primary-btn {
  --el-button-bg-color: var(--wb-blue);
  --el-button-border-color: var(--wb-blue);
}

.wb-scenario-pop {
  padding: 4px 0;
}
.wb-scenario-pop-title {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 700;
  color: var(--wb-muted);
}
.wb-scenario-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  text-align: left;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  color: var(--wb-text);
}
.wb-scenario-item:hover {
  background: var(--wb-bg);
}

.native {
  position: relative;
  min-height: calc(100vh - 100px);
  padding: 8px 8px 120px;
  max-width: 1120px;
  margin: 0 auto;
  transition: background-color 0.35s ease;
}

.native--dim .native-bg {
  opacity: 0.38;
  filter: saturate(0.75);
}

.native-bg {
  pointer-events: none;
  position: fixed;
  inset: 0;
  background: radial-gradient(ellipse 80% 50% at 50% -20%, rgba(99, 102, 241, 0.14), transparent 55%),
    radial-gradient(ellipse 60% 40% at 100% 0%, rgba(14, 165, 233, 0.08), transparent 45%);
  z-index: 0;
  transition: opacity 0.35s ease;
}

.native > .native-bg {
  z-index: 0;
}

.native > .composer-zone,
.native > .workspace {
  position: relative;
  z-index: 2;
}
.native > .dock {
  z-index: 30;
}

.composer-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 28px 12px 8px;
  transition:
    padding 0.45s cubic-bezier(0.22, 1, 0.36, 1),
    align-items 0.35s ease;
}

.composer-zone--top {
  align-items: stretch;
  padding: 8px 0 12px;
  position: sticky;
  top: 0;
  z-index: 20;
  background: linear-gradient(180deg, var(--el-bg-color-page, #f8fafc) 75%, transparent);
  backdrop-filter: blur(12px);
}

.greeting {
  margin: 0 0 24px 0;
  font-size: clamp(21px, 3.4vw, 28px);
  font-weight: 650;
  letter-spacing: -0.02em;
  text-align: center;
  line-height: 1.38;
  max-width: 820px;
  color: var(--text-primary);
}

.greeting-char {
  display: inline-block;
  opacity: 0.08;
  transform: translateY(6px);
  transition:
    opacity 0.32s ease,
    transform 0.42s cubic-bezier(0.22, 1, 0.36, 1);
}

.greeting-char--on {
  opacity: 1;
  transform: translateY(0);
}

.greet-fade-enter-active,
.greet-fade-leave-active {
  transition: opacity 0.35s ease, transform 0.35s ease;
}
.greet-fade-enter-from,
.greet-fade-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.floating-shell {
  width: 100%;
  max-width: 760px;
  position: relative;
}

.composer-zone--top .floating-shell {
  max-width: none;
}

.floating-shell--pulse .omnibox-halo {
  position: absolute;
  inset: -3px;
  border-radius: 22px;
  background: linear-gradient(
    120deg,
    rgba(99, 102, 241, 0.45),
    rgba(14, 165, 233, 0.35),
    rgba(99, 102, 241, 0.45)
  );
  background-size: 200% 200%;
  animation: halo-breathe 4s ease-in-out infinite;
  opacity: 0.55;
  filter: blur(8px);
  z-index: 0;
  pointer-events: none;
}
@keyframes halo-breathe {
  0%,
  100% {
    background-position: 0% 50%;
    opacity: 0.45;
  }
  50% {
    background-position: 100% 50%;
    opacity: 0.7;
  }
}

.omnibox-ready {
  position: relative;
  z-index: 1;
  margin: 0 0 10px 4px;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  display: flex;
  align-items: center;
  gap: 8px;
}
.ready-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.35);
  animation: pulse 2s ease-in-out infinite;
}

.floating-bar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 14px 14px 14px 20px;
  border-radius: 20px;
  background: var(--bg-card);
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow:
    0 4px 6px -1px rgba(15, 23, 42, 0.06),
    0 18px 48px -12px rgba(79, 70, 229, 0.2);
}

.composer-zone--top .floating-bar {
  border-radius: 14px;
  padding: 10px 12px 10px 16px;
  box-shadow: 0 8px 28px rgba(15, 23, 42, 0.08);
}

.composer-zone--top .omnibox-halo,
.composer-zone--top .omnibox-ready {
  display: none;
}

.floating-input {
  flex: 1;
  border: none;
  outline: none;
  resize: none;
  min-height: 52px;
  max-height: 160px;
  font-size: 16px;
  line-height: 1.5;
  background: transparent;
  color: var(--text-primary);
  font-family: inherit;
}

.composer-zone--top .floating-input {
  min-height: 40px;
  font-size: 15px;
}

.floating-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}

.file-input {
  display: none;
}

.ico-btn {
  color: var(--text-muted);
}

.send-btn {
  padding: 10px 20px;
  font-weight: 600;
}

.floating-hint {
  position: relative;
  z-index: 1;
  margin: 10px 0 0 0;
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
}

.try-example-wrap {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: center;
  margin-top: 14px;
  width: 100%;
  max-width: 760px;
  margin-left: auto;
  margin-right: auto;
  padding: 0 8px;
}
.try-example-ghost {
  appearance: none;
  max-width: 100%;
  padding: 10px 18px 10px 16px;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.45;
  text-align: center;
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid rgba(99, 102, 241, 0.35);
  border-radius: 999px;
  cursor: pointer;
  transition:
    background 0.2s ease,
    border-color 0.2s ease,
    color 0.2s ease,
    box-shadow 0.2s ease;
}
.try-example-ghost:hover:not(:disabled) {
  color: var(--primary);
  border-color: var(--primary);
  background: rgba(99, 102, 241, 0.08);
  box-shadow: 0 2px 12px rgba(79, 70, 229, 0.12);
}
.try-example-ghost:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.scenario-reply-wrap {
  margin-bottom: 18px;
}
.scenario-reply-bubble {
  display: inline-block;
  max-width: 100%;
  padding: 14px 18px 16px;
  border-radius: 16px;
  background: var(--bg-card, #fff);
  border: 1px solid rgba(15, 23, 42, 0.07);
  box-shadow: 0 4px 18px rgba(15, 23, 42, 0.07);
}
.scenario-reply-meta {
  margin: 0 0 10px 0;
  font-size: 12px;
  line-height: 1.35;
  color: var(--text-muted);
}
.scenario-reply-name {
  font-weight: 700;
  color: var(--text-secondary);
}
.scenario-reply-dot {
  margin: 0 6px;
  opacity: 0.45;
}
.scenario-reply-tag {
  font-size: 11px;
  letter-spacing: 0.02em;
}

.scenario-reply-body {
  margin: 0;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text-primary);
  white-space: pre-wrap;
}

.submit-success-overlay {
  position: fixed;
  inset: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(8px);
}

.submit-success-card {
  position: relative;
  text-align: center;
  padding: 40px 48px 36px;
  border-radius: 24px;
  background: var(--bg-card);
  box-shadow:
    0 24px 80px rgba(15, 23, 42, 0.2),
    0 0 0 1px rgba(255, 255, 255, 0.08) inset;
  animation: success-card-in 0.55s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.submit-success-ring {
  position: absolute;
  left: 50%;
  top: 44px;
  width: 88px;
  height: 88px;
  margin-left: -44px;
  margin-top: -44px;
  border-radius: 50%;
  border: 3px solid rgba(16, 185, 129, 0.35);
  animation: success-ring-pulse 1.4s ease-out 0.2s both;
  pointer-events: none;
}

.submit-success-icon {
  color: #10b981;
  margin-bottom: 12px;
  animation: success-icon-pop 0.6s cubic-bezier(0.22, 1, 0.36, 1) 0.15s both;
}

.submit-success-title {
  margin: 0 0 8px 0;
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
}

.submit-success-desc {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted);
  line-height: 1.5;
}

.success-pop-enter-active,
.success-pop-leave-active {
  transition: opacity 0.35s ease;
}
.success-pop-enter-active .submit-success-card,
.success-pop-leave-active .submit-success-card {
  transition:
    transform 0.35s cubic-bezier(0.22, 1, 0.36, 1),
    opacity 0.35s ease;
}
.success-pop-enter-from,
.success-pop-leave-to {
  opacity: 0;
}
.success-pop-enter-from .submit-success-card,
.success-pop-leave-to .submit-success-card {
  opacity: 0;
  transform: scale(0.92) translateY(12px);
}

@keyframes success-card-in {
  from {
    opacity: 0;
    transform: translateY(20px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes success-icon-pop {
  from {
    opacity: 0;
    transform: scale(0.2);
  }
  70% {
    transform: scale(1.08);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

@keyframes success-ring-pulse {
  from {
    opacity: 0.9;
    transform: scale(0.75);
  }
  to {
    opacity: 0;
    transform: scale(1.45);
  }
}

.demo-caret {
  display: inline-block;
  width: 7px;
  height: 1em;
  margin-left: 1px;
  vertical-align: -2px;
  border-radius: 1px;
  background: var(--primary);
  animation: caret-blink 0.9s step-end infinite;
}

.demo-caret--dim {
  background: var(--text-muted);
  opacity: 0.65;
}

@keyframes caret-blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}

.capability-row {
  margin-top: 10px;
  text-align: center;
}

.capability-toggle {
  font-weight: 650;
}

.cap-panel-enter-active,
.cap-panel-leave-active {
  transition:
    opacity 0.3s ease,
    transform 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}
.cap-panel-enter-from,
.cap-panel-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.capability-panel {
  margin-top: 8px;
  width: 100%;
  max-width: 760px;
  border-radius: 14px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: var(--bg-card, #fff);
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  padding: 12px 14px;
}

.capability-panel-inner {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cap-role {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  align-self: flex-start;
  padding: 2px 8px;
  border-radius: 6px;
}

.cap-role--u {
  color: #4f46e5;
  background: rgba(79, 70, 229, 0.12);
}

.cap-role--a {
  color: #0d9488;
  background: rgba(13, 148, 136, 0.14);
}

.cap-typing {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--text-primary);
  min-height: 2.8em;
}

.insight-section {
  width: 100%;
  max-width: 100%;
  margin-top: 28px;
  padding: 0 4px 8px;
  transition: opacity 0.35s ease, filter 0.35s ease;
}
.insight-section--dim {
  opacity: 0.4;
  filter: saturate(0.8);
  pointer-events: none;
}
.insight-head {
  margin-bottom: 10px;
  max-width: 760px;
  margin-left: auto;
  margin-right: auto;
}
.insight-title {
  font-weight: 750;
  font-size: 14px;
  display: block;
  margin-bottom: 4px;
  color: var(--text-secondary);
}
.insight-sub {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.45;
}

.insight-chips {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  max-width: 760px;
  margin: 0 auto;
  padding: 4px 2px 6px;
}
.insight-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 13px 7px 11px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  background: var(--bg-card, #fff);
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 999px;
  cursor: pointer;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05);
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.15s ease;
}
.insight-chip:hover:not(:disabled) {
  border-color: rgba(99, 102, 241, 0.45);
  box-shadow: 0 4px 14px rgba(79, 70, 229, 0.12);
  transform: translateY(-1px);
}
.insight-chip:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.insight-chip--minor {
  font-size: 12px;
  font-weight: 600;
  padding: 6px 12px;
  color: var(--text-secondary);
  background: rgba(15, 23, 42, 0.03);
  border-color: rgba(15, 23, 42, 0.08);
}
.insight-chip--minor:hover:not(:disabled) {
  border-color: rgba(245, 158, 11, 0.45);
  box-shadow: 0 2px 10px rgba(245, 158, 11, 0.12);
}
.insight-chip-ico {
  flex-shrink: 0;
  color: var(--text-muted);
}
.insight-chip-text {
  white-space: nowrap;
}
.insight-chip--in {
  opacity: 0;
  animation: chip-in 0.45s cubic-bezier(0.22, 1, 0.36, 1) forwards;
}
@keyframes chip-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.result-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}

.workspace {
  padding: 8px 0 32px;
  max-width: 960px;
  margin: 0 auto;
}

.think-panel {
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: var(--bg-card, #fff);
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
  margin-bottom: 16px;
}
.think-stream {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 12px;
  min-height: 1.4em;
  line-height: 1.45;
}
.think-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
  font-size: 15px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.think-time-counter {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  color: #475569;
}
.spin {
  animation: spin 1.1s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.think-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.think-step {
  padding: 10px 0 10px 2px;
  border-bottom: 1px dashed rgba(15, 23, 42, 0.08);
  opacity: 0.62;
  transform: translateY(4px);
  transition: all 0.28s ease;
}
.think-step:last-child {
  border-bottom: none;
}
.think-step-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.think-step-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}
.think-step-title {
  font-size: 13px;
  font-weight: 700;
  color: #334155;
}
.think-step-sub,
.think-step-detail {
  margin: 4px 0 0 24px;
  font-size: 12px;
  line-height: 1.45;
  color: #64748b;
}
.think-step-detail {
  margin-top: 2px;
}
.think-step.is-active,
.think-step.is-done {
  opacity: 1;
  transform: translateY(0);
}
.think-step.is-active .think-step-title {
  color: #1d4ed8;
}
.think-step.is-done .think-step-title {
  color: #0f766e;
}
.loading {
  color: #2563eb;
  animation: spin 0.95s linear infinite;
}
.chk {
  color: var(--el-color-success);
}
.idle-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #cbd5e1;
}
.think-step-enter-active {
  transition: all 0.34s ease;
}
.think-step-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

.linkage-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 14px;
  padding: 0 2px;
  border-radius: 0;
  background: transparent;
  border: none;
}
.dot-sep {
  opacity: 0.45;
}
.linkage-ok {
  margin-left: auto;
  color: #059669;
  font-weight: 700;
}

.sheet-panel {
  border-radius: 18px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: var(--bg-card, #fff);
  padding: 20px 22px 18px;
  box-shadow: 0 8px 28px rgba(15, 23, 42, 0.07);
}
.sheet-panel.abnormal {
  border-color: rgba(239, 68, 68, 0.35);
  background: var(--bg-card, #fff);
  box-shadow: 0 8px 28px rgba(239, 68, 68, 0.08);
}
.abn-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
  color: #dc2626;
  margin-bottom: 10px;
}
.abn-text {
  margin: 0 0 16px 0;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}

.sheet-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  align-items: flex-start;
}
.sheet-title {
  margin: 0 0 8px 0;
  font-size: 21px;
  font-weight: 800;
  letter-spacing: -0.02em;
}
.sheet-note {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.55;
  white-space: pre-wrap;
  max-width: 640px;
}
.sheet-trace {
  margin-top: 8px;
}
.sheet-trace-panel {
  margin-top: 6px;
  border-radius: 10px;
  border: 1px solid rgba(59, 130, 246, 0.18);
  background: rgba(239, 246, 255, 0.45);
  padding: 8px 10px;
  max-width: 700px;
}
.sheet-trace-step + .sheet-trace-step {
  margin-top: 7px;
  padding-top: 7px;
  border-top: 1px dashed rgba(15, 23, 42, 0.1);
}
.sheet-trace-title {
  margin: 0;
  font-size: 12px;
  font-weight: 700;
  color: #1d4ed8;
}
.sheet-trace-line {
  margin: 2px 0 0;
  font-size: 12px;
  color: #475569;
  line-height: 1.4;
}
.fade-up-enter-active,
.fade-up-leave-active {
  transition: all 0.22s ease;
}
.fade-up-enter-from,
.fade-up-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
.sheet-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
  color: #059669;
  padding: 6px 10px;
  border-radius: 999px;
  background: rgba(16, 185, 129, 0.1);
  border: 1px solid rgba(16, 185, 129, 0.2);
}
.sheet-badge--muted {
  color: #64748b;
  background: rgba(100, 116, 139, 0.12);
  border-color: rgba(100, 116, 139, 0.2);
}
.live-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.25);
  animation: pulse 1.6s ease-in-out infinite;
}
@keyframes pulse {
  50% {
    opacity: 0.65;
    transform: scale(0.92);
  }
}

.sheet-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(268px, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.sku-card {
  display: flex;
  gap: 12px;
  padding: 14px;
  border-radius: 14px;
  background: var(--bg-elevated);
  border: 1px solid var(--border-subtle);
}
.sku-card--readonly {
  opacity: 0.92;
}
.sku-emoji {
  width: 56px;
  height: 56px;
  border-radius: 12px;
  background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  flex-shrink: 0;
}
.sku-photo {
  display: none;
}
.sku-name {
  font-weight: 600;
  font-size: 15px;
  margin-bottom: 6px;
}
.stock-pill {
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 6px;
  font-weight: 600;
  &.ok {
    background: #d1fae5;
    color: #047857;
  }
  &.low {
    background: #fef9c3;
    color: #a16207;
  }
  &.sub {
    background: #e0e7ff;
    color: #4338ca;
  }
}
.subst-note {
  margin: 8px 0 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: #92400e;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(251, 191, 36, 0.15);
  border: 1px dashed rgba(245, 158, 11, 0.45);
}
.qty-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.qty-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-right: 4px;
}
.qty-val {
  min-width: 28px;
  text-align: center;
  font-weight: 700;
  font-size: 15px;
}
.unit {
  font-size: 12px;
  color: var(--text-muted);
}
.unit-price {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: auto;
}

.sheet-footer {
  border-top: 1px solid var(--border-subtle);
  padding-top: 16px;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 16px;
  justify-content: space-between;
}
.sheet-footer--readonly {
  align-items: center;
}
.readonly-hint {
  margin-left: auto;
  font-size: 12px;
  color: #64748b;
}
.footer-left {
  flex: 1;
  min-width: 240px;
}
.estimate-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
}
.estimate-label {
  font-size: 13px;
  color: var(--text-muted);
}
.estimate-val {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  letter-spacing: -0.02em;
}
.recv-form {
  flex: 1;
  min-width: 240px;
}
.recv-form--row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 28px;
  align-items: flex-end;
}
.recv-input {
  width: 200px;
  max-width: 100%;
}
.recv-input-wide {
  width: 260px;
  max-width: 100%;
}
.confirm-btn {
  min-width: 220px;
  font-weight: 800;
  font-size: 15px;
  border-radius: 14px;
  padding: 22px 28px;
  box-shadow: 0 8px 28px rgba(79, 70, 229, 0.35);
}
.full-btn {
  width: 100%;
  margin-top: 8px;
}

.empty-hint {
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
  padding: 32px 12px;
}

.panel-rise-enter-active {
  transition: all 0.45s cubic-bezier(0.22, 1, 0.36, 1);
}
.panel-rise-enter-from {
  opacity: 0;
  transform: translateY(24px);
}

.dock {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 16px;
  width: calc(100% - 32px);
  max-width: 1120px;
  z-index: 30;
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px 20px;
  padding: 12px 16px;
  border-radius: 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  box-shadow: 0 12px 48px rgba(15, 23, 42, 0.12);
}
.dock--compact {
  padding: 10px 14px;
}
.dock-bundles {
  flex: 1;
  min-width: 200px;
}
.dock-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 700;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 8px;
}
.dock-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.dock-bundle-btn {
  border: 1px solid var(--border-subtle);
  background: var(--bg-elevated);
  font-size: 12px;
  font-weight: 600;
  padding: 8px 14px;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.15s ease;
  &:hover:not(:disabled) {
    border-color: rgba(99, 102, 241, 0.45);
    color: var(--primary);
  }
  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}
.dock-track {
  flex: 1;
  min-width: 260px;
  max-width: 400px;
  padding: 8px 12px;
  border-radius: 12px;
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.12);
}
.dock-track-head {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.mono {
  font-family: ui-monospace, monospace;
  font-size: 11px;
  color: var(--primary);
}
.dock-track-msg {
  margin: 0 0 8px 0;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.4;
}
.dock-progress {
  height: 4px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.08);
  overflow: hidden;
  margin-bottom: 6px;
}
.dock-progress-fill {
  height: 100%;
  border-radius: 4px;
  background: linear-gradient(90deg, #6366f1, #22d3ee);
  transition: width 0.4s ease;
}
.dock-steps {
  display: flex;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text-muted);
  span.on {
    color: var(--primary);
    font-weight: 700;
  }
}
.dock-refresh {
  align-self: center;
}

:global(html.dark) .floating-bar {
  border-color: rgba(148, 163, 184, 0.15);
  box-shadow: 0 18px 48px rgba(0, 0, 0, 0.35);
}
:global(html.dark) .composer-zone--top {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.94) 70%, transparent);
}
:global(html.dark) .dock {
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.45);
}
</style>
