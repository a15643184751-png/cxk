<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, Loading } from '@element-plus/icons-vue'
import {
  listPurchases,
  approvePurchaseWithEvidence,
  rejectPurchaseWithEvidence,
  runPurchaseAiJudgment,
} from '@/api/purchase'
import { listInventory, type InventoryItem } from '@/api/stock'
import { isAbnormalOrder, setApprovalAlert, addMisapprovalRecord } from '@/stores/demo'
import type { Purchase } from '@/api/purchase'

const loading = ref(false)
const aiAnalysisDialogVisible = ref(false)
const aiAnalysisLoading = ref(false)
/** 当前正在进行 AI 分析的行 id（用于按钮 loading） */
const aiAnalysisBusyId = ref<number | null>(null)
const approvalDialogVisible = ref(false)
const approvalAction = ref<'approve' | 'reject'>('approve')
const approvalRow = ref<Purchase | null>(null)
const approvalReasonOption = ref('')
const approvalOpinion = ref('')
const approvalSignatureMode = ref<'draw' | 'stamp'>('draw')
const selectedStamp = ref('')
const signatureTimestamp = ref('')
/** 仅用于「AI 分析」弹窗展示 */
const analysisReport = ref<{
  recommendation: 'pass' | 'cautious' | 'reject'
  recommendation_label: string
  score: number
  summary: string
  dimensions: Record<string, { result: string; note: string }>
} | null>(null)
const signatureCanvasRef = ref<HTMLCanvasElement | null>(null)
const drawing = ref(false)
const hasDrawnSignature = ref(false)
const tableData = ref<Purchase[]>([])
const statusFilter = ref<string>('')

const invLoading = ref(false)
const invSummary = ref<{ goods_name: string; quantity: number; unit: string; low: boolean }[]>([])

const dimLabels: Record<string, string> = {
  inventory: '库存',
  budget: '预算',
  price: '历史价格',
  compliance: '类型合规',
  supplier: '供应商风险',
}

function dimResultText(r?: string) {
  if (r === 'good') return '正常'
  if (r === 'risk') return '关注'
  return '异常'
}

function buildInventorySummary(rows: InventoryItem[]) {
  const map = new Map<string, { quantity: number; unit: string; low: boolean }>()
  for (const r of rows) {
    const cur = map.get(r.goods_name) || { quantity: 0, unit: r.unit || '件', low: false }
    cur.quantity += Number(r.quantity || 0)
    cur.unit = r.unit || cur.unit
    cur.low = cur.low || r.is_low_stock
    map.set(r.goods_name, cur)
  }
  const all = [...map.entries()].map(([goods_name, v]) => ({ goods_name, ...v }))
  const prefer = ['消毒酒精', '薯片', '玻片']
  const out: { goods_name: string; quantity: number; unit: string; low: boolean }[] = []
  for (const n of prefer) {
    const f = all.find((a) => a.goods_name === n)
    if (f) out.push(f)
  }
  const rest = all.filter((a) => !out.some((o) => o.goods_name === a.goods_name))
  rest.sort((a, b) => a.quantity - b.quantity)
  while (out.length < 4 && rest.length) {
    out.push(rest.shift()!)
  }
  return out
}

async function fetchInventorySummary() {
  invLoading.value = true
  try {
    const res: any = await listInventory()
    const rows: InventoryItem[] = Array.isArray(res) ? res : res?.data ?? []
    invSummary.value = buildInventorySummary(rows)
  } catch {
    invSummary.value = []
  } finally {
    invLoading.value = false
  }
}

const statusLabels: Record<string, string> = {
  pending: '待审批',
  approved: '待供应商接单',
  confirmed: '待供应商发货',
  shipped: '待仓储入库',
  stocked_in: '待按申请出库',
  stocked_out: '待创建配送',
  delivering: '配送中待签收',
  rejected: '已驳回',
  completed: '已签收完成',
}
const statusTypes: Record<string, string> = {
  pending: 'warning',
  approved: 'primary',
  confirmed: 'warning',
  shipped: 'primary',
  stocked_in: 'success',
  stocked_out: 'success',
  delivering: 'warning',
  rejected: 'danger',
  completed: 'success',
}

