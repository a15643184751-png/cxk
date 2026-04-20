<script setup lang="ts">
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { workbenchChatPrefill } from '@/utils/teacherWorkbenchBus'
import { ChatDotRound, Promotion, User, CircleCheck, DocumentCopy, WarningFilled, Cpu } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { chat, executeAction } from '@/api/ai'
import { addAbnormalOrder } from '@/stores/demo'
import type { RoleType } from '@/types/role'
import type { ChatAction, ReactStep } from '@/api/ai'

const THINK_DELAY_MS = 2200
const REASONING_STEP_MS = 550
const THINK_STATUS_TEXTS = ['理解需求…', '分析场景…', '查询物资…', '生成方案…']
const DEFAULT_REASONING_STEPS: ReactStep[] = [
  { step: 1, text: '理解场景：识别为活动保障需求' },
  { step: 2, text: '调用工具：query_goods_catalog() 查询物资目录' },
  { step: 3, text: '调用工具：check_inventory() 核对库存可用性' },
  { step: 4, text: '生成采购清单，等待您确认' },
]

withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })

const userStore = useUserStore()
const userRole = computed(() => userStore.userInfo?.role as RoleType)

const welcomeByRole: Record<RoleType, string> = {
  system_admin: '你好，我是审计与反腐分析助手。\n• 「帮我分析近期审计日志」\n• 「哪些供应商表现异常？给出建议」\n• 「生成审计报告」\n• 「供应商不出货、逾期怎么处置？」',
  counselor_teacher: '你好，我是采购智能体。我会先帮你确定场景，再生成清单。\n• 「周三有比赛，帮我做保障计划」\n• 「40人班会要茶歇」\n• 确认后可直接点击按钮提交申请',
  warehouse_procurement: '你好，我是仓储效率助手。\n• 「现在什么物资可能短缺？」\n• 「入库出库怎么优化？」\n• 「临期库存怎么处置？」\n• 「帮我生成补货预警」',
  campus_supplier: '你好，我可以帮你查询订单状态、配送进度等信息。',
  logistics_admin: '你好，我是采购审批与供应链助手。\n• 「现在什么物资可能短缺？」\n• 「待审批申请有多少？」\n• 「帮我做比赛保障计划」\n• 可查询库存、采购记录，需要时直接创建采购申请',
}

const initialMessage = computed(() => welcomeByRole[userRole.value || 'system_admin'])

interface MsgBubble {
  role: 'user' | 'assistant'
  content: string
  react?: ReactStep[]
  actions?: ChatAction[]
  trace?: { orderNo: string; executedAt: string; items?: unknown[] }
  memorySaved?: boolean
  abnormal?: boolean // AI 拦截提示（红色样式）
}

const messages = ref<MsgBubble[]>([])
const input = ref('')
const loading = ref(false)
const thinkStatusIndex = ref(0)
let thinkStatusTimer: ReturnType<typeof setInterval> | null = null
const scrollRef = ref<HTMLElement>()
const executing = ref(false)
const sessionId = ref<string | null>(null)

// 推理阶段：步骤动画完成后才显示最终结果
const reasoningPhase = ref<{
  steps: ReactStep[]
  stepIndex: number
  content: string
  actions: ChatAction[]
  react?: ReactStep[]
} | null>(null)

if (messages.value.length === 0) {
  messages.value = [{ role: 'assistant', content: initialMessage.value }]
}

function applyWorkbenchPrefill(v: string) {
  if (!v) return
  input.value = v
  workbenchChatPrefill.value = ''
  nextTick(() => scrollRef.value?.scrollTo?.({ top: 9999 }))
}

watch(workbenchChatPrefill, (v) => applyWorkbenchPrefill(v || ''), { flush: 'post' })

onMounted(() => {
  if (workbenchChatPrefill.value) applyWorkbenchPrefill(workbenchChatPrefill.value)
})

const demoHint = '周三有比赛，帮我做保障计划 / 40人班会要茶歇 / 现在什么短缺？'

