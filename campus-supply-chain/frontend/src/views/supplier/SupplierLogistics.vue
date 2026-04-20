<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { listSupplierOrders } from '@/api/supplier'
import type { SupplierOrder } from '@/api/supplier'

const loading = ref(false)
const tableData = ref<SupplierOrder[]>([])

// 物流流转步骤：发货→入库→出库→配送→签收
const FLOW_STEPS = [
  { key: 'shipped', label: '已发货' },
  { key: 'stocked_in', label: '已入库' },
  { key: 'stocked_out', label: '已出库' },
  { key: 'delivering', label: '配送中' },
  { key: 'completed', label: '已签收' },
] as const

const FLOW_ORDER: Record<string, number> = {
  shipped: 0, stocked_in: 1, stocked_out: 2, delivering: 3, completed: 4,
}

// 仅展示已发货及之后的订单（物流中的订单）
const logisticsOrders = computed(() =>
  tableData.value.filter((o) =>
    ['shipped', 'stocked_in', 'stocked_out', 'delivering', 'completed'].includes(o.status)
  )
)

function getFlowState(row: SupplierOrder) {
  const idx = FLOW_ORDER[row.status] ?? 0
  return FLOW_STEPS.map((s, i) => ({
    ...s,
    done: i < idx,
    current: i === idx,
  }))
}

const stageLabels: Record<string, string> = {
  shipped: '待仓储入库',
  stocked_in: '已入库待出库',
  stocked_out: '待创建配送',
  delivering: '配送中',
  completed: '已签收',
}

const stageTypes: Record<string, string> = {
  shipped: 'warning',
  stocked_in: 'primary',
  stocked_out: 'primary',
  delivering: 'warning',
  completed: 'success',
}

async function fetchData() {
  loading.value = true
  try {
    const res: any = await listSupplierOrders()
    tableData.value = Array.isArray(res) ? res : res?.data ?? []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>物流-仓储配送管理</h2>
      <p class="page-desc">发完货不用问 · 随时查进度 · 全链路可见</p>
    </div>

    <!-- 物流流转 · 流程条展示 -->
    <div v-if="logisticsOrders.length" class="flow-section">
      <h3 class="flow-section-title">物流流转 · 发完货不用问</h3>
      <div v-for="row in logisticsOrders" :key="row.id" class="flow-card">
        <div class="flow-card-header">
          <span class="order-no">{{ row.order_no }}</span>
          <span class="goods-brief">{{ row.goods_summary || '-' }}</span>
          <span v-if="row.delivery_no" class="delivery-no">配送单：{{ row.delivery_no }}</span>
        </div>
        <div class="flow-bar">
          <template v-for="(step, i) in getFlowState(row)" :key="step.key">
            <div class="flow-step" :class="{ done: step.done, current: step.current }">
              <span class="step-dot" />
              <span class="step-label">{{ step.label }}</span>
            </div>
            <div v-if="i < FLOW_STEPS.length - 1" class="flow-line" :class="{ done: step.done }" />
          </template>
        </div>
        <div class="flow-card-footer">
          <span v-if="row.destination">送至 {{ row.destination }}</span>
          <span v-if="row.receiver_name"> · 收货人 {{ row.receiver_name }}</span>
        </div>
      </div>
    </div>

    <div class="table-card">
      <el-table
        :data="logisticsOrders"
        v-loading="loading"
        style="width: 100%"
        :empty-text="logisticsOrders.length === 0 && !loading ? '暂无物流中的订单，请先在「我的订单」中接单并发货' : ''"
      >
        <el-table-column prop="order_no" label="采购单号" width="150" />
        <el-table-column prop="goods_summary" label="物资明细" min-width="160" show-overflow-tooltip />
        <el-table-column prop="applicant" label="申请人" width="90" />
        <el-table-column prop="receiver_name" label="收货人" width="90">
          <template #default="{ row }">
            {{ row.receiver_name || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="destination" label="目的地" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.destination || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="handoff_code" label="交接码" width="130">
          <template #default="{ row }">
            {{ row.handoff_code || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="delivery_no" label="配送单号" width="130">
          <template #default="{ row }">
            {{ row.delivery_no || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="当前节点" width="140">
          <template #default="{ row }">
            <el-tag :type="stageTypes[row.status] || 'info'" size="small">
              {{ stageLabels[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="下单时间" width="100" />
      </el-table>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.page {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;

  h2 {
    margin: 0 0 8px 0;
    font-size: 18px;
    font-weight: 600;
  }
}

.page-desc {
  margin: 0;
  font-size: 13px;
  color: var(--text-muted);
}

.flow-section {
  margin-bottom: 24px;
}
.flow-section-title {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0 0 12px 0;
  font-weight: 500;
}
.flow-card {
  background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
  border: 1px solid #a7f3d0;
  border-radius: 12px;
  padding: 16px 20px;
  margin-bottom: 12px;
}
.flow-card-header {
  margin-bottom: 14px;
  .order-no { font-weight: 700; color: #059669; font-size: 15px; margin-right: 12px; }
  .goods-brief { font-size: 13px; color: var(--text-secondary); margin-right: 12px; }
  .delivery-no { font-size: 12px; color: #047857; }
}
.flow-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0 4px;
}
.flow-step {
  display: flex;
  align-items: center;
  flex-direction: column;
  gap: 4px;
  .step-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #cbd5e1;
    transition: all 0.2s;
  }
  .step-label { font-size: 11px; color: #94a3b8; }
  &.done .step-dot { background: var(--el-color-success); }
  &.done .step-label { color: var(--el-color-success); }
  &.current .step-dot {
    background: #059669;
    transform: scale(1.3);
    box-shadow: 0 0 0 3px rgba(5, 150, 105, 0.3);
  }
  &.current .step-label { color: #059669; font-weight: 600; }
}
.flow-line {
  width: 28px;
  height: 2px;
  background: #cbd5e1;
  margin: 0 2px;
  flex-shrink: 0;
  &.done { background: var(--el-color-success); }
}
.flow-card-footer {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #d1fae5;
  font-size: 12px;
  color: var(--text-muted);
}

.table-card {
  padding: 24px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  box-shadow: var(--shadow-card);
}
</style>
