/**
 * 扫码出库：二维码 / 条码载荷须与 SCAN_OUTBOUND_CODE 完全一致（区分大小写），末尾为回车。
 */
export const SCAN_OUTBOUND_CODE = 'CAMPUS-SC-OUT-2026'

/** 出库成功弹窗展示的固定文案（与扫码出库单模板一致时可在此维护） */
export const SCAN_SUCCESS_DISPLAY = {
  outOrderNo: 'OUT-HIST-80006-1',
  receiver: '张老师',
  destination: '教学楼 A303 教室',
  handoffCode: 'HDP80006',
  /** 与弹窗展示一致；可与实际接口返回时间分开维护 */
  outTime: '2026-04-15 14:30:00',
} as const

/** 成功弹窗表格行（含规格、库存状态） */
export const SCAN_SUCCESS_LINES = [
  { goods_name: '答题卡', spec: 'A4', quantity: 240, unit: '张', stock_status: '充足' },
  { goods_name: '草稿纸', spec: '通用', quantity: 240, unit: '张', stock_status: '充足' },
  { goods_name: '备用中性笔', spec: '通用', quantity: 20, unit: '支', stock_status: '仅剩 8' },
  { goods_name: '密封条', spec: '通用', quantity: 8, unit: '卷', stock_status: '充足' },
  { goods_name: '瓶装饮用水', spec: '550ml', quantity: 80, unit: '瓶', stock_status: '充足' },
  { goods_name: '标准型便携急救箱', spec: '通用', quantity: 2, unit: '个', stock_status: '仅剩 1' },
] as const

/** 提交出库接口用的行（无规格字段） */
export const SCAN_OUTBOUND_API_ITEMS = SCAN_SUCCESS_LINES.map((r) => ({
  goods_name: r.goods_name,
  quantity: r.quantity,
  unit: r.unit,
}))