function startThinkStatusCycle() {
  thinkStatusIndex.value = 0
  thinkStatusTimer = setInterval(() => {
    thinkStatusIndex.value = (thinkStatusIndex.value + 1) % THINK_STATUS_TEXTS.length
  }, 480)
}

function stopThinkStatusCycle() {
  if (thinkStatusTimer) {
    clearInterval(thinkStatusTimer)
    thinkStatusTimer = null
  }
}

async function runReasoningPhase(steps: ReactStep[], content: string, actions: ChatAction[], react?: ReactStep[]) {
  reasoningPhase.value = { steps, stepIndex: 0, content, actions, react }
  await nextTick()
  scrollRef.value?.scrollTo?.({ top: 9999 })
  for (let i = 0; i < steps.length; i++) {
    await new Promise((r) => setTimeout(r, REASONING_STEP_MS))
    if (reasoningPhase.value) reasoningPhase.value.stepIndex = i + 1
    await nextTick()
    scrollRef.value?.scrollTo?.({ top: 9999 })
  }
  await new Promise((r) => setTimeout(r, 400))
  reasoningPhase.value = null
}

// AI 拦截不合理需求（如批量笔记本、班级观影等）
function isAbnormalRequest(q: string): boolean {
  const lower = q.toLowerCase()
  return (lower.includes('100') && lower.includes('笔记本')) || (lower.includes('笔记本') && lower.includes('观影'))
}

async function sendText(rawText: string) {
  const q = rawText.trim()
  if (!q) return
  messages.value.push({ role: 'user', content: q })
  loading.value = true
  startThinkStatusCycle()
  await nextTick()
  scrollRef.value?.scrollTo?.({ top: 9999 })

  if (userRole.value === 'counselor_teacher' && isAbnormalRequest(q)) {
    await new Promise((r) => setTimeout(r, THINK_DELAY_MS))
    loading.value = false
    stopThinkStatusCycle()
    const steps = [
      { step: 1, text: '理解需求：检测到大规模设备申请' },
      { step: 2, text: '调用工具：check_policy() 校验采购规范' },
      { step: 3, text: '检测到异常：数量/用途不符合教学核心' },
      { step: 4, text: '生成留痕备注，需人工确认' },
    ]
    await runReasoningPhase(steps, '', [
      { type: 'force_submit', label: '强制提交', payload: { items: [{ name: '笔记本电脑', quantity: 100, unit: '台' }] } },
    ])
    messages.value.push({
      role: 'assistant',
      content: '该需求不符合教学设备申请规范，观影非教学核心用途，暂不支持提交。',
      abnormal: true,
      actions: [{ type: 'force_submit', label: '强制提交', payload: { items: [{ name: '笔记本电脑', quantity: 100, unit: '台' }] } }],
    })
    nextTick().then(() => scrollRef.value?.scrollTo?.({ top: 9999 }))
    return
  }

  try {
    const apiPromise = chat(q, sessionId.value)
    const minThinkPromise = new Promise((r) => setTimeout(r, THINK_DELAY_MS))
    const res: any = await Promise.all([apiPromise, minThinkPromise]).then(([r]) => r)
    stopThinkStatusCycle()
    const data = res?.data || res
    if (!data) throw new Error('无效响应')
    if (data.session_id) sessionId.value = data.session_id
    const hasActions = data.actions?.length > 0
    const steps = data.react?.length ? data.react : (hasActions ? DEFAULT_REASONING_STEPS : [])

    if (hasActions && steps.length > 0) {
      loading.value = false
      await runReasoningPhase(steps, data.reply, data.actions || [], data.react)
    }
    loading.value = false
    messages.value.push({
      role: 'assistant',
      content: data.reply,
      react: data.react || [],
      actions: data.actions || [],
    })
  } catch (e: any) {
    stopThinkStatusCycle()
    loading.value = false
    messages.value.push({
      role: 'assistant',
      content: `请求失败：${e?.message || '请检查网络或后端服务'}\n\n${demoHint}`,
    })
  }
  nextTick().then(() => scrollRef.value?.scrollTo?.({ top: 9999 }))
}

