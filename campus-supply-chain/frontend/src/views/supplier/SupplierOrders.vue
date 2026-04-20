<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { listSupplierOrders, confirmSupplierOrder, shipSupplierOrder } from '@/api/supplier'

const loading = ref(false)
const tableData = ref<any[]>([])

async function onConfirm(row: { id: number; status: string }) {
  if (row.status !== 'approved') return
  try {
    await confirmSupplierOrder(row.id)
    ElMessage.success('接单成功')
    fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '操作失败')
  }
}

async function onShip(row: { id: number; status: string }) {
  if (row.status !== 'confirmed') return
  try {
    await shipSupplierOrder(row.id)
    ElMessage.success('发货成功')
    fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '操作失败')
  }
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

function getStatusType(status: string) {
  const map: Record<string, string> = {
    pending: 'warning',
    approved: 'primary',
    confirmed: 'warning',
    shipped: 'primary',
    stocked_in: 'success',
    stocked_out: 'success',
    delivering: 'warning',
    completed: 'success',
  }
  return map[status] || 'info'
}

function getStatusLabel(status: string) {
  const map: Record<string, string> = {
    pending: '待接单',
    approved: '待接单',
    confirmed: '待发货',
    shipped: '待仓储入库',
    stocked_in: '待出库配送',
    stocked_out: '待创建配送',
    delivering: '配送中',
    completed: '已完成',
  }
  return map[status] || status
}
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>我的订单</h2>
    </div>
    <div class="table-card">
      <el-table :data="tableData" v-loading="loading" style="width: 100%">
        <el-table-column prop="order_no" label="采购单号" width="160" />
        <el-table-column prop="applicant" label="申请人" width="100" />
        <el-table-column prop="goods_summary" label="物资明细" />
        <el-table-column prop="handoff_code" label="交接码" width="170" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="下单时间" width="120" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'approved'" type="primary" size="small" @click="onConfirm(row)">接单</el-button>
            <el-button v-if="row.status === 'confirmed'" type="success" size="small" @click="onShip(row)">发货</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.page { padding: 0; }
.page-header { display: flex; justify-content: space-between; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 18px; font-weight: 600; }
.table-card { padding: 24px; background: var(--bg-card); border: 1px solid var(--border-subtle); border-radius: 16px; box-shadow: var(--shadow-card); }
</style>
