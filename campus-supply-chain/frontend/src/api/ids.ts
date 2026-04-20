import request from './request'

export interface IDSEventItem {
  id: number
  client_ip: string
  attack_type: string
  attack_type_label: string
  signature_matched: string
  method: string
  path: string
  query_snippet: string
  body_snippet: string
  user_agent: string
  blocked: number
  firewall_rule: string
  archived: number
  status?: string
  review_note?: string
  action_taken?: string
  risk_score?: number
  confidence?: number
  hit_count?: number
  created_at: string | null
  ai_risk_level?: string
  ai_analysis?: string
  ai_confidence?: number
  ai_analyzed_at?: string | null
}

export interface IDSEventsResponse {
  total: number
  items: IDSEventItem[]
}

export interface IDSStatsResponse {
  total: number
  blocked_count: number
  high_risk_count?: number
  by_type: { attack_type: string; attack_type_label: string; count: number }[]
  by_status?: { status: string; count: number }[]
}

export interface IDSBridgeStatusResponse {
  bridge_enabled: boolean
  standalone_base_url: string
  source_system: string
  token_configured: boolean
  health: {
    ok: boolean
    status_code: number | null
    detail: unknown
  }
  site_console_url: string
  site_api_url: string
  anfu_console_url: string
  standalone_console_url: string
  standalone_api_url: string
}

export function listIDSEvents(params?: {
  attack_type?: string
  client_ip?: string
  blocked?: number
  archived?: number
  status?: string
  min_score?: number
  limit?: number
  offset?: number
}) {
  return request.get<IDSEventsResponse>('/ids/events', { params })
}

export function getIDSStats() {
  return request.get<IDSStatsResponse>('/ids/stats')
}

export async function getIDSBridgeStatus(): Promise<IDSBridgeStatusResponse> {
  return await request.get<IDSBridgeStatusResponse>('/ids/bridge-status') as unknown as IDSBridgeStatusResponse
}

export interface IDSTrendResponse {
  dates: string[]
  counts: number[]
}

export function getIDSTrend(days?: number) {
  return request.get<IDSTrendResponse>('/ids/stats/trend', { params: { days: days ?? 7 } })
}

export function archiveIDSEvent(eventId: number) {
  return request.put<{ code: number; message: string }>(`/ids/events/${eventId}/archive`)
}

export function archiveIDSBatch(eventIds: number[]) {
  return request.post<{ code: number; message: string; archived: number }>('/ids/events/archive-batch', {
    event_ids: eventIds,
  })
}

export function analyzeIDSEventAI(eventId: number) {
  return request.post<{
    code: number
    message: string
    ai_risk_level: string
    ai_analysis: string
    ai_analyzed_at: string | null
  }>(`/ids/events/${eventId}/analyze`)
}

export function updateIDSEventStatus(eventId: number, data: { status: string; review_note?: string }) {
  return request.put<{ code: number; message: string; status: string }>(`/ids/events/${eventId}/status`, data)
}

export function blockIDSEventIp(eventId: number) {
  return request.post<{ code: number; message: string; ok: boolean; rule?: string }>(`/ids/events/${eventId}/block`)
}

export function unblockIDSEventIp(eventId: number) {
  return request.post<{ code: number; message: string; ok: boolean }>(`/ids/events/${eventId}/unblock`)
}

export function getIDSEventReport(eventId: number, forceAI?: boolean) {
  return request.get<{ report: any; markdown: string }>(`/ids/events/${eventId}/report`, {
    params: { force_ai: forceAI ? 1 : 0 },
  })
}

/** 主标题彩蛋：多向量并发攻击聚合研判报告 */
export function getIDSPhase1AggregateReport() {
  return request.get<{ report: any }>('/ids/demo/phase1/aggregate-report')
}

export function seedIDSDemoPhase1(autoAnalyze = true) {
  return request.post<{ code: number; message: string; event_ids: number[] }>('/ids/demo/phase1', {
    auto_analyze: autoAnalyze,
  })
}

export function seedIDSDemoPhase2(autoAnalyze = true) {
  return request.post<{ code: number; message: string; event_id: number }>('/ids/demo/phase2', {
    auto_analyze: autoAnalyze,
  })
}

export function resetIDSDemoEvents() {
  return request.post<{ code: number; message: string; deleted: number }>('/ids/demo/reset')
}
