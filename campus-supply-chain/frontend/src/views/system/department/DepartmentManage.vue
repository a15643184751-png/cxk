<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { FormInstance, FormRules } from 'element-plus'
import {
  Refresh,
  Search,
  Plus,
  Edit,
  Delete,
  FullScreen,
  Grid,
  CirclePlus,
} from '@element-plus/icons-vue'
import {
  useSystemManagementStore,
  type DepartmentRow,
  type DepartmentTreeNode,
  departmentDescendantIds,
} from '@/stores/systemManagement'

const store = useSystemManagementStore()
const { departmentTree, departments } = storeToRefs(store)

const loading = ref(false)
const showFilter = ref(true)
const tableSize = ref<'large' | 'default' | 'small'>('default')
const fullscreenRef = ref<HTMLElement | null>(null)
const expandAll = ref(true)
const expandTick = ref(0)
function toggleExpandTree() {
  expandAll.value = !expandAll.value
  expandTick.value += 1
}

const filter = ref({ keyword: '' })

function filterTree(nodes: DepartmentTreeNode[], kw: string): DepartmentTreeNode[] {
  if (!kw) return nodes
  const lower = kw.toLowerCase()
  const out: DepartmentTreeNode[] = []
  for (const n of nodes) {
    const selfMatch = n.name.toLowerCase().includes(lower) || n.code.toLowerCase().includes(lower)
    const children = n.children ? filterTree(n.children, kw) : []
    if (selfMatch || children.length) {
      out.push({
        ...n,
        children: children.length ? children : n.children,
      })
    }
  }
  return out
}

const displayTree = computed(() => filterTree(departmentTree.value, filter.value.keyword.trim()))

