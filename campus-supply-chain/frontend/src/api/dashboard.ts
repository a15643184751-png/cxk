import request from './request'

export interface StatItem {
  title: string
  value: number
  trend: string
  trendValue: string
  icon: string
  path: string
}

export interface WarningItem {
  id: number
  time: string
  level: string
  levelLabel: string
  material: string
  desc: string
}

export interface TodoItem {
  id: number
  time: string
  status: string
  statusLabel: string
  title: string
  desc: string
}

export interface SupplierOrderItem {
  id: number
  time: string
  title: string
  desc: string
}

export interface ExpiringItem {
  name: string
  days: number
  count: number
}

export interface ChartData {
  x: string[]
  purchase: number[]
  output: number[]
}

export interface HandoffTask {
  id: number
  order_no: string
  status: string
  status_label: string
  receiver_name: string
  destination: string
  handoff_code: string
}

export interface TodayTodos {
  pendingStockIn: number
  pendingStockOut: number
  pendingDeliveryCreate: number
}

export interface IDSSecurity {
  total: number
  blockedCount: number
  todayCount: number
  latest?: {
    client_ip: string
    attack_type: string
    created_at: string
  }
}

export interface OutboundLine {
  goods_name: string
  quantity: number
  unit: string
  batch_no?: string
}

export interface PendingOutboundDocument {
  purchase_id: number
  order_no: string
  destination: string
  receiver_name: string
  applicant_name: string
  applicant_role: string
  material_type: string
  created_at: string
  lines: OutboundLine[]
}

export interface RecentOutboundSlip {
  stock_out_order_no: string
  purchase_id: number | null
  purchase_order_no: string
  destination: string
  receiver_name: string
  handoff_code: string
  created_at: string
  lines: OutboundLine[]
}

export interface DashboardData {
  stats: StatItem[]
  warnings?: WarningItem[]
  warningList?: (WarningItem | TodoItem | SupplierOrderItem)[]
  expiringItems: ExpiringItem[]
  chartData: ChartData
  todayTodos?: TodayTodos
  handoffTasks?: HandoffTask[]
  idsSecurity?: IDSSecurity
  pendingOutboundDocuments?: PendingOutboundDocument[]
  recentOutboundSlips?: RecentOutboundSlip[]
}

export function getDashboard() {
  return request.get<DashboardData>('/dashboard')
}

export interface WarehouseScreenData {
  stats: {
    inventoryTotal: number
    inventoryQtySum: number
    stockInToday: number
    stockOutToday: number
    warningPending: number
    deliveryOngoing: number
    pendingStockIn: number
    pendingStockOut: number
    pendingDeliveryCreate: number
    waitingReceive: number
  }
  chart: { labels: string[]; in: number[]; out: number[] }
  inventoryTop: { name: string; quantity: number }[]
  warnings: { id: number; material: string; level: string; desc: string }[]
  expiring: { name: string; days: number; count: number }[]
  deliveries: { id: number; delivery_no: string; destination: string; status: string; status_label: string; receiver_name: string; handoff_code: string }[]
  handoffTasks: { id: number; order_no: string; status: string; status_label: string; receiver_name: string; destination: string; handoff_code: string; summary: string }[]
  pendingOutboundDocuments?: PendingOutboundDocument[]
  recentOutboundSlips?: RecentOutboundSlip[]
}

export function getWarehouseScreen() {
  return request.get<WarehouseScreenData>('/dashboard/screen/warehouse')
}

export interface LogisticsScreenData {
  stats: {
    purchasePending: number
    supplierPending: number
    stockPending: number
    dispatchPending: number
    receivePending: number
    purchaseCompleted: number
    supplierCount: number
    warningPending: number
    deliveryOngoing: number
  }
  chart: { labels: string[]; purchase: number[] }
  pendingPurchases: { id: number; order_no: string; applicant: string; summary: string }[]
  handoffList: { id: number; order_no: string; status: string; status_label: string; handoff_code: string; receiver_name: string; destination: string }[]
  warnings: { id: number; material: string; level: string; desc: string }[]
  deliveries: { id: number; delivery_no: string; destination: string; status: string; receiver_name: string; handoff_code: string }[]
}

export function getLogisticsScreen() {
  return request.get<LogisticsScreenData>('/dashboard/screen/logistics')
}

export interface SupplyChainOverviewScreenData {
  stats: { title: string; value: number; path: string; accent: string }[]
  pipeline: {
    key: string
    title: string
    subtitle: string
    count: number
    done: boolean
    targetPath: string
  }[]
  risk: {
    warningPending: number
    idsToday: number
    idsBlocked: number
    recentWarnings: {
      id: number
      material: string
      level: string
      status: string
      desc: string
      created_at: string
    }[]
    recentEvents: {
      id: number
      client_ip: string
      attack_type: string
      blocked: number
      path: string
      created_at: string
    }[]
  }
  recentOrders: {
    id: number
    order_no: string
    status: string
    status_label: string
    receiver_name: string
    destination: string
    created_at: string
  }[]
  updatedAt: string
}

export function getSupplyChainOverviewScreen() {
  return request.get<SupplyChainOverviewScreenData>('/overview/screen')
}

