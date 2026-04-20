import request from './request'

export interface TraceItem {
  trace_key: string
  stage: string
  content: string
  time: string
}

export interface TraceSummary {
  order_no: string
  status: string
  status_label: string
  handoff_code: string
  receiver_name: string
  destination: string
  applicant_name: string
  delivery_no: string
  delivery_status: string
  delivery_status_label: string
  trace_count: number
}

export interface TraceQueryResult {
  summary: TraceSummary | null
  records: TraceItem[]
}

export function traceQuery(params: { keyword: string; query_type: 'all' | 'batch' | 'order' | 'stock' }) {
  return request.get<TraceQueryResult>('/trace/query', { params })
}
