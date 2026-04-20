<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Search, Plus, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listGoods, createGoods, updateGoods, deleteGoods } from '@/api/goods'
import type { GoodsItem } from '@/api/goods'
import { listInventory } from '@/api/stock'
import type { InventoryItem } from '@/api/stock'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const tableData = ref<GoodsItem[]>([])
const searchForm = ref({ keyword: '', category: '' })
const dialogVisible = ref(false)
const submitting = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const formData = ref<Partial<GoodsItem>>({
  name: '',
  category: '',
  spec: '',
  unit: '件',
  safety_level: 'medium',
  shelf_life_days: 30,
})

const mainTab = ref<'catalog' | 'stock'>('catalog')
const invLoading = ref(false)
const inventoryKeyword = ref('')
const inventoryRows = ref<InventoryItem[]>([])

function syncTabFromRoute() {
  mainTab.value = route.query.tab === 'stock' ? 'stock' : 'catalog'
}

watch(
  () => route.query.tab,
  () => {
    syncTabFromRoute()
    if (mainTab.value === 'stock') void fetchInventory()
  }
)

watch(mainTab, (v) => {
  void router.replace({ path: '/goods', query: v === 'stock' ? { tab: 'stock' } : {} })
  if (v === 'stock') void fetchInventory()
})

async function fetchData() {
  loading.value = true
  try {
    const res: any = await listGoods(searchForm.value)
    tableData.value = Array.isArray(res) ? res : res?.data ?? []
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

async function fetchInventory() {
  invLoading.value = true
  try {
    const res: any = await listInventory(inventoryKeyword.value.trim() ? { keyword: inventoryKeyword.value.trim() } : {})
    inventoryRows.value = Array.isArray(res) ? res : res?.data ?? []
  } catch {
    inventoryRows.value = []
  } finally {
    invLoading.value = false
  }
}

onMounted(() => {
  syncTabFromRoute()
  void fetchData()
  if (mainTab.value === 'stock') void fetchInventory()
})

function openCreateDialog() {
  dialogMode.value = 'create'
  formData.value = {
    name: '',
    category: '',
    spec: '',
    unit: '件',
    safety_level: 'medium',
    shelf_life_days: 30,
  }
  dialogVisible.value = true
}

function openEditDialog(row: GoodsItem) {
  dialogMode.value = 'edit'
  formData.value = { ...row }
  dialogVisible.value = true
}

async function submitForm() {
  if (!formData.value.name?.trim()) {
    ElMessage.warning('请填写物资名称')
    return
  }
  submitting.value = true
  try {
    if (dialogMode.value === 'create') {
      await createGoods(formData.value)
      ElMessage.success('新增成功')
    } else if (formData.value.id) {
      await updateGoods(formData.value.id, formData.value)
      ElMessage.success('更新成功')
    }
    dialogVisible.value = false
    await fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '操作失败')
  } finally {
    submitting.value = false
  }
}

async function handleDelete(row: GoodsItem) {
  try {
    await ElMessageBox.confirm(`确认删除物资「${row.name}」吗？`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await deleteGoods(row.id)
    ElMessage.success('删除成功')
    await fetchData()
  } catch (e: any) {
    if (e === 'cancel' || e === 'close') return
    ElMessage.error(e?.response?.data?.detail || e?.message || '删除失败')
  }
}
</script>

<template>
  <div class="page goods-list">
    <div class="page-header">
      <h2>物资管理</h2>
      <el-button v-show="mainTab === 'catalog'" type="primary" :icon="Plus" @click="openCreateDialog">新增物资</el-button>
    </div>

    <el-tabs v-model="mainTab" class="goods-main-tabs">
      <el-tab-pane label="物资档案" name="catalog">
        <div class="search-bar">
          <el-input v-model="searchForm.keyword" placeholder="搜索物资名称" clearable style="width: 260px" />
          <el-select v-model="searchForm.category" placeholder="分类" clearable style="width: 140px">
            <el-option label="食材" value="食材" />
            <el-option label="防疫" value="防疫" />
            <el-option label="办公" value="办公" />
            <el-option label="实验" value="实验" />
          </el-select>
          <el-button type="primary" :icon="Search" @click="fetchData">查询</el-button>
        </div>
        <div class="table-card">
          <el-table :data="tableData" v-loading="loading" stripe style="width: 100%">
            <el-table-column prop="name" label="物资名称" />
            <el-table-column prop="category" label="分类" width="100" />
            <el-table-column prop="spec" label="规格" width="120" />
            <el-table-column prop="unit" label="单位" width="80" />
            <el-table-column prop="safety_level" label="安全等级" width="100">
              <template #default="{ row }">
                <el-tag :type="row.safety_level === 'high' ? 'danger' : 'warning'" size="small">{{ row.safety_level }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="shelf_life_days" label="保质期(天)" width="100" />
            <el-table-column label="操作" width="140" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" :icon="Edit" @click="openEditDialog(row)">编辑</el-button>
                <el-button link type="danger" :icon="Delete" @click="handleDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination class="pagination" layout="total, sizes, prev, pager, next" :total="tableData.length" :page-sizes="[10, 20, 50]" />
        </div>
      </el-tab-pane>

      <el-tab-pane label="库存查询" name="stock">
        <p class="tab-hint">按物资名称、批次检索在库数量与安全线（原「库存查询」已合并至此）</p>
        <div class="search-bar">
          <el-input
            v-model="inventoryKeyword"
            placeholder="搜索物资名 / 关键词"
            clearable
            style="width: 280px"
            @keyup.enter="fetchInventory"
          />
          <el-button type="primary" :icon="Search" @click="fetchInventory">查询</el-button>
        </div>
        <div class="table-card">
          <el-table :data="inventoryRows" v-loading="invLoading" stripe style="width: 100%">
            <el-table-column prop="goods_name" label="物资" min-width="140" />
            <el-table-column prop="category" label="分类" width="100" />
            <el-table-column prop="batch_no" label="批次号" width="140" />
            <el-table-column prop="quantity" label="数量" width="100" />
            <el-table-column prop="unit" label="单位" width="80" />
            <el-table-column label="库存状态" width="160">
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
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="dialogVisible" :title="dialogMode === 'create' ? '新增物资' : '编辑物资'" width="560px">
      <el-form label-width="90px">
        <el-form-item label="物资名称">
          <el-input v-model="formData.name" placeholder="请输入物资名称" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="formData.category" placeholder="请选择分类" style="width: 100%">
            <el-option label="食材" value="食材" />
            <el-option label="防疫" value="防疫" />
            <el-option label="办公" value="办公" />
            <el-option label="实验" value="实验" />
          </el-select>
        </el-form-item>
        <el-form-item label="规格">
          <el-input v-model="formData.spec" placeholder="例如：500g/袋" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="formData.unit" placeholder="例如：件、箱、袋" />
        </el-form-item>
        <el-form-item label="安全等级">
          <el-select v-model="formData.safety_level" style="width: 100%">
            <el-option label="high" value="high" />
            <el-option label="medium" value="medium" />
            <el-option label="low" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="保质期(天)">
          <el-input-number v-model="formData.shelf_life_days" :min="1" :max="3650" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitForm">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.page {
  padding: 0;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.page-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}
.goods-main-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 16px;
  }
}
.tab-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.5;
}
.search-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  align-items: center;
}
.table-card {
  padding: 24px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  box-shadow: var(--shadow-card);
}
.pagination {
  margin-top: 16px;
  justify-content: flex-end;
}
.safe-line {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-muted);
}
</style>
