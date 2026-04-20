import request from './request'

export interface IDSUploadAuditTrace {
  verdict: string
  risk_level: string
  confidence: number
  summary: string
  provider?: string
  analysis_mode?: string
  analysis_mode_label?: string
  llm_used?: boolean
  ai_available?: boolean
  recommended_actions?: string[]
}

export interface IDSUploadIndicator {
  code: string
  detail: string
}

export interface IDSUploadTrace {
  saved_as: string
  file_name: string
  sha256?: string
  size?: number
  storage_location?: string
  indicator_count?: number
  indicators?: IDSUploadIndicator[]
  decision_basis?: {
    final_source?: string
    analysis_mode?: string
    analysis_mode_label?: string
    mode_reason?: string
    hold_reason_summary?: string
    linked_event_id?: number | null
  } | null
  audit: IDSUploadAuditTrace
}

export interface IDSAlertProfile {
  tier: 'critical_popup' | 'standard_notice' | string
  channel: 'modal' | 'notification' | string
  sound: 'loop' | 'once' | 'none' | string
  category?: 'upload' | 'request' | string
  title?: string
  summary?: string
}

export interface IDSRequestPacketHeader {
  name: string
  value: string
}

export interface IDSRequestPacket {
  request_line: string
  method: string
  path: string
  query_string: string
  body: string
  headers: IDSRequestPacketHeader[]
  headers_snippet?: string
  user_agent?: string
  raw_request: string
  body_truncated?: boolean
  headers_truncated?: boolean
}

export interface IDSMatchedHit {
  id?: string
  attack_type?: string
  pattern?: string
  signature_matched: string
  weight?: number
  runtime_priority?: number
  source_classification?: string
  detector_family?: string
  detector_name?: string
  source_rule_id?: string
  source_rule_name?: string
  source_version?: string
  source_freshness?: string
  matched_part?: string
  matched_value?: string
}

export interface IDSAIStatus {
  analysis_mode?: string
  analysis_mode_label?: string
  mode_reason?: string
  llm_used?: boolean
  ai_available?: boolean
  ai_risk_level?: string
  ai_confidence?: number
  ai_analyzed_at?: string | null
}

export interface IDSDecisionBasis {
  final_source?: 'static' | 'llm' | 'hybrid' | string
  static_source_mode?: 'external_runtime' | 'legacy_local' | string
  static_source_label?: string
  analysis_mode?: string
  analysis_mode_label?: string
  mode_reason?: string
  static_risk_score?: number
  block_threshold?: number
  rule_confidence?: number
  llm_used?: boolean
  ai_available?: boolean
  ai_risk_level?: string
  ai_confidence?: number
}

export type IDSLogAuditSeverity = 'informational' | 'suspicious' | 'critical' | string

export interface IDSLogAuditItem {
  id: number
  user_name: string
  user_role: string
  action: string
  target_type: string
  target_id: string
  detail: string
  severity: IDSLogAuditSeverity
  metadata?: Record<string, string | number | null>
  created_at: string | null
}

export interface IDSLogAuditSummary {
  total: number
  critical?: number
  suspicious?: number
  informational?: number
  by_action?: { action: string; count: number }[]
  by_target_type?: { target_type: string; count: number }[]
}

export interface IDSLogAuditResponse {
  items: IDSLogAuditItem[]
  total: number
  summary?: IDSLogAuditSummary
  available_actions?: string[]
  available_targets?: string[]
  available_severities?: IDSLogAuditSeverity[]
}

export interface IDSHTTPSessionItem {
  id: number
  client_ip: string
  scheme: string
  host: string
  method: string
  path: string
  query_string: string
  route_kind: 'api' | 'frontend' | string
  upstream_base: string
  upstream_url: string
  user_agent: string
  request_headers: string
  request_body: string
  raw_request: string
  request_size: number
  response_status: number
  response_headers: string
  response_body: string
  raw_response: string
  response_size: number
  content_type: string
  duration_ms: number
  blocked: number
  attack_type: string
  risk_score: number
  confidence: number
  incident_id?: number | null
  response_note?: string
  ip_policy_blocked?: boolean
  created_at: string | null
}

export interface IDSBlockedIPItem {
  ip: string
  source: string
  actor: string
  note: string
  event_id?: number | null
  blocked_at?: string | null
  updated_at?: string | null
  total_sessions?: number
  blocked_sessions?: number
  last_seen_at?: string | null
  last_path?: string
  last_status?: number
}

