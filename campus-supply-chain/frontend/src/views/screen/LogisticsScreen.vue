<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import {
  chartEnterAnimation,
  chartLoadingOption,
  chartMutedAreaGradient,
  chartSupplyAxis,
  chartSupplyPalette,
} from '@/utils/chartAnimation'
import { getLogisticsScreen } from '@/api/dashboard'
import type { LogisticsScreenData } from '@/api/dashboard'

const router = useRouter()
const loading = ref(true)
const data = ref<LogisticsScreenData | null>(null)
const now = ref(new Date())
let chartInstance: echarts.ECharts | null = null
let refreshTimer: ReturnType<typeof setInterval> | null = null
let clockTimer: ReturnType<typeof setInterval> | null = null

const formattedTime = computed(() => {
  const d = now.value
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).replace(/\//g, '-')
})

function padNum(n: number) {
  return String(n).padStart(2, '0')
}

async function load() {
  const el = document.getElementById('lg-chart')
  if (el) {
    if (!chartInstance) chartInstance = echarts.init(el)
    chartInstance.showLoading('default', chartLoadingOption)
  }
  try {
    const res: any = await getLogisticsScreen()
    data.value = (res?.data ?? res) as LogisticsScreenData
    nextTick(() => renderChart())
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
}

function cssVar(name: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

function renderChart() {
  const el = document.getElementById('lg-chart')
  if (!el || !data.value?.chart) return
  if (!chartInstance) chartInstance = echarts.init(el)
  const { labels, purchase } = data.value.chart
  const accent = cssVar('--screen-accent', chartSupplyPalette.indigo)
  chartInstance.setOption({
    ...chartEnterAnimation,
    color: [accent],
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.95)',
      borderColor: 'rgba(141, 160, 192, 0.42)',
      textStyle: { color: '#94a3b8', fontSize: 12 },
      transitionDuration: 0.25,
    },
    grid: { left: 52, right: 24, top: 40, bottom: 32 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLine: { lineStyle: { color: chartSupplyAxis.axisLine } },
      axisLabel: { color: chartSupplyAxis.axisLabel, fontSize: 11 },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: chartSupplyAxis.splitLine } },
      axisLabel: { color: chartSupplyAxis.axisLabel, fontSize: 11 },
    },
    series: [
      {
        name: '采购申请',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 5,
        data: purchase,
        lineStyle: { width: 2, color: accent },
        itemStyle: { color: accent },
        showSymbol: false,
        emphasis: { focus: 'series', scale: true },
        universalTransition: true,
        areaStyle: {
          color: chartMutedAreaGradient('rgba(122, 141, 184, 0.34)', 'rgba(122, 141, 184, 0.03)'),
        },
      },
    ],
  }, true)
  chartInstance.hideLoading()
}

function goTo(path: string) {
  router.push(path)
}

const statCards = computed(() => {
  if (!data.value?.stats) return []
  const s = data.value.stats
  return [
    { value: s.purchasePending, label: '待审批申请', desc: '需要后勤审批', path: '/purchase', urgent: s.purchasePending > 0 },
    { value: s.supplierPending, label: '待供应商接单', desc: '供应侧待确认', path: '/purchase' },
    { value: s.stockPending, label: '待仓储入库', desc: '已发货待入库', path: '/purchase' },
    { value: s.dispatchPending, label: '待出库/配送', desc: '待执行配送链路', path: '/purchase' },
    { value: s.receivePending, label: '待教师签收', desc: '配送完成待确认', path: '/delivery' },
    { value: s.purchaseCompleted, label: '今日闭环完成', desc: '本日完成单据', path: '/purchase' },
  ]
})

const handoffInProgress = computed(() => {
  return (data.value?.handoffList || []).filter((h) => h.status !== 'pending')
})

const healthScore = computed(() => {
  const s = data.value?.stats
  if (!s) return 96
  const total = s.purchasePending + s.supplierPending + s.stockPending + s.dispatchPending + s.receivePending + s.purchaseCompleted
  if (total <= 0) return 96
  const pending = s.purchasePending + s.supplierPending + s.stockPending + s.dispatchPending + s.receivePending
  const score = Math.max(72, Math.min(99, Math.round((1 - pending / (total + 2)) * 100)))
  return score
})

const highWarningCount = computed(() => (data.value?.warnings || []).filter((w) => w.level === 'high').length)
const focusWarnings = computed(() => (data.value?.warnings || []).slice(0, 5))
const focusDeliveries = computed(() => (data.value?.deliveries || []).slice(0, 6))
const focusPurchases = computed(() => (data.value?.pendingPurchases || []).slice(0, 6))

onMounted(() => {
  load()
  refreshTimer = setInterval(load, 30000)
  clockTimer = setInterval(() => { now.value = new Date() }, 1000)
})

