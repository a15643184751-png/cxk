<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { listStockOut, createStockOut, listInventory } from '@/api/stock'
import { listPurchases } from '@/api/purchase'
import type { Purchase } from '@/api/purchase'
import {
  SCAN_OUTBOUND_CODE,
  SCAN_SUCCESS_DISPLAY,
  SCAN_SUCCESS_LINES,
  SCAN_OUTBOUND_API_ITEMS,
} from './stockScanOutboundPreset'

const loading = ref(false)
const tableData = ref<any[]>([])
const dialogVisible = ref(false)
/** 等待扫码枪输入 */
const scanWaitVisible = ref(false)
/** 扫码并自动出库成功后的结果弹窗 */
const scanSuccessVisible = ref(false)
const scanSuccessOrderNo = ref('')
/** 扫码弹窗内隐藏输入框（扫码枪需落在可编辑控件上才能稳定接收） */
const scanHiddenInput = ref<HTMLInputElement | null>(null)
const outMode = ref<'purchase' | 'manual'>('purchase')
const selectedPurchaseId = ref<number | null>(null)
const outItems = ref([{ goods_name: '', quantity: 1, unit: '件' }])
const inventoryList = ref<{ goods_name: string; quantity: number; unit: string }[]>([])
const availablePurchases = ref<Purchase[]>([])
const submitting = ref(false)
let stockOutVoiceAudio: HTMLAudioElement | null = null

function playStockOutVoice(filename: string) {
  if (!stockOutVoiceAudio) stockOutVoiceAudio = new Audio()
  stockOutVoiceAudio.pause()
  stockOutVoiceAudio.currentTime = 0
  stockOutVoiceAudio.src = `/api/voice/${encodeURIComponent(filename)}`
  void stockOutVoiceAudio.play().catch(() => {
    // 不阻塞扫码出库流程
  })
}

async function fetchData() {
  loading.value = true
  try {
    const res: any = await listStockOut()
    tableData.value = Array.isArray(res) ? res : res?.data ?? []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

async function openDialog() {
  dialogVisible.value = true
  outMode.value = 'purchase'
  selectedPurchaseId.value = null
  outItems.value = [{ goods_name: '', quantity: 1, unit: '件' }]
  try {
    const purchaseRes: any = await listPurchases()
    const purchaseRows = Array.isArray(purchaseRes) ? purchaseRes : purchaseRes?.data ?? []
    availablePurchases.value = purchaseRows.filter((p: Purchase) => p.status === 'stocked_in')
    const res: any = await listInventory()
    const raw = Array.isArray(res) ? res : res?.data ?? []
    const map = new Map<string, { quantity: number; unit: string }>()
    for (const r of raw) {
      const cur = map.get(r.goods_name)
      if (cur) cur.quantity += r.quantity
      else map.set(r.goods_name, { quantity: r.quantity, unit: r.unit || '件' })
    }
    inventoryList.value = [...map.entries()].map(([goods_name, v]) => ({ goods_name, ...v }))
  } catch {
    inventoryList.value = []
  }
}

function addRow() {
  outItems.value.push({ goods_name: '', quantity: 1, unit: '件' })
}

function removeRow(i: number) {
  if (outItems.value.length > 1) outItems.value.splice(i, 1)
}

function selectGoods(row: (typeof outItems.value)[0]) {
  const inv = inventoryList.value.find((x) => x.goods_name === row.goods_name)
  if (inv) {
    row.unit = inv.unit || '件'
  }
}

async function submitOut() {
  submitting.value = true
  try {
    if (outMode.value === 'purchase' && selectedPurchaseId.value) {
      await createStockOut({ purchase_id: selectedPurchaseId.value })
    } else {
      const items = outItems.value.filter((r) => r.goods_name.trim())
      if (!items.length) {
        ElMessage.warning('请至少填写一条物资')
        return
      }
      await createStockOut({ items })
    }
    ElMessage.success('出库成功')
    dialogVisible.value = false
    fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '出库失败')
  } finally {
    submitting.value = false
  }
}

function normalizeScanPayload(s: string) {
  return s.replace(/[\s\r\n\u0000\u001a]/g, '')
}

function resetScanField() {
  const el = scanHiddenInput.value
  if (el) el.value = ''
}

/** 焦点不在隐藏输入框时（例如落在「取消」上），仍用全局缓冲接收扫码枪 */
let scanFallbackBuf = ''
let scanFallbackLast = 0
const SCAN_FALLBACK_GAP_MS = 520

function resetFallbackBuf() {
  scanFallbackBuf = ''
  scanFallbackLast = 0
}

function onGlobalScanFallback(e: KeyboardEvent) {
  if (!scanWaitVisible.value) return
  if (document.activeElement === scanHiddenInput.value) return

  if (e.key === 'Escape') {
    e.preventDefault()
    closeScanWait()
    return
  }

  const now = Date.now()
  if (now - scanFallbackLast > SCAN_FALLBACK_GAP_MS) scanFallbackBuf = ''
  scanFallbackLast = now

  const isEnter = e.key === 'Enter' || e.code === 'Enter' || e.code === 'NumpadEnter'
  if (isEnter) {
    const raw = scanFallbackBuf.replace(/\r/g, '').trim()
    scanFallbackBuf = ''
    if (!raw) {
      ElMessage.info('请先扫描出库二维码，或确认扫码枪输出末尾带回车')
      return
    }
    e.preventDefault()
    if (normalizeScanPayload(raw) === normalizeScanPayload(SCAN_OUTBOUND_CODE)) {
      closeScanWait()
      void runScanOutboundSuccess()
    } else {
      ElMessage.warning('未识别的出库码，请重试')
    }
    return
  }

  if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
    const t = e.target as HTMLElement | null
    if (t?.closest('input, textarea, [contenteditable=true]')) return
    e.preventDefault()
    scanFallbackBuf += e.key
  }
}

