import request from './request'

export interface PurchaseItem {
  goods_name: string
  quantity: number
  unit: string
  /** 前端静态展示用：商品图 URL（如 /teacher-demo/xxx.jpg） */
  image?: string
}

export interface Purchase {
  id: number
  order_no: string
  status: string
  status_label?: string
  applicant_id?: number
  applicant_name?: string
  created_at: string | null
  items: PurchaseItem[]
  destination?: string
  receiver_name?: string
  handoff_code?: string
  delivery_id?: number | null
  delivery_no?: string
  delivery_status?: string
  delivery_status_label?: string
  can_confirm_receive?: boolean
  goods_summary?: string
  material_type?: string
  material_spec?: string
  estimated_amount?: number
  delivery_date?: string | null
  attachment_names?: string[]
  is_draft?: number
  approval_level?: string
  approval_required_role?: string
  approval_deadline_at?: string | null
  urgent_level?: 'normal' | 'urgent'
  forwarded_to?: string
  forwarded_note?: string
  is_overdue?: boolean
  ai_judgment?: 'pass' | 'cautious' | 'reject' | ''
  ai_judgment_score?: number
  ai_judgment_summary?: string
  ai_judgment_at?: string | null
  approval_opinion?: string
  approval_reason_option?: string
  approval_signature_mode?: string
  approval_signed_at?: string | null
}

export interface PurchaseTimelineItem {
  stage: string
  content: string
  time: string
}

export interface PurchaseTimelineSummary {
  purchase_id: number
  order_no: string
  status: string
  status_label: string
  applicant_id?: number | null
  applicant_name?: string
  created_at?: string
  material_type?: string
  ai_judgment?: string
  ai_judgment_summary?: string
  items?: { goods_name: string; quantity: number; unit: string }[]
  receiver_name: string
  destination: string
  handoff_code: string
  delivery_count: number
  deliveries: {
    delivery_no: string
    status: string
    status_label: string
    receiver_name: string
    destination: string
    created_at: string
  }[]
}

export interface PurchaseApplyReq {
  goods_id: number
  quantity: number
  apply_reason?: string
  destination?: string
  receiver_name?: string
  material_type?: string
  material_spec?: string
  estimated_amount?: number
  delivery_date?: string
  attachment_names?: string[]
  is_draft?: number
}

export function listPurchases(params?: { status?: string }) {
  return request.get<Purchase[]>('/purchase', { params })
}

export function listMyPurchases() {
  return request.get<Purchase[]>('/purchase/my')
}

export function createPurchase(data: PurchaseApplyReq) {
  return request.post<{ id: number; order_no: string; status: string; message: string }>('/purchase', data)
}

export function approvePurchase(id: number, supplierId?: number) {
  return request.put<{ code: number; message: string; order_no: string; handoff_code: string; status: string }>(`/purchase/${id}/approve`, {
    supplier_id: supplierId,
  })
}

export function approvePurchaseWithEvidence(
  id: number,
  payload: {
    supplier_id?: number
    reason_option: string
    opinion: string
    signature_mode: 'draw' | 'stamp'
    signature_data: string
    ai_recommendation: string
    ai_score: number
  }
) {
  return request.put<{ code: number; message: string; order_no: string; handoff_code: string; status: string }>(
    `/purchase/${id}/approve`,
    payload
  )
}

export function rejectPurchase(id: number, reason?: string) {
  return request.put<{ code: number; message: string; order_no: string }>(`/purchase/${id}/reject`, {
    reason,
  })
}

export function rejectPurchaseWithEvidence(
  id: number,
  payload: {
    reason?: string
    reason_option: string
    opinion: string
    signature_mode: 'draw' | 'stamp'
    signature_data: string
    ai_recommendation: string
    ai_score: number
  }
) {
  return request.put<{ code: number; message: string; order_no: string }>(`/purchase/${id}/reject`, payload)
}

export function runPurchaseAiJudgment(id: number) {
  return request.post<{
    recommendation: 'pass' | 'cautious' | 'reject'
    recommendation_label: string
    score: number
    summary: string
    dimensions: {
      inventory: { result: string; note: string }
      budget: { result: string; note: string }
      price: { result: string; note: string }
      compliance: { result: string; note: string }
      supplier: { result: string; note: string }
    }
  }>(`/purchase/${id}/ai-judgment`)
}

export function forwardPurchase(id: number, toRole: string, note?: string) {
  return request.put<{ code: number; message: string; order_no: string; to_role: string }>(`/purchase/${id}/forward`, {
    to_role: toRole,
    note: note || '',
  })
}

export function listPurchaseHistory(keyword?: string, limit?: number) {
  return request.get<Purchase[]>('/purchase/history', {
    params: { keyword, limit: limit || 20 },
  })
}

export function getPurchaseFavorites() {
  return request.get<Array<{
    goods_name: string
    quantity: number
    unit: string
    material_type: string
    material_spec: string
    estimated_amount: number
    count: number
  }>>('/purchase/favorites')
}

export function getPurchaseTimeline(id: number) {
  return request.get<{ summary: PurchaseTimelineSummary; timeline: PurchaseTimelineItem[] }>(`/purchase/${id}/timeline`)
}

export interface AdminAbnormalResolvePayload {
  action: 'warn' | 'penalty'
  summary_reason: string
  warn_preset?: string
  warn_custom?: string
  penalty_level?: string
  penalty_custom?: string
  penalty_note?: string
  penalty_valid_until?: string | null
  penalty_long_term?: boolean
}

export function adminAbnormalResolve(id: number, data: AdminAbnormalResolvePayload) {
  return request.post<{
    code: number
    message: string
    order_no: string
    action: string
    notice_body: string
  }>(`/purchase/${id}/admin-abnormal-resolve`, data)
}