onUnmounted(() => {
  refreshTimer && clearInterval(refreshTimer)
  clockTimer && clearInterval(clockTimer)
  chartInstance?.dispose()
})
</script>

<template>
  <div class="screen">
    <header class="header">
      <div>
        <p class="head-kicker">LOGISTICS CONTROL CENTER</p>
        <h1>后勤运营大屏</h1>
        <p class="head-sub">采购审批、仓配联动与风险处置一体化看板</p>
      </div>
      <div class="header-meta">
        <span class="meta-pill">每 30 秒自动刷新</span>
        <span class="clock">{{ formattedTime }}</span>
      </div>
    </header>

    <main v-loading="loading" class="main">
      <template v-if="data">
        <section class="hero-grid">
          <div class="hero-kpis">
            <div
              v-for="(card, i) in statCards"
              :key="i"
              class="kpi-card"
              :class="{ urgent: card.urgent }"
              @click="goTo(card.path)"
            >
              <p class="kpi-label">{{ card.label }}</p>
              <p class="kpi-value">{{ padNum(card.value) }}</p>
              <p class="kpi-desc">{{ card.desc }}</p>
            </div>
          </div>
          <div class="health-card">
            <div class="panel-head">
              <span class="panel-title">链路健康度</span>
              <span class="panel-badge">{{ healthScore }}分</span>
            </div>
            <div class="health-meter">
              <div class="health-track">
                <div class="health-fill" :style="{ width: `${healthScore}%` }" />
              </div>
              <div class="health-meta">
                <span>高优先预警 {{ highWarningCount }}</span>
                <span>进行中交接 {{ handoffInProgress.length }}</span>
              </div>
            </div>
            <div class="quick-actions">
              <el-button size="small" type="primary" @click="goTo('/purchase')">进入审批台</el-button>
              <el-button size="small" @click="goTo('/delivery')">查看配送看板</el-button>
            </div>
          </div>
        </section>

        <section class="canvas-grid">
          <div class="panel trend-panel">
            <div class="panel-head">
              <span class="panel-title">申请趋势与波峰监控</span>
              <span class="panel-sub">识别高峰日，提前准备审批与仓储资源</span>
            </div>
            <div id="lg-chart" class="chart" />
          </div>

          <div class="panel todo-panel">
            <div class="panel-head">
              <span class="panel-title">审批工作池</span>
              <span class="panel-badge">{{ focusPurchases.length }}</span>
            </div>
            <div class="list-wrap">
              <div v-for="p in focusPurchases" :key="'p-' + p.id" class="list-row" @click="goTo('/purchase')">
                <span class="col-order">{{ p.order_no }}</span>
                <span class="col-applicant">{{ p.applicant }}</span>
                <span class="col-summary">{{ p.summary }}</span>
              </div>
              <div v-if="!focusPurchases.length" class="empty">当前无待审批申请</div>
            </div>
          </div>
        </section>

        <section class="ops-grid">
          <div class="panel warning-panel">
            <div class="panel-head">
              <span class="panel-title">风险预警队列</span>
              <span class="panel-badge">{{ focusWarnings.length }}</span>
            </div>
            <div class="list-wrap">
              <div v-for="w in focusWarnings" :key="w.id" class="list-row alert-row">
                <span class="tag" :class="w.level">{{ w.level === 'high' ? '高优' : '关注' }}</span>
                <span class="col-name">{{ w.material }}</span>
                <span class="col-desc">{{ w.desc }}</span>
              </div>
              <div v-if="!focusWarnings.length" class="empty">当前无预警</div>
            </div>
          </div>

          <div class="panel handoff-panel">
            <div class="panel-head">
              <span class="panel-title">在途交接链路</span>
              <span class="panel-badge">{{ focusDeliveries.length }}</span>
            </div>
            <div class="list-wrap">
              <div v-for="d in focusDeliveries" :key="d.id" class="list-row" @click="goTo('/delivery')">
                <span class="col-name">{{ d.delivery_no }}</span>
                <span class="col-dot" :class="d.status" />
                <span class="col-summary">{{ d.destination }} · {{ d.receiver_name }}</span>
              </div>
              <div v-if="!focusDeliveries.length" class="empty">当前无在途配送</div>
            </div>
          </div>
        </section>
      </template>
    </main>
  </div>
</template>

<style lang="scss" scoped>
.screen {
  min-height: calc(100vh - 64px);
  background:
    radial-gradient(1200px 380px at -10% -20%, rgba(139, 92, 246, 0.14), transparent 60%),
    radial-gradient(900px 320px at 110% -10%, rgba(76, 136, 255, 0.12), transparent 58%),
    linear-gradient(180deg, #f8f9ff 0%, #eef2ff 100%);
  color: #334155;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 28px 8px;
}

.head-kicker {
  margin: 0 0 6px;
  font-size: 11px;
  letter-spacing: 0.12em;
  color: #6b6eff;
  font-weight: 600;
}

.header h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
  color: #3b4ac8;
}

