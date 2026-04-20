<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Box,
  Calendar,
  DataLine,
  FullScreen,
  Location,
  Monitor,
  TrendCharts,
  Van,
  WarningFilled,
} from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { getWarehouseScreen } from '@/api/dashboard'
import { createStockIn, createStockOut } from '@/api/stock'
import { createDelivery } from '@/api/delivery'
import type { WarehouseScreenData } from '@/api/dashboard'
import {
  chartEnterAnimation,
  chartLoadingOption,
  chartPieSectorEnter,
  chartSupplyAxis,
  chartSupplyPalette,
} from '@/utils/chartAnimation'
import { getWarehouseScreenMock, mergeWarehouseScreenMock, type CampusCategory } from './warehouseScreenMock'

const router = useRouter()
const screenRoot = ref<HTMLElement | null>(null)
const loading = ref(true)
const apiData = ref<WarehouseScreenData | null>(null)
const baseMock = getWarehouseScreenMock()
const merged = computed(() => mergeWarehouseScreenMock(baseMock, apiData.value))

const trendPeriod = ref<'week' | 'month' | 'quarter'>('week')
const pieCategory = ref<CampusCategory | null>(null)
const top10Sort = ref<'qty' | 'turnover' | 'alert'>('qty')

const trendHost = ref<HTMLElement | null>(null)
const pieHost = ref<HTMLElement | null>(null)
let trendChart: echarts.ECharts | null = null
let pieChart: echarts.ECharts | null = null
let refreshTimer: ReturnType<typeof setInterval> | null = null

const filteredTop10 = computed(() => {
  let rows = [...merged.value.top10]
  if (pieCategory.value) {
    rows = rows.filter((r) => r.category === pieCategory.value)
  }
  if (top10Sort.value === 'qty') rows.sort((a, b) => b.quantity - a.quantity)
  else if (top10Sort.value === 'turnover') rows.sort((a, b) => a.turnoverDays - b.turnoverDays)
  else {
    rows.sort((a, b) => {
      const w: Record<string, number> = { critical: 3, low: 2, overstock: 1, ok: 0 }
      return (w[b.alertLevel] ?? 0) - (w[a.alertLevel] ?? 0)
    })
  }
  return rows.slice(0, 10)
})

const maxQty = computed(() => Math.max(1, ...filteredTop10.value.map((r) => r.quantity)))

function go(path: string) {
  void router.push(path)
}

function goGoodsStock() {
  void router.push({ path: '/goods', query: { tab: 'stock' } })
}

function toggleFullscreen() {
  const el = screenRoot.value
  if (!el) return
  if (!document.fullscreenElement) void el.requestFullscreen().catch(() => ElMessage.warning('全屏不可用'))
  else void document.exitFullscreen()
}

function renderTrend() {
  const el = trendHost.value
  const pack = merged.value.trend[trendPeriod.value]
  if (!el || !pack) return
  if (!trendChart) trendChart = echarts.init(el)
  trendChart.showLoading('default', chartLoadingOption)
  const accent = chartSupplyPalette.indigo
  const outC = chartSupplyPalette.cyan
  trendChart.setOption({
    ...chartEnterAnimation,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderColor: 'rgba(141, 160, 192, 0.35)',
      textStyle: { color: '#e2e8f0', fontSize: 12 },
    },
    legend: { data: ['入库', '出库'], textStyle: { color: 'rgba(226,232,240,0.85)', fontSize: 12 }, top: 4 },
    grid: { left: 52, right: 52, top: 40, bottom: 28 },
    xAxis: {
      type: 'category',
      data: pack.labels,
      axisLine: { lineStyle: { color: chartSupplyAxis.axisLine } },
      axisLabel: { color: chartSupplyAxis.axisLabel, fontSize: 11 },
    },
    yAxis: [
      {
        type: 'value',
        name: '件数',
        nameTextStyle: { color: chartSupplyAxis.axisLabel, fontSize: 11 },
        axisLine: { show: false },
        splitLine: { lineStyle: { color: chartSupplyAxis.splitLine } },
        axisLabel: { color: chartSupplyAxis.axisLabel, fontSize: 11 },
      },
      {
        type: 'value',
        name: '对比',
        show: false,
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: '入库',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        areaStyle: { color: 'rgba(107, 110, 255, 0.18)' },
        lineStyle: { width: 2, color: accent },
        itemStyle: { color: accent },
        data: pack.in,
        markPoint: {
          symbol: 'pin',
          symbolSize: 42,
          itemStyle: { color: '#a78bfa' },
          data: [{ type: 'max', name: '入库峰值' }],
        },
      },
      {
        name: '出库',
        type: 'line',
        smooth: true,
        symbol: 'circle',
        symbolSize: 8,
        areaStyle: { color: 'rgba(57, 168, 255, 0.14)' },
        lineStyle: { width: 2, color: outC },
        itemStyle: { color: outC },
        data: pack.out,
        markPoint: {
          symbol: 'pin',
          symbolSize: 42,
          itemStyle: { color: '#fbbf24' },
          data: [{ type: 'max', name: '出库峰值' }],
        },
      },
    ],
  })
  trendChart.hideLoading()
}

