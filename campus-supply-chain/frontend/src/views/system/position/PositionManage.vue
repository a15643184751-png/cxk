<script setup lang="ts">
import { ref, reactive, computed, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import { Refresh, Plus, Search, Edit, Delete, FullScreen, Grid } from '@element-plus/icons-vue'
import { useSystemManagementStore, type PositionRow } from '@/stores/systemManagement'

const store = useSystemManagementStore()
const { positions } = storeToRefs(store)

const loading = ref(false)
const showFilter = ref(true)
const tableSize = ref<'large' | 'default' | 'small'>('default')
const fullscreenRef = ref<HTMLElement | null>(null)

const filter = ref({ keyword: '' })

const filtered = computed(() => {
  const kw = filter.value.keyword.trim().toLowerCase()
  if (!kw) return positions.value
  return positions.value.filter(
    (p) =>
      p.name.toLowerCase().includes(kw) ||
      p.code.toLowerCase().includes(kw) ||
      (p.remark || '').toLowerCase().includes(kw)
  )
})

const page = ref(1)
const pageSize = ref(20)
const paged = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

watch([filtered, pageSize], () => {
  const max = Math.max(1, Math.ceil(filtered.value.length / pageSize.value) || 1)
  if (page.value > max) page.value = max
})

const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<Partial<PositionRow> & { id?: string }>({
  id: undefined,
  name: '',
  code: '',
  sort: 1,
  enabled: true,
  remark: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入岗位名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入岗位编码', trigger: 'blur' }],
}

function resetForm() {
  form.id = undefined
  form.name = ''
  form.code = ''
  form.sort = 1
  form.enabled = true
  form.remark = ''
}

function openAdd() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: PositionRow) {
  form.id = row.id
  form.name = row.name
  form.code = row.code
  form.sort = row.sort
  form.enabled = row.enabled
  form.remark = row.remark
  dialogVisible.value = true
}

function submitForm() {
  formRef.value?.validate((ok) => {
    if (!ok) return
    const existing = form.id ? positions.value.find((p) => p.id === form.id) : undefined
    const row: PositionRow = {
      id: form.id || '',
      name: form.name!.trim(),
      code: form.code!.trim().toUpperCase(),
      sort: Number(form.sort) || 0,
      enabled: !!form.enabled,
      remark: (form.remark || '').trim(),
      createdAt: existing?.createdAt || new Date().toISOString().slice(0, 19).replace('T', ' '),
    }
    store.upsertPosition(row)
    dialogVisible.value = false
    ElMessage.success(form.id ? '已保存' : '已新增')
  })
}

function rowDelete(row: PositionRow) {
  ElMessageBox.confirm(`确定删除岗位「${row.name}」？`, '提示', { type: 'warning' })
    .then(() => {
      store.deletePosition(row.id)
      ElMessage.success('已删除')
    })
    .catch(() => {})
}

function refresh() {
  loading.value = true
  setTimeout(() => {
    loading.value = false
    ElMessage.success('已刷新')
  }, 200)
}

async function toggleFullscreen() {
  const el = fullscreenRef.value
  if (!el) return
  try {
    if (!document.fullscreenElement) await el.requestFullscreen()
    else await document.exitFullscreen()
  } catch {
    ElMessage.info('当前环境不支持全屏')
  }
}
</script>

<template>
  <div ref="fullscreenRef" class="sys-page art-full-height">
    <el-card v-show="showFilter" shadow="never" class="search-card">
      <el-form :inline="true" @submit.prevent>
        <el-form-item label="关键词">
          <el-input v-model="filter.keyword" clearable placeholder="岗位名称 / 编码" style="width: 220px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search" @click="page = 1">查询</el-button>
          <el-button @click="filter.keyword = ''; page = 1">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <div class="table-toolbar">
        <div class="left">
          <el-button type="primary" :icon="Plus" @click="openAdd">新增岗位</el-button>
        </div>
        <div class="right-tools">
          <el-tooltip content="筛选" placement="top">
            <el-button :icon="Search" circle @click="showFilter = !showFilter" />
          </el-tooltip>
          <el-tooltip content="刷新" placement="top">
            <el-button :icon="Refresh" circle @click="refresh" />
          </el-tooltip>
          <el-dropdown trigger="click" @command="(c: 'large' | 'default' | 'small') => (tableSize = c)">
            <el-button :icon="Grid" circle />
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="large">宽松</el-dropdown-item>
                <el-dropdown-item command="default">默认</el-dropdown-item>
                <el-dropdown-item command="small">紧凑</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
          <el-tooltip content="全屏" placement="top">
            <el-button :icon="FullScreen" circle @click="toggleFullscreen" />
          </el-tooltip>
        </div>
      </div>

      <el-table v-loading="loading" :data="paged" row-key="id" border :size="tableSize">
        <el-table-column type="index" label="序号" width="64" :index="(i: number) => (page - 1) * pageSize + i + 1" />
        <el-table-column prop="name" label="岗位名称" min-width="140" />
        <el-table-column prop="code" label="岗位编码" width="140" />
        <el-table-column prop="sort" label="排序" width="80" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || '—' }}</template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="178" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="openEdit(row)" />
            <el-button type="danger" link :icon="Delete" @click="rowDelete(row)" />
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="filtered.length"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          background
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="form.id ? '编辑岗位' : '新增岗位'"
      width="480px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
        <el-form-item label="岗位名称" prop="name">
          <el-input v-model="form.name" placeholder="请输入岗位名称" />
        </el-form-item>
        <el-form-item label="岗位编码" prop="code">
          <el-input v-model="form.code" placeholder="如 DEV-FE" />
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" :max="9999" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.enabled" active-text="启用" inactive-text="停用" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.sys-page.art-full-height {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: calc(100vh - 120px);
}
.search-card {
  border-radius: 12px;
  :deep(.el-card__body) {
    padding-bottom: 4px;
  }
}
.table-card {
  flex: 1;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  :deep(.el-card__body) {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
}
.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  .right-tools {
    display: flex;
    gap: 8px;
  }
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.sys-page:fullscreen {
  background: var(--el-bg-color);
  padding: 16px;
  overflow: auto;
}
</style>
