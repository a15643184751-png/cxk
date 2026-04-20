<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listInventory } from '@/api/stock'
import type { InventoryItem } from '@/api/stock'

const keyword = ref('')
const loading = ref(false)
const tableData = ref<InventoryItem[]>([])

async function fetchData() {
  loading.value = true
  try {
    const res: any = await listInventory(keyword.value ? { keyword: keyword.value } : {})
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
      <h2>库存查询</h2>
      <el-input v-model="keyword" placeholder="物资名" style="width: 200px" @keyup.enter="fetchData" />
      <el-button type="primary" @click="fetchData">查询</el-button>
    </div>
    <div class="table-card">
      <el-table :data="tableData" v-loading="loading" style="width: 100%">
        <el-table-column prop="goods_name" label="物资" />
        <el-table-column prop="category" label="分类" width="100" />
        <el-table-column prop="batch_no" label="批次号" width="140" />
        <el-table-column prop="quantity" label="数量" width="100" />
        <el-table-column prop="unit" label="单位" width="80" />
        <el-table-column label="库存状态" width="140">
          <template #default="{ row }">
            <el-tag :type="row.is_low_stock ? 'danger' : 'success'" size="small">
              {{ row.is_low_stock ? '低库存' : '正常' }}
            </el-tag>
            <div class="safe-line">安全线: {{ row.safe_qty }}{{ row.unit || '件' }}</div>
          </template>
        </el-table-column>
        <el-table-column label="临期(天)" width="120">
          <template #default="{ row }">
            <el-tag
              v-if="row.days_to_expire !== null"
              :type="row.days_to_expire <= 7 ? 'danger' : row.days_to_expire <= 30 ? 'warning' : 'info'"
              size="small"
            >
              {{ row.days_to_expire }}
            </el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.page { padding: 0; }
.page-header { display: flex; justify-content: space-between; margin-bottom: 20px; }
.table-card { padding: 20px; background: var(--bg-card); border-radius: 12px; }
.safe-line { margin-top: 4px; font-size: 12px; color: var(--text-muted); }
</style>