function renderPie() {
  const el = pieHost.value
  if (!el) return
  if (!pieChart) pieChart = echarts.init(el)
  pieChart.off('click')
  pieChart.setOption({
    ...chartEnterAnimation,
    ...chartPieSectorEnter,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderColor: 'rgba(141, 160, 192, 0.35)',
      textStyle: { color: '#e2e8f0' },
    },
    legend: { bottom: 0, textStyle: { color: 'rgba(226,232,240,0.75)', fontSize: 10 }, itemWidth: 10, itemHeight: 10 },
    series: [
      {
        type: 'pie',
        radius: ['42%', '68%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 6, borderColor: 'rgba(15,23,42,0.9)', borderWidth: 2 },
        label: { color: 'rgba(226,232,240,0.9)', fontSize: 11 },
        data: merged.value.categoryPie.map((d, i) => ({
          ...d,
          itemStyle: {
            color: ['#6B6EFF', '#39A8FF', '#8B5CF6', '#4C88FF', '#D6A44A'][i % 5],
          },
        })),
      },
    ],
  })
  pieChart.on('click', (p: any) => {
    const name = p?.name as CampusCategory
    if (pieCategory.value === name) pieCategory.value = null
    else pieCategory.value = name
    ElMessage.info(pieCategory.value ? `已筛选：${pieCategory.value}` : '已显示全部分类')
  })
}

function resizeCharts() {
  trendChart?.resize()
  pieChart?.resize()
}

async function load() {
  loading.value = true
  try {
    const res: any = await getWarehouseScreen()
    apiData.value = (res?.data ?? res) as WarehouseScreenData
  } catch {
    apiData.value = null
    ElMessage.info('接口暂不可用，已使用本地缓存数据')
  } finally {
    loading.value = false
    await nextTick()
    renderTrend()
    renderPie()
    resizeCharts()
  }
}

async function quickStockIn(task: { id: number }) {
  try {
    await createStockIn({ purchase_id: task.id })
    ElMessage.success('入库成功')
    load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '入库失败')
  }
}

async function quickStockOut(task: { id: number }) {
  try {
    await createStockOut({ purchase_id: task.id })
    ElMessage.success('出库成功')
    load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '出库失败')
  }
}

async function quickCreateDelivery(task: { id: number; destination?: string; receiver_name?: string }) {
  try {
    await createDelivery({
      purchase_id: task.id,
      destination: task.destination || '',
      receiver_name: task.receiver_name || '',
    })
    ElMessage.success('配送单已创建')
    load()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '创建失败')
  }
}

function alertToneClass(level: string) {
  if (level === 'red') return 'is-red'
  if (level === 'yellow') return 'is-yellow'
  return 'is-blue'
}

function warehouseDotClass(s: string) {
  if (s === 'danger') return 'dot--danger'
  if (s === 'warn') return 'dot--warn'
  return 'dot--ok'
}

function chainClass(s: string) {
  if (s === 'error') return 'chain-node--err'
  if (s === 'delay') return 'chain-node--delay'
  return 'chain-node--ok'
}

watch([merged, trendPeriod], () => {
  void nextTick(() => renderTrend())
})

watch(merged, () => {
  void nextTick(() => renderPie())
})

onMounted(() => {
  load()
  refreshTimer = setInterval(load, 30000)
  window.addEventListener('resize', resizeCharts)
})

onUnmounted(() => {
  refreshTimer && clearInterval(refreshTimer)
  window.removeEventListener('resize', resizeCharts)
  trendChart?.dispose()
  pieChart?.dispose()
  trendChart = null
  pieChart = null
})

const handoffTasks = computed(() => apiData.value?.handoffTasks ?? [])
const pendingOutboundDocuments = computed(() => apiData.value?.pendingOutboundDocuments ?? [])
const recentOutboundSlips = computed(() => apiData.value?.recentOutboundSlips ?? [])
</script>

