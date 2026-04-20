<script setup lang="ts">
import { ref, reactive, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, MoreFilled, Search, ArrowDown } from '@element-plus/icons-vue'
import type { RoleType } from '@/types/role'
import { ROLE_LABELS } from '@/types/role'

/** 列表行：含扩展角色行；campusRole 为内置五角色 */
interface RoleRow {
  roleId: number
  roleName: string
  roleCode: string
  description: string
  enabled: boolean
  createTime: string
  campusRole?: RoleType
}

function pad(n: number) {
  return n < 10 ? `0${n}` : String(n)
}

function randomTime(seed: number) {
  const h = seed % 12
  const m = (seed * 7) % 60
  const s = (seed * 13) % 60
  return `2026-${pad((seed % 11) + 1)}-${pad((seed % 27) + 1)} ${pad(h + 8)}:${pad(m)}:${pad(s)}`
}

function campusDescription(code: RoleType): string {
  const m: Record<RoleType, string> = {
    system_admin: '全局配置、用户与角色、审计日志与安全中心',
    logistics_admin: '采购审批、预警处置、后勤与全景大屏',
    warehouse_procurement: '入库出库、库存、配送协同；侧栏「仓储大屏」为仓储数据大屏',
    campus_supplier: '订单履约、物流回传与协同门户',
    counselor_teacher: '智能工作台、日程规划、个人中心、采购申请与溯源',
  }
  return m[code]
}

const campusCodes: Record<RoleType, string> = {
  system_admin: 'R_SYS_ADMIN',
  logistics_admin: 'R_LOGISTICS',
  warehouse_procurement: 'R_WAREHOUSE',
  campus_supplier: 'R_SUPPLIER',
  counselor_teacher: 'R_TEACHER',
}

function buildAllRows(): RoleRow[] {
  const base = (Object.keys(ROLE_LABELS) as RoleType[]).map((code, i) => ({
    roleId: i + 1,
    roleName: ROLE_LABELS[code],
    roleCode: campusCodes[code],
    description: campusDescription(code),
    enabled: true,
    createTime: randomTime(100 + i),
    campusRole: code,
  }))

  const templates: Omit<RoleRow, 'roleId' | 'createTime'>[] = [
    { roleName: '超级管理员', roleCode: 'R_SUPER', description: '拥有系统全部操作权限', enabled: true },
    { roleName: '运营', roleCode: 'R_OPS', description: '负责业务运营与数据看板', enabled: true },
    { roleName: '测试', roleCode: 'R_TEST', description: '测试环境联调与验收', enabled: false },
    { roleName: '访客', roleCode: 'R_GUEST', description: '只读浏览公开报表', enabled: true },
    { roleName: '项目经理', roleCode: 'R_PM', description: '项目里程碑与供应商协调', enabled: true },
    { roleName: '数据分析师', roleCode: 'R_DATA', description: '采购与库存数据分析', enabled: true },
    { roleName: '质检专员', roleCode: 'R_QC', description: '到货质检与溯源核对', enabled: true },
    { roleName: '车队调度', roleCode: 'R_FLEET', description: '配送路线与在途监控', enabled: false },
    { roleName: '财务对账', roleCode: 'R_FIN', description: '采购对账与发票核验', enabled: true },
    { roleName: '安全审计', roleCode: 'R_AUDIT', description: '操作审计与异常复核', enabled: true },
  ]

  const extra: RoleRow[] = []
  for (let i = 6; i <= 100; i++) {
    const t = templates[(i - 6) % templates.length]
    const gen = Math.floor((i - 6) / templates.length)
    extra.push({
      roleId: i,
      roleName: gen ? `${t.roleName} · ${gen}` : t.roleName,
      roleCode: gen ? `${t.roleCode}_${gen}` : t.roleCode,
      description: `${t.description}（#${i}）`,
      enabled: (i + gen) % 7 !== 0,
      createTime: randomTime(i * 17),
    })
  }

  return [...base, ...extra]
}

const tableData = ref<RoleRow[]>(buildAllRows())
const loading = ref(false)
const searchKeyword = ref('')
const showSearchBar = ref(false)

const page = ref(1)
const pageSize = ref(20)

const filteredList = computed(() => {
  const kw = searchKeyword.value.trim().toLowerCase()
  if (!kw) return tableData.value
  return tableData.value.filter(
    (r) =>
      r.roleName.toLowerCase().includes(kw) ||
      r.roleCode.toLowerCase().includes(kw) ||
      r.description.toLowerCase().includes(kw)
  )
})