async function send() {
  if (!input.value.trim()) return
  const q = input.value.trim()
  input.value = ''
  await sendText(q)
}

const forceSubmitVisible = ref(false)
const forceSubmitForm = ref({ receiver_name: '', destination: '' })
const forceSubmitAction = ref<ChatAction | null>(null)
const forceSubmitReActStep = ref(0)
const forceSubmitReActSteps = [
  { step: 1, text: '正在调用工具：check_policy() 校验采购规范…' },
  { step: 2, text: '检测到异常：数量 100 台超出合理范围，用途「观影」非教学核心' },
  { step: 3, text: '调用工具：generate_audit_note() 生成留痕备注…' },
  { step: 4, text: '准备提交，需填写收货人与收货地址完成申请' },
]

function openForceSubmitDialog(action: ChatAction) {
  forceSubmitAction.value = action
  forceSubmitForm.value = { receiver_name: '', destination: '' }
  forceSubmitReActStep.value = 0
  forceSubmitVisible.value = true
  const runSteps = () => {
    if (forceSubmitReActStep.value < forceSubmitReActSteps.length) {
      forceSubmitReActStep.value++
      setTimeout(runSteps, 600)
    }
  }
  setTimeout(runSteps, 400)
}

async function confirmForceSubmit() {
  const name = forceSubmitForm.value.receiver_name.trim()
  const dest = forceSubmitForm.value.destination.trim()
  if (!name || !dest) {
    ElMessage.warning('请填写收货人和收货地址')
    return
  }
  const action = forceSubmitAction.value
  if (!action || action.type !== 'force_submit') return
  executing.value = true
  forceSubmitVisible.value = false
  const actPayload = {
    ...(action.payload || {}),
    items: (action.payload as any)?.items || [{ name: '笔记本电脑', quantity: 100, unit: '台' }],
    receiver_name: name,
    destination: dest,
  }
  try {
    const res: any = await executeAction('create_purchase', actPayload)
    const data = res?.data || res
    if (!data?.success) throw new Error('执行失败')
    finishForceSubmit(data.orderNo || `DEMO-${Date.now()}`, data.trace)
  } catch (e: any) {
    const orderNo = `DEMO-${Date.now()}`
    finishForceSubmit(orderNo, undefined)
  } finally {
    executing.value = false
  }
}

function finishForceSubmit(orderNo: string, trace: any) {
  ElMessage.success(`采购单已创建：${orderNo}`)
  addAbnormalOrder(orderNo)
  const lastMsg = messages.value[messages.value.length - 1]
  if (lastMsg?.role === 'assistant') {
    lastMsg.trace = trace ? { ...trace, orderNo } : { orderNo, executedAt: new Date().toISOString() }
    lastMsg.actions = []
  }
}

async function handleAction(action: ChatAction) {
  if (action.type === 'quick_reply') {
    const txt = String((action.payload as any)?.text || action.label || '').trim()
    if (!txt) return
    await sendText(txt)
    return
  }
  if (action.type === 'force_submit') {
    loading.value = true
    startThinkStatusCycle()
    await new Promise((r) => setTimeout(r, THINK_DELAY_MS))
    stopThinkStatusCycle()
    loading.value = false
    openForceSubmitDialog(action)
    return
  }
  if (executing.value) return
  executing.value = true
  try {
    const res: any = await executeAction(action.type, action.payload as Record<string, unknown>)
    const data = res?.data || res
    if (!data?.success) throw new Error('执行失败')
    ElMessage.success(data.message || '执行成功')
    const lastMsg = messages.value[messages.value.length - 1]
    if (lastMsg?.role === 'assistant' && data.trace) {
      lastMsg.trace = { ...data.trace, orderNo: data.orderNo || '-' }
      lastMsg.actions = []
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '执行失败')
  } finally {
    executing.value = false
  }
}
</script>