export interface IDSBlockedIPListResponse {
  total: number
  items: IDSBlockedIPItem[]
}

export interface IDSHTTPSessionListResponse {
  total: number
  items: IDSHTTPSessionItem[]
  summary?: {
    total: number
    blocked_count: number
    api_count: number
    frontend_count: number
    active_blocked_ips?: number
  }
}

export interface IDSEventItem {
  id: number
  client_ip: string
  event_origin?: string
  event_origin_label?: string
  source_classification?: string
  detector_family?: string
  detector_name?: string
  source_rule_id?: string
  source_rule_name?: string
  source_version?: string
  source_freshness?: string
  event_fingerprint?: string
  correlation_key?: string
  counted_in_real_metrics?: boolean
  attack_type: string
  attack_type_label: string
  signature_matched: string
  method: string
  path: string
  query_snippet: string
  body_snippet: string
  user_agent: string
  headers_snippet?: string
  blocked: number
  firewall_rule: string
  archived: number
  status?: string
  review_note?: string
  action_taken?: string
  response_result?: string
  response_detail?: string
  upload_trace?: IDSUploadTrace | null
  alert_profile?: IDSAlertProfile | null
  risk_score?: number
  confidence?: number
  hit_count?: number
  created_at: string | null
  ai_risk_level?: string
  ai_analysis?: string
  ai_confidence?: number
  ai_analyzed_at?: string | null
  matched_hits?: IDSMatchedHit[]
  request_packet?: IDSRequestPacket | null
  packet_preview?: string
  decision_basis?: IDSDecisionBasis | null
  ai_status?: IDSAIStatus | null
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
  by_origin?: { event_origin: string; count: number }[]
}

export interface IDSSituationAttackItem {
  id: string
  timestamp: string
  source_ip: string
  source_location: {
    country: string
    city: string
    lat: number
    lng: number
    derived?: boolean
  }
  target_ip: string
  target_location: {
    lat: number
    lng: number
  }
  attack_type: string
  severity: string
  status: string
  blocked: boolean
  detector_name: string
  uptime: string
}

export interface IDSSituationResponse {
  generated_at: string
  scope: string
  disclaimer: string
  target: {
    lat: number
    lng: number
    city: string
    country: string
    ip: string
  }
  metrics: {
    total_blocked: number
    active_threats: number
    uptime_seconds: number
    online_sources: number
  }
  attacks: IDSSituationAttackItem[]
}

export function listIDSEvents(params?: {
  attack_type?: string
  client_ip?: string
  blocked?: number
  archived?: number
  status?: string
  event_origin?: string
  source_classification?: string
  min_score?: number
  limit?: number
  offset?: number
}) {
  return request.get<IDSEventsResponse>('/ids/events', { params })
}

export function getIDSEvent(eventId: number) {
  return request.get<{ item: IDSEventItem }>(`/ids/events/${eventId}`)
}

export function getIDSStats(params?: { event_origin?: string; source_classification?: string }) {
  return request.get<IDSStatsResponse>('/ids/stats', { params })
}

export interface IDSTrendResponse {
  dates: string[]
  counts: number[]
}

export interface IDSEventReport {
  event_id: number
  generated_at: string
  overview?: {
    time?: string
    client_ip?: string
    attack_type?: string
    attack_type_label?: string
    method?: string
    path?: string
    status?: string
    event_origin?: string
    detector_name?: string
  }
  score?: {
    risk_score?: number
    rule_confidence?: number
    hit_count?: number
    ai_risk_level?: string
    ai_confidence?: number
  }
  evidence?: {
    signature?: string
    query_snippet?: string
    body_snippet?: string
    user_agent?: string
  }
  packet?: IDSRequestPacket
  matched_hits?: IDSMatchedHit[]
  decision_basis?: IDSDecisionBasis
  ai_status?: IDSAIStatus
  response?: {
    blocked?: boolean
    firewall_rule?: string
    action_taken?: string
    review_note?: string
    response_result?: string
    response_detail?: string
  }
  provenance?: {
    source_classification?: string
    detector_family?: string
    detector_name?: string
    source_rule_id?: string
    source_rule_name?: string
    source_version?: string
    source_freshness?: string
  }
  upload_trace?: IDSUploadTrace | null
  ai_analysis?: string
}

export interface IDSEventReportResponse {
  report: IDSEventReport
  markdown: string
}

export interface IDSGeoLocation {
  country: string
  city: string
  lat: number
  lng: number
  derived?: boolean
}