const pagedData = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredList.value.slice(start, start + pageSize.value)
})

watch(filteredList, () => {
  const maxPage = Math.max(1, Math.ceil(filteredList.value.length / pageSize.value) || 1)
  if (page.value > maxPage) page.value = maxPage
})

function handleSizeChange(n: number) {
  pageSize.value = n
  page.value = 1
}

function handlePageChange(n: number) {
  page.value = n
}

function refreshData() {
  loading.value = true
  setTimeout(() => {
    loading.value = false
    ElMessage.success('已刷新')
  }, 320)
}

const permDialogVisible = ref(false)
const permTitle = ref('')
const permDefaultKeys = ref<string[]>([])
const permTreeKey = ref(0)
const permTreeRef = ref<{ setCheckedKeys: (keys: string[], leafOnly?: boolean) => void }>()
const currentRow = ref<RoleRow | null>(null)

const menuTree = [
  {
    id: 'dash',
    label: '工作台',
    children: [
      { id: 'dashboard', label: '工作台' },
      { id: 'panorama', label: '全景大屏' },
    ],
  },
  {
    id: 'biz',
    label: '业务管理',
    children: [
      { id: 'goods', label: '物资管理' },
      { id: 'purchase', label: '审批台' },
      { id: 'purchase_apply', label: '采购申请' },
      { id: 'trace', label: '溯源查询' },
      { id: 'warning', label: '预警中心' },
      { id: 'ai', label: 'AI 助手' },
    ],
  },
  {
    id: 'stock',
    label: '仓储与配送',
    children: [
      { id: 'stock_in', label: '入库管理' },
      { id: 'stock_out', label: '出库管理' },
      { id: 'inventory', label: '库存查询' },
      { id: 'delivery', label: '配送管理' },
      { id: 'delivery_map', label: '配送地图' },
      { id: 'wh_screen', label: '仓储大屏（与侧栏入口一致）' },
    ],
  },
  {
    id: 'teacher',
    label: '教师工作台',
    children: [
      { id: 'teacher_wb', label: '智能工作台' },
      { id: 'teacher_sched', label: '日程与规划' },
      { id: 'teacher_personal', label: '个人中心' },
    ],
  },
  {
    id: 'supplier_portal',
    label: '供应商门户',
    children: [
      { id: 'sup_orders', label: '我的订单' },
      { id: 'sup_log', label: '物流-仓储配送' },
    ],
  },
  {
    id: 'sys',
    label: '系统管理',
    children: [
      { id: 'users', label: '用户管理' },
      { id: 'roles', label: '角色管理' },
      { id: 'supplier', label: '供应商管理' },
      { id: 'operation_logs', label: '操作日志与审计' },
      { id: 'login_logs', label: '登录日志' },
      { id: 'file_center', label: '文件中心' },
      { id: 'positions', label: '岗位管理' },
      { id: 'departments', label: '部门管理' },
    ],
  },
  {
    id: 'sec',
    label: '安全中心',
    children: [
      { id: 'ids', label: 'IDS 入侵检测' },
      { id: 'situation', label: '安全态势感知' },
      { id: 'sandbox', label: '安全沙箱' },
    ],
  },
  {
    id: 'screen',
    label: '数据大屏',
    children: [{ id: 'log_screen', label: '后勤大屏' }],
  },
]

function mockKeysForRole(code: RoleType): string[] {
  if (code === 'system_admin') {
    return menuTree.flatMap((n) => [n.id, ...(n.children?.map((c) => c.id) || [])])
  }
  if (code === 'logistics_admin') {
    return ['dash', 'dashboard', 'panorama', 'biz', 'goods', 'purchase', 'trace', 'warning', 'ai', 'screen', 'log_screen']
  }
  if (code === 'warehouse_procurement') {
    return [
      'dash',
      'dashboard',
      'panorama',
      'biz',
      'goods',
      'trace',
      'warning',
      'ai',
      'stock',
      'stock_in',
      'stock_out',
      'inventory',
      'delivery',
      'delivery_map',
      'wh_screen',
      'screen',
      'log_screen',
    ]
  }
  if (code === 'campus_supplier') {
    return ['dash', 'dashboard', 'panorama', 'supplier_portal', 'sup_orders', 'sup_log', 'screen']
  }
  return ['biz', 'purchase_apply', 'trace', 'teacher', 'teacher_wb', 'teacher_sched', 'teacher_personal']
}

