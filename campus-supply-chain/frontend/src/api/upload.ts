import request from './request'

export interface UploadSecurityAlert {
  style?: string
  http_status_hint?: number
  title?: string
  message?: string
  detail?: string
}

export interface UploadResult {
  ok: boolean
  filename: string
  saved_as: string
  size: number
  url: string
  /** 存在时：上传已成功落盘，但应展示安全告警（非成功 Toast） */
  security_alert?: UploadSecurityAlert
}

export function publicUpload(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request.post<UploadResult>('/upload', form)
}

export type QuarantineRiskLevel = 'high' | 'medium' | 'low'

export interface QuarantineItem {
  saved_as: string
  size: number
  modified_at: string
  url: string
  risk_level?: QuarantineRiskLevel
  extension?: string
  /** 前端内存捕获：未落盘 */
  local_only?: boolean
}

export interface QuarantineAnalysis {
  total_bytes: number
  today_count: number
  week_count: number
  high_risk_count: number
  medium_risk_count: number
  by_extension: { ext: string; count: number }[]
  daily_labels: string[]
  daily_counts: number[]
  insights: string[]
  generated_at: string
}

export interface QuarantineListResponse {
  items: QuarantineItem[]
  count: number
  analysis?: QuarantineAnalysis
}

export function listQuarantineFiles(): Promise<QuarantineListResponse> {
  // 拦截器已解包 res.data，与 axios 默认泛型不一致
  return request.get('/upload/quarantine') as Promise<QuarantineListResponse>
}

export function deleteQuarantineFile(savedAs: string) {
  return request.delete<{ ok: boolean }>(`/upload/quarantine/${encodeURIComponent(savedAs)}`)
}
