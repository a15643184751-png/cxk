<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { listWarnings, handleWarning } from '@/api/warning'
import type { WarningItem } from '@/api/warning'

const filterStatus = ref('')
const loading = ref(false)
const tableData = ref<WarningItem[]>([])

async function fetchData() {
  loading.value = true
  try {
    const res: any = await listWarnings(filterStatus.value ? { status: filterStatus.value } : {})
    tableData.value = Array.isArray(res) ? res : res?.data ?? []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

async function onHandle(row: WarningItem) {
  try {
    await handleWarning(row.id)
    ElMessage.success('已处理')
    fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '操作失败')
  }
}

onMounted(fetchData)
watch(filterStatus, fetchData)
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>预警中心</h2>
      <el-select v-model="filterStatus" placeholder="状态" clearable style="width: 120px">
        <el-option label="全部" value="" />
        <el-option label="待处理" value="pending" />
        <el-option label="已处理" value="handled" />
      </el-select>
    </div>
    <div class="table-card">
      <el-table :data="tableData" v-loading="loading" style="width: 100%">
        <el-table-column prop="material" label="物资" width="140" />
        <el-table-column prop="description" label="描述" min-width="200" />
        <el-table-column prop="level" label="等级" width="100">
          <template #default="{ row }">
            <el-tag :type="row.level === 'high' ? 'danger' : 'warning'" size="small">{{ row.level === 'high' ? '紧急' : '关注' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'handled' ? 'success' : 'warning'" size="small">{{ row.status === 'handled' ? '已处理' : '待处理' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button v-if="row.status !== 'handled'" type="primary" link size="small" @click="onHandle(row)">立即处理</el-button>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">{{ row.created_at ? row.created_at.slice(0, 19) : '-' }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.page { padding: 0; }
.page-header { display: flex; justify-content: space-between; margin-bottom: 20px; }
.table-card { padding: 20px; background: var(--bg-card); border-radius: 12px; }
</style>