function demoKeysForExtraRow(row: RoleRow): string[] {
  const k = row.roleId % 5
  const pools = [
    ['dash', 'dashboard', 'biz', 'goods', 'trace'],
    ['dash', 'dashboard', 'stock', 'stock_in', 'inventory'],
    ['dash', 'dashboard', 'supplier_portal', 'sup_orders'],
    ['dash', 'dashboard', 'sys', 'users', 'roles', 'supplier'],
    ['dash', 'dashboard', 'sec', 'ids', 'situation'],
  ]
  return pools[k]
}

function openPerm(row: RoleRow) {
  currentRow.value = row
  permTitle.value = `菜单权限 · ${row.roleName}`
  const keys = row.campusRole ? mockKeysForRole(row.campusRole) : demoKeysForExtraRow(row)
  permDefaultKeys.value = keys
  permTreeKey.value += 1
  permDialogVisible.value = true
  nextTick(() => {
    permTreeRef.value?.setCheckedKeys(permDefaultKeys.value, false)
  })
}

function savePerm() {
  ElMessage.success('已保存；实际权限以登录角色为准')
  permDialogVisible.value = false
}

const editVisible = ref(false)
const addVisible = ref(false)
const editForm = reactive({ roleName: '', description: '', roleCode: '' })
const addForm = reactive({ roleName: '', description: '', roleCode: '' })

function openEdit(row: RoleRow) {
  currentRow.value = row
  editForm.roleName = row.roleName
  editForm.description = row.description
  editForm.roleCode = row.roleCode
  editVisible.value = true
}

function saveEdit() {
  const row = tableData.value.find((r) => r.roleId === currentRow.value?.roleId)
  if (row) {
    row.roleName = editForm.roleName.trim() || row.roleName
    row.description = editForm.description.trim() || row.description
    if (!row.campusRole) {
      row.roleCode = (editForm.roleCode || row.roleCode).trim() || row.roleCode
    }
  }
  ElMessage.success('已更新')
  editVisible.value = false
}

function openAdd() {
  addForm.roleName = ''
  addForm.description = ''
  addForm.roleCode = `R_NEW_${Date.now().toString(36).slice(-4).toUpperCase()}`
  addVisible.value = true
}

function saveAdd() {
  if (!addForm.roleName.trim()) {
    ElMessage.warning('请输入角色名称')
    return
  }
  const nextId = Math.max(...tableData.value.map((r) => r.roleId)) + 1
  tableData.value.unshift({
    roleId: nextId,
    roleName: addForm.roleName.trim(),
    roleCode: addForm.roleCode.trim() || `R_${nextId}`,
    description: addForm.description.trim() || '新建角色',
    enabled: true,
    createTime: randomTime(nextId * 31),
  })
  page.value = 1
  ElMessage.success('已添加')
  addVisible.value = false
}

function onDelete(row: RoleRow) {
  if (row.campusRole) {
    ElMessageBox.alert('内置校园角色不可删除；扩展角色行可移除。', '提示', { type: 'info' })
    return
  }
  ElMessageBox.confirm(`确定删除角色「${row.roleName}」吗？`, '删除确认', {
    type: 'warning',
  })
    .then(() => {
      const i = tableData.value.findIndex((r) => r.roleId === row.roleId)
      if (i >= 0) tableData.value.splice(i, 1)
      ElMessage.success('已删除')
    })
    .catch(() => {})
}

function onDropdownCommand(cmd: string, row: RoleRow) {
  if (cmd === 'perm') openPerm(row)
  else if (cmd === 'edit') openEdit(row)
  else if (cmd === 'delete') onDelete(row)
}
</script>

