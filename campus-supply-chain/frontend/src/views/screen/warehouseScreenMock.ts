/**
 * 仓储大屏本地数据：校园物资场景 + 供应链安全/溯源叙事（可与接口返回值合并）
 */
import type { WarehouseScreenData } from '@/api/dashboard'

export type CampusCategory =
  | '教学耗材'
  | '食堂物资'
  | '实验室设备'
  | '办公物资'
  | '应急物资'

export interface KpiItem {
  key: string
  label: string
  value: number | string
  unit?: string
  tag?: string
  route: string
  /** 用于数字动画的目标值（若为 number） */
  animate?: boolean
}

export interface KpiGroup {
  id: string
  title: string
  subtitle: string
  tone: 'blue' | 'amber' | 'green' | 'rose'
  items: KpiItem[]
}

export interface Top10Row {
  rank: number
  name: string
  category: CampusCategory
  quantity: number
  safeQty: number
  turnoverDays: number
  alertLevel: 'ok' | 'low' | 'critical' | 'overstock'
}

export interface StockAlertRow {
  id: string
  level: 'red' | 'yellow' | 'blue'
  title: string
  reason: string
  dept: string
  suggestion: string
  route: string
}

export interface CampusWarehouse {
  id: string
  name: string
  short: string
  /** 地图占位坐标 0–100 */
  x: number
  y: number
  status: 'ok' | 'warn' | 'danger'
  inventory: number
  todos: number
}

export interface DeliveryLiveRow {
  id: string
  delivery_no: string
  goods: string
  destination: string
  progress: number
  eta: string
  status: string
}

export interface ChainNode {
  id: string
  label: string
  status: 'ok' | 'delay' | 'error'
  hint: string
  route?: string
}

export interface WarehouseScreenMock {
  kpiGroups: KpiGroup[]
  trend: Record<'week' | 'month' | 'quarter', { labels: string[]; in: number[]; out: number[]; note: string }>
  categoryPie: { name: CampusCategory; value: number }[]
  top10: Top10Row[]
  stockAlerts: StockAlertRow[]
  campusWarehouses: CampusWarehouse[]
  deliveriesLive: DeliveryLiveRow[]
  aiHealth: { score: number; deductions: string[]; suggestions: string[] }
  chainNodes: ChainNode[]
  /** 全链路溯源 / 安全检测一句话 */
  heroTags: string[]
}