<template>
  <div ref="screenRoot" class="wh-screen">
    <header class="wh-head">
      <div class="wh-head__left">
        <div class="wh-brand">
          <el-icon class="wh-brand__ico"><Monitor /></el-icon>
          <div>
            <h1>校园仓储智慧大屏</h1>
            <p class="wh-brand__sub">
              <span v-for="(t, i) in merged.heroTags" :key="i" class="wh-chip">{{ t }}</span>
            </p>
          </div>
        </div>
      </div>
      <div class="wh-head__right">
        <span class="wh-refresh">每 30 秒自动刷新</span>
        <el-button type="primary" plain size="small" class="wh-fs-btn" @click="toggleFullscreen">
          <el-icon><FullScreen /></el-icon>
          全屏展示
        </el-button>
      </div>
    </header>

    <div v-loading="loading" class="wh-body">
      <!-- 顶部 KPI 四组 -->
      <section class="wh-kpi">
        <article
          v-for="grp in merged.kpiGroups"
          :key="grp.id"
          class="wh-kpi-card"
          :class="`wh-kpi-card--${grp.tone}`"
        >
          <header class="wh-kpi-card__hd">
            <span class="wh-kpi-card__title">{{ grp.title }}</span>
            <span class="wh-kpi-card__sub">{{ grp.subtitle }}</span>
          </header>
          <div class="wh-kpi-card__grid">
            <button
              v-for="it in grp.items"
              :key="it.key"
              type="button"
              class="wh-kpi-item"
              @click="go(it.route)"
            >
              <span class="wh-kpi-item__label">{{ it.label }}</span>
              <span class="wh-kpi-item__val">
                <template v-if="typeof it.value === 'number'">
                  <el-statistic :value="it.value" :value-style="{ fontSize: '26px', fontWeight: 700 }" />
                </template>
                <template v-else>{{ it.value }}<small v-if="it.unit" class="wh-unit">{{ it.unit }}</small></template>
              </span>
              <span v-if="it.tag" class="wh-kpi-tag">{{ it.tag }}</span>
            </button>
          </div>
        </article>
      </section>

      <!-- 中部：左双图 + 右 TOP10 / 预警 -->
      <section class="wh-mid">
        <div class="wh-panel wh-panel--wide">
          <div class="wh-panel__hd">
            <div class="wh-panel__title">
              <el-icon><TrendCharts /></el-icon>
              出入库趋势
            </div>
            <el-radio-group v-model="trendPeriod" size="small" class="wh-seg">
              <el-radio-button label="week">本周</el-radio-button>
              <el-radio-button label="month">本月</el-radio-button>
              <el-radio-button label="quarter">本季度</el-radio-button>
            </el-radio-group>
          </div>
          <p class="wh-trend-note">{{ merged.trend[trendPeriod].note }}</p>
          <div ref="trendHost" class="wh-chart wh-chart--trend" />
        </div>
        <div class="wh-panel">
          <div class="wh-panel__hd">
            <div class="wh-panel__title">
              <el-icon><DataLine /></el-icon>
              校园物资分类占比
            </div>
          </div>
          <p class="wh-pie-hint">点击扇区联动左侧库存 TOP10 · 再点一次取消筛选</p>
          <div ref="pieHost" class="wh-chart wh-chart--pie" />
          <div v-if="pieCategory" class="wh-filter-pill">
            当前：<strong>{{ pieCategory }}</strong>
            <el-button link type="primary" size="small" @click="pieCategory = null">清除</el-button>
          </div>
        </div>
        <div class="wh-panel wh-panel--list">
          <div class="wh-panel__hd">
            <div class="wh-panel__title">
              <el-icon><Box /></el-icon>
              库存 TOP10
            </div>
            <el-select v-model="top10Sort" size="small" style="width: 150px">
              <el-option label="按库存数量" value="qty" />
              <el-option label="按周转天数" value="turnover" />
              <el-option label="按预警等级" value="alert" />
            </el-select>
          </div>
          <div v-if="!filteredTop10.length" class="wh-empty-tip">当前分类下暂无 TOP 物资，请切换饼图筛选</div>
          <div v-else class="wh-top10">
            <div v-for="(row, idx) in filteredTop10" :key="row.name + idx" class="wh-top10__row">
              <span class="wh-top10__rank">{{ idx + 1 }}</span>
              <div class="wh-top10__meta">
                <span class="wh-top10__name">{{ row.name }}</span>
                <span class="wh-top10__cat">{{ row.category }}</span>
              </div>
              <div class="wh-top10__bar-wrap">
                <div class="wh-top10__bar" :style="{ width: `${(row.quantity / maxQty) * 100}%` }" />
              </div>
              <div class="wh-top10__nums">
                <span>{{ row.quantity }}</span>
                <small>安全线 {{ row.safeQty }}</small>
              </div>
            </div>
          </div>
        </div>
        <div class="wh-panel wh-panel--alerts">
          <div class="wh-panel__hd">
            <div class="wh-panel__title">
              <el-icon><WarningFilled /></el-icon>
              库存预警清单
              <span class="wh-badge">供应链安全检测</span>
            </div>
            <el-button type="danger" link size="small" @click="go('/warning')">去处理</el-button>
          </div>
          <ul class="wh-alert-list">
            <li
              v-for="a in merged.stockAlerts"
              :key="a.id"
              class="wh-alert"
              :class="alertToneClass(a.level)"
              @click="go(a.route)"
            >
              <div class="wh-alert__hd">
                <span class="wh-alert__title">{{ a.title }}</span>
                <div class="wh-alert__actions" @click.stop>
                  <button type="button" class="wh-alert__btn" @click="go('/purchase/apply')">发起采购</button>
                  <button type="button" class="wh-alert__link" @click="go('/stock/out')">调拨出库</button>
                </div>
              </div>
              <p class="wh-alert__reason">{{ a.reason }}</p>
              <p class="wh-alert__meta"><strong>影响部门</strong> {{ a.dept }}</p>
              <p class="wh-alert__sug"><strong>建议</strong> {{ a.suggestion }}</p>
            </li>
          </ul>
        </div>
      </section>

      <!-- 地图 + 配送 -->
      <section class="wh-map-row">
        <div class="wh-panel wh-map">
          <div class="wh-panel__hd">
            <div class="wh-panel__title">
              <el-icon><Location /></el-icon>
              校园仓储分布（示意）
            </div>
            <span class="wh-map-legend">
              <i class="dot dot--ok" />正常
              <i class="dot dot--warn" />预警
              <i class="dot dot--danger" />异常
            </span>
          </div>
          <div class="wh-map__canvas">
            <div class="wh-map__grid" />
            <div
              v-for="w in merged.campusWarehouses"
              :key="w.id"
              class="wh-map__pin"
              :class="warehouseDotClass(w.status)"
              :style="{ left: w.x + '%', top: w.y + '%' }"
              @click="goGoodsStock()"
            >
              <span class="wh-map__pin-label">{{ w.short }}</span>
              <div class="wh-map__tip">
                <strong>{{ w.name }}</strong>
                <span>在库约 {{ w.inventory }} 件 · 待办 {{ w.todos }}</span>
              </div>
            </div>
          </div>
        </div>
        <div class="wh-panel wh-deliver">
          <div class="wh-panel__hd">
            <div class="wh-panel__title">
              <el-icon><Van /></el-icon>
              配送实时看板 · 全链路溯源
            </div>
            <el-button link type="primary" size="small" @click="go('/delivery')">进入配送管理</el-button>
          </div>
          <div class="wh-deliver__list">
            <div v-for="d in merged.deliveriesLive" :key="d.id" class="wh-deliver__row" @click="go('/trace')">
              <div class="wh-deliver__no">{{ d.delivery_no }}</div>
              <div class="wh-deliver__goods">{{ d.goods }}</div>
              <div class="wh-deliver__dest">{{ d.destination }}</div>
              <el-progress :percentage="d.progress" :stroke-width="10" striped striped-flow />
              <div class="wh-deliver__foot">
                <span>{{ d.status }}</span>
                <span class="wh-deliver__eta">{{ d.eta }}</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 出库单与备货（与工作台同源） -->
      <section
        v-if="pendingOutboundDocuments.length || recentOutboundSlips.length"
        class="wh-outbound-sync"
      >
        <div class="wh-panel wh-panel--full">
          <div class="wh-panel__hd">
            <div class="wh-panel__title">
              <el-icon><Box /></el-icon>
              教师申领 · 出库备货单 / 已开出库回执
            </div>
            <el-button link type="primary" size="small" @click="go('/dashboard')">工作台</el-button>
          </div>
          <div class="wh-outbound-sync__grid">
            <div
              v-for="doc in pendingOutboundDocuments"
              :key="doc.purchase_id"
              class="wh-outbound-card wh-outbound-card--pending"
            >
              <div class="wh-outbound-card__hd">
                <span class="wh-outbound-tag">待出库</span>
                <strong>{{ doc.order_no }}</strong>
                <el-button type="success" size="small" @click="quickStockOut({ id: doc.purchase_id })">出库</el-button>
              </div>
              <p class="wh-muted">{{ doc.applicant_name }} → {{ doc.destination || '—' }}</p>
              <p class="wh-outbound-lines">{{ doc.lines.map((l) => `${l.goods_name}×${l.quantity}${l.unit}`).join('；') }}</p>
            </div>
            <div
              v-for="slip in recentOutboundSlips"
              :key="slip.stock_out_order_no"
              class="wh-outbound-card wh-outbound-card--done"
            >
              <div class="wh-outbound-card__hd">
                <span class="wh-outbound-tag wh-outbound-tag--done">已出库</span>
                <strong>{{ slip.stock_out_order_no }}</strong>
              </div>
              <p class="wh-muted">{{ slip.purchase_order_no }} · 交接 {{ slip.handoff_code || '—' }}</p>
              <p class="wh-outbound-lines">{{ slip.lines.slice(0, 4).map((l) => `${l.goods_name}×${l.quantity}`).join('；') }}</p>
            </div>
          </div>
        </div>
      </section>

      <!-- 仓储执行闭环（接口有则展示） -->
      <section v-if="handoffTasks.length" class="wh-handoff">
        <div class="wh-panel wh-panel--full">
          <div class="wh-panel__hd">
            <div class="wh-panel__title">
              <el-icon><Calendar /></el-icon>
              仓储执行闭环（来自业务系统）
            </div>
          </div>
          <div class="wh-handoff__grid">
            <div v-for="task in handoffTasks" :key="task.id" class="wh-handoff__card">
              <div class="wh-handoff__no">{{ task.order_no }}</div>
              <el-tag size="small" type="warning">{{ task.status_label }}</el-tag>
              <p>{{ task.receiver_name }} · {{ task.destination }}</p>
              <p class="wh-muted">交接码 {{ task.handoff_code }}</p>
              <div class="wh-handoff__act">
                <el-button
                  v-if="task.status === 'shipped' || task.status === 'approved'"
                  type="primary"
                  size="small"
                  @click="quickStockIn(task)"
                >入库</el-button>
                <el-button v-if="task.status === 'stocked_in'" type="success" size="small" @click="quickStockOut(task)">出库</el-button>
                <el-button v-if="task.status === 'stocked_out'" type="warning" size="small" @click="quickCreateDelivery(task)">创建配送</el-button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- 底部 AI + 全链路 -->
      <section class="wh-bottom">
        <div class="wh-panel wh-ai">
          <div class="wh-panel__hd">
            <div class="wh-panel__title">AI 仓储健康度</div>
            <el-tag type="success" effect="dark">综合 {{ merged.aiHealth.score }} 分</el-tag>
          </div>
          <div class="wh-ai__body">
            <div class="wh-ai__score-ring">
              <span class="wh-ai__num">{{ merged.aiHealth.score }}</span>
              <span class="wh-ai__lbl">健康度</span>
            </div>
            <div class="wh-ai__txt">
              <p class="wh-ai__sec-title">扣分项</p>
              <ul>
                <li v-for="(d, i) in merged.aiHealth.deductions" :key="'d' + i">{{ d }}</li>
              </ul>
              <p class="wh-ai__sec-title">智能建议</p>
              <ul>
                <li v-for="(s, i) in merged.aiHealth.suggestions" :key="'s' + i">{{ s }}</li>
              </ul>
            </div>
          </div>
        </div>
        <div class="wh-panel wh-chain">
          <div class="wh-panel__hd">
            <div class="wh-panel__title">全链路流程监控</div>
            <el-button link type="primary" size="small" @click="go('/trace')">溯源查询</el-button>
          </div>
          <div class="wh-chain__flow">
            <template v-for="(node, idx) in merged.chainNodes" :key="node.id">
              <button
                type="button"
                class="wh-chain-node"
                :class="chainClass(node.status)"
                @click="node.route && go(node.route)"
              >
                <span class="wh-chain-node__label">{{ node.label }}</span>
                <span class="wh-chain-node__hint">{{ node.hint }}</span>
              </button>
              <span v-if="idx < merged.chainNodes.length - 1" class="wh-chain__arrow">→</span>
            </template>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.wh-screen {
  min-height: calc(100vh - 64px);
  background: linear-gradient(160deg, var(--screen-bg-top) 0%, var(--screen-bg-mid) 45%, var(--screen-bg-bottom) 100%);
  color: var(--screen-text);
  padding: 20px 24px 28px;
}