async function fetchData() {
  loading.value = true
  try {
    const res: any = await listPurchases(statusFilter.value ? { status: statusFilter.value } : undefined)
    tableData.value = Array.isArray(res) ? res : res?.data ?? []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

async function refreshPurchasePage() {
  await fetchData()
  await fetchInventorySummary()
}

const approvalReasonOptions = [
  '库存充足且流程合规，同意通过',
  '预算接近上限，谨慎通过并建议后续复核',
  '价格偏高，需后续议价与比价证明',
  '数量超出合理范围，不符合采购规范',
  '用途非教学核心，暂不支持',
  '供应商风险较高，建议更换后重提',
  '预算不足，需重新评估',
]

function getGoodsSummary(row: Purchase): string {
  return row.goods_summary || (row.items || []).map((i: any) => `${i.goods_name}${i.quantity}${i.unit}`).join('、')
}

function handleStartPurchase() {
  ElMessage.success('已发起采购申请')
}

function nowTimestamp() {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function minDelay(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

/** 先点「AI 分析」生成报告后，才允许进入审批签名 */
async function openAiAnalysis(row: Purchase) {
  analysisReport.value = null
  aiAnalysisBusyId.value = row.id
  aiAnalysisLoading.value = true
  aiAnalysisDialogVisible.value = true
  try {
    const [res] = await Promise.all([runPurchaseAiJudgment(row.id), minDelay(900)])
    const result: any = (res as any)?.data ?? res
    row.ai_judgment = result?.recommendation || ''
    row.ai_judgment_score = result?.score ?? 0
    row.ai_judgment_summary = result?.summary || ''
    row.ai_judgment_at = new Date().toISOString()
    analysisReport.value = result
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || 'AI 分析失败')
    aiAnalysisDialogVisible.value = false
  } finally {
    aiAnalysisLoading.value = false
    aiAnalysisBusyId.value = null
  }
}

function openApprovalDialog(row: Purchase, action: 'approve' | 'reject') {
  if (!row.ai_judgment_at) {
    ElMessage.warning('请先点击「AI 分析」查看合规报告后，再进行通过或驳回')
    return
  }
  approvalRow.value = row
  approvalAction.value = action
  approvalReasonOption.value = action === 'approve' ? approvalReasonOptions[0] : approvalReasonOptions[3]
  approvalOpinion.value = ''
  approvalSignatureMode.value = 'draw'
  selectedStamp.value = ''
  signatureTimestamp.value = nowTimestamp()
  approvalDialogVisible.value = true
  void nextTick(() => resetSignaturePad())
}

function resetSignaturePad() {
  const canvas = signatureCanvasRef.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  ctx.clearRect(0, 0, canvas.width, canvas.height)
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.strokeStyle = '#111827'
  ctx.lineWidth = 2
  ctx.lineCap = 'round'
  hasDrawnSignature.value = false
}

function getCanvasPoint(e: MouseEvent | TouchEvent) {
  const canvas = signatureCanvasRef.value
  if (!canvas) return { x: 0, y: 0 }
  const rect = canvas.getBoundingClientRect()
  if ('touches' in e && e.touches.length) {
    return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top }
  }
  const me = e as MouseEvent
  return { x: me.clientX - rect.left, y: me.clientY - rect.top }
}

function startDraw(e: MouseEvent | TouchEvent) {
  if (approvalSignatureMode.value !== 'draw') return
  const canvas = signatureCanvasRef.value
  const ctx = canvas?.getContext('2d')
  if (!canvas || !ctx) return
  const p = getCanvasPoint(e)
  drawing.value = true
  ctx.beginPath()
  ctx.moveTo(p.x, p.y)
}

function drawMove(e: MouseEvent | TouchEvent) {
  if (!drawing.value || approvalSignatureMode.value !== 'draw') return
  const ctx = signatureCanvasRef.value?.getContext('2d')
  if (!ctx) return
  const p = getCanvasPoint(e)
  ctx.lineTo(p.x, p.y)
  ctx.stroke()
  hasDrawnSignature.value = true
}

function stopDraw() {
  drawing.value = false
}

const signatureReady = computed(() => {
  if (approvalSignatureMode.value === 'stamp') return !!selectedStamp.value
  return hasDrawnSignature.value
})

const canSubmitApproval = computed(
  () => approvalDialogVisible.value && !!approvalRow.value?.ai_judgment_at && signatureReady.value
)

function getSignatureData() {
  if (approvalSignatureMode.value === 'stamp') return `STAMP:${selectedStamp.value}`
  return signatureCanvasRef.value?.toDataURL('image/png') || ''
}

async function submitApproval() {
  const row = approvalRow.value
  if (!row?.ai_judgment_at) return
  if (!signatureReady.value) {
    ElMessage.warning('请先完成签名或选择电子签章')
    return
  }
  const opinion = (approvalOpinion.value || '').trim() || approvalReasonOption.value
  const payload = {
    reason_option: approvalReasonOption.value,
    opinion,
    signature_mode: approvalSignatureMode.value,
    signature_data: getSignatureData(),
    ai_recommendation: row.ai_judgment || '',
    ai_score: row.ai_judgment_score || 0,
  }
  try {
    if (approvalAction.value === 'approve') {
      const res: any = await approvePurchaseWithEvidence(row.id, payload)
      const result = res?.data ?? res
      ElMessage.success(result?.message || '审批通过')
      if (isAbnormalOrder(row.order_no, getGoodsSummary(row))) {
        setApprovalAlert(row.order_no, '审批了 AI 标记异常的申请', row.id, {
          applicantName: row.applicant_name,
          applicantCollege: row.destination || row.material_type || '—',
          createdAt: row.created_at || undefined,
          goodsSummary: getGoodsSummary(row),
        })
        addMisapprovalRecord({
          orderNo: row.order_no,
          applicantName: row.applicant_name,
          goodsSummary: getGoodsSummary(row),
          operatorName: '后勤管理员',
          operatorRole: 'logistics_admin',
          firstConfirmAt: row.ai_judgment_at || new Date().toISOString(),
          secondConfirmAt: new Date().toISOString(),
          decisionTimeMs: 2000,
          estimatedLoss: '系统自动记录',
          intentProbability: '系统自动研判',
          report: `审批意见：${opinion}；AI建议：${row.ai_judgment}(${row.ai_judgment_score})；签名时间：${signatureTimestamp.value}`,
        })
      }
    } else {
      await rejectPurchaseWithEvidence(row.id, { ...payload, reason: opinion })
      ElMessage.success('已驳回')
    }
    approvalDialogVisible.value = false
    await refreshPurchasePage()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '审批提交失败')
  }
}

function onApprovalDialogClosed() {
  approvalRow.value = null
}

function onAiAnalysisDialogClosed() {
  analysisReport.value = null
}

onMounted(async () => {
  await refreshPurchasePage()
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h2>审批台</h2>
        <p class="page-desc">请先点击「AI 分析」查看合规报告；再通过或驳回进入审批留痕（理由与电子签名）。</p>
      </div>
      <el-button type="primary" @click="handleStartPurchase">发起采购</el-button>
    </div>
    <div v-if="invSummary.length || invLoading" v-loading="invLoading" class="inventory-box">
      <span class="inv-title">库存联动（实时）：</span>
      <template v-if="!invLoading && invSummary.length">
        <span
          v-for="(it, i) in invSummary"
          :key="i"
          class="inv-item"
          :class="it.low ? 'fail' : 'ok'"
        >
          {{ it.goods_name }}：{{ it.quantity }}{{ it.unit }}（{{ it.low ? '偏低' : '正常' }}）
        </span>
      </template>
      <span v-else-if="!invLoading" class="inv-muted">暂无库存数据</span>
    </div>
    <div class="filter-bar">
      <el-radio-group v-model="statusFilter" @change="refreshPurchasePage">
        <el-radio-button label="">全部</el-radio-button>
        <el-radio-button label="pending">待审批</el-radio-button>
        <el-radio-button label="approved">待接单</el-radio-button>
        <el-radio-button label="confirmed">待发货</el-radio-button>
        <el-radio-button label="shipped">待入库</el-radio-button>
        <el-radio-button label="delivering">配送中</el-radio-button>
        <el-radio-button label="completed">已闭环</el-radio-button>
        <el-radio-button label="rejected">已驳回</el-radio-button>
      </el-radio-group>
    </div>
    <div class="table-card">
      <el-table :data="tableData" v-loading="loading" style="width: 100%">
        <el-table-column prop="order_no" label="单号" width="200">
          <template #default="{ row }">
            <div class="order-cell">
              <span>{{ row.order_no }}</span>
              <el-tag v-if="isAbnormalOrder(row.order_no, getGoodsSummary(row))" type="danger" size="small">AI 异常</el-tag>
              <el-tag v-if="row.is_overdue" type="danger" size="small">⏰ 超时</el-tag>
              <el-tag v-if="row.urgent_level === 'urgent'" type="warning" size="small">⚡ 紧急</el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="applicant_name" label="申请人" width="90" />
        <el-table-column label="类型/金额" width="130">
          <template #default="{ row }">
            <div class="level-cell">
              <span v-if="row.material_type" class="mat-type">{{ row.material_type }}</span>
              <span v-if="row.estimated_amount" class="mat-amount">¥{{ row.estimated_amount }}</span>
            </div>
            <div v-if="row.approval_level" class="approval-level-badge" :class="row.approval_level">
              {{ row.approval_level === 'minor' ? '小额' : row.approval_level === 'special' ? '特殊' : '大额' }}审批
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="(statusTypes[row.status] || 'info') as any" size="small">{{ statusLabels[row.status] || row.status }}</el-tag>
            <div v-if="row.forwarded_to" class="forwarded-hint">→ {{ row.forwarded_to === 'system_admin' ? '管理员' : '后勤' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="明细" min-width="160">
          <template #default="{ row }">
            <span v-for="(i, k) in row.items" :key="k">{{ i.goods_name }} {{ i.quantity }}{{ i.unit }}{{ k < row.items.length - 1 ? '；' : '' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="receiver_name" label="收货人" width="90" />
        <el-table-column prop="destination" label="收货地点" min-width="130" />
        <el-table-column label="截止时间" width="120">
          <template #default="{ row }">
            <span v-if="row.approval_deadline_at" :class="row.is_overdue ? 'overdue-text' : ''">
              {{ row.approval_deadline_at.slice(0, 16).replace('T', ' ') }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="120">
          <template #default="{ row }">{{ row.created_at ? row.created_at.slice(0, 10) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" min-width="300" fixed="right" align="left">
          <template #default="{ row }">
            <div v-if="row.status === 'pending'" class="action-row">
              <el-button
                class="action-row__btn action-row__btn--ai"
                type="primary"
                size="small"
                :loading="aiAnalysisBusyId === row.id"
                @click="openAiAnalysis(row)"
              >
                AI 分析
              </el-button>
              <el-button class="action-row__btn" type="success" size="small" :disabled="!row.ai_judgment_at" @click="openApprovalDialog(row, 'approve')">通过</el-button>
              <el-button class="action-row__btn" type="danger" size="small" :disabled="!row.ai_judgment_at" @click="openApprovalDialog(row, 'reject')">驳回</el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- AI 分析：加载动画 → 合规报告（与审批签名分离） -->
    <el-dialog
      v-model="aiAnalysisDialogVisible"
      title="审批详情"
      width="560px"
      class="approval-detail-dialog ai-report-dialog"
      :close-on-click-modal="false"
      destroy-on-close
      @closed="onAiAnalysisDialogClosed"
    >
      <div class="approval-panel">
        <div v-if="aiAnalysisLoading" class="ai-loading-block">
          <el-icon class="ai-loading-icon is-loading"><Loading /></el-icon>
          <p class="ai-loading-title">AI 分析中</p>
          <p class="ai-loading-desc">正在汇总库存、预算、价格、合规与供应商资信等维度，请稍候…</p>
        </div>

        <template v-else-if="analysisReport">
          <div class="panel-block ai-result-block ai-result-block--ok">
            <div class="panel-title panel-title--ok">
              <el-icon class="ok-ico"><CircleCheck /></el-icon>
              AI 研判结果
            </div>
            <div class="panel-line">
              建议：
              <el-tag type="success" size="small">{{ analysisReport.recommendation_label }}</el-tag>
              <span class="score-text">评分 {{ analysisReport.score }}</span>
            </div>
            <div class="dim-grid">
              <div
                v-for="(meta, key) in analysisReport.dimensions"
                :key="key"
                class="dim-item"
              >
                <span class="dim-name">{{ dimLabels[String(key)] || key }}</span>
                <el-tag size="small" type="success">{{ dimResultText(meta.result) }}</el-tag>
                <p class="dim-note">{{ meta.note }}</p>
              </div>
            </div>
            <p class="panel-wrap summary-text">{{ analysisReport.summary }}</p>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button type="primary" @click="aiAnalysisDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 通过 / 驳回：理由 + 电子签名 -->
    <el-dialog
      v-model="approvalDialogVisible"
      :title="`审批留痕 · ${approvalAction === 'approve' ? '通过' : '驳回'}`"
      width="520px"
      class="approval-detail-dialog"
      :close-on-click-modal="false"
      destroy-on-close
      @closed="onApprovalDialogClosed"
    >
      <div v-if="approvalRow" class="approval-panel">
        <el-alert
          v-if="approvalRow.ai_judgment_summary"
          type="success"
          :closable="false"
          show-icon
          class="approval-ai-hint"
          title="已基于 AI 合规报告，请填写审批理由并完成签名。"
          :description="`建议：${approvalRow.ai_judgment === 'pass' ? '通过' : approvalRow.ai_judgment === 'reject' ? '驳回' : '谨慎通过'} · 评分 ${approvalRow.ai_judgment_score ?? '-'}`"
        />
        <div class="panel-block">
          <div class="panel-title">审批理由</div>
          <el-select v-model="approvalReasonOption" placeholder="请选择常用审批理由" filterable allow-create style="width: 100%">
            <el-option v-for="r in approvalReasonOptions" :key="r" :label="r" :value="r" />
          </el-select>
          <el-input v-model="approvalOpinion" type="textarea" :rows="3" style="margin-top: 8px" placeholder="可补充自定义审批意见" />
        </div>
        <div class="panel-block">
          <div class="panel-title">电子签名</div>
          <el-radio-group v-model="approvalSignatureMode" size="small">
            <el-radio-button label="draw">手写签名</el-radio-button>
            <el-radio-button label="stamp">电子签章</el-radio-button>
          </el-radio-group>
          <div v-if="approvalSignatureMode === 'draw'" class="sign-canvas-wrap">
            <canvas
              ref="signatureCanvasRef"
              width="420"
              height="160"
              class="sign-canvas"
              @mousedown="startDraw"
              @mousemove="drawMove"
              @mouseup="stopDraw"
              @mouseleave="stopDraw"
              @touchstart.prevent="startDraw"
              @touchmove.prevent="drawMove"
              @touchend.prevent="stopDraw"
            />
            <el-button size="small" @click="resetSignaturePad">清空签名</el-button>
          </div>
          <div v-else class="stamp-area">
            <el-select v-model="selectedStamp" placeholder="选择电子签章" style="width: 100%">
              <el-option label="后勤审批专用章" value="后勤审批专用章" />
              <el-option label="采购风控复核章" value="采购风控复核章" />
              <el-option label="预算合规签章" value="预算合规签章" />
            </el-select>
          </div>
          <div class="panel-line">签名时间戳：{{ signatureTimestamp }}</div>
        </div>
      </div>
      <template #footer>
        <div class="drawer-footer">
          <el-button @click="approvalDialogVisible = false">取消</el-button>
          <el-button type="primary" :disabled="!canSubmitApproval" @click="submitApproval">确认并留痕提交</el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.page { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.inventory-box {
  padding: 12px 16px; background: rgba(79, 70, 229, 0.06); border: 1px solid rgba(79, 70, 229, 0.2);
  border-radius: 8px; margin-bottom: 16px; font-size: 13px;
  .inv-title { font-weight: 600; color: var(--text-secondary); margin-right: 12px; }
  .inv-item { margin-right: 16px; }
  .inv-item.ok { color: var(--el-color-success); }
  .inv-item.fail { color: var(--el-color-danger); }
  .inv-muted { color: var(--text-muted); }
}
.page-header h2 { margin: 0; font-size: 18px; }
.filter-bar { margin-bottom: 16px; }
.page-desc { margin: 4px 0 0 0; font-size: 13px; color: var(--text-muted); }
.table-card { padding: 20px; background: var(--bg-card); border-radius: 12px; }
/* 固定列操作区避免把按钮裁成色块 */
.table-card :deep(.el-table__fixed-right .cell) {
  overflow: visible;
  line-height: normal;
}

.order-cell { display: flex; flex-direction: column; gap: 3px; }
.level-cell { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.mat-type { font-size: 11px; background: #e0f2fe; color: #0369a1; padding: 1px 6px; border-radius: 4px; }
.mat-amount { font-size: 12px; color: #d97706; font-weight: 600; }
.approval-level-badge {
  font-size: 10px; padding: 1px 5px; border-radius: 3px; display: inline-block; margin-top: 2px;
  &.minor { background: #dcfce7; color: #16a34a; }
  &.major { background: #fef3c7; color: #d97706; }
  &.special { background: #fee2e2; color: #dc2626; }
}
.forwarded-hint { font-size: 10px; color: #6366f1; margin-top: 2px; }
.overdue-text { color: #dc2626; font-weight: 600; }
/* 固定列内按钮勿被压扁：给足最小宽度 + 禁止 flex 收缩 */
.action-row {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  max-width: 100%;
}
:deep(.action-row__btn.el-button) {
  flex: 0 0 auto;
  min-width: 72px;
  padding-left: 12px;
  padding-right: 12px;
  box-sizing: border-box;
}
/* 实心主色 + 白字，避免 plain/主题下紫底紫字看不清 */
:deep(.action-row__btn--ai.el-button--primary) {
  min-width: 100px;
  font-weight: 600;
  color: #ffffff !important;
  --el-button-text-color: #ffffff;
  --el-button-hover-text-color: #ffffff;
  --el-button-active-text-color: #ffffff;
  background-color: #4f46e5 !important;
  border-color: #4f46e5 !important;
  --el-button-bg-color: #4f46e5;
  --el-button-border-color: #4f46e5;
  --el-button-hover-bg-color: #4338ca;
  --el-button-hover-border-color: #4338ca;
  --el-button-active-bg-color: #3730a3;
  --el-button-active-border-color: #3730a3;
}
:deep(.action-row__btn--ai.el-button--primary .el-icon) {
  color: #ffffff;
}

:deep(.approval-detail-dialog) {
  .el-dialog__body { padding-top: 8px; }
}

.ai-loading-block {
  text-align: center;
  padding: 28px 16px 20px;
  .ai-loading-icon { font-size: 40px; color: var(--el-color-primary); }
  .ai-loading-title { margin: 12px 0 6px; font-size: 16px; font-weight: 600; }
  .ai-loading-desc { margin: 0; font-size: 13px; color: var(--text-muted); line-height: 1.5; }
}

.approval-panel { display: grid; gap: 12px; padding-bottom: 4px; max-height: 70vh; overflow-y: auto; }
.panel-block { border: 1px solid var(--border-subtle); border-radius: 10px; padding: 10px 12px; background: var(--bg-hover); }
.ai-result-block { background: rgba(79, 70, 229, 0.06); }
.ai-result-block--ok { background: rgba(22, 163, 74, 0.08); border-color: rgba(22, 163, 74, 0.25); }
.panel-title { display: flex; align-items: center; gap: 6px; font-weight: 600; margin-bottom: 8px; }
.panel-title--ok { color: #15803d; }
.ok-ico { font-size: 18px; color: #16a34a; }
.approval-ai-hint { margin-bottom: 12px; }
.panel-line { font-size: 13px; color: var(--text-secondary); margin-top: 6px; display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.score-text { font-weight: 600; color: var(--text-primary); }
.dim-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 10px;
}
.dim-item {
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  padding: 8px;
  background: var(--bg-card);
  .dim-name { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 4px; }
  .dim-note { margin: 6px 0 0; font-size: 12px; color: var(--text-secondary); line-height: 1.4; }
}
.summary-text { margin: 10px 0 0; font-size: 13px; line-height: 1.55; color: var(--text-secondary); }
.panel-wrap { line-height: 1.5; }
.sign-canvas-wrap { margin-top: 8px; display: grid; gap: 8px; }
.sign-canvas { border: 1px dashed #94a3b8; border-radius: 6px; background: #fff; touch-action: none; }
.stamp-area { margin-top: 8px; }
.drawer-footer { display: flex; justify-content: flex-end; gap: 8px; width: 100%; }
</style>