export function getWarehouseScreenMock(): WarehouseScreenMock {
  return {
    heroTags: ['供应链安全检测', 'AI 智能预警', '全链路溯源'],
    kpiGroups: [
      {
        id: 'overview',
        title: '库存总览',
        subtitle: '全局在库与结构健康度',
        tone: 'blue',
        items: [
          { key: 'qty', label: '在库总量（件）', value: 283420, route: '/goods?tab=stock', animate: true },
          { key: 'sku', label: '在库物资品类', value: 1286, unit: '类', route: '/goods?tab=stock', animate: true },
          { key: 'turn', label: '近30天周转率', value: '5.1', unit: '次/月', route: '/goods?tab=stock' },
        ],
      },
      {
        id: 'todo',
        title: '待办任务',
        subtitle: '需仓储侧闭环处理',
        tone: 'amber',
        items: [
          { key: 'in', label: '待入库申请', value: 36, tag: '待处理', route: '/stock/in', animate: true },
          { key: 'out', label: '待出库申请', value: 52, tag: '待处理', route: '/stock/out', animate: true },
          { key: 'del', label: '待创建配送', value: 24, tag: '待处理', route: '/delivery', animate: true },
          { key: 'recv', label: '待教师签收', value: 19, tag: '待处理', route: '/delivery', animate: true },
        ],
      },
      {
        id: 'today',
        title: '今日动态',
        subtitle: '当日作业进度',
        tone: 'green',
        items: [
          { key: 'tin', label: '今日入库', value: 138, unit: '单', route: '/stock/in', animate: true },
          { key: 'tout', label: '今日出库', value: 96, unit: '单', route: '/stock/out', animate: true },
          { key: 'tdone', label: '今日配送完成', value: 58, unit: '单', route: '/delivery', animate: true },
        ],
      },
      {
        id: 'risk',
        title: '风险预警',
        subtitle: '安全检测前置',
        tone: 'rose',
        items: [
          { key: 'warn', label: '待处理预警', value: 41, tag: '待闭环', route: '/warning', animate: true },
          { key: 'late', label: '超期未签收', value: 17, unit: '单', route: '/delivery', animate: true },
          { key: 'short', label: '低于安全线物资', value: 156, unit: 'SKU', route: '/warning', animate: true },
        ],
      },
    ],
    trend: {
      week: {
        labels: ['周一', '周二', '周三', '周四', '周五', '周六', '周日'],
        in: [118, 96, 142, 128, 165, 88, 74],
        out: [104, 112, 121, 138, 152, 94, 81],
        note: '本周五随「期中监考包」集中出库，入库在周三、周五形成双峰；出库峰值高于入库，建议关注教学耗材安全线。',
      },
      month: {
        labels: ['4/4', '4/5', '4/6', '4/7', '4/8', '4/9', '4/10', '4/11', '4/12', '4/13', '4/14', '4/15'],
        in: [52, 48, 61, 44, 55, 63, 58, 49, 71, 66, 54, 62],
        out: [46, 51, 55, 50, 48, 59, 62, 57, 68, 72, 61, 58],
        note: '本月上旬平稳，4/12 起随院系领用与食堂补货双向抬升；中旬出入库差值收窄，整体处于紧平衡。',
      },
      quarter: {
        labels: ['1月', '2月', '3月', '4月(累计)'],
        in: [2860, 2420, 3180, 1960],
        out: [2680, 2550, 3010, 1880],
        note: '一季度开学与春运后补库双峰；四月受赛事与考试周叠加，建议提前锁定「试卷袋、粉笔、饮用水」三类战略库存。',
      },
    },
    categoryPie: [
      { name: '教学耗材', value: 44 },
      { name: '食堂物资', value: 26 },
      { name: '实验室设备', value: 16 },
      { name: '办公物资', value: 20 },
      { name: '应急物资', value: 9 },
    ],
    top10: [
      { rank: 1, name: '矿泉水 550ml（箱）', category: '食堂物资', quantity: 1614, safeQty: 400, turnoverDays: 5, alertLevel: 'ok' },
      { rank: 2, name: '粉笔（彩色/白）', category: '教学耗材', quantity: 1410, safeQty: 600, turnoverDays: 7, alertLevel: 'ok' },
      { rank: 3, name: 'A4 打印纸 70g', category: '办公物资', quantity: 1135, safeQty: 400, turnoverDays: 10, alertLevel: 'ok' },
      { rank: 4, name: '大米 25kg', category: '食堂物资', quantity: 1021, safeQty: 300, turnoverDays: 13, alertLevel: 'ok' },
      { rank: 5, name: '食用油 5L', category: '食堂物资', quantity: 982, safeQty: 250, turnoverDays: 15, alertLevel: 'low' },
      { rank: 6, name: '课堂计时器', category: '教学耗材', quantity: 978, safeQty: 200, turnoverDays: 8, alertLevel: 'ok' },
      { rank: 7, name: '实验手套（乳胶）', category: '实验室设备', quantity: 756, safeQty: 400, turnoverDays: 19, alertLevel: 'low' },
      { rank: 8, name: '急救箱（标准配置）', category: '应急物资', quantity: 320, safeQty: 80, turnoverDays: 42, alertLevel: 'ok' },
      { rank: 9, name: '投影仪灯泡（通用型）', category: '教学耗材', quantity: 86, safeQty: 120, turnoverDays: 118, alertLevel: 'critical' },
      { rank: 10, name: '消毒液 5L', category: '应急物资', quantity: 64, safeQty: 100, turnoverDays: 17, alertLevel: 'critical' },
      { rank: 11, name: '激光笔/翻页笔', category: '教学耗材', quantity: 512, safeQty: 180, turnoverDays: 22, alertLevel: 'ok' },
      { rank: 12, name: '培养皿 90mm', category: '实验室设备', quantity: 2880, safeQty: 800, turnoverDays: 12, alertLevel: 'overstock' },
      { rank: 13, name: '订书钉 24/6', category: '办公物资', quantity: 1890, safeQty: 500, turnoverDays: 25, alertLevel: 'ok' },
      { rank: 14, name: '应急手电筒', category: '应急物资', quantity: 210, safeQty: 60, turnoverDays: 90, alertLevel: 'low' },
    ],
    stockAlerts: [
      {
        id: 'a1',
        level: 'red',
        title: '库存不足 · 投影仪灯泡',
        reason: '可用量低于安全线 28%，且两周内有 6 场公开课与 2 场校外监考抽测。',
        dept: '教务处 · 多媒体运维',
        suggestion: '建议发起紧急采购或校内调拨（图书馆分仓有少量备件）。',
        route: '/warning',
      },
      {
        id: 'a2',
        level: 'red',
        title: '超期在库 · 消毒液批次 H2024-11',
        reason: '批次已在主仓 C 区静置 15 天，周转偏慢；距保质期 18 天。',
        dept: '后勤保障处',
        suggestion: '优先保障食堂、医务室与宿舍消杀点位，剩余纳入演练消耗计划。',
        route: '/warning',
      },
      {
        id: 'a3',
        level: 'red',
        title: '库存不足 · 粉笔（白）',
        reason: '下周 4 场公开课 + 3 场教研活动共用教室，粉笔消耗模型预测缺口约 120 盒。',
        dept: '教学运行中心',
        suggestion: '可从教学楼便民点紧急调拨 80 盒，并同步触发补货审批。',
        route: '/purchase/apply',
      },
      {
        id: 'a4',
        level: 'yellow',
        title: '库存偏低 · 食用油',
        reason: '低于安全线 12%，食堂下周「校园开放日」与校友返校餐双线供餐。',
        dept: '饮食服务中心',
        suggestion: '确认供应商到货窗口，必要时启用备用品牌一件代发。',
        route: '/warning',
      },
      {
        id: 'a5',
        level: 'yellow',
        title: '临期关注 · 实验手套',
        reason: '180 天内到期占比 15%，实验课排课密度上升。',
        dept: '实验教学中心',
        suggestion: '拣货策略改为「先产先出」，并向各学院推送领用提醒。',
        route: '/stock/out',
      },
      {
        id: 'a6',
        level: 'yellow',
        title: '签收滞后 · 理工实验楼 B 座',
        reason: '2 单配送已到店超 48h 未签收，影响闭环率与 IDS 风险评分。',
        dept: '材料学院办公室',
        suggestion: '推送辅导员协助督促签收，或改约二次配送时段。',
        route: '/delivery',
      },
      {
        id: 'a7',
        level: 'blue',
        title: '库存积压 · 培养皿 90mm',
        reason: '生物学院课改后用量下降，连续 60 天出库低于安全出库线的 40%。',
        dept: '生物学院资产管理员',
        suggestion: '可校内调拨至医学院或发起学期末集中领用活动，释放库容。',
        route: '/goods?tab=stock',
      },
      {
        id: 'a8',
        level: 'blue',
        title: '库位占用 · 旧款订书机',
        reason: '90 天零出库，占用主仓流利架黄金面位。',
        dept: '行政资产科',
        suggestion: '报废评估或调拨至院系库房，提升拣货效率约 6%。',
        route: '/goods?tab=stock',
      },
    ],
    campusWarehouses: [
      { id: 'w1', name: '主仓库（北区中心仓）', short: '主仓', x: 22, y: 38, status: 'ok', inventory: 14120, todos: 4 },
      { id: 'w2', name: '食堂冷链分仓', short: '食堂', x: 48, y: 28, status: 'warn', inventory: 4680, todos: 6 },
      { id: 'w3', name: '实验楼危化暂存', short: '实验', x: 72, y: 44, status: 'ok', inventory: 2120, todos: 2 },
      { id: 'w4', name: '教学楼便民点', short: '教学', x: 58, y: 62, status: 'ok', inventory: 3840, todos: 1 },
      { id: 'w5', name: '体育馆赛事仓', short: '赛事', x: 38, y: 72, status: 'danger', inventory: 920, todos: 5 },
      { id: 'w6', name: '图书馆密集书库', short: '图书', x: 28, y: 58, status: 'ok', inventory: 1760, todos: 0 },
      { id: 'w7', name: '医务室药品微仓', short: '医务', x: 65, y: 30, status: 'warn', inventory: 902, todos: 2 },
    ],
    deliveriesLive: [
      {
        id: 'd1',
        delivery_no: 'DL20260415001',
        goods: '答题卡、草稿纸、密封条',
        destination: '第一教学楼 · 302 考场',
        progress: 78,
        eta: '今日 14:20 前',
        status: '配送中',
      },
      {
        id: 'd2',
        delivery_no: 'DL20260415002',
        goods: '桶装水 18.9L、急救箱',
        destination: '体育馆主场 · 赛事保障点',
        progress: 52,
        eta: '今日 16:00 前',
        status: '配送中',
      },
      {
        id: 'd3',
        delivery_no: 'DL20260415006',
        goods: '粉笔、白板笔、激光笔',
        destination: '人文学院 · 智慧教室 A201',
        progress: 34,
        eta: '今日 17:30 前',
        status: '已装车',
      },
      {
        id: 'd4',
        delivery_no: 'DL20260415009',
        goods: '实验废液收集桶（空）',
        destination: '理工实验楼 B 座 · 危化暂存区',
        progress: 88,
        eta: '今日 13:45 前',
        status: '已到店待签收',
      },
      {
        id: 'd5',
        delivery_no: 'DL20260414088',
        goods: '实验手套、护目镜、口罩',
        destination: '理工实验楼 B 座',
        progress: 100,
        eta: '昨日 18:02 完成',
        status: '已签收',
      },
      {
        id: 'd6',
        delivery_no: 'DL20260415011',
        goods: 'A4 纸、订书机、档案盒',
        destination: '行政楼 · 教务处',
        progress: 66,
        eta: '今日 15:10 前',
        status: '配送中',
      },
    ],
    aiHealth: {
      score: 82,
      deductions: [
        '待处理预警 41 条中红色级仍占 8 条，闭环滞后',
        '低于安全线 SKU 达 156 个，教学与食堂双线承压',
        '超期未签收 17 单，影响全链路溯源评分',
      ],
      suggestions: [
        '优先闭环三条红色预警，预计评分可回升 4～6 分。',
        '将「粉笔、答题卡、饮用水」纳入考试周日历联动预测，降低峰值缺货概率。',
        '对培养皿等慢动销 SKU 做一次院系调拨清单，可释放约 12㎡ 拣货面。',
        '开启配送节点 IDS 复核：到店 24h 未签收自动升级黄色提醒。',
        '食堂开放日前完成食用油补货，避免待办与预警双叠加。',
      ],
    },
    chainNodes: [
      { id: 'c1', label: '采购申请', status: 'ok', hint: '当日 64 单', route: '/purchase' },
      { id: 'c2', label: '审批', status: 'ok', hint: '平均 2.1h', route: '/purchase' },
      { id: 'c3', label: '入库', status: 'delay', hint: '36 单待办', route: '/stock/in' },
      { id: 'c4', label: '在库', status: 'ok', hint: '1286 类 SKU', route: '/goods?tab=stock' },
      { id: 'c5', label: '出库', status: 'delay', hint: '52 单待办', route: '/stock/out' },
      { id: 'c6', label: '配送', status: 'delay', hint: '24 单待发运', route: '/delivery' },
      { id: 'c7', label: '签收溯源', status: 'ok', hint: '19 单待签收', route: '/trace' },
    ],
  }
}