<template>
  <div class="role-page art-full-height">
    <el-collapse-transition>
      <el-card v-show="showSearchBar" shadow="never" class="search-card">
        <el-form :inline="true" class="search-form" @submit.prevent>
          <el-form-item label="关键词">
            <el-input v-model="searchKeyword" clearable placeholder="角色名称 / 标识 / 描述" style="width: 260px" />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :icon="Search" @click="page = 1">查询</el-button>
            <el-button
              @click="
                searchKeyword = '';
                page = 1;
              "
            >
              重置
            </el-button>
          </el-form-item>
        </el-form>
      </el-card>
    </el-collapse-transition>

    <el-card shadow="never" class="table-card art-table-card">
      <div class="table-head">
        <div class="table-head-left">
          <el-button type="primary" :icon="Plus" @click="openAdd">新增角色</el-button>
          <el-button text type="primary" class="toggle-search" @click="showSearchBar = !showSearchBar">
            {{ showSearchBar ? '收起筛选' : '展开筛选' }}
            <el-icon class="chev" :class="{ rotated: showSearchBar }"><ArrowDown /></el-icon>
          </el-button>
        </div>
        <el-button :icon="Refresh" circle @click="refreshData" />
      </div>

      <el-table
        v-loading="loading"
        :data="pagedData"
        row-key="roleId"
        class="role-table"
        :border="false"
        stripe
      >
        <el-table-column prop="roleId" label="角色ID" width="88" />
        <el-table-column prop="roleName" label="角色名称" min-width="132" show-overflow-tooltip />
        <el-table-column prop="roleCode" label="角色标识" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="mono">{{ row.roleCode }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="角色描述" min-width="200" show-overflow-tooltip />
        <el-table-column label="角色状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.enabled" type="success" effect="light" size="small">启用</el-tag>
            <el-tag v-else type="warning" effect="light" size="small">禁用</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="createTime" label="创建日期" width="178" sortable />
        <el-table-column label="操作" width="72" align="center" fixed="right">
          <template #default="{ row }">
            <el-dropdown trigger="click" @command="(c: string) => onDropdownCommand(c, row)">
              <el-button text class="more-btn" aria-label="更多">
                <el-icon :size="18"><MoreFilled /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="perm">菜单权限</el-dropdown-item>
                  <el-dropdown-item command="edit">编辑角色</el-dropdown-item>
                  <el-dropdown-item command="delete" divided>删除角色</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="filteredList.length"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-dialog v-model="permDialogVisible" :title="permTitle" width="520px" destroy-on-close align-center>
      <el-tree
        :key="permTreeKey"
        ref="permTreeRef"
        :data="menuTree"
        node-key="id"
        show-checkbox
        default-expand-all
        :props="{ label: 'label', children: 'children' }"
        :default-checked-keys="permDefaultKeys"
      />
      <template #footer>
        <el-button @click="permDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePerm">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑角色" width="460px" destroy-on-close align-center>
      <el-form :model="editForm" label-width="96px">
        <el-form-item label="角色名称">
          <el-input v-model="editForm.roleName" />
        </el-form-item>
        <el-form-item v-if="!currentRow?.campusRole" label="角色标识">
          <el-input v-model="editForm.roleCode" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">确定</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="addVisible" title="新增角色" width="460px" destroy-on-close align-center>
      <el-form :model="addForm" label-width="96px">
        <el-form-item label="角色名称" required>
          <el-input v-model="addForm.roleName" placeholder="如：供应链协调员" />
        </el-form-item>
        <el-form-item label="角色标识">
          <el-input v-model="addForm.roleCode" placeholder="如：R_SCM" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="addForm.description" type="textarea" :rows="3" placeholder="职责说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" @click="saveAdd">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.art-full-height {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: calc(100vh - 120px);
}

.search-card {
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter);
  :deep(.el-card__body) {
    padding: 16px 20px 8px;
  }
}

.table-card {
  flex: 1;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  :deep(.el-card__body) {
    padding: 16px 20px 20px;
  }
}

.table-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.table-head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.toggle-search {
  font-weight: 400;
  .chev {
    margin-left: 4px;
    vertical-align: middle;
    transition: transform 0.2s ease;
    &.rotated {
      transform: rotate(180deg);
    }
  }
}

.role-table {
  width: 100%;
  --el-table-border-color: transparent;
  --el-table-header-bg-color: #fafafa;
  --el-table-row-hover-bg-color: #f5f7ff;
  :deep(.el-table__inner-wrapper::before) {
    display: none;
  }
  :deep(.el-table__header th) {
    font-weight: 600;
    color: var(--el-text-color-regular);
    font-size: 13px;
  }
  :deep(.el-table__body td) {
    border-bottom: 1px solid #f0f0f0;
    font-size: 13px;
  }
  :deep(.el-table__body tr:last-child td) {
    border-bottom: none;
  }
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.more-btn {
  padding: 4px 8px;
  color: var(--el-text-color-secondary);
  &:hover {
    color: var(--el-color-primary);
    background: rgba(22, 119, 255, 0.06);
  }
}

.pager-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
  padding-top: 4px;
}
</style>
