import request from './request'

export interface Supplier {
  id: number
  name: string
  contact: string
  phone: string
  address: string
}

export function listSuppliers(params?: { keyword?: string }) {
  return request.get<Supplier[]>('/supplier', { params })
}

export interface SupplierOrder {
  id: number
  order_no: string
  applicant: string
  goods_summary: string
  status: string
  created_at: string | null
  handoff_code?: string
  receiver_name?: string
  destination?: string
  delivery_no?: string
}

export function listSupplierOrders() {
  return request.get<SupplierOrder[]>('/supplier/orders')
}

export function confirmSupplierOrder(orderId: number) {
  return request.put<{ code: number; message: string; order_no: string }>(`/supplier/orders/${orderId}/confirm`)
}

export function shipSupplierOrder(orderId: number) {
  return request.put<{ code: number; message: string; order_no: string }>(`/supplier/orders/${orderId}/ship`)
}