function focusScanField() {
  nextTick(() => {
    const el = scanHiddenInput.value
    if (!el) return
    el.focus()
    el.select()
    // 晚一帧再抢焦点，避免被弹窗默认焦点（如取消按钮）抢走
    setTimeout(() => {
      el.focus()
      el.select()
    }, 80)
  })
}

/** 隐藏框内：扫码枪写入整段内容后按 Enter */
function onScanFieldKeydown(e: KeyboardEvent) {
  if (!scanWaitVisible.value) return
  if (e.key === 'Escape') {
    e.preventDefault()
    closeScanWait()
    return
  }
  const isEnter = e.key === 'Enter' || e.code === 'Enter' || e.code === 'NumpadEnter'
  if (!isEnter) return
  e.preventDefault()
  e.stopPropagation()
  const raw = (scanHiddenInput.value?.value || '').replace(/\r/g, '').trim()
  resetScanField()
  if (!raw) {
    ElMessage.info('请先扫描出库二维码，或确认扫码枪输出末尾带回车')
    return
  }
  if (normalizeScanPayload(raw) === normalizeScanPayload(SCAN_OUTBOUND_CODE)) {
    closeScanWait()
    void runScanOutboundSuccess()
  } else {
    ElMessage.warning('未识别的出库码，请重试')
  }
}

function openScanWait() {
  scanWaitVisible.value = true
}

function onScanWaitDialogOpened() {
  resetScanField()
  resetFallbackBuf()
  window.addEventListener('keydown', onGlobalScanFallback, true)
  focusScanField()
}

function onScanWaitDialogClosed() {
  window.removeEventListener('keydown', onGlobalScanFallback, true)
  resetScanField()
  resetFallbackBuf()
}

function closeScanWait() {
  window.removeEventListener('keydown', onGlobalScanFallback, true)
  scanWaitVisible.value = false
  resetScanField()
  resetFallbackBuf()
}

function closeScanSuccess() {
  scanSuccessVisible.value = false
  scanSuccessOrderNo.value = ''
}

async function runScanOutboundSuccess() {
  scanSuccessOrderNo.value = SCAN_SUCCESS_DISPLAY.outOrderNo
  scanSuccessVisible.value = true
  playStockOutVoice('出库成功语音.mp3')
  submitting.value = true
  try {
    const res: any = await createStockOut({ items: [...SCAN_OUTBOUND_API_ITEMS] })
    const rawNo = res?.order_no ?? res?.data?.order_no
    if (typeof rawNo === 'string' && rawNo.trim()) scanSuccessOrderNo.value = rawNo.trim()
    await fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '出库同步失败，请稍后重试或联系管理员')
  } finally {
    submitting.value = false
  }
}

onMounted(fetchData)