.wh-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}
.wh-brand {
  display: flex;
  gap: 14px;
  align-items: center;
  h1 {
    margin: 0;
    font-size: 22px;
    font-weight: 700;
    letter-spacing: 0.02em;
  }
}
.wh-brand__ico {
  font-size: 32px;
  color: var(--screen-accent-strong);
}
.wh-brand__sub {
  margin: 6px 0 0;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.wh-chip {
  font-size: 11px;
  padding: 3px 10px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.2);
  color: #c7d2fe;
  border: 1px solid rgba(165, 180, 252, 0.35);
}
.wh-head__right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
.wh-refresh {
  font-size: 12px;
  color: var(--screen-muted);
}
.wh-fs-btn {
  color: #e0e7ff !important;
  border-color: rgba(165, 180, 252, 0.45) !important;
}

.wh-body {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* KPI */
.wh-kpi {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
@media (max-width: 1400px) {
  .wh-kpi {
    grid-template-columns: repeat(2, 1fr);
  }
}
.wh-kpi-card {
  border-radius: 14px;
  padding: 14px 14px 12px;
  border: 1px solid var(--screen-border-soft);
  background: var(--screen-panel);
  &--blue {
    box-shadow: 0 0 0 1px rgba(76, 136, 255, 0.12) inset;
  }
  &--amber {
    box-shadow: 0 0 0 1px rgba(214, 164, 74, 0.2) inset;
  }
  &--green {
    box-shadow: 0 0 0 1px rgba(52, 211, 153, 0.15) inset;
  }
  &--rose {
    box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.18) inset;
  }
}
.wh-kpi-card__hd {
  margin-bottom: 10px;
}
.wh-kpi-card__title {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: var(--screen-text);
}
.wh-kpi-card__sub {
  font-size: 11px;
  color: var(--screen-muted);
}
.wh-kpi-card__grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 8px;
}
.wh-kpi-item {
  text-align: left;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 10px;
  padding: 10px 10px 8px;
  background: rgba(15, 23, 42, 0.35);
  cursor: pointer;
  color: inherit;
  font: inherit;
  transition: border-color 0.2s, background 0.2s;
  &:hover {
    border-color: rgba(165, 180, 252, 0.45);
    background: rgba(30, 41, 59, 0.55);
  }
}
.wh-kpi-item__label {
  display: block;
  font-size: 11px;
  color: var(--screen-muted);
  margin-bottom: 4px;
}
.wh-kpi-item__val {
  display: block;
  :deep(.el-statistic__content) {
    color: var(--screen-accent-strong);
  }
}
.wh-kpi-card--amber .wh-kpi-item__val :deep(.el-statistic__content) {
  color: #fbbf24;
}
.wh-kpi-card--green .wh-kpi-item__val :deep(.el-statistic__content) {
  color: #6ee7b7;
}
.wh-kpi-card--rose .wh-kpi-item__val :deep(.el-statistic__content) {
  color: #fca5a5;
}
.wh-unit {
  margin-left: 4px;
  font-size: 12px;
  color: var(--screen-muted);
}
.wh-kpi-tag {
  display: inline-block;
  margin-top: 6px;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(251, 191, 36, 0.2);
  color: #fcd34d;
}

