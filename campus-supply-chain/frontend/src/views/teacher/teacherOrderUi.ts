import type { Purchase } from '@/api/purchase'

/** 与老师认知一致的 4 态（内部状态映射为展示态） */
export type OrderFourState = 'pending' | 'receiving' | 'completed' | 'cancelled'

export function orderFourState(p: Purchase): OrderFourState {
  if (p.status === 'rejected') return 'cancelled'
  if (p.status === 'completed') return 'completed'
  if (p.status === 'pending') return 'pending'
  return 'receiving'
}

export function orderStatusPillClass(f: OrderFourState) {
  switch (f) {
    case 'pending':
      return { label: '待审批', class: 'pill--pending' }
    case 'receiving':
      return { label: '待收货', class: 'pill--receiving' }
    case 'completed':
      return { label: '已完成', class: 'pill--completed' }
    case 'cancelled':
      return { label: '已取消', class: 'pill--cancelled' }
  }
}