export interface IDSEventMiniItem {
  id: number
  created_at: string | null
  attack_type: string
  attack_type_label: string
  risk_score: number
  status: string
  blocked: boolean
  method: string
  path: string
  signature_matched: string
  detector_name?: string
  response_detail?: string
}

export interface IDSEventInsightProfile {
  client_ip: string
  source_location: IDSGeoLocation
  user_agent_family: string
  user_agent_sample: string
  total_events_from_ip: number
  blocked_events_from_ip: number
  high_risk_events_from_ip: number
  first_seen_at: string | null
  last_seen_at: string | null
  distinct_attack_types: string[]
  top_paths: { path: string; count: number }[]
  historical_behaviors: { label: string; count: number }[]
}

export interface IDSEventInsightTimeline {
  basis: 'correlation_key' | 'client_ip' | string
  anchor_value: string
  total: number
  items: IDSEventMiniItem[]
}

export interface IDSEventInsightCluster {
  cluster_key: string
  summary: string
  total: number
  same_attack_type_total: number
  same_signature_total: number
  same_path_total: number
  recent_items: IDSEventMiniItem[]
}

export interface IDSFalsePositiveSignal {
  kind: string
  pattern: string
  count: number
  recommendation: string
  source: 'history' | 'memory' | string
}

export interface IDSFalsePositiveLearning {
  matched_learning_events: number
  signals: IDSFalsePositiveSignal[]
  recommendation: string
  last_learned_at?: string | null
}

export interface IDSEventInsightResponse {
  item: IDSEventItem
  profile: IDSEventInsightProfile
  timeline: IDSEventInsightTimeline
  cluster: IDSEventInsightCluster
  false_positive_learning: IDSFalsePositiveLearning
}

export interface IDSAttackHeatboardResponse {
  generated_at: string
  today_total: number
  today_high_risk_total: number
  today_blocked_total: number
  by_type: { attack_type_label: string; count: number }[]
  hourly: { hour: string; total: number; high_risk: number }[]
  high_risk_trend: { date: string; count: number }[]
  hot_ips: { client_ip: string; count: number }[]
}

export interface IDSRequestDetectPayload {
  method: string
  path: string
  query?: string
  body?: string
  user_agent?: string
  client_ip?: string
  headers?: Record<string, string>
}

export interface IDSRequestDetectResponse {
  matched: boolean
  blocked: boolean
  would_block: boolean
  attack_type: string
  risk_score: number
  confidence: number
  event_id?: number | null
  detail?: string
}

export interface IDSNotificationEmailSettings {
  enabled: boolean
  smtp_host: string
  smtp_port: number
  username: string
  password?: string
  password_configured?: boolean
  from_addr: string
  to_addrs: string
  use_tls: boolean
  use_ssl: boolean
}

export interface IDSNotificationWeComSettings {
  enabled: boolean
  webhook_url: string
}

export interface IDSNotificationWebhookSettings {
  enabled: boolean
  url: string
  secret?: string
  secret_configured?: boolean
}

export interface IDSNotificationSettings {
  email: IDSNotificationEmailSettings
  wecom: IDSNotificationWeComSettings
  webhook: IDSNotificationWebhookSettings
}

export interface IDSNotificationDispatchResult {
  channel: string
  status: string
  detail?: string
  http_status?: number
}

export interface IDSNotificationDispatchResponse {
  payload: {
    title: string
    body: string
    event: Record<string, string | number | boolean>
  }
  results: IDSNotificationDispatchResult[]
}

export interface IDSCommunicationRealSettings {
  gateway_port: number
  frontend_ip: string
  frontend_port: number
  backend_ip: string
  backend_port: number
}

export interface IDSCommunicationDisplaySettings {
  site_label: string
  domain_code: string
  link_template: string
  routing_profile: string
  packet_profile: string
  signal_band: string
  coordination_group: string
  display_mode: string
  session_track_mode: string
  trace_color_mode: string
  link_sync_clock: string
  relay_group: string
  auto_rotate: boolean
  popup_broadcast: boolean
  packet_shadow: boolean
  link_keepalive: boolean
}

export interface IDSCommunicationDerivedSettings {
  frontend_upstream_url: string
  backend_upstream_url: string
  gateway_port: number
  restart_required: boolean
  effective_scope: string
  effective_hint: string
  env_path: string
}

export interface IDSCommunicationSettings {
  real: IDSCommunicationRealSettings
  display: IDSCommunicationDisplaySettings
  derived: IDSCommunicationDerivedSettings
  updated_at?: string | null
}

