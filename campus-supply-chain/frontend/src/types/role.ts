// 角色定义
export type RoleType = 'system_admin' | 'logistics_admin' | 'warehouse_procurement' | 'campus_supplier' | 'counselor_teacher'

export const ROLE_LABELS: Record<RoleType, string> = {
  system_admin: '管理员',
  logistics_admin: '后勤管理员',
  warehouse_procurement: '仓储采购员',
  campus_supplier: '校园合作供应商',
  counselor_teacher: '辅导员教师',
}
