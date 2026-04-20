import request from './request'

export interface AuditItem {
  id: number
  user_name: string
  user_role: string
  action: string
  target_type: string
  target_id: string
  detail: string
  created_at: string | null
}

export function listAuditLogs(params?: { action?: string; target_type?: string }) {
  return request.get<AuditItem[]>('/audit', { params })
}