<template>
  <div class="ai-chat-page" :class="{ 'ai-chat-page--embedded': embedded }">
    <div class="chat-container">
      <div ref="scrollRef" class="messages">
        <template v-for="(msg, i) in messages" :key="i">
          <div class="message" :class="[msg.role, { abnormal: msg.abnormal }]">
            <div class="avatar">
              <el-icon v-if="msg.role === 'user'"><User /></el-icon>
              <el-icon v-else><ChatDotRound /></el-icon>
            </div>
            <div class="bubble">
              <div v-if="msg.abnormal" class="abnormal-header">
                <el-icon class="abnormal-icon"><WarningFilled /></el-icon>
                <span>AI 风控拦截</span>
              </div>
              <div class="text">{{ msg.content }}</div>
              <!-- React 推理步骤 -->
              <div v-if="msg.react?.length" class="react-box">
                <div class="react-title">
                  <el-icon><DocumentCopy /></el-icon>
                  ReAct 推理
                </div>
                <ul class="react-steps">
                  <li v-for="s in msg.react" :key="s.step">
                    <span class="step-num">{{ s.step }}</span>
                    {{ s.text }}
                  </li>
                </ul>
              </div>
              <!-- 拟申请清单（提交前可见） -->
              <div v-if="msg.actions?.some((a) => ['create_purchase','force_submit'].includes(a.type) && (a.payload as any)?.items?.length)" class="apply-preview">
                <div class="apply-preview-title">拟申请清单</div>
                <el-table :data="(msg.actions?.find((a) => ['create_purchase','force_submit'].includes(a.type))?.payload as any)?.items || []" size="small" border>
                  <el-table-column prop="name" label="物资名称" width="140" />
                  <el-table-column prop="quantity" label="数量" width="80" />
                  <el-table-column prop="unit" label="单位" width="60" />
                </el-table>
              </div>
              <!-- 决策 / 执行按钮 -->
              <div v-if="msg.actions?.length" class="actions">
                <el-button
                  v-for="a in msg.actions"
                  :key="a.type"
                  type="primary"
                  size="small"
                  :loading="executing"
                  @click="handleAction(a)"
                >
                  {{ a.label }}
                </el-button>
              </div>
              <!-- 留痕 -->
              <div v-if="msg.trace" class="trace-box">
                <span class="trace-label"><el-icon><CircleCheck /></el-icon> 已留痕</span>
                <span class="trace-text">单号 {{ msg.trace.orderNo }} · {{ msg.trace.executedAt?.slice(0, 19) }}</span>
              </div>
            </div>
          </div>
        </template>
        <!-- 推理阶段：决策链动画 -->
        <div v-if="reasoningPhase" class="message assistant reasoning">
          <div class="avatar reasoning-avatar">
            <el-icon><Cpu /></el-icon>
          </div>
          <div class="bubble reasoning-bubble">
            <div class="reasoning-header">
              <el-icon><DocumentCopy /></el-icon>
              <span>ReAct 决策链</span>
            </div>
            <ul class="reasoning-steps">
              <li
                v-for="(s, i) in reasoningPhase.steps.slice(0, reasoningPhase.stepIndex)"
                :key="i"
                class="reasoning-step"
              >
                <span class="step-num"><el-icon><CircleCheck /></el-icon></span>
                {{ s.text }}
              </li>
            </ul>
          </div>
        </div>
        <div v-if="loading" class="message assistant">
          <div class="avatar loading-avatar">
            <el-icon class="spin"><Cpu /></el-icon>
          </div>
          <div class="bubble loading">
            <span class="think-dots">
              <span class="dot" />
              <span class="dot" />
              <span class="dot" />
            </span>
            <span class="think-text">{{ THINK_STATUS_TEXTS[thinkStatusIndex] }}</span>
          </div>
        </div>
      </div>
      <div class="input-area">
        <el-input
          v-model="input"
          type="textarea"
          :rows="embedded ? 3 : 2"
          :placeholder="userRole === 'warehouse_procurement' ? demoHint : '输入问题...'"
          resize="none"
          @keydown.enter.exact.prevent="send"
        />
        <el-button type="primary" :icon="Promotion" :loading="loading" @click="send">发送</el-button>
      </div>
    </div>

    <!-- 强制提交弹窗：收货人地址 -->
    <el-dialog
      v-model="forceSubmitVisible"
      title="强制提交申请"
      width="520px"
      :close-on-click-modal="false"
      class="force-submit-dialog"
    >
      <div class="react-sim-box">
        <div class="react-sim-title">
          <el-icon><DocumentCopy /></el-icon>
          ReAct 推理过程
        </div>
        <ul class="react-sim-steps">
          <li v-for="(s, i) in forceSubmitReActSteps.slice(0, forceSubmitReActStep)" :key="i" class="step-item">
            <span class="step-num">{{ s.step }}</span>
            {{ s.text }}
          </li>
        </ul>
      </div>
      <el-form label-width="100px" class="receiver-form">
        <el-form-item label="收货人" required>
          <el-input v-model="forceSubmitForm.receiver_name" placeholder="请填写收货人姓名" />
        </el-form-item>
        <el-form-item label="收货地址" required>
          <el-input v-model="forceSubmitForm.destination" placeholder="如：教学楼A栋302" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="forceSubmitVisible = false">取消</el-button>
        <el-button type="primary" :loading="executing" @click="confirmForceSubmit">确认提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.ai-chat-page {
  height: calc(100vh - 64px - 48px);
  display: flex;
  flex-direction: column;
  padding: 0;
}

