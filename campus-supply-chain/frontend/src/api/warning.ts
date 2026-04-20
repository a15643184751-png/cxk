import request from './request'

export interface WarningItem {
  id: number
  level: string
  material: string
  description: string
  status: string
  created_at: string | null
}

export function listWarnings(params?: { status?: string }) {
  return request.get<WarningItem[]>('/warning', { params })
}

export function handleWarning(id: number) {
  return request.put<{ code: number; message: string }>(`/warning/${id}/handle`)
}
