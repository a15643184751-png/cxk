<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listDeliveries, createDelivery, updateDeliveryStatus } from '@/api/delivery'
import { listStockOut } from '@/api/stock'
import type { DeliveryItem } from '@/api/delivery'

const loading = ref(false)
const tableData = ref<DeliveryItem[]>([])
const createVisible = ref(false)
const createLoading = ref(false)
const stockOutList = ref<{ id: number; order_no: string; goods_name: string; quantity: number; unit: string; destination?: string; receiver_name?: string }[]>([])

const form = ref({
  stock_out_id: undefined as number | undefined,
  destination: '',
  receiver_name: '',
  remark: '',
})

const statusLabels: Record<string, string> = {
  pending: '待发车',
  loading: '装车中',
  on_way: '运输中',
  received: '已签收',
}

const statusNext: Record<string, string | null> = {
  pending: 'loading',
  loading: 'on_way',
  on_way: null,
  received: null,
}

async function fetchData() {
  loading.value = true
  try {
    const res: any = await listDeliveries()
    tableData.value = Array.isArray(res) ? res : res?.data ?? []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

async function openCreate() {
  createVisible.value = true
  form.value = { stock_out_id: undefined, destination: '', receiver_name: '', remark: '' }
  try {
    const res: any = await listStockOut()
    const rows = Array.isArray(res) ? res : res?.data ?? []
    stockOutList.value = rows.map((r: any) => ({
      id: r.id,
      order_no: r.order_no,
      goods_name: r.goods_name,
      quantity: r.quantity,
      unit: r.unit || '件',
      destination: r.destination || '',
      receiver_name: r.receiver_name || '',
    }))
  } catch {
    stockOutList.value = []
  }
}

async function submitCreate() {
  if (form.value.stock_out_id) {
    const linked = stockOutList.value.find((x) => x.id === form.value.stock_out_id)
    if (linked) {
      form.value.destination = form.value.destination.trim() || linked.destination || ''
      form.value.receiver_name = form.value.receiver_name.trim() || linked.receiver_name || ''
    }
  }
  if (!form.value.destination.trim()) {
    ElMessage.warning('请填写配送目的地')
    return
  }
  createLoading.value = true
  try {
    await createDelivery({
      stock_out_id: form.value.stock_out_id,
      destination: form.value.destination.trim(),
      receiver_name: form.value.receiver_name.trim(),
      remark: form.value.remark.trim(),
    })
    ElMessage.success('配送单已创建')
    createVisible.value = false
    fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '创建失败')
  } finally {
    createLoading.value = false
  }
}

async function changeStatus(row: DeliveryItem, nextStatus: string) {
  try {
    await updateDeliveryStatus(row.id, { status: nextStatus })
    ElMessage.success(`状态已更新为 ${statusLabels[nextStatus]}`)
    fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '更新失败')
  }
}

onMounted(fetchData)

// 无接口数据时的配送轨迹与供应商状态占位
const demoTrail = [
  { time: '09:00', place: '中央仓库', status: '已装车' },
  { time: '09:35', place: '校园南路', status: '运输中' },
  { time: '10:05', place: '教学楼A栋302', status: '待签收' },
]
const demoPurchaseStatus = [
  { order_no: 'P20260318001', supplier: '校园文具', status: '已发货' },
  { order_no: 'P20260318002', supplier: '-', status: '库存直采' },
]
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>配送管理</h2>
      <el-button type="primary" size="default" @click="openCreate">新建配送</el-button>
    </div>
    <div class="demo-box">
      <div class="demo-block">
        <span class="demo-title">配送轨迹：</span>
        <div class="trail">
          <div v-for="(p, i) in demoTrail" :key="i" class="trail-step">
            <span class="trail-time">{{ p.time }}</span>
            <span class="trail-place">{{ p.place }}</span>
            <span class="trail-status">{{ p.status }}</span>
          </div>
        </div>
      </div>
      <div class="demo-block">
        <span class="demo-title">供应商采购状态：</span>
        <span v-for="(s, i) in demoPurchaseStatus" :key="i" class="purchase-item">{{ s.order_no }}：{{ s.status }}</span>
      </div>
    </div>
    <div class="table-card">
      <el-table :data="tableData" v-loading="loading" style="width: 100%">
        <el-table-column prop="delivery_no" label="配送单号" width="160" />
        <el-table-column prop="purchase_order_no" label="申请单号" width="160" />
        <el-table-column prop="destination" label="目的地" />
        <el-table-column prop="receiver_name" label="收货人" width="110" />
        <el-table-column prop="handoff_code" label="交接码" width="170" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'received' ? 'success' : 'primary'" size="small">
              {{ row.status_label || statusLabels[row.status] || row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="scheduled_at" label="计划时间" width="180">
          <template #default="{ row }">{{ row.scheduled_at ? row.scheduled_at.slice(0, 19) : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <template v-if="statusNext[row.status]">
              <el-button type="primary" link size="small" @click="changeStatus(row, statusNext[row.status]!)">
                更新为 {{ statusLabels[statusNext[row.status]!] }}
              </el-button>
            </template>
            <el-button v-else type="info" link size="small" disabled>{{ row.status === 'on_way' ? '待老师签收' : '已完成' }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="createVisible" title="新建配送" width="500" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px">
        <el-form-item label="关联出库">
          <el-select v-model="form.stock_out_id" placeholder="可选，关联出库单" clearable style="width: 100%">
            <el-option
              v-for="s in stockOutList"
              :key="s.id"
              :label="`${s.order_no} - ${s.goods_name} x${s.quantity}${s.unit}`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目的地" required>
          <el-input v-model="form.destination" placeholder="如：教学楼A栋302" />
        </el-form-item>
        <el-form-item label="收货人">
          <el-input v-model="form.receiver_name" placeholder="可选" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="createLoading" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.page { padding: 0; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.demo-box {
  display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 20px;
  padding: 16px 20px; background: rgba(79, 70, 229, 0.06); border: 1px solid rgba(79, 70, 229, 0.2);
  border-radius: 12px;
}
.demo-block { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.demo-title { font-weight: 600; color: var(--text-secondary); font-size: 13px; }
.trail { display: flex; gap: 16px; align-items: center; flex-wrap: wrap; }
.trail-step { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.trail-time { color: var(--text-muted); }
.trail-place { font-weight: 500; color: var(--primary); }
.trail-status { color: var(--el-color-success); }
.purchase-item { margin-right: 16px; font-size: 13px; }
.table-card { padding: 20px; background: var(--bg-card); border-radius: 12px; }
</style>
