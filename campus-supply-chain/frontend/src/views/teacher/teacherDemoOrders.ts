import type { Purchase, PurchaseItem, PurchaseTimelineItem } from '@/api/purchase'
import { catalogImageForGoodsName } from './teacherDemoCatalog'

/**
 * 教师端「我的订单」本地缓存行：与接口数据合并展示，id 为负数避免与库内主键冲突
 */
function item(
  goods_name: string,
  quantity: number,
  unit: string,
  image: string
): PurchaseItem & { image?: string } {
  return { goods_name, quantity, unit, image }
}

export const TEACHER_DEMO_ORDERS: Purchase[] = [
  {
    id: -1001,
    order_no: 'PO202604150101',
    status: 'pending',
    created_at: '2026-04-15T09:20:00',
    applicant_name: '张老师（自动化学院）',
    items: [
      item('A4 复印纸 70g', 12, '包', '/teacher-demo/a4-paper.jpg'),
      item('无尘粉笔 白色', 8, '盒', '/teacher-demo/chalk.jpg'),
      item('白板笔（黑/蓝）', 24, '支', '/teacher-demo/chalk.jpg'),
    ],
    destination: '教学楼 A303 教室（课程讲义打印）',
    receiver_name: '张老师',
    estimated_amount: 428.0,
    handoff_code: undefined,
    delivery_id: null,
    can_confirm_receive: false,
  },
  {
    id: -1002,
    order_no: 'PO202604120215',
    status: 'delivering',
    created_at: '2026-04-12T14:05:00',
    applicant_name: '张老师（自动化学院）',
    items: [
      item('瓶装饮用水 550ml', 6, '箱', '/teacher-demo/water.jpg'),
      item('一次性纸杯', 6, '包', '/teacher-demo/chalk.jpg'),
      item('桌签卡纸', 2, '包', '/teacher-demo/a4-paper.jpg'),
    ],
    destination: '体育馆 东侧签到区（学院创新赛）',
    receiver_name: '张老师',
    estimated_amount: 386.0,
    delivery_no: 'DL-20260414-008',
    delivery_status: 'out_for_delivery',
    delivery_status_label: '配送中',
    delivery_id: null,
    can_confirm_receive: false,
  },
  {
    id: -1003,
    order_no: 'PO202603180321',
    status: 'completed',
    created_at: '2026-03-18T11:00:00',
    applicant_name: '张老师（自动化学院）',
    items: [
      item('A4 复印纸 70g', 6, '包', '/teacher-demo/a4-paper.jpg'),
      item('教学投影仪配套 HDMI 线', 2, '条', '/teacher-demo/projector.jpg'),
      item('激光翻页笔', 2, '支', '/teacher-demo/laser-pointer.jpg'),
    ],
    destination: '信息楼 B202（公开课）',
    receiver_name: '张老师',
    estimated_amount: 512.0,
    handoff_code: '7631',
    delivery_id: null,
    can_confirm_receive: false,
  },
  {
    id: -1004,
    order_no: 'PO202602260412',
    status: 'rejected',
    created_at: '2026-02-26T16:00:00',
    applicant_name: '张老师（自动化学院）',
    items: [
      item('便携式扩音器', 1, '台', '/teacher-demo/projector.jpg'),
      item('激光翻页笔', 1, '支', '/teacher-demo/laser-pointer.jpg'),
    ],
    destination: '学生活动中心 201（社团分享会）',
    receiver_name: '张老师',
    estimated_amount: 260.0,
    delivery_id: null,
    can_confirm_receive: false,
  },
]

export function getDemoPurchaseById(id: number): Purchase | undefined {
  return TEACHER_DEMO_ORDERS.find((p) => p.id === id)
}

export function getDemoTimelineForOrder(orderId: number): PurchaseTimelineItem[] {
  const map: Record<number, PurchaseTimelineItem[]> = {
    [-1001]: [
      { stage: '提交申请', content: '申请人：张老师；用途：自动化原理课程资料打印。', time: '2026-04-15 09:20' },
      { stage: '学院审批中', content: '当前节点：自动化学院教学副院长审批。', time: '2026-04-15 09:31' },
    ],
    [-1002]: [
      { stage: '审批通过', content: '自动化学院审批通过，转后勤集中采购。', time: '2026-04-12 15:30' },
      { stage: '仓储备货', content: '仓储已按赛事清单完成分拣。', time: '2026-04-13 10:10' },
      { stage: '配送中', content: '配送员前往体育馆东侧签到区。', time: '2026-04-14 14:00' },
    ],
    [-1003]: [
      { stage: '审批通过', content: '学院与后勤审批通过。', time: '2026-03-18 13:00' },
      { stage: '仓储出库', content: '信息楼公开课物资已完成出库。', time: '2026-03-19 09:10' },
      { stage: '签收完成', content: '王老师现场签收，课堂当天使用。', time: '2026-03-19 10:02' },
    ],
    [-1004]: [
      { stage: '已驳回', content: '活动设备可从院内共享资产借用，暂不走新增申领。', time: '2026-02-27 09:00' },
    ],
  }
  return map[orderId] ?? []
}

/** 本地缓存单优先展示，再跟接口数据，按时间倒序 */
export function mergeTeacherOrderList(apiList: Purchase[]): Purchase[] {
  const demos = TEACHER_DEMO_ORDERS
  const demoNos = new Set(demos.map((d) => d.order_no))
  const rest = apiList.filter((p) => !demoNos.has(p.order_no))
  const merged = [...demos, ...rest]
  merged.sort((a, b) => {
    const ta = a.created_at ? new Date(a.created_at).getTime() : 0
    const tb = b.created_at ? new Date(b.created_at).getTime() : 0
    return tb - ta
  })
  return merged.map((p) => ({
    ...p,
    goods_summary:
      p.goods_summary ||
      (p.items || []).map((i) => `${i.goods_name}${i.quantity}${i.unit}`).join('、'),
    items: (p.items || []).map((i) => ({
      ...i,
      image: i.image || catalogImageForGoodsName(i.goods_name),
    })),
  }))
}
