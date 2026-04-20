import request from './request'

export interface DeliveryItem {
  id: number
  delivery_no: string
  purchase_id?: number
  purchase_order_no?: string
  destination: string
  status: string
  status_label?: string
  receiver_name?: string
  handoff_code?: string
  can_confirm_receive?: boolean
  scheduled_at: string | null
  created_at: string | null
}

export function listDeliveries(params?: { status?: string }) {
  return request.get<DeliveryItem[]>('/delivery', { params })
}

export function listMyDeliveries(params?: { status?: string }) {
  return request.get<DeliveryItem[]>('/delivery/my', { params })
}

export function createDelivery(data: {
  stock_out_id?: number
  purchase_id?: number
  destination?: string
  receiver_name?: string
  remark?: string
}) {
  return request.post<{ code: number; message: string; delivery_no: string }>('/delivery', data)
}

export function updateDeliveryStatus(deliveryId: number, data: { status: string; remark?: string }) {
  return request.put<{ code: number; message: string; status: string }>(`/delivery/${deliveryId}/status`, data)
}

export function confirmDeliveryReceive(deliveryId: number, data?: { remark?: string }) {
  return request.put<{ code: number; message: string; status: string }>(`/delivery/${deliveryId}/receive`, data || {})
}
