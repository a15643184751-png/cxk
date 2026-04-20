import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

function uid(prefix: string) {
  return `${prefix}${Date.now()}${Math.random().toString(36).slice(2, 8)}`
}

/** —— 操作日志 —— */
export type OpType = 'query' | 'add' | 'delete' | 'update'

export interface OperationLogRow {
  id: string
  module: string
  opType: OpType
  operator: string
  ip: string
  status: 'success' | 'fail'
  createdAt: string
  costMs: number
  requestJson: string
  responseJson: string
}

const OP_TYPE_LABEL: Record<OpType, string> = {
  query: '查询',
  add: '新增',
  delete: '删除',
  update: '修改',
}

function seedOperationLogs(): OperationLogRow[] {
  const base = new Date('2026-04-12T10:00:00')
  const mods = ['物资分类', '岗位管理', '角色管理', '用户管理', '菜单管理', '部门管理', '文件中心', '参数设置']
  const ops: OpType[] = ['query', 'add', 'delete', 'update']
  const users = ['Super', 'admin', 'auditor01']
  return Array.from({ length: 24 }, (_, i) => {
    const t = new Date(base.getTime() - i * 3600_000)
    const op = ops[i % ops.length]
    const ok = i % 11 !== 0
    return {
      id: `OP${1776000000000000 + i}`,
      module: mods[i % mods.length],
      opType: op,
      operator: users[i % users.length],
      ip: `192.168.1.${(i % 200) + 10}`,
      status: ok ? 'success' : 'fail',
      createdAt: t.toISOString().slice(0, 19).replace('T', ' '),
      costMs: 5 + (i % 20) * 3,
      requestJson: JSON.stringify({ path: `/api/sys/${mods[i % mods.length]}`, method: op === 'query' ? 'GET' : 'POST', query: { page: 1 } }, null, 2),
      responseJson: JSON.stringify({ code: ok ? 0 : 500, message: ok ? 'ok' : 'timeout', data: ok ? { rows: 10 } : null }, null, 2),
    }
  })
}

/** —— 登录日志 —— */
export interface LoginLogRow {
  id: string
  userId: string
  username: string
  device: string
  ip: string
  location: string
  os: string
  browser: string
  status: 'success' | 'fail'
  message: string
  createdAt: string
}

function seedLoginLogs(): LoginLogRow[] {
  const base = new Date('2026-04-13T08:00:00')
  const browsers = ['Chrome', 'Edge', 'Safari']
  const oss = ['Windows', 'macOS', 'Linux']
  return Array.from({ length: 28 }, (_, i) => {
    const t = new Date(base.getTime() - i * 1800_000)
    const ok = i % 9 !== 0
    return {
      id: `LG${1776048281448550000 + i}`,
      userId: String(10000 + i),
      username: i % 4 === 0 ? 'Super' : `user_${i}`,
      device: 'pc',
      ip: `10.0.${(i % 5) + 1}.${(i % 200) + 2}`,
      location: i % 6 === 0 ? '未知' : ['上海', '北京', '广州', '成都'][i % 4],
      os: oss[i % oss.length],
      browser: browsers[i % browsers.length],
      status: ok ? 'success' : 'fail',
      message: ok ? (i % 3 === 0 ? '刷新 token 成功' : '登录成功') : '验证码错误',
      createdAt: t.toISOString().slice(0, 19).replace('T', ' '),
    }
  })
}

/** —— 文件中心 —— */
export interface FileCenterRow {
  id: string
  name: string
  path: string
  size: number
  ext: string
  uploader: string
  createdAt: string
  thumbColor: string
}