// Source operations and package-history payloads for the IDS security-center
// registry panel.
export interface IDSSourceSyncAttemptItem {
  id: number
  source_id: number
  started_at: string | null
  finished_at: string | null
  result_status: string
  detail: string
  freshness_after_sync: string
  package_version: string
  package_intake_id?: number | null
  resolved_sync_endpoint?: string
  triggered_by: string
}

export interface IDSSourcePackageIntakeItem {
  id: number
  source_id: number | null
  source_key: string
  package_version: string
  release_timestamp: string | null
  trust_classification: string
  detector_family: string
  provenance_note: string
  intake_result: string
  intake_detail: string
  artifact_path?: string
  artifact_sha256?: string
  artifact_size_bytes?: number
  rule_count?: number
  triggered_by: string
  created_at: string | null
}

export interface IDSSourcePackagePreviewItem {
  source_id: number
  source_key: string
  package_version: string
  version_change_state: string
  changed_fields: string[]
  visible_warning: string
  artifact_path?: string
  artifact_sha256?: string
  artifact_size_bytes?: number
  rule_count?: number
}

export interface IDSSourceItem {
  id: number
  source_key: string
  display_name: string
  trust_classification: string
  detector_family: string
  operational_status: string
  freshness_target_hours: number
  sync_mode: string
  sync_endpoint: string
  last_synced_at: string | null
  last_sync_status: string
  last_sync_detail: string
  health_state: string
  visible_warning: string
  recent_incident_count: number
  recent_incident_last_seen_at: string | null
  provenance_note: string
  is_production_trusted: boolean
  created_at: string | null
  updated_at: string | null
  latest_sync_attempt?: IDSSourceSyncAttemptItem | null
  recent_sync_attempts: IDSSourceSyncAttemptItem[]
  active_package_version?: string
  active_package_activated_at?: string | null
  active_package_activated_by?: string
  latest_package_preview?: IDSSourcePackagePreviewItem | null
  recent_package_intakes: IDSSourcePackageIntakeItem[]
}

export interface IDSSourceListResponse {
  total: number
  items: IDSSourceItem[]
  summary: {
    total: number
    healthy_count: number
    degraded_count: number
    trusted_count: number
    demo_test_count: number
  }
}

export interface IDSSourceRegistryPayload {
  source_key: string
  display_name: string
  trust_classification: string
  detector_family: string
  operational_status: string
  freshness_target_hours: number
  sync_mode: string
  sync_endpoint?: string
  provenance_note?: string
}

export interface IDSSourceSyncResponse {
  source_id: number
  sync_attempt_id: number
  result_status: string
  health_state: string
  last_synced_at: string | null
  detail: string
  package_version?: string
  package_intake_id?: number | null
  resolved_sync_endpoint?: string
  activation_required?: boolean
  rule_count?: number
  artifact_path?: string
  artifact_sha256?: string
  change_summary?: string
  source: IDSSourceItem
}

export interface IDSSourcePackagePreviewPayload {
  source_key: string
  package_version: string
  release_timestamp?: string
  trust_classification: string
  detector_family: string
  provenance_note?: string
  triggered_by: string
}

export interface IDSSourcePackagePreviewResponse extends IDSSourcePackagePreviewItem {
  package_intake_id: number
  intake_result: string
}

export interface IDSSourcePackageActivationPayload {
  package_intake_id: number
  triggered_by: string
  activation_note?: string
}

export interface IDSSourcePackageActivationResponse {
  source_id: number
  package_activation_id: number
  package_version: string
  result_status: string
  active_package_version: string
  detail: string
}

export interface IDSSourcePackageActivationItem {
  id: number
  source_id: number
  package_intake_id: number
  package_version: string
  activated_at: string | null
  activated_by: string
  activation_detail: string
  created_at: string | null
}

export interface IDSSourcePackageHistoryItem {
  source: {
    id: number
    source_key: string
    display_name: string
    trust_classification: string
    detector_family: string
  } | null
  source_key: string
  active_package_version: string
  active_package_activated_at: string | null
  active_package_activated_by: string
  recent_intakes: IDSSourcePackageIntakeItem[]
  recent_activations: IDSSourcePackageActivationItem[]
}

export interface IDSSourcePackageHistoryResponse {
  total: number
  items: IDSSourcePackageHistoryItem[]
}

export function getIDSTrend(
  days?: number,
  params?: { event_origin?: string; source_classification?: string },
) {
  return request.get<IDSTrendResponse>('/ids/stats/trend', {
    params: { days: days ?? 7, ...params },
  })
}

