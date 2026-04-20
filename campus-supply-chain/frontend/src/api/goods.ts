import request from './request'

export interface GoodsItem {
  id: number
  name: string
  category: string
  spec: string
  unit: string
  safety_level: string
  shelf_life_days: number
}

export function listGoods(params?: { keyword?: string; category?: string }) {
  return request.get<GoodsItem[]>('/goods', { params })
}

export function createGoods(data: Partial<GoodsItem>) {
  return request.post<GoodsItem>('/goods', data)
}

export function updateGoods(id: number, data: Partial<GoodsItem>) {
  return request.put<GoodsItem>(`/goods/${id}`, data)
}

export function deleteGoods(id: number) {
  return request.delete(`/goods/${id}`)
}
