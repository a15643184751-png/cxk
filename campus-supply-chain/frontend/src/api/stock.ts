import request from './request'

export function listStockIn() {
  return request.get('/stock/in')
}

export function listStockOut() {
  return request.get('/stock/out')
}

export interface InventoryItem {
  id: number
  goods_name: string
  category: string
  quantity: number
  unit: string
  batch_no: string
  safe_qty: number
  is_low_stock: boolean
  days_to_expire: number | null
  updated_at: string | null
}

export function listInventory(params?: { keyword?: string }) {
  return request.get<InventoryItem[]>('/stock/inventory', { params })
}

export interface StockInItem {
  goods_name: string
  quantity: number
  unit: string
  batch_no?: string
}

export function createStockIn(data: { purchase_id?: number; items?: StockInItem[] }) {
  return request.post<{ code: number; message: string; order_no: string }>('/stock/in', data)
}

export interface StockOutItem {
  goods_name: string
  quantity: number
  unit: string
  batch_no?: string
}

export function createStockOut(data: { purchase_id?: number; items?: StockOutItem[] }) {
  return request.post<{ code: number; message: string; order_no: string }>('/stock/out', data)
}
