<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listStockIn, createStockIn } from '@/api/stock'
import { listPurchases } from '@/api/purchase'
import type { Purchase } from '@/api/purchase'

const loading = ref(false)
const tableData = ref<any[]>([])
const dialogVisible = ref(false)
const inMode = ref<'purchase' | 'manual'>('purchase')
const selectedPurchaseId = ref<number | null>(null)
const approvedPurchases = ref<Purchase[]>([])
const manualItems = ref([{ goods_name: '', quantity: 1, unit: '件', batch_no: '' }])
const submitting = ref(false)

async function fetchData() {
  loading.value = true
  try {
    const res: any = await listStockIn()
    tableData.value = Array.isArray(res) ? res : res?.data ?? []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

async function openDialog() {
  dialogVisible.value = true
  inMode.value = 'purchase'
  selectedPurchaseId.value = null
  try {
    const res: any = await listPurchases()
    const all = Array.isArray(res) ? res : res?.data ?? []
    // 可入库：库存直采(approved且无供应商) 或 供应商已发货(shipped)
  approvedPurchases.value = all.filter(
    (p: { status: string; supplier_id?: number | null }) =>
      (p.status === 'approved' && !p.supplier_id) || p.status === 'shipped'
  )
  } catch {
    approvedPurchases.value = []
  }
  manualItems.value = [{ goods_name: '', quantity: 1, unit: '件', batch_no: '' }]
}

function addManualRow() {
  manualItems.value.push({ goods_name: '', quantity: 1, unit: '件', batch_no: '' })
}

function removeManualRow(i: number) {
  if (manualItems.value.length > 1) manualItems.value.splice(i, 1)
}

async function submitIn() {
  submitting.value = true
  try {
    if (inMode.value === 'purchase' && selectedPurchaseId.value) {
      await createStockIn({ purchase_id: selectedPurchaseId.value })
    } else if (inMode.value === 'manual') {
      const items = manualItems.value.filter((r) => r.goods_name.trim())
      if (!items.length) {
        ElMessage.warning('请至少填写一条物资')
        return
      }
      await createStockIn({ items: items.map((r) => ({ goods_name: r.goods_name, quantity: r.quantity, unit: r.unit, batch_no: r.batch_no })) })
    } else {
      ElMessage.warning('请选择采购单或填写入库明细')
      return
    }
    ElMessage.success('入库成功')
    dialogVisible.value = false
    fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '入库失败')
  } finally {
    submitting.value = false
  }
}

onMounted(fetchData)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>入库管理</h2>
      <el-button type="primary" size="default" @click="openDialog">新建入库</el-button>
    </div>
    <div class="table-card">
      <el-table :data="tableData" v-loading="loading" style="width: 100%">
        <el-table-column prop="order_no" label="入库单号" width="160" />
        <el-table-column prop="goods_name" label="物资" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column prop="batch_no" label="批次号" width="140" />
        <el-table-column prop="created_at" label="入库时间" width="180">
          <template #default="{ row }">{{ row.created_at ? row.created_at.slice(0, 19) : '-' }}</template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" title="新建入库" width="520" @close="dialogVisible = false">
      <el-radio-group v-model="inMode" style="margin-bottom: 16px">
        <el-radio-button label="purchase">从采购单入库</el-radio-button>
        <el-radio-button label="manual">手工录入</el-radio-button>
      </el-radio-group>

      <template v-if="inMode === 'purchase'">
        <div v-if="!approvedPurchases.length" class="hint-box">
          暂无待入库采购单。需满足：库存直采（已审批且无供应商）或供应商已发货（shipped）。
        </div>
        <el-select v-else v-model="selectedPurchaseId" placeholder="选择供应商已接单的采购单（货到接收）" filterable style="width: 100%">
          <el-option v-for="p in approvedPurchases" :key="p.id" :label="`${p.order_no} - ${p.applicant_name || '-'}`" :value="p.id" />
        </el-select>
        <div v-if="selectedPurchaseId" class="purchase-preview">
          <div v-for="(it, k) in approvedPurchases.find((x) => x.id === selectedPurchaseId)?.items || []" :key="k">
            {{ it.goods_name }} {{ it.quantity }}{{ it.unit }}
          </div>
        </div>
      </template>

      <template v-else>
        <div v-for="(row, i) in manualItems" :key="i" class="manual-row">
          <el-input v-model="row.goods_name" placeholder="物资名" size="small" style="width: 140px" />
          <el-input-number v-model="row.quantity" :min="0.1" size="small" style="width: 100px" />
          <el-input v-model="row.unit" placeholder="单位" size="small" style="width: 70px" />
          <el-input v-model="row.batch_no" placeholder="批次" size="small" style="width: 100px" />
          <el-button type="danger" link size="small" @click="removeManualRow(i)">删除</el-button>
        </div>
        <el-button type="primary" link size="small" @click="addManualRow">+ 添加一行</el-button>
      </template>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitIn">确认入库</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.page { padding: 0; }
.page-header { display: flex; justify-content: space-between; margin-bottom: 20px; }
.table-card { padding: 20px; background: var(--bg-card); border-radius: 12px; }
.purchase-preview { margin-top: 12px; padding: 10px; background: var(--bg-hover); border-radius: 8px; font-size: 13px; }
.hint-box { padding: 12px; background: var(--el-color-info-light-9); border-radius: 8px; font-size: 13px; color: var(--el-text-color-regular); }
.manual-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
</style>
