export type RoleType = 'ids_admin' | 'ids_operator' | 'ids_auditor' | 'ids_viewer'

export const ROLE_LABELS: Record<RoleType, string> = {
  ids_admin: 'IDS 管理员',
  ids_operator: 'IDS 处置员',
  ids_auditor: 'IDS 审计员',
  ids_viewer: 'IDS 观察员',
}
