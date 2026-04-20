import request from './request'

export interface UploadSecurityAlert {
  style?: string
  http_status_hint?: number
  title?: string
  message?: string
  detail?: string
}

export type UploadState = 'accepted' | 'quarantined'
export type UploadAuditVerdict = 'pass' | 'review' | 'quarantine' | 'accepted' | 'quarantined'
export type QuarantineRiskLevel = 'high' | 'medium' | 'low'
export type UploadAuditRiskLevel = QuarantineRiskLevel | 'unknown'

export interface UploadAuditResult {
  generated_at?: string
  engine?: string
  provider?: string
  analysis_mode?: string
  mode_reason?: string
  llm_used?: boolean
  llm_available?: boolean
  ai_available?: boolean
  verdict: UploadAuditVerdict
  risk_level: UploadAuditRiskLevel
  confidence: number
  summary: string
  evidence?: string[]
  reasons?: string[]
  recommended_action?: string
  recommended_actions?: string[]
  heuristic_risk_level?: UploadAuditRiskLevel
  heuristic_verdict?: UploadAuditVerdict
  static_risk_level?: QuarantineRiskLevel
  linked_event_id?: number | null
}

export interface UploadResult {
  ok: boolean
  filename: string
  saved_as: string
  size: number
  url?: string | null
  upload_state?: UploadState
  quarantined?: boolean
  stored_in?: 'accepted' | 'quarantine'
  audit: UploadAuditResult
  security_alert?: UploadSecurityAlert
}

export function submitDetectionSample(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request.post<UploadResult>('/upload', form)
}

export type UploadAuditMode = 'static_only' | 'llm_assisted'

export interface UploadAuditRuntimeStatus {
  status: string
  ids_ai_analysis_enabled: boolean
  llm_configured: boolean
  llm_provider: string
  llm_model: string
  llm_required_field: string
  llm_base_url?: string | null
  ids_upload_audit_mode: UploadAuditMode
  ids_upload_audit_label: string
  ids_upload_audit_message: string
  ids_upload_audit_mode_reason?: string
  ids_upload_ai_active?: boolean
}

export function getUploadAuditRuntime(): Promise<UploadAuditRuntimeStatus> {
  return request.get('/health') as Promise<UploadAuditRuntimeStatus>
}

export interface QuarantineItem {
  saved_as: string
  original_name?: string
  file_name?: string
  size: number
  modified_at: string
  url?: string | null
  risk_level?: QuarantineRiskLevel
  extension?: string
  has_report?: boolean
  report_generated_at?: string | null
  report_risk_level?: QuarantineRiskLevel | null
  audit_verdict?: UploadAuditVerdict | null
  report_verdict?: UploadAuditVerdict | null
  audit_confidence?: number | null
  audit_summary?: string | null
}

export interface QuarantineAnalysis {
  total_bytes: number
  today_count: number
  week_count: number
  ai_quarantined_count?: number
  audit_hold_count?: number
  high_risk_count: number
  medium_risk_count: number
  by_extension: { ext: string; count: number }[]
  daily_labels: string[]
  daily_counts: number[]
  insights: string[]
  generated_at: string
}

export interface QuarantinePhaseLog {
  phase: string
  message: string
}

export interface QuarantineReportSection {
  title: string
  body: string
}

export interface QuarantineReportIndicator {
  code: string
  detail: string
}

export interface QuarantineDecisionIndicator {
  code: string
  detail: string
}

export interface QuarantineDecisionBasis {
  final_source?: 'static' | 'llm' | 'hybrid' | string
  analysis_mode?: UploadAuditMode | string
  analysis_mode_label?: string
  mode_reason?: string
  verdict?: UploadAuditVerdict | string
  blocked?: boolean
  risk_level?: UploadAuditRiskLevel
  confidence?: number
  hold_reason_summary?: string
  indicator_count?: number
  matched_indicators?: QuarantineDecisionIndicator[]
  llm_used?: boolean
  ai_available?: boolean
  provider?: string
  recommended_actions?: string[]
  reasons?: string[]
  static_risk_level?: UploadAuditRiskLevel
  heuristic_risk_level?: UploadAuditRiskLevel
  heuristic_verdict?: UploadAuditVerdict | string
  linked_event_id?: number | null
}

export interface QuarantineAnalysisReport {
  saved_as: string
  file_name: string
  original_name?: string
  generated_at: string
  last_updated_at?: string
  analysis_generated_at?: string | null
  size: number
  extension: string
  sha256: string
  risk_level: QuarantineRiskLevel
  indicator_count: number
  indicators: QuarantineReportIndicator[]
  storage_location?: string
  analysis_source?: string
  decision_basis?: QuarantineDecisionBasis
  audit: UploadAuditResult
  sections: QuarantineReportSection[]
}

export interface QuarantineListResponse {
  items: QuarantineItem[]
  count: number
  analysis?: QuarantineAnalysis
  latest_report?: QuarantineAnalysisReport | null
}

export interface QuarantineAnalyzeResponse {
  saved_as: string
  logs: QuarantinePhaseLog[]
  report: QuarantineAnalysisReport | null
}

export function listQuarantineFiles(): Promise<QuarantineListResponse> {
  return request.get('/upload/quarantine') as Promise<QuarantineListResponse>
}

export function deleteQuarantineFile(savedAs: string) {
  return request.delete<{ ok: boolean }>(`/upload/quarantine/${encodeURIComponent(savedAs)}`)
}

export function analyzeQuarantineFiles(savedAs?: string): Promise<QuarantineAnalyzeResponse> {
  return request.post('/upload/quarantine/analyze', savedAs ? { saved_as: savedAs } : {}) as Promise<QuarantineAnalyzeResponse>
}

export function getQuarantineReport(savedAs: string): Promise<QuarantineAnalysisReport> {
  return request.get(`/upload/quarantine/${encodeURIComponent(savedAs)}/report`) as Promise<QuarantineAnalysisReport>
}
