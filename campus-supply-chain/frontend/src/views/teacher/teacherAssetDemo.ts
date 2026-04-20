/** 领用/借还本地示例（与 teacher-demo 静态图对应） */
export type DemoAssetStatus = 'ok' | 'soon' | 'overdue' | 'returned'

export interface DemoAsset {
  id: number
  name: string
  spec: string
  borrowedAt: string
  dueAt: string
  location: string
  status: DemoAssetStatus
  /** 列表/详情左侧图 */
  image: string
  traceNote?: string
  historyLines?: string[]
}

export const DEMO_ASSETS: DemoAsset[] = [
  {
    id: 1,
    name: '教学投影仪（公开课）',
    spec: 'Epson EF-12 · 含 HDMI 线',
    borrowedAt: '2026-03-01',
    dueAt: '2026-04-28',
    location: '教学楼 A303 多媒体柜',
    status: 'soon',
    image: '/teacher-demo/projector.jpg',
    traceNote: '用途：自动化学院公开课与课程答辩；资产编号 AV-2025-018。',
    historyLines: [
      '2026-03-01 领用审批通过 · 场景：课程公开课',
      '2026-03-28 设备检查通过 · 灯泡寿命正常',
      '2025-09-15 归还后检修并再次入库',
    ],
  },
  {
    id: 2,
    name: '激光翻页笔（比赛答辩）',
    spec: '2.4G 无线 · 含接收器',
    borrowedAt: '2026-02-18',
    dueAt: '2026-04-12',
    location: '办公室抽屉',
    status: 'overdue',
    image: '/teacher-demo/laser-pointer.jpg',
    traceNote: '用途：学生创新创业大赛指导答辩；登记编码 OFF-PEN-2024-06。',
    historyLines: [
      '2026-02-18 领用 · 场景：校赛路演答辩',
      '2026-04-10 系统提醒即将到期',
      '2026-04-13 已逾期待归还',
    ],
  },
  {
    id: 3,
    name: '实验课耗材包（机械原理）',
    spec: '课堂粉笔 + A4 讲义夹',
    borrowedAt: '2025-11-10',
    dueAt: '2026-12-31',
    location: '实验楼 B202 仪器柜',
    status: 'ok',
    image: '/teacher-demo/a4-paper.jpg',
    traceNote: '用途：机械原理实验课常规教学；学期内持续领用。',
    historyLines: [
      '2025-11-10 首次领用 · 场景：实验课',
      '2026-03-05 补充领用 · 场景：期中实训',
    ],
  },
  {
    id: 4,
    name: '活动扩音设备（迎新宣讲）',
    spec: '充电款 · 含肩带',
    borrowedAt: '2025-09-01',
    dueAt: '2025-12-20',
    location: '已归还 · 后勤仓库',
    status: 'returned',
    image: '/teacher-demo/water.jpg',
    traceNote: '用途：迎新与社团宣讲活动；已完成归还入库。',
    historyLines: [
      '2025-09-01 领用 · 场景：新生见面会',
      '2025-10-22 二次使用 · 场景：社团招新宣讲',
      '2025-12-18 归还登记完成',
    ],
  },
]

export function getDemoAsset(id: number): DemoAsset | undefined {
  return DEMO_ASSETS.find((a) => a.id === id)
}