onUnmounted(() => {
  window.removeEventListener('keydown', onGlobalScanFallback, true)
})
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>出库管理</h2>
      <div class="page-header__actions">
        <el-button type="primary" size="default" @click="openDialog">新建出库</el-button>
        <el-button size="default" @click="openScanWait">扫码出库</el-button>
      </div>
    </div>
    <div class="table-card">
      <el-table :data="tableData" v-loading="loading" style="width: 100%">
        <el-table-column prop="order_no" label="出库单号" width="160" />
        <el-table-column prop="goods_name" label="物资" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="batch_no" label="批次号" width="140" />
        <el-table-column prop="receiver_name" label="收货人" width="110" />
        <el-table-column prop="destination" label="目的地" min-width="140" />
        <el-table-column prop="handoff_code" label="交接码" width="170" />
        <el-table-column prop="created_at" label="出库时间" width="180">
          <template #default="{ row }">{{ row.created_at ? row.created_at.slice(0, 19) : '-' }}</template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" title="新建出库" width="520" @close="dialogVisible = false">
      <el-radio-group v-model="outMode" style="margin-bottom: 16px">
        <el-radio-button label="purchase">按申请单出库</el-radio-button>
        <el-radio-button label="manual">手工出库</el-radio-button>
      </el-radio-group>

      <template v-if="outMode === 'purchase'">
        <div v-if="!availablePurchases.length" class="hint-box">
          暂无已入库待出库的申请单。库存直采或供应商补货入库后，申请单会出现在此；或使用「手工出库」。
        </div>
        <el-select v-else v-model="selectedPurchaseId" placeholder="选择已入库待出库申请单" filterable style="width: 100%">
          <el-option
            v-for="p in availablePurchases"
            :key="p.id"
            :label="`${p.order_no} - ${p.receiver_name || '-'} - ${p.destination || '未填写地点'}`"
            :value="p.id"
          />
        </el-select>
        <div v-if="selectedPurchaseId" class="purchase-preview">
          <div>收货人：{{ availablePurchases.find((x) => x.id === selectedPurchaseId)?.receiver_name || '-' }}</div>
          <div>收货地点：{{ availablePurchases.find((x) => x.id === selectedPurchaseId)?.destination || '-' }}</div>
          <div v-for="(it, k) in availablePurchases.find((x) => x.id === selectedPurchaseId)?.items || []" :key="k">
            {{ it.goods_name }} {{ it.quantity }}{{ it.unit }}
          </div>
        </div>
      </template>

      <template v-else>
        <div v-for="(row, i) in outItems" :key="i" class="out-row">
          <el-select v-model="row.goods_name" placeholder="选择物资" filterable style="width: 180px" @change="selectGoods(row)">
            <el-option v-for="inv in inventoryList" :key="inv.goods_name" :label="`${inv.goods_name} (库存${inv.quantity}${inv.unit})`" :value="inv.goods_name" />
          </el-select>
          <el-input-number v-model="row.quantity" :min="0.1" size="default" style="width: 110px" />
          <el-input v-model="row.unit" placeholder="单位" size="default" style="width: 70px" disabled />
          <el-button type="danger" link @click="removeRow(i)">删除</el-button>
        </div>
        <el-button type="primary" link @click="addRow">+ 添加一行</el-button>
      </template>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitOut">确认出库</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="scanWaitVisible"
      title="扫码出库"
      width="440px"
      align-center
      :close-on-click-modal="false"
      destroy-on-close
      @opened="onScanWaitDialogOpened"
      @closed="onScanWaitDialogClosed"
    >
      <input
        ref="scanHiddenInput"
        type="text"
        class="scan-hidden-input"
        autocomplete="off"
        aria-label="出库扫码"
        @keydown="onScanFieldKeydown"
      />
      <p class="scan-wait__tip">请使用扫码枪对准出库二维码扫描。</p>
      <p class="scan-wait__hint">扫码完成后将自动确认；按 Esc 可取消。</p>
      <template #footer>
        <el-button @click="closeScanWait">取消</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="scanSuccessVisible"
      class="scan-success-dialog"
      width="820px"
      align-center
      append-to-body
      destroy-on-close
      :close-on-click-modal="true"
      :close-on-press-escape="true"
      @closed="closeScanSuccess"
    >
      <template #header>
        <div class="scan-success__title">扫码出库・出库成功</div>
      </template>

      <div class="scan-success__block scan-success__block--lead">
        <p class="scan-success__line">
          <span class="scan-success__icon" aria-hidden="true">✅</span>
          扫码已确认，自动完成出库
        </p>
        <p class="scan-success__outno">
          出库单号：<strong>{{ scanSuccessOrderNo || SCAN_SUCCESS_DISPLAY.outOrderNo }}</strong>
        </p>
      </div>

      <div class="scan-success__section-label">【订单信息】</div>
      <div class="scan-success__order">
        <p>收货人：{{ SCAN_SUCCESS_DISPLAY.receiver }}</p>
        <p>收货地点：{{ SCAN_SUCCESS_DISPLAY.destination }}</p>
        <p>交接码：{{ SCAN_SUCCESS_DISPLAY.handoffCode }}</p>
        <p>出库时间：{{ SCAN_SUCCESS_DISPLAY.outTime }}</p>
      </div>

      <div class="scan-success__section-label">【物资明细】</div>
      <el-table :data="[...SCAN_SUCCESS_LINES]" border stripe size="small" class="scan-success__table">
        <el-table-column prop="goods_name" label="物资名称" min-width="140" />
        <el-table-column prop="spec" label="规格" width="100" />
        <el-table-column prop="quantity" label="数量" width="88" align="right" />
        <el-table-column prop="unit" label="单位" width="72" align="center" />
        <el-table-column prop="stock_status" label="库存状态" min-width="100">
          <template #default="{ row }">
            <span
              class="scan-success__stock"
              :class="row.stock_status.includes('仅剩') ? 'is-low' : 'is-ok'"
            >{{ row.stock_status }}</span>
          </template>
        </el-table-column>
      </el-table>

      <p class="scan-success__footer-tip">
        物资已同步至配送环节，可在配送列表查看进度
        <span class="scan-success__esc">按 ESC 关闭弹窗</span>
      </p>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.page { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.page-header__actions { display: flex; gap: 10px; flex-wrap: wrap; }
.scan-wait__tip { margin: 0 0 10px; font-size: 14px; line-height: 1.55; color: var(--el-text-color-primary); }
.scan-wait__hint { margin: 0; font-size: 12px; color: var(--el-text-color-secondary); }
.scan-hidden-input {
  position: fixed;
  left: -2400px;
  top: 0;
  width: 8px;
  height: 8px;
  opacity: 0;
  border: 0;
  padding: 0;
  margin: 0;
  font-size: 16px;
  caret-color: transparent;
}

.scan-success-dialog :deep(.el-dialog__header) {
  margin-right: 0;
  padding-bottom: 8px;
}
.scan-success__title {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: var(--el-color-success);
  line-height: 1.35;
}
.scan-success__block--lead {
  margin-bottom: 18px;
  padding: 14px 16px;
  border-radius: 10px;
  background: var(--el-color-success-light-9);
  border: 1px solid var(--el-color-success-light-5);
}
.scan-success__line {
  margin: 0 0 10px;
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}
.scan-success__icon {
  font-size: 20px;
  line-height: 1;
}
.scan-success__outno {
  margin: 0;
  font-size: 15px;
  color: var(--el-text-color-regular);
}
.scan-success__outno strong {
  color: var(--el-text-color-primary);
  font-size: 17px;
  letter-spacing: 0.02em;
}
.scan-success__section-label {
  margin: 16px 0 8px;
  font-size: 14px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}
.scan-success__order {
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--bg-hover);
  font-size: 14px;
  line-height: 1.75;
  color: var(--el-text-color-regular);
}
.scan-success__order p {
  margin: 0;
}
.scan-success__table {
  margin-top: 4px;
}
.scan-success__stock.is-ok {
  color: var(--el-color-success);
  font-weight: 600;
}
.scan-success__stock.is-low {
  color: var(--el-color-warning);
  font-weight: 600;
}
.scan-success__footer-tip {
  margin: 18px 0 0;
  padding-top: 14px;
  border-top: 1px solid var(--el-border-color-lighter);
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.65;
}
.scan-success__esc {
  display: inline-block;
  margin-left: 10px;
  padding: 2px 10px;
  border-radius: 6px;
  background: var(--el-fill-color-dark);
  color: var(--el-text-color-primary);
  font-weight: 600;
  font-size: 12px;
}

.table-card { padding: 20px; background: var(--bg-card); border-radius: 12px; }
.out-row { display: flex; gap: 8px; align-items: center; margin-bottom: 12px; }
.purchase-preview { margin-top: 12px; padding: 12px; background: var(--bg-hover); border-radius: 8px; font-size: 13px; }
.hint-box { padding: 12px; background: var(--el-color-info-light-9); border-radius: 8px; font-size: 13px; color: var(--el-text-color-regular); }
</style>