function seedFiles(): FileCenterRow[] {
  const colors = ['#6366f1', '#0d9488', '#ea580c', '#7c3aed', '#0891b2']
  return [
    { id: 'f1', name: '供应商资质.pdf', path: '/upload/2026/04/supplier-qual.pdf', size: 1024 * 820, ext: 'pdf', uploader: 'admin', createdAt: '2026-04-12 11:20:00', thumbColor: colors[0] },
    { id: 'f2', name: '配送路线示意图.png', path: '/upload/2026/04/route-map.png', size: 1024 * 420, ext: 'png', uploader: 'logistics', createdAt: '2026-04-11 16:05:33', thumbColor: colors[1] },
    { id: 'f3', name: '库存盘点模板.xlsx', path: '/upload/2026/03/stock-template.xlsx', size: 1024 * 56, ext: 'xlsx', uploader: 'warehouse', createdAt: '2026-04-10 09:12:00', thumbColor: colors[2] },
    { id: 'f4', name: '安全演练记录.docx', path: '/upload/2026/04/security-drill.docx', size: 1024 * 240, ext: 'docx', uploader: 'Super', createdAt: '2026-04-09 14:40:12', thumbColor: colors[3] },
    { id: 'f5', name: '大屏背景.webp', path: '/upload/2026/04/screen-bg.webp', size: 1024 * 1800, ext: 'webp', uploader: 'admin', createdAt: '2026-04-08 20:01:55', thumbColor: colors[4] },
  ]
}

/** —— 岗位 —— */
export interface PositionRow {
  id: string
  name: string
  code: string
  sort: number
  enabled: boolean
  remark: string
  createdAt: string
}

function seedPositions(): PositionRow[] {
  const rows: PositionRow[] = [
    { id: 'p1', name: '运维工程师', code: 'OPS-ENG', sort: 1, enabled: true, remark: '', createdAt: '2026-01-10 10:00:00' },
    { id: 'p2', name: '测试工程师', code: 'QA-ENG', sort: 1, enabled: true, remark: '', createdAt: '2026-01-10 10:00:00' },
    { id: 'p3', name: '前端开发工程师', code: 'DEV-FE', sort: 1, enabled: true, remark: '供应链前端', createdAt: '2026-01-12 09:30:00' },
    { id: 'p4', name: '后勤调度', code: 'LOG-DISPATCH', sort: 2, enabled: true, remark: '-', createdAt: '2026-02-01 14:00:00' },
    { id: 'p5', name: '仓储主管', code: 'WH-LEAD', sort: 3, enabled: false, remark: '冻结', createdAt: '2026-02-15 11:11:11' },
  ]
  return rows
}

/** —— 部门（扁平，树由 getter 组装） —— */
export interface DepartmentRow {
  id: string
  parentId: string | null
  name: string
  code: string
  leader: string
  phone: string
  email: string
  sort: number
  enabled: boolean
  remark: string
  updatedAt: string
}

export type DepartmentTreeNode = DepartmentRow & { children?: DepartmentTreeNode[] }

function seedDepartments(): DepartmentRow[] {
  return [
    { id: 'd1', parentId: null, name: '研发中心', code: 'RD', leader: '张三', phone: '13800000001', email: 'rd@campus.edu', sort: 1, enabled: true, remark: '', updatedAt: '2026-04-08 09:19:50' },
    { id: 'd2', parentId: 'd1', name: '产品部', code: 'PD', leader: '', phone: '', email: '', sort: 1, enabled: true, remark: '', updatedAt: '2026-04-08 09:19:50' },
    { id: 'd3', parentId: 'd1', name: '研发一组', code: 'RD-G1', leader: '李四', phone: '', email: '', sort: 2, enabled: true, remark: '', updatedAt: '2026-04-07 15:00:00' },
    { id: 'd4', parentId: null, name: '运营中心', code: 'OP', leader: '', phone: '', email: '', sort: 2, enabled: true, remark: '', updatedAt: '2026-04-06 12:00:00' },
    { id: 'd5', parentId: 'd4', name: '后勤调度部', code: 'OP-LOG', leader: '王五', phone: '13900000002', email: 'log@campus.edu', sort: 1, enabled: true, remark: '', updatedAt: '2026-04-05 10:30:00' },
    { id: 'd6', parentId: null, name: '供应链管理部', code: 'SCM', leader: '', phone: '', email: '', sort: 3, enabled: true, remark: '', updatedAt: '2026-04-04 08:00:00' },
  ]
}