/* 中部栅格 */
.wh-mid {
  display: grid;
  grid-template-columns: 1.35fr 0.85fr;
  grid-template-rows: auto auto;
  gap: 14px;
}
.wh-panel--wide {
  grid-column: 1;
  grid-row: 1;
}
.wh-panel:not(.wh-panel--wide):not(.wh-panel--list):not(.wh-panel--alerts) {
  grid-column: 2;
  grid-row: 1;
}
.wh-panel--list {
  grid-column: 1;
  grid-row: 2;
}
.wh-panel--alerts {
  grid-column: 2;
  grid-row: 2;
}
@media (max-width: 1200px) {
  .wh-mid {
    grid-template-columns: 1fr;
  }
  .wh-panel--wide,
  .wh-panel:not(.wh-panel--wide):not(.wh-panel--list):not(.wh-panel--alerts),
  .wh-panel--list,
  .wh-panel--alerts {
    grid-column: 1;
    grid-row: auto;
  }
}

.wh-panel {
  background: var(--screen-panel);
  border: 1px solid var(--screen-border-soft);
  border-radius: 12px;
  padding: 14px 16px 16px;
}
.wh-panel__hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}
.wh-panel__title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--screen-text);
}
.wh-seg :deep(.el-radio-button__inner) {
  padding: 6px 12px;
}
.wh-trend-note {
  margin: 0 0 6px;
  font-size: 12px;
  color: var(--screen-muted);
  line-height: 1.45;
}
.wh-chart--trend {
  height: 260px;
}
.wh-chart--pie {
  height: 220px;
}
.wh-pie-hint {
  margin: 0 0 4px;
  font-size: 11px;
  color: var(--screen-muted);
}
.wh-filter-pill {
  margin-top: 6px;
  font-size: 12px;
  color: #c7d2fe;
}