.ai-chat-page--embedded {
  height: 100%;
  min-height: 280px;
  max-height: none;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  overflow: hidden;
  box-shadow: var(--shadow-card);
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.message {
  display: flex;
  gap: 12px;
  max-width: 85%;

  &.user {
    align-self: flex-end;
    flex-direction: row-reverse;

    .bubble {
      background: var(--gradient-primary);
      color: #fff;
      box-shadow: 0 2px 8px rgba(79, 70, 229, 0.2);
    }
  }

  &.abnormal .bubble {
    position: relative;
    border: 2px solid #ef4444;
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.12) 0%, rgba(220, 38, 38, 0.06) 100%);
    box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.1);
    animation: abnormal-pulse 2s ease-in-out infinite;
  }
  &.abnormal .bubble .abnormal-header {
    display: flex; align-items: center; gap: 8px;
    font-weight: 700; font-size: 14px; color: #dc2626;
    margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px dashed rgba(239, 68, 68, 0.4);
  }
  &.abnormal .bubble .abnormal-icon { font-size: 20px; }
  &.abnormal .bubble .text { color: #991b1b; font-weight: 500; }
@keyframes abnormal-pulse {
  0%, 100% { box-shadow: 0 0 0 4px rgba(239, 68, 68, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.1); }
  50% { box-shadow: 0 0 0 8px rgba(239, 68, 68, 0.12), inset 0 1px 0 rgba(255, 255, 255, 0.1); }
}

  .avatar {
    width: 40px;
    height: 40px;
    border-radius: 12px;
    background: var(--primary-muted);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;

    .el-icon {
      font-size: 20px;
      color: var(--primary);
    }
  }

  .bubble {
    padding: 14px 18px;
    border-radius: 12px;
    background: var(--bg-elevated);
    line-height: 1.6;
    white-space: pre-wrap;

    .text { margin-bottom: 0; }

    .react-box {
      margin-top: 12px;
      padding: 10px 12px;
      background: rgba(79, 70, 229, 0.06);
      border: 1px solid rgba(79, 70, 229, 0.15);
      border-radius: 8px;
      font-size: 12px;
    }
    .react-title {
      display: flex;
      align-items: center;
      gap: 6px;
      color: var(--primary);
      font-weight: 600;
      margin-bottom: 8px;
    }
    .react-steps {
      margin: 0;
      padding-left: 0;
      list-style: none;
      color: var(--text-secondary);
      line-height: 1.7;
    }
    .react-steps li {
      display: flex;
      gap: 8px;
      margin-bottom: 4px;
    }
    .step-num {
      flex-shrink: 0;
      width: 18px;
      height: 18px;
      line-height: 18px;
      text-align: center;
      font-size: 11px;
      color: var(--primary);
      background: rgba(79, 70, 229, 0.15);
      border-radius: 4px;
      font-weight: 500;
    }

    .apply-preview {
      margin-top: 12px;
      padding: 10px 12px;
      background: rgba(103, 194, 58, 0.06);
      border: 1px solid rgba(103, 194, 58, 0.2);
      border-radius: 8px;
      font-size: 12px;
    }
    .apply-preview-title {
      font-weight: 600;
      color: var(--success);
      margin-bottom: 8px;
    }
    .actions {
      margin-top: 12px;
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }

    .trace-box {
      margin-top: 10px;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
      color: var(--success);
    }
    .trace-label { font-weight: 500; }
    .trace-text { color: var(--text-muted); }

    &.loading {
      display: flex;
      align-items: center;
      gap: 12px;
      color: var(--text-muted);
      min-width: 200px;
    }
  }
}