function buildDepartmentTree(flat: DepartmentRow[]): DepartmentTreeNode[] {
  const map = new Map<string, DepartmentTreeNode>()
  for (const d of flat) {
    map.set(d.id, { ...d, children: [] })
  }
  const roots: DepartmentTreeNode[] = []
  for (const d of flat) {
    const node = map.get(d.id)!
    if (d.parentId && map.has(d.parentId)) {
      map.get(d.parentId)!.children!.push(node)
    } else {
      roots.push(node)
    }
  }
  function sortTree(nodes: DepartmentTreeNode[]) {
    nodes.sort((a, b) => a.sort - b.sort || a.name.localeCompare(b.name))
    for (const n of nodes) {
      if (n.children?.length) sortTree(n.children)
      else delete n.children
    }
  }
  sortTree(roots)
  return roots
}

export function departmentDescendantIds(flat: DepartmentRow[], id: string): Set<string> {
  const set = new Set<string>([id])
  let growing = true
  while (growing) {
    growing = false
    for (const d of flat) {
      if (d.parentId && set.has(d.parentId) && !set.has(d.id)) {
        set.add(d.id)
        growing = true
      }
    }
  }
  return set
}

export function formatFileSize(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(2)} MB`
}

export const useSystemManagementStore = defineStore('systemManagement', () => {
  const operationLogs = ref<OperationLogRow[]>(seedOperationLogs())
  const loginLogs = ref<LoginLogRow[]>(seedLoginLogs())
  const files = ref<FileCenterRow[]>(seedFiles())
  const positions = ref<PositionRow[]>(seedPositions())
  const departments = ref<DepartmentRow[]>(seedDepartments())

  const departmentTree = computed(() => buildDepartmentTree(departments.value))

  function removeOperationLogs(ids: string[]) {
    const s = new Set(ids)
    operationLogs.value = operationLogs.value.filter((x) => !s.has(x.id))
  }

  function removeLoginLogs(ids: string[]) {
    const s = new Set(ids)
    loginLogs.value = loginLogs.value.filter((x) => !s.has(x.id))
  }

  function removeFiles(ids: string[]) {
    const s = new Set(ids)
    files.value = files.value.filter((x) => !s.has(x.id))
  }

  function addMockFile(payload: { name: string; size: number; ext: string; uploader: string }) {
    const id = uid('f')
    const safe = payload.name.replace(/[^\w\u4e00-\u9fa5.-]/g, '_')
    files.value.unshift({
      id,
      name: payload.name,
      path: `/upload/2026/04/${safe}`,
      size: payload.size,
      ext: payload.ext,
      uploader: payload.uploader,
      createdAt: new Date().toISOString().slice(0, 19).replace('T', ' '),
      thumbColor: ['#6366f1', '#0d9488', '#ea580c', '#7c3aed', '#0891b2'][files.value.length % 5],
    })
  }

  function upsertPosition(row: PositionRow) {
    const i = positions.value.findIndex((p) => p.id === row.id)
    if (i >= 0) positions.value[i] = { ...row }
    else positions.value.unshift({ ...row, id: row.id || uid('p'), createdAt: row.createdAt || new Date().toISOString().slice(0, 19).replace('T', ' ') })
  }

  function deletePosition(id: string) {
    positions.value = positions.value.filter((p) => p.id !== id)
  }

  function upsertDepartment(row: DepartmentRow) {
    const i = departments.value.findIndex((d) => d.id === row.id)
    if (i >= 0) departments.value[i] = { ...row, updatedAt: new Date().toISOString().slice(0, 19).replace('T', ' ') }
    else
      departments.value.push({
        ...row,
        id: row.id || uid('d'),
        updatedAt: new Date().toISOString().slice(0, 19).replace('T', ' '),
      })
  }

  function deleteDepartment(id: string) {
    const drop = departmentDescendantIds(departments.value, id)
    departments.value = departments.value.filter((d) => !drop.has(d.id))
  }

  function opTypeLabel(t: OpType) {
    return OP_TYPE_LABEL[t]
  }

  return {
    operationLogs,
    loginLogs,
    files,
    positions,
    departments,
    departmentTree,
    removeOperationLogs,
    removeLoginLogs,
    removeFiles,
    addMockFile,
    upsertPosition,
    deletePosition,
    upsertDepartment,
    deleteDepartment,
    opTypeLabel,
    formatFileSize,
  }
})
