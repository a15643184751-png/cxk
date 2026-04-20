<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listSuppliers } from '@/api/supplier'
import type { Supplier } from '@/api/supplier'

const loading = ref(false)
const tableData = ref<Supplier[]>([])

async function fetchData() {
  loading.value = true
  try {
    const res: any = await listSuppliers()
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
      <h2>供应商列表</h2>
      <el-button type="primary">新增供应商</el-button>
    </div>
    <div class="table-card">
      <el-table :data="tableData" v-loading="loading" style="width: 100%">
        <el-table-column prop="name" label="供应商名称" />
        <el-table-column prop="contact" label="联系人" width="120" />
        <el-table-column prop="phone" label="电话" width="140" />
        <el-table-column prop="address" label="地址" min-width="180" />
      </el-table>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.page { padding: 0; }
.page-header { display: flex; justify-content: space-between; margin-bottom: 20px; }
.page-header h2 { margin: 0; font-size: 18px; }
.table-card { padding: 20px; background: var(--bg-card); border-radius: 12px; }
</style>