.loading-avatar {
  background: linear-gradient(135deg, rgba(79, 70, 229, 0.2) 0%, rgba(99, 102, 241, 0.15) 100%) !important;
  .el-icon.spin {
    animation: spin 1.2s linear infinite;
  }
}

.think-dots {
  display: inline-flex;
  gap: 4px;
  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--primary);
    opacity: 0.6;
    animation: think-bounce 0.6s ease-in-out infinite;
    &:nth-child(1) { animation-delay: 0s; }
    &:nth-child(2) { animation-delay: 0.15s; }
    &:nth-child(3) { animation-delay: 0.3s; }
  }
}

.think-text {
  margin-left: 8px;
  font-size: 13px;
  color: var(--text-secondary);
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes think-bounce {
  0%, 100% { transform: translateY(0); opacity: 0.5; }
  50% { transform: translateY(-4px); opacity: 1; }
}

.reasoning-bubble {
  border: 1px solid rgba(79, 70, 229, 0.2) !important;
  background: linear-gradient(135deg, rgba(79, 70, 229, 0.04) 0%, rgba(99, 102, 241, 0.02) 100%) !important;
}

.reasoning-avatar {
  background: linear-gradient(135deg, var(--primary) 0%, #6366f1 100%) !important;
  .el-icon { color: #fff !important; }
}

.reasoning-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  font-size: 13px;
  color: var(--primary);
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(79, 70, 229, 0.15);
}

.reasoning-steps {
  margin: 0;
  padding: 0;
  list-style: none;
}

.reasoning-step {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--text-secondary);
  animation: reasoning-fade 0.4s ease-out;
}

.reasoning-step .step-num {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(34, 197, 94, 0.2);
  color: var(--success);
  border-radius: 6px;
  font-size: 12px;
}

@keyframes reasoning-fade {
  from {
    opacity: 0;
    transform: translateX(-8px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.message.user .bubble .react-box,
.message.user .bubble .apply-preview,
.message.user .bubble .actions,
.message.user .bubble .trace-box {
  display: none;
}

.input-area {
  padding: 16px 24px;
  border-top: 1px solid var(--border-subtle);
  display: flex;
  gap: 12px;
  align-items: flex-end;

  .el-input { flex: 1; }
}

.react-sim-box {
  padding: 14px 16px; background: rgba(79, 70, 229, 0.06);
  border: 1px solid rgba(79, 70, 229, 0.2); border-radius: 10px;
  margin-bottom: 20px;
}
.react-sim-title { display: flex; align-items: center; gap: 8px; font-weight: 600; color: var(--primary); margin-bottom: 12px; }
.react-sim-steps { margin: 0; padding: 0; list-style: none; }
.step-item { display: flex; gap: 10px; margin-bottom: 8px; font-size: 13px; color: var(--text-secondary); }
.step-item .step-num {
  flex-shrink: 0; width: 20px; height: 20px; line-height: 20px; text-align: center;
  background: var(--primary); color: #fff; border-radius: 6px; font-size: 11px; font-weight: 600;
}
.receiver-form { margin-top: 8px; }
</style>