export function getIDSSituation() {
  return request.get<IDSSituationResponse>('/ids/situation')
}

export function listIDSSources() {
  return request.get<IDSSourceListResponse>('/ids/sources')
}

export function createIDSSource(data: IDSSourceRegistryPayload) {
  return request.post<IDSSourceItem>('/ids/sources', data)
}

export function updateIDSSource(sourceId: number, data: IDSSourceRegistryPayload) {
  return request.put<IDSSourceItem>(`/ids/sources/${sourceId}`, data)
}

export function syncIDSSource(sourceId: number, data: { triggered_by: string; reason?: string }) {
  return request.post<IDSSourceSyncResponse>(`/ids/sources/${sourceId}/sync`, data)
}

export function previewIDSSourcePackage(data: IDSSourcePackagePreviewPayload) {
  return request.post<IDSSourcePackagePreviewResponse>('/ids/source-packages/preview', data)
}

export function activateIDSSourcePackage(data: IDSSourcePackageActivationPayload) {
  return request.post<IDSSourcePackageActivationResponse>('/ids/source-packages/activate', data)
}

export function listIDSSourcePackages(params?: { source_id?: number; source_key?: string; limit?: number }) {
  return request.get<IDSSourcePackageHistoryResponse>('/ids/source-packages', { params })
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
  }>(`/ids/events/${eventId}/analyze`, undefined, {
    timeout: 120000,
  })
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
  return request.get<IDSEventReportResponse>(`/ids/events/${eventId}/report`, {
    params: { force_ai: forceAI ? 1 : 0 },
    timeout: forceAI ? 120000 : 60000,
  })
}

export function getIDSEventInsight(eventId: number) {
  return request.get<IDSEventInsightResponse>(`/ids/events/${eventId}/insight`)
}

export function getIDSHeatboard() {
  return request.get<IDSAttackHeatboardResponse>('/ids/stats/heatboard')
}

export function detectIDSRequest(data: IDSRequestDetectPayload) {
  return request.post<IDSRequestDetectResponse>('/ids/request-detect', data)
}

export function getIDSNotificationSettings() {
  return request.get<IDSNotificationSettings>('/ids/notifications/settings')
}

export function updateIDSNotificationSettings(data: IDSNotificationSettings) {
  return request.put<IDSNotificationSettings>('/ids/notifications/settings', data)
}

export function testIDSNotifications(eventId?: number) {
  return request.post<IDSNotificationDispatchResponse>('/ids/notifications/test', {
    event_id: eventId ?? null,
  })
}

export function getIDSCommunicationSettings() {
  return request.get<IDSCommunicationSettings>('/ids/communication-settings')
}

export function updateIDSCommunicationSettings(data: {
  real: IDSCommunicationRealSettings
  display: IDSCommunicationDisplaySettings
}) {
  return request.put<IDSCommunicationSettings>('/ids/communication-settings', data)
}

export function dispatchIDSEventNotifications(eventId: number) {
  return request.post<IDSNotificationDispatchResponse>(`/ids/events/${eventId}/dispatch-notifications`)
}

export interface IDSLogAuditListParams {
  action?: string
  target_type?: string
  user_name?: string
  severity?: IDSLogAuditSeverity
  limit?: number
  offset?: number
}

export function listIDSLogAudits(params?: IDSLogAuditListParams) {
  return request.get<IDSLogAuditResponse>('/ids/log-audit', { params })
}

export function listIDSHTTPSessions(params?: {
  method?: string
  client_ip?: string
  route_kind?: string
  blocked?: number
  path_keyword?: string
  limit?: number
  offset?: number
}) {
  return request.get<IDSHTTPSessionListResponse>('/traffic/sessions', { params })
}

export function getIDSHTTPSession(sessionId: number) {
  return request.get<IDSHTTPSessionItem>(`/traffic/sessions/${sessionId}`)
}

export function listIDSBlockedIps() {
  return request.get<IDSBlockedIPListResponse>('/traffic/blocklist')
}

export function addIDSBlockedIp(data: { ip: string; note?: string }) {
  return request.post<{ ok: boolean; message: string; item: IDSBlockedIPItem }>('/traffic/blocklist', data)
}

export function removeIDSBlockedIp(data: { ip: string }) {
  return request.post<{ ok: boolean; message: string; total: number }>('/traffic/blocklist/remove', data)
}

/** 主标题彩蛋：多向量并发攻击聚合研判报告 */
// Aggregate report for the seeded phase1 demo chain.