/** 有接口数据时严格采用接口数值，与工作台 /dashboard 一致；无接口时保留本地基准 */
function useApiKpi(mockVal: number | string, apiVal: number | undefined | null): number | string {
  if (typeof mockVal !== 'number') return mockVal
  if (apiVal === undefined || apiVal === null) return mockVal
  const a = Number(apiVal)
  return Number.isFinite(a) ? a : mockVal
}

/** 接口周趋势若全为 0 或长度不齐，会压扁 Y 轴；此时保留 mock 丰富曲线 */
function warehouseWeekChartIsUsable(chart: WarehouseScreenData['chart'] | undefined): boolean {
  if (!chart?.labels?.length) return false
  const n = Math.min(chart.labels.length, chart.in.length, chart.out.length)
  if (n < 3) return false
  let sum = 0
  for (let i = 0; i < n; i++) sum += (chart.in[i] ?? 0) + (chart.out[i] ?? 0)
  return sum > 0
}

/** 将后端仓储大屏数据与本地基准合并（在库总量用接口；待办/今日与接口同源，与工作台对齐） */
export function mergeWarehouseScreenMock(
  mock: WarehouseScreenMock,
  api: WarehouseScreenData | null
): WarehouseScreenMock {
  if (!api?.stats) return mock
  const s = api.stats
  const g = mock.kpiGroups.map((group) => ({
    ...group,
    items: group.items.map((it) => {
      if (group.id === 'overview' && it.key === 'qty') {
        const v = s.inventoryQtySum
        return { ...it, value: v != null && v > 0 ? v : it.value }
      }
      if (group.id === 'todo' && it.key === 'in') return { ...it, value: useApiKpi(it.value, s.pendingStockIn) }
      if (group.id === 'todo' && it.key === 'out') return { ...it, value: useApiKpi(it.value, s.pendingStockOut) }
      if (group.id === 'todo' && it.key === 'del') return { ...it, value: useApiKpi(it.value, s.pendingDeliveryCreate) }
      if (group.id === 'todo' && it.key === 'recv') return { ...it, value: useApiKpi(it.value, s.waitingReceive) }
      if (group.id === 'today' && it.key === 'tin') return { ...it, value: useApiKpi(it.value, s.stockInToday) }
      if (group.id === 'today' && it.key === 'tout') return { ...it, value: useApiKpi(it.value, s.stockOutToday) }
      if (group.id === 'risk' && it.key === 'warn') return { ...it, value: useApiKpi(it.value, s.warningPending) }
      return it
    }),
  }))
  const useApiWeek = warehouseWeekChartIsUsable(api.chart)
  const trend: WarehouseScreenMock['trend'] = {
    week: useApiWeek
      ? {
          labels: [...api.chart!.labels],
          in: [...api.chart!.in],
          out: [...api.chart!.out],
          note: mock.trend.week.note,
        }
      : { ...mock.trend.week },
    month: { ...mock.trend.month },
    quarter: { ...mock.trend.quarter },
  }
  return { ...mock, kpiGroups: g, trend }
}