.wh-empty-tip {
  padding: 24px 12px;
  text-align: center;
  font-size: 12px;
  color: var(--screen-muted);
  border: 1px dashed var(--screen-border-soft);
  border-radius: 10px;
}

.wh-top10 {
  max-height: 320px;
  overflow-y: auto;
  padding-right: 2px;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.wh-top10::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}
.wh-top10__row {
  display: grid;
  grid-template-columns: 28px 1fr 1fr 72px;
  gap: 8px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--screen-border-soft);
  font-size: 12px;
}
.wh-top10__rank {
  font-weight: 700;
  color: var(--screen-accent-strong);
}
.wh-top10__meta {
  min-width: 0;
}
.wh-top10__name {
  display: block;
  color: var(--screen-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.wh-top10__cat {
  font-size: 10px;
  color: #93c5fd;
}
.wh-top10__bar-wrap {
  height: 8px;
  background: rgba(30, 41, 59, 0.85);
  border-radius: 999px;
  overflow: hidden;
}
.wh-top10__bar {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #4c88ff, #6b6eff);
  min-width: 4px;
  transition: width 0.45s ease;
}
.wh-top10__nums {
  text-align: right;
  color: #e2e8f0;
  small {
    display: block;
    font-size: 10px;
    color: var(--screen-muted);
  }
}

.wh-badge {
  margin-left: 8px;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(220, 38, 38, 0.25);
  color: #fecaca;
  font-weight: 600;
}
.wh-alert-list {
  list-style: none;
  margin: 0;
  padding: 0;
  max-height: 320px;
  overflow-y: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.wh-alert-list::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}
.wh-alert {
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 10px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: background 0.2s, border-color 0.2s;
  &.is-red {
    background: rgba(127, 29, 29, 0.35);
    border-color: rgba(248, 113, 113, 0.35);
  }
  &.is-yellow {
    background: rgba(113, 63, 18, 0.35);
    border-color: rgba(251, 191, 36, 0.35);
  }
  &.is-blue {
    background: rgba(30, 58, 138, 0.35);
    border-color: rgba(129, 140, 248, 0.35);
  }
  &:hover {
    filter: brightness(1.08);
  }
}
.wh-alert__hd {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 10px 12px;
  margin-bottom: 6px;
}
.wh-alert__title {
  font-weight: 600;
  flex: 1;
  min-width: 0;
  line-height: 1.35;
}
.wh-alert__actions {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px 12px;
  flex-shrink: 0;
  margin-left: auto;
}
.wh-alert__btn {
  appearance: none;
  margin: 0;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.2;
  padding: 7px 14px;
  cursor: pointer;
  border: 1px solid rgba(147, 197, 253, 0.55);
  background: rgba(15, 23, 42, 0.65);
  color: #f8fafc;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.06) inset;
  transition:
    background 0.18s ease,
    border-color 0.18s ease,
    color 0.18s ease;
}
.wh-alert__btn:hover {
  background: rgba(37, 99, 235, 0.35);
  border-color: rgba(186, 230, 253, 0.85);
  color: #fff;
}
.wh-alert__link {
  appearance: none;
  margin: 0;
  padding: 7px 6px;
  border: none;
  background: none;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
  color: #7dd3fc;
  text-decoration: underline;
  text-underline-offset: 3px;
  letter-spacing: 0.02em;
  transition: color 0.15s ease;
}
.wh-alert__link:hover {
  color: #e0f2fe;
  text-decoration-thickness: 2px;
}
.wh-alert__reason,
.wh-alert__meta,
.wh-alert__sug {
  margin: 4px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: rgba(226, 232, 240, 0.9);
}

/* 地图行 */
.wh-map-row {
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 14px;
}
@media (max-width: 1200px) {
  .wh-map-row {
    grid-template-columns: 1fr;
  }
}
.wh-map__canvas {
  position: relative;
  height: 240px;
  border-radius: 10px;
  overflow: hidden;
  background: radial-gradient(ellipse 80% 70% at 50% 40%, rgba(76, 136, 255, 0.12), rgba(15, 23, 42, 0.95));
  border: 1px solid var(--screen-border-soft);
}
.wh-map__grid {
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(148, 163, 184, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(148, 163, 184, 0.08) 1px, transparent 1px);
  background-size: 28px 28px;
  opacity: 0.6;
}
.wh-map-legend {
  font-size: 11px;
  color: var(--screen-muted);
  display: flex;
  align-items: center;
  gap: 10px;
  .dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 4px;
  }
  .dot--ok {
    background: #34d399;
  }
  .dot--warn {
    background: #fbbf24;
  }
  .dot--danger {
    background: #f87171;
  }
}
.wh-map__pin {
  position: absolute;
  transform: translate(-50%, -50%);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
  color: #0f172a;
  border: 2px solid rgba(255, 255, 255, 0.35);
  transition: transform 0.2s, box-shadow 0.2s;
  &:hover {
    transform: translate(-50%, -50%) scale(1.08);
    z-index: 3;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    .wh-map__tip {
      opacity: 1;
      pointer-events: none;
    }
  }
}
.wh-map__pin.dot--ok {
  background: linear-gradient(145deg, #6ee7b7, #34d399);
}
.wh-map__pin.dot--warn {
  background: linear-gradient(145deg, #fcd34d, #f59e0b);
}
.wh-map__pin.dot--danger {
  background: linear-gradient(145deg, #fca5a5, #ef4444);
  animation: wh-pulse 1.8s ease-in-out infinite;
}
@keyframes wh-pulse {
  0%,
  100% {
    box-shadow: 0 0 0 0 rgba(248, 113, 113, 0.5);
  }
  50% {
    box-shadow: 0 0 0 12px rgba(248, 113, 113, 0);
  }
}
.wh-map__pin-label {
  position: relative;
  z-index: 1;
}
.wh-map__tip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  min-width: 200px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(148, 163, 184, 0.35);
  font-size: 11px;
  font-weight: 400;
  color: #e2e8f0;
  opacity: 0;
  transition: opacity 0.2s;
  strong {
    display: block;
    margin-bottom: 4px;
  }
}

.wh-deliver__list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.wh-deliver__row {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid var(--screen-border-soft);
  cursor: pointer;
  transition: border-color 0.2s;
  &:hover {
    border-color: rgba(129, 140, 248, 0.45);
  }
}
.wh-deliver__no {
  font-size: 12px;
  font-weight: 600;
  color: #a5b4fc;
  margin-bottom: 4px;
}
.wh-deliver__goods {
  font-size: 13px;
  color: var(--screen-text);
  margin-bottom: 2px;
}
.wh-deliver__dest {
  font-size: 11px;
  color: var(--screen-muted);
  margin-bottom: 8px;
}
.wh-deliver__foot {
  display: flex;
  justify-content: space-between;
  margin-top: 6px;
  font-size: 11px;
  color: var(--screen-muted);
}
.wh-deliver__eta {
  color: #fcd34d;
}

.wh-outbound-sync {
  margin-top: 2px;
}
.wh-outbound-sync__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 10px;
}
.wh-outbound-card {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.45);
  border: 1px solid rgba(52, 211, 153, 0.35);
}
.wh-outbound-card--done {
  border-color: rgba(148, 163, 184, 0.35);
}
.wh-outbound-card__hd {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.wh-outbound-card__hd strong {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: #e2e8f0;
}
.wh-outbound-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 6px;
  border-radius: 4px;
  background: #059669;
  color: #fff;
}
.wh-outbound-tag--done {
  background: #475569;
}
.wh-outbound-lines {
  margin: 0;
  font-size: 11px;
  color: rgba(226, 232, 240, 0.88);
  line-height: 1.45;
}

.wh-handoff {
  margin-top: 2px;
}
.wh-panel--full {
  width: 100%;
}
.wh-handoff__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 10px;
}
.wh-handoff__card {
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.4);
  border: 1px solid var(--screen-border-soft);
}
.wh-handoff__no {
  font-weight: 600;
  margin-bottom: 6px;
}
.wh-muted {
  font-size: 11px;
  color: var(--screen-muted);
}
.wh-handoff__act {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.wh-bottom {
  display: grid;
  grid-template-columns: 1fr 1.2fr;
  gap: 14px;
}
@media (max-width: 1200px) {
  .wh-bottom {
    grid-template-columns: 1fr;
  }
}
.wh-ai__body {
  display: flex;
  gap: 20px;
  align-items: flex-start;
}
.wh-ai__score-ring {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: conic-gradient(from 210deg, #4c88ff, #6b6eff, #34d399, #4c88ff);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 12px 40px rgba(79, 70, 229, 0.25);
}
.wh-ai__num {
  font-size: 32px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
}
.wh-ai__lbl {
  font-size: 11px;
  color: #1e293b;
  margin-top: 4px;
}
.wh-ai__txt {
  flex: 1;
  font-size: 12px;
  line-height: 1.55;
  color: rgba(226, 232, 240, 0.92);
  ul {
    margin: 4px 0 12px 1.1em;
    padding: 0;
  }
}
.wh-ai__sec-title {
  margin: 0 0 4px;
  font-size: 12px;
  font-weight: 600;
  color: #93c5fd;
}

.wh-chain__flow {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}
.wh-chain-node {
  border: 1px solid var(--screen-border-soft);
  border-radius: 10px;
  padding: 10px 14px;
  min-width: 100px;
  text-align: center;
  background: rgba(15, 23, 42, 0.45);
  color: inherit;
  font: inherit;
  cursor: pointer;
  transition: border-color 0.2s, transform 0.2s;
  &:hover {
    transform: translateY(-2px);
    border-color: rgba(165, 180, 252, 0.45);
  }
}
.wh-chain-node__label {
  display: block;
  font-size: 13px;
  font-weight: 600;
}
.wh-chain-node__hint {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: var(--screen-muted);
}
.wh-chain-node--ok {
  border-color: rgba(52, 211, 153, 0.35);
}
.wh-chain-node--delay {
  border-color: rgba(251, 191, 36, 0.45);
}
.wh-chain-node--err {
  border-color: rgba(248, 113, 113, 0.55);
}
.wh-chain__arrow {
  color: var(--screen-muted);
  font-size: 14px;
}
</style>