const dialogVisible = ref(false)
const formRef = ref<FormInstance>()
const form = reactive<Partial<DepartmentRow> & { id?: string }>({
  id: undefined,
  parentId: null,
  name: '',
  code: '',
  leader: '',
  phone: '',
  email: '',
  sort: 1,
  enabled: true,
  remark: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请输入部门名称', trigger: 'blur' }],
  code: [{ required: true, message: '请输入部门编码', trigger: 'blur' }],
}

const parentOptions = computed(() => {
  const ex = form.id ? departmentDescendantIds(departments.value, form.id) : new Set<string>()
  const opts: { label: string; value: string | null }[] = [{ label: '无（顶级部门）', value: null }]
  function walk(nodes: DepartmentTreeNode[], depth: number) {
    const pad = '\u3000'.repeat(depth)
    for (const n of nodes) {
      if (ex.has(n.id)) continue
      opts.push({ value: n.id, label: pad + n.name })
      if (n.children?.length) walk(n.children, depth + 1)
    }
  }
  walk(departmentTree.value, 0)
  return opts
})

function resetForm() {
  form.id = undefined
  form.parentId = null
  form.name = ''
  form.code = ''
  form.leader = ''
  form.phone = ''
  form.email = ''
  form.sort = 1
  form.enabled = true
  form.remark = ''
}

function openAdd(parentId: string | null = null) {
  resetForm()
  form.parentId = parentId
  dialogVisible.value = true
}

function openEdit(row: DepartmentRow) {
  form.id = row.id
  form.parentId = row.parentId
  form.name = row.name
  form.code = row.code
  form.leader = row.leader
  form.phone = row.phone
  form.email = row.email
  form.sort = row.sort
  form.enabled = row.enabled
  form.remark = row.remark
  dialogVisible.value = true
}

function submitForm() {
  formRef.value?.validate((ok) => {
    if (!ok) return
    const row: DepartmentRow = {
      id: form.id || '',
      parentId: form.parentId ?? null,
      name: form.name!.trim(),
      code: form.code!.trim(),
      leader: (form.leader || '').trim(),
      phone: (form.phone || '').trim(),
      email: (form.email || '').trim(),
      sort: Number(form.sort) || 0,
      enabled: !!form.enabled,
      remark: (form.remark || '').trim(),
      updatedAt: '',
    }
    store.upsertDepartment(row)
    dialogVisible.value = false
    ElMessage.success(form.id ? '已保存' : '已新增')
  })
}

function rowDelete(row: DepartmentRow) {
  ElMessageBox.confirm(`确定删除部门「${row.name}」及其下级？`, '提示', { type: 'warning' })
    .then(() => {
      store.deleteDepartment(row.id)
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
          <el-input v-model="filter.keyword" clearable placeholder="部门名称 / 编码" style="width: 220px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :icon="Search">查询</el-button>
          <el-button @click="filter.keyword = ''">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <div class="table-toolbar">
        <div class="left">
          <el-button type="primary" :icon="Plus" @click="openAdd(null)">新增部门</el-button>
          <el-button @click="toggleExpandTree">{{ expandAll ? '折叠全部' : '展开全部' }}</el-button>
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

      <el-table
        :key="expandTick"
        v-loading="loading"
        :data="displayTree"
        row-key="id"
        border
        :size="tableSize"
        :default-expand-all="expandAll"
        :tree-props="{ children: 'children' }"
      >
        <el-table-column prop="name" label="部门名称" min-width="200" show-overflow-tooltip />
        <el-table-column prop="code" label="部门编码" width="110" />
        <el-table-column prop="leader" label="负责人" width="100" show-overflow-tooltip>
          <template #default="{ row }">{{ row.leader || '—' }}</template>
        </el-table-column>
        <el-table-column prop="phone" label="联系电话" width="130" show-overflow-tooltip>
          <template #default="{ row }">{{ row.phone || '—' }}</template>
        </el-table-column>
        <el-table-column prop="email" label="邮箱" min-width="160" show-overflow-tooltip>
          <template #default="{ row }">{{ row.email || '—' }}</template>
        </el-table-column>
        <el-table-column prop="sort" label="排序" width="72" />
        <el-table-column label="状态" width="88">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" size="small">{{ row.enabled ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="updatedAt" label="更新时间" width="178" />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-tooltip content="新增子部门" placement="top">
              <el-button type="primary" link :icon="CirclePlus" @click="openAdd(row.id)" />
            </el-tooltip>
            <el-button type="primary" link :icon="Edit" @click="openEdit(row)" />
            <el-button type="danger" link :icon="Delete" @click="rowDelete(row)" />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="form.id ? '编辑部门' : '新增部门'"
      width="640px"
      destroy-on-close
      class="dept-dlg"
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="上级部门">
              <el-select v-model="form.parentId" clearable filterable placeholder="无则顶级" style="width: 100%">
                <el-option
                  v-for="(o, idx) in parentOptions"
                  :key="`${idx}-${o.value ?? 'root'}`"
                  :label="o.label"
                  :value="o.value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="排序">
              <el-input-number v-model="form.sort" :min="0" :max="9999" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="部门名称" prop="name">
              <el-input v-model="form.name" placeholder="请输入部门名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="部门编码" prop="code">
              <el-input v-model="form.code" placeholder="如 RD" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="负责人">
              <el-input v-model="form.leader" placeholder="请输入负责人" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="联系电话">
              <el-input v-model="form.phone" placeholder="请输入联系电话" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="邮箱">
              <el-input v-model="form.email" placeholder="请输入邮箱" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-switch v-model="form.enabled" active-text="启用" inactive-text="停用" />
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="备注">
              <el-input v-model="form.remark" type="textarea" :rows="3" placeholder="请输入备注" />
            </el-form-item>
          </el-col>
        </el-row>
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
  .left {
    display: flex;
    gap: 8px;
  }
  .right-tools {
    display: flex;
    gap: 8px;
  }
}
.sys-page:fullscreen {
  background: var(--el-bg-color);
  padding: 16px;
  overflow: auto;
}
</style>