.head-sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: #66779f;
}

.header-meta {
  display: flex;
  align-items: center;
  gap: 14px;
}

.meta-pill {
  height: 30px;
  padding: 0 12px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: #5363cf;
  background: rgba(107, 110, 255, 0.12);
}

.clock {
  font-size: 13px;
  font-weight: 500;
  color: #4f5ebe;
}

.main {
  padding: 12px 28px 28px;
  min-height: calc(100vh - 64px - 80px);
}

.hero-grid {
  display: grid;
  grid-template-columns: 1fr 300px;
  gap: 16px;
  margin-bottom: 16px;
}

.hero-kpis {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}

.kpi-card {
  background: linear-gradient(180deg, #ffffff 0%, #f7f9ff 100%);
  border: 1px solid #dde3ff;
  border-radius: 12px;
  padding: 12px 14px;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;

  &:hover {
    border-color: rgba(107, 110, 255, 0.34);
    box-shadow: 0 8px 20px rgba(107, 110, 255, 0.12);
    transform: translateY(-1px);
  }

  &.urgent {
    border-color: rgba(245, 158, 11, 0.4);
  }
}

.kpi-label {
  margin: 0;
  font-size: 12px;
  color: #687aa6;
}

.kpi-value {
  margin: 8px 0 4px;
  font-size: 30px;
  font-weight: 700;
  color: #4656d6;
  line-height: 1;
}

.kpi-desc {
  margin: 0;
  font-size: 11px;
  color: #8a97b9;
}

.health-card {
  background: linear-gradient(180deg, #ffffff 0%, #f7f9ff 100%);
  border: 1px solid #dde3ff;
  border-radius: 12px;
  padding: 14px;
}

.health-meter {
  margin-top: 8px;
}

.health-track {
  height: 10px;
  border-radius: 999px;
  background: #e6ebff;
  overflow: hidden;
}

.health-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #6b6eff 0%, #4c88ff 100%);
  transition: width 0.4s ease;
}

.health-meta {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #64759e;
}

.quick-actions {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.canvas-grid {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
  gap: 16px;
  margin-bottom: 24px;
}

.ops-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.panel {
  background: linear-gradient(180deg, #ffffff 0%, #f7f9ff 100%);
  border: 1px solid #dde3ff;
  border-radius: 12px;
  padding: 16px;
}

.panel-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid #e6ebff;
}

.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: #3f4fcb;
}

.panel-sub {
  font-size: 11px;
  color: #7d8bb0;
}

.panel-badge {
  font-size: 11px;
  padding: 2px 8px;
  background: rgba(107, 110, 255, 0.14);
  color: #4f5ebe;
  border-radius: 4px;
  margin-left: auto;
}

.trend-panel .chart {
  height: 240px;
}

.list-wrap {
  max-height: 220px;
  overflow-y: auto;
}

.list-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  font-size: 12px;
  border-bottom: 1px solid #ebefff;
  cursor: pointer;
  transition: background 0.2s ease;

  &:hover {
    background: rgba(107, 110, 255, 0.06);
  }

  &:last-child {
    border-bottom: none;
  }
}

.col-order {
  min-width: 140px;
  font-weight: 600;
  color: #4b5bd2;
}

.col-applicant { color: #6b7aa2; flex-shrink: 0; }
.col-name { flex: 1; color: #334155; min-width: 0; }
.col-summary { color: #7082ab; font-size: 12px; flex: 1; min-width: 0; }
.col-desc { color: #7082ab; font-size: 12px; flex: 1; min-width: 0; }

.col-tag {
  padding: 2px 8px;
  font-size: 11px;
  border-radius: 4px;
  background: rgba(107, 110, 255, 0.14);
  color: #4f5ebe;
  flex-shrink: 0;
}

.tag {
  padding: 2px 8px;
  font-size: 11px;
  border-radius: 4px;
  flex-shrink: 0;
  &.high { background: rgba(239, 68, 68, 0.12); color: #c2410c; }
  &:not(.high) { background: rgba(245, 158, 11, 0.16); color: #b45309; }
}

.col-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  background: #7f8cff;

  &.on_way { background: #22c55e; }
  &.pending, &.loading { background: #fbbf24; }
}

.alert-row { cursor: default; }
.alert-row:hover { background: transparent; }

.empty {
  padding: 24px;
  text-align: center;
  color: #8d9abc;
  font-size: 12px;
}

@media (max-width: 1400px) {
  .hero-grid {
    grid-template-columns: 1fr;
  }
  .hero-kpis {
    grid-template-columns: repeat(3, 1fr);
  }
  .canvas-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .hero-kpis {
    grid-template-columns: repeat(2, 1fr);
  }
  .ops-grid,
  .quick-actions {
    grid-template-columns: 1fr;
  }
}
</style>
