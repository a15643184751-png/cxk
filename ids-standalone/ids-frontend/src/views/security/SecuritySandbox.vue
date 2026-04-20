<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Search, WarningFilled } from '@element-plus/icons-vue'
import { analyzeQuarantineFiles, deleteQuarantineFile, getQuarantineReport, listQuarantineFiles } from '@/api/upload'
import type {
  QuarantineAnalysis,
  QuarantineAnalysisReport,
  QuarantineDecisionBasis,
  QuarantineItem,
  QuarantineRiskLevel,
  UploadAuditResult,
  UploadAuditVerdict,
} from '@/api/upload'

const loading = ref(false)
const route = useRoute()
const router = useRouter()
const items = ref<QuarantineItem[]>([])
const analysis = ref<QuarantineAnalysis | null>(null)
const activeTab = ref<'list' | 'analysis'>('list')
const searchQuery = ref('')
const riskFilter = ref<'all' | QuarantineRiskLevel>('all')
const detailOpen = ref(false)
const detailRow = ref<QuarantineItem | null>(null)
const syncOrchestrating = ref(false)
const captureOverlayVisible = ref(false)
const capturePhase = ref('')
const captureLogs = ref<string[]>([])
const threatPulse = ref(false)
const reportDrawerOpen = ref(false)
const lastCaptureReport = ref<QuarantineAnalysisReport | null>(null)
const highlightSavedAs = ref('')
const liveClock = ref('')
const tableRef = ref<any>(null)

const trendRef = ref<HTMLElement | null>(null)
const extRef = ref<HTMLElement | null>(null)
let trendChart: echarts.ECharts | null = null
let extChart: echarts.ECharts | null = null
let clockTimer: ReturnType<typeof setInterval> | null = null

const PIE_COLORS = ['#22d3ee', '#0ea5e9', '#34d399', '#f59e0b', '#fb7185', '#a78bfa']
const PIPELINE_STEPS = [
  { key: 'receive', label: '接收样本' },
  { key: 'scan', label: '静态扫描' },
  { key: 'ai', label: '上传审计' },
  { key: 'decision', label: '处置决策' },
  { key: 'done', label: '报告落账' },
] as const

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

function pushCaptureLog(message: string) {
  const ts = new Date().toLocaleString('zh-CN', { hour12: false })
  captureLogs.value = [...captureLogs.value, `[${ts}] ${message}`].slice(-80)
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function formatTime(iso?: string | null) {
  if (!iso) return '--'
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}

function riskLabel(level?: string) {
  if (level === 'high') return '高风险'
  if (level === 'medium') return '中风险'
  return '低风险'
}

function riskTagType(level?: string): 'danger' | 'warning' | 'info' {
  if (level === 'high') return 'danger'
  if (level === 'medium') return 'warning'
  return 'info'
}

function verdictLabel(verdict?: UploadAuditVerdict | null) {
  if (verdict === 'quarantine') return '扣留隔离'
  if (verdict === 'pass') return '通过放行'
  return '待复核'
}

function verdictTagType(verdict?: UploadAuditVerdict | null): 'danger' | 'success' | 'warning' {
  if (verdict === 'quarantine') return 'danger'
  if (verdict === 'pass') return 'success'
  return 'warning'
}

function reportTime(report?: QuarantineAnalysisReport | null) {
  return report?.analysis_generated_at || report?.last_updated_at || report?.generated_at || ''
}

function rowClassName({ row }: { row: QuarantineItem }) {
  return row.saved_as === highlightSavedAs.value ? 'is-new-capture' : ''
}

const filteredItems = computed(() => {
  const query = searchQuery.value.trim().toLowerCase()
  return items.value.filter((row) => {
    if (riskFilter.value !== 'all' && (row.risk_level ?? 'low') !== riskFilter.value) return false
    if (!query) return true
    return [row.saved_as, row.extension ?? '', row.audit_summary ?? '']
      .join(' ')
      .toLowerCase()
      .includes(query)
  })
})

const pipelineActiveIndex = computed(() => {
  if (!syncOrchestrating.value && !captureOverlayVisible.value) return -1
  const mapping: Record<string, number> = {
    接收样本: 0,
    静态扫描: 1,
    上传审计: 2,
    处置决策: 3,
    完成: 4,
  }
  return mapping[capturePhase.value] ?? 0
})

function detailNarrative(row: QuarantineItem) {
  return [
    `隔离编号：${row.saved_as}`,
    `扩展名：${row.extension ?? '(未知)'}`,
    `综合风险：${riskLabel(row.risk_level)}`,
    `最新裁决：${verdictLabel(row.audit_verdict)}`,
    `审计置信度：${row.audit_confidence ?? 0}`,
    `审计摘要：${row.audit_summary ?? '当前样本尚未生成可展示的摘要'}`,
    `入箱时间：${formatTime(row.modified_at)}`,
    `文件大小：${formatSize(row.size)}`,
  ].join('\n')
}

function detailReport(row?: QuarantineItem | null) {
  if (!row?.saved_as) return null
  return lastCaptureReport.value?.saved_as === row.saved_as ? lastCaptureReport.value : null
}

function hasPersistedReport(row?: QuarantineItem | null) {
  return Boolean(row?.has_report || detailReport(row))
}

function reportActionLabel(row?: QuarantineItem | null) {
  return hasPersistedReport(row) ? '查看报告' : '重新分析'
}

function openDetail(row: QuarantineItem) {
  detailRow.value = row
  detailOpen.value = true
}

function openFile(row: QuarantineItem) {
  if (!row.url?.trim()) {
    ElMessage.info('当前样本没有可访问的下载地址')
    return
  }
  window.open(row.url, '_blank', 'noopener,noreferrer')
}

function renderCharts() {
  const data = analysis.value
  if (!data) return

  if (trendRef.value) {
    if (!trendChart) trendChart = echarts.init(trendRef.value, 'dark')
    trendChart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 44, right: 16, top: 20, bottom: 28 },
      xAxis: {
        type: 'category',
        data: data.daily_labels ?? [],
        axisLine: { lineStyle: { color: 'rgba(34,211,238,0.25)' } },
        axisLabel: { color: 'rgba(226,232,240,0.82)' },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: 'rgba(34,211,238,0.08)', type: 'dashed' } },
        axisLabel: { color: 'rgba(226,232,240,0.82)' },
      },
      series: [
        {
          type: 'bar',
          data: data.daily_counts ?? [],
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(34,211,238,0.85)' },
              { offset: 1, color: 'rgba(59,130,246,0.16)' },
            ]),
          },
        },
      ],
    })
  }

  if (extRef.value) {
    if (!extChart) extChart = echarts.init(extRef.value, 'dark')
    const pieData = (data.by_extension ?? []).map((item) => ({ name: item.ext, value: item.count }))
    extChart.setOption({
      backgroundColor: 'transparent',
      tooltip: pieData.length ? { trigger: 'item', formatter: '{b}: {c} ({d}%)' } : { show: false },
      color: PIE_COLORS,
      graphic: pieData.length
        ? []
        : [
            {
              type: 'text',
              left: 'center',
              top: 'middle',
              style: {
                text: '暂无扩展名分布',
                fill: 'rgba(203,213,225,0.75)',
                fontSize: 16,
              },
            },
          ],
      series: [
        {
          type: 'pie',
          radius: ['42%', '68%'],
          center: ['50%', '50%'],
          data: pieData,
          silent: !pieData.length,
          label: { color: 'rgba(248,250,252,0.9)' },
        },
      ],
    })
  }
}

function disposeCharts() {
  trendChart?.dispose()
  extChart?.dispose()
  trendChart = null
  extChart = null
}

function onResize() {
  trendChart?.resize()
  extChart?.resize()
}

function pulseHighlight(savedAs: string) {
  highlightSavedAs.value = savedAs
  window.setTimeout(() => {
    if (highlightSavedAs.value === savedAs) highlightSavedAs.value = ''
  }, 10000)
}

async function openPersistedReport(savedAs: string) {
  lastCaptureReport.value = await getQuarantineReport(savedAs)
  reportDrawerOpen.value = true
  activeTab.value = 'list'
}

async function focusSampleFromRoute() {
  const savedAs = typeof route.query.saved_as === 'string' ? route.query.saved_as : ''
  if (savedAs) {
    const row = items.value.find((item) => item.saved_as === savedAs)
    if (row) {
      pulseHighlight(savedAs)
      tableRef.value?.setCurrentRow?.(row)
      detailRow.value = row
      detailOpen.value = true
      if (route.query.report === '1') {
        try {
          await openPersistedReport(savedAs)
        } catch {
          ElMessage.error('指定样本报告加载失败')
        }
      }
    } else {
      ElMessage.warning(`未找到样本：${savedAs}`)
    }
  }

  if (route.query.saved_as || route.query.report) {
    const nextQuery = { ...route.query }
    delete nextQuery.saved_as
    delete nextQuery.report
    void router.replace({ path: route.path, query: nextQuery })
  }
}

async function fetchQuarantine() {
  loading.value = true
  try {
    const result = await listQuarantineFiles()
    items.value = result.items ?? []
    analysis.value = result.analysis ?? null
    lastCaptureReport.value = result.latest_report ?? null
    await nextTick()
    if (activeTab.value === 'analysis') renderCharts()
    await focusSampleFromRoute()
  } catch {
    items.value = []
    analysis.value = null
  } finally {
    loading.value = false
  }
}

async function runSyncSequence(savedAs?: string) {
  if (syncOrchestrating.value) return
  syncOrchestrating.value = true
  captureOverlayVisible.value = true
  captureLogs.value = []
  capturePhase.value = '接收样本'
  threatPulse.value = false

  try {
    const result = await analyzeQuarantineFiles(savedAs)
    lastCaptureReport.value = result.report ?? null
    await fetchQuarantine()
    await nextTick()
    if (activeTab.value === 'analysis') renderCharts()

    for (const log of result.logs ?? []) {
      capturePhase.value = log.phase
      threatPulse.value = log.phase === '上传审计' || log.phase === '处置决策'
      pushCaptureLog(log.message)
      await sleep(log.phase === '上传审计' ? 380 : 220)
    }

    if (result.report?.saved_as) {
      pulseHighlight(result.report.saved_as)
      const row = items.value.find((item) => item.saved_as === result.report?.saved_as)
      tableRef.value?.setCurrentRow?.(row)
      reportDrawerOpen.value = true
      activeTab.value = 'list'
      ElMessage.warning({
        message: `已完成样本审计：${result.report.file_name}`,
        duration: 5000,
      })
    } else {
      reportDrawerOpen.value = false
      ElMessage.success('审计任务完成，当前没有可展示的报告。')
    }
  } catch {
    capturePhase.value = ''
    ElMessage.error('分析任务异常中断')
  } finally {
    threatPulse.value = false
    captureOverlayVisible.value = false
    syncOrchestrating.value = false
  }
}

function openLatestReport(row: QuarantineItem) {
  if (detailReport(row)) {
    reportDrawerOpen.value = true
    return
  }
  if (row.has_report) {
    void openPersistedReport(row.saved_as)
    return
  }
  void runSyncSequence(row.saved_as)
}

async function removeRow(row: QuarantineItem) {
  try {
    await ElMessageBox.confirm(
      `确定从隔离区永久删除「${row.saved_as}」吗？删除后不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteQuarantineFile(row.saved_as)
    if (detailRow.value?.saved_as === row.saved_as) detailOpen.value = false
    if (lastCaptureReport.value?.saved_as === row.saved_as) lastCaptureReport.value = null
    ElMessage.success('已删除')
    await fetchQuarantine()
  } catch {
    /* cancelled */
  }
}

watch(activeTab, async (tab) => {
  if (tab === 'analysis') {
    await nextTick()
    renderCharts()
    onResize()
  }
})

watch(
  () => [route.query.saved_as, route.query.report],
  async () => {
    if (items.value.length && (route.query.saved_as || route.query.report)) {
      await focusSampleFromRoute()
    }
  },
)

watch(
  () => analysis.value,
  async () => {
    if (activeTab.value === 'analysis') {
      await nextTick()
      renderCharts()
    }
  },
  { deep: true },
)

function tickClock() {
  liveClock.value = new Date().toLocaleString('zh-CN', { hour12: false })
}

function auditEngineText(audit?: UploadAuditResult | null) {
  if (audit?.analysis_mode === 'static_only') {
    return audit?.provider || audit?.engine || 'static_guardrail:v1'
  }
  return audit?.provider || audit?.engine || '--'
}

function auditLlmUsed(audit?: UploadAuditResult | null) {
  return audit?.llm_used ?? audit?.analysis_mode === 'llm_assisted'
}

function auditAiAvailable(audit?: UploadAuditResult | null) {
  return audit?.ai_available ?? audit?.llm_available ?? false
}

function reportDecisionBasis(report?: QuarantineAnalysisReport | null): QuarantineDecisionBasis | null {
  return report?.decision_basis || null
}

function reportDecisionSource(report?: QuarantineAnalysisReport | null) {
  const source = reportDecisionBasis(report)?.final_source
  if (source === 'hybrid') return 'Static + AI'
  if (source === 'llm') return 'AI'
  return 'Static'
}

function reportAnalysisMode(report?: QuarantineAnalysisReport | null) {
  return (
    reportDecisionBasis(report)?.analysis_mode_label ||
    reportDecisionBasis(report)?.analysis_mode ||
    report?.audit?.analysis_mode ||
    report?.analysis_source ||
    '-'
  )
}

function reportProvider(report?: QuarantineAnalysisReport | null) {
  return reportDecisionBasis(report)?.provider || report?.audit?.provider || report?.analysis_source || '-'
}

function reportHoldReason(report?: QuarantineAnalysisReport | null) {
  return reportDecisionBasis(report)?.hold_reason_summary || report?.audit?.summary || '-'
}

function reportStaticIndicators(report?: QuarantineAnalysisReport | null) {
  const basisIndicators = reportDecisionBasis(report)?.matched_indicators
  if (basisIndicators?.length) return basisIndicators
  return report?.indicators || []
}

function reportRecommendedActions(report?: QuarantineAnalysisReport | null) {
  const actions = [
    ...(reportDecisionBasis(report)?.recommended_actions || []),
    ...(report?.audit?.recommended_actions || []),
    ...(report?.audit?.recommended_action ? [report.audit.recommended_action] : []),
  ]
  return Array.from(new Set(actions.filter((item) => item && item.trim())))
}

function reportReasons(report?: QuarantineAnalysisReport | null) {
  return reportDecisionBasis(report)?.reasons || report?.audit?.reasons || report?.audit?.evidence || []
}

function reportLinkedEventId(report?: QuarantineAnalysisReport | null) {
  return reportDecisionBasis(report)?.linked_event_id ?? report?.audit?.linked_event_id ?? null
}

function openLinkedEvent(eventId?: number | null) {
  if (!eventId) return
  reportDrawerOpen.value = false
  void router.push({ path: '/events', query: { event: String(eventId), report: '1' } })
}

onMounted(() => {
  tickClock()
  clockTimer = setInterval(tickClock, 1000)
  void fetchQuarantine()
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  if (clockTimer) clearInterval(clockTimer)
  window.removeEventListener('resize', onResize)
  disposeCharts()
})
</script>

<template>
  <div class="sandbox-page">
    <Teleport to="body">
      <Transition name="capture-fade">
        <div
          v-if="captureOverlayVisible"
          class="capture-overlay"
          :class="{ 'threat-pulse': threatPulse }"
          role="dialog"
          aria-modal="true"
          aria-label="安全沙箱分析任务"
        >
          <div class="capture-panel">
            <div class="capture-phase">{{ capturePhase || '接收样本' }}</div>
            <div class="capture-hint">任务日志来自后端真实分析链路。</div>
            <div class="capture-terminal">
              <div class="term-bar">
                <span>security-sandbox-audit.log</span>
                <span>{{ liveClock }}</span>
              </div>
              <ul class="term-body">
                <li v-for="(line, index) in captureLogs" :key="`${index}-${line}`">{{ line }}</li>
              </ul>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <div class="page-head">
      <div>
        <h1>安全沙箱</h1>
        <p>所有未通过上传审计的文件都会在这里保留，支持后端复检、静态审计回看、结果核对和人工研判联动。</p>
      </div>
      <button type="button" class="hud-sync" :disabled="syncOrchestrating" @click="runSyncSequence()">
        <el-icon :class="{ spin: syncOrchestrating }"><Refresh /></el-icon>
        <span>{{ syncOrchestrating ? '分析任务执行中…' : '生成审计报告' }}</span>
      </button>
    </div>

    <div class="warn-banner">
      <el-icon><WarningFilled /></el-icon>
      <span>当前页面只展示真实隔离样本。内部送检通过的样本不会出现在这里，未通过的样本会直接扣留并生成审计报告。</span>
    </div>

    <div class="pipeline-track">
      <div
        v-for="(step, index) in PIPELINE_STEPS"
        :key="step.key"
        class="pipeline-step"
        :class="{
          active: pipelineActiveIndex === index,
          done: pipelineActiveIndex > index,
          pending: pipelineActiveIndex >= 0 && index > pipelineActiveIndex,
        }"
      >
        <span class="pipeline-step__idx">{{ index + 1 }}</span>
        <span>{{ step.label }}</span>
      </div>
    </div>

    <el-tabs v-model="activeTab" class="sandbox-tabs">
      <el-tab-pane name="list" label="隔离样本">
        <div class="toolbar">
          <el-input
            v-model="searchQuery"
            class="toolbar-search"
            placeholder="搜索隔离编号、扩展名或审计摘要"
            :prefix-icon="Search"
            clearable
          />
          <el-select v-model="riskFilter" class="toolbar-risk">
            <el-option label="全部风险" value="all" />
            <el-option label="高风险" value="high" />
            <el-option label="中风险" value="medium" />
            <el-option label="低风险" value="low" />
          </el-select>
          <span class="toolbar-meta">当前时间 {{ liveClock }}</span>
        </div>

        <el-table
          ref="tableRef"
          v-loading="loading"
          :data="filteredItems"
          row-key="saved_as"
          class="sandbox-table"
          :row-class-name="rowClassName"
        >
          <el-table-column label="样本" min-width="320">
            <template #default="{ row }">
              <button type="button" class="file-link" @click="openDetail(row)">
                {{ row.saved_as }}
              </button>
              <p class="subline">{{ row.audit_summary || '尚未生成摘要' }}</p>
            </template>
          </el-table-column>
          <el-table-column label="审计裁决" width="140">
            <template #default="{ row }">
              <el-tag :type="verdictTagType(row.audit_verdict)" effect="dark">
                {{ verdictLabel(row.audit_verdict) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="风险" width="120">
            <template #default="{ row }">
              <el-tag :type="riskTagType(row.risk_level)" effect="dark">
                {{ riskLabel(row.risk_level) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="置信度" width="110">
            <template #default="{ row }">{{ row.audit_confidence ?? 0 }}</template>
          </el-table-column>
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ formatSize(row.size) }}</template>
          </el-table-column>
          <el-table-column label="更新时间" min-width="180">
            <template #default="{ row }">{{ formatTime(row.modified_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <div class="row-actions">
                <button type="button" class="link-btn" @click="openDetail(row)">研判简报</button>
                <button type="button" class="link-btn" @click="openLatestReport(row)">{{ reportActionLabel(row) }}</button>
                <button type="button" class="link-btn" @click="openFile(row)">下载样本</button>
                <button type="button" class="link-btn danger" @click="removeRow(row)">删除</button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane name="analysis" label="统计与遥测">
        <div v-if="analysis" class="analysis-layout">
          <div class="stat-row">
            <div class="stat-card">
              <div class="stat-label">隔离样本总数</div>
              <div class="stat-num">{{ items.length }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">占用空间</div>
              <div class="stat-num">{{ formatSize(analysis.total_bytes) }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">今日新增</div>
              <div class="stat-num">{{ analysis.today_count }}</div>
            </div>
            <div class="stat-card">
              <div class="stat-label">近 7 日</div>
              <div class="stat-num">{{ analysis.week_count }}</div>
            </div>
            <div class="stat-card danger">
              <div class="stat-label">审计扣留 / 高风险</div>
              <div class="stat-num">{{ analysis.ai_quarantined_count ?? 0 }} / {{ analysis.high_risk_count }}</div>
            </div>
          </div>

          <div class="insight-panel">
            <div class="insight-head">
              <span>隔离区观察</span>
              <span>{{ formatTime(analysis.generated_at) }}</span>
            </div>
            <ul>
              <li v-for="(line, index) in analysis.insights" :key="`${index}-${line}`">{{ line }}</li>
            </ul>
          </div>

          <div class="charts-row">
            <div class="chart-card">
              <div class="chart-title">近 14 天隔离样本趋势</div>
              <div ref="trendRef" class="chart-box" />
            </div>
            <div class="chart-card">
              <div class="chart-title">扩展名分布</div>
              <div ref="extRef" class="chart-box pie" />
            </div>
          </div>
        </div>
        <div v-else class="empty-analysis">暂无统计数据，请先刷新页面或执行一次分析。</div>
      </el-tab-pane>
    </el-tabs>

    <el-drawer v-model="detailOpen" title="样本研判简报" size="520px" class="sandbox-drawer">
      <template v-if="detailRow">
        <pre class="narrative">{{ detailNarrative(detailRow) }}</pre>
        <div v-if="detailReport(detailRow)" class="brief-grid">
          <div class="brief-item">
            <span class="audit-label">拦截原因</span>
            <span class="audit-value">{{ reportHoldReason(detailReport(detailRow)) }}</span>
          </div>
          <div class="brief-item">
            <span class="audit-label">分析模式</span>
            <span class="audit-value">{{ reportAnalysisMode(detailReport(detailRow)) }}</span>
          </div>
          <div class="brief-item">
            <span class="audit-label">决策来源</span>
            <span class="audit-value">{{ reportDecisionSource(detailReport(detailRow)) }}</span>
          </div>
          <div class="brief-item">
            <span class="audit-label">关联 IDS 事件</span>
            <span class="audit-value">{{ reportLinkedEventId(detailReport(detailRow)) || '-' }}</span>
          </div>
        </div>
        <div class="drawer-actions">
          <button
            v-if="hasPersistedReport(detailRow)"
            type="button"
            class="hud-sync hud-sync--sm"
            @click="openLatestReport(detailRow)"
          >
            查看审计报告
          </button>
          <button type="button" class="hud-sync hud-sync--sm" @click="openFile(detailRow)">下载样本</button>
          <button type="button" class="hud-ghost" @click="detailOpen = false">关闭</button>
        </div>
      </template>
    </el-drawer>

    <el-drawer
      v-model="reportDrawerOpen"
      title="上传审计报告"
      direction="rtl"
      size="560px"
      class="sandbox-drawer report-drawer"
    >
      <template v-if="lastCaptureReport">
        <div class="report-head">
          <p class="report-file">{{ lastCaptureReport.file_name }}</p>
          <p class="report-sub">隔离编号：{{ lastCaptureReport.saved_as }}</p>
          <div class="report-tags">
            <el-tag :type="riskTagType(lastCaptureReport.risk_level)" effect="dark">
              {{ riskLabel(lastCaptureReport.risk_level) }}
            </el-tag>
            <el-tag :type="verdictTagType(lastCaptureReport.audit?.verdict)" effect="dark">
              {{ verdictLabel(lastCaptureReport.audit?.verdict) }}
            </el-tag>
            <el-tag type="warning" effect="plain">{{ reportDecisionSource(lastCaptureReport) }}</el-tag>
          </div>
          <p class="report-time">分析完成时间：{{ formatTime(reportTime(lastCaptureReport)) }}</p>
          <p class="report-time sub">SHA-256：{{ lastCaptureReport.sha256 }}</p>
        </div>

        <div class="audit-summary">
          <div class="audit-grid">
            <div class="audit-item">
              <span class="audit-label">静态规则来源</span>
              <span class="audit-value">{{ auditEngineText(lastCaptureReport.audit) }}</span>
            </div>
            <div class="audit-item">
              <span class="audit-label">分析模式</span>
              <span class="audit-value">{{ reportAnalysisMode(lastCaptureReport) }}</span>
            </div>
            <div class="audit-item">
              <span class="audit-label">LLM 已调用 / AI 可用</span>
              <span class="audit-value">
                {{ auditLlmUsed(lastCaptureReport.audit) ? '是' : '否' }} / {{ auditAiAvailable(lastCaptureReport.audit) ? '是' : '否' }}
              </span>
            </div>
            <div class="audit-item">
              <span class="audit-label">置信度</span>
              <span class="audit-value">{{ lastCaptureReport.audit.confidence }}</span>
            </div>
            <div class="audit-item">
              <span class="audit-label">最终裁决</span>
              <span class="audit-value">{{ reportDecisionBasis(lastCaptureReport)?.blocked ? '已拦截并扣留沙箱' : '已放行' }}</span>
            </div>
            <div class="audit-item">
              <span class="audit-label">关联 IDS 事件</span>
              <span class="audit-value">{{ reportLinkedEventId(lastCaptureReport) || '-' }}</span>
            </div>
          </div>
          <p class="audit-paragraph">{{ reportHoldReason(lastCaptureReport) }}</p>
        </div>

        <div class="report-list-block report-list-block--danger">
          <h4>为什么会被拦截</h4>
          <p class="report-plain">{{ reportHoldReason(lastCaptureReport) }}</p>
          <div class="report-tags report-tags--compact">
            <el-tag size="small" type="danger">{{ lastCaptureReport.audit.risk_level || lastCaptureReport.risk_level }}</el-tag>
            <el-tag size="small" type="warning">{{ reportProvider(lastCaptureReport) }}</el-tag>
            <el-tag v-if="reportLinkedEventId(lastCaptureReport)" size="small" type="info" effect="plain">
              IDS Event #{{ reportLinkedEventId(lastCaptureReport) }}
            </el-tag>
          </div>
        </div>

        <div v-if="reportReasons(lastCaptureReport).length" class="report-list-block">
          <h4>拦截依据</h4>
          <ul>
            <li v-for="reason in reportReasons(lastCaptureReport)" :key="reason">{{ reason }}</li>
          </ul>
        </div>

        <div v-if="reportStaticIndicators(lastCaptureReport).length" class="report-list-block">
          <h4>静态命中指标</h4>
          <ul>
            <li
              v-for="indicator in reportStaticIndicators(lastCaptureReport)"
              :key="`${indicator.code}-${indicator.detail}`"
            >
              {{ indicator.code }}: {{ indicator.detail }}
            </li>
          </ul>
        </div>

        <div v-if="reportRecommendedActions(lastCaptureReport).length" class="report-list-block">
          <h4>建议动作</h4>
          <ul>
            <li v-for="action in reportRecommendedActions(lastCaptureReport)" :key="action">{{ action }}</li>
          </ul>
        </div>

        <div
          v-for="(section, index) in lastCaptureReport.sections"
          :key="`${index}-${section.title}`"
          class="report-section"
        >
          <h4>{{ section.title }}</h4>
          <p>{{ section.body }}</p>
        </div>

        <div class="drawer-actions">
          <button
            v-if="reportLinkedEventId(lastCaptureReport)"
            type="button"
            class="hud-sync hud-sync--sm"
            @click="openLinkedEvent(reportLinkedEventId(lastCaptureReport))"
          >
            打开关联 IDS 事件
          </button>
          <button type="button" class="hud-ghost" @click="reportDrawerOpen = false">关闭报告</button>
        </div>
      </template>
      <div v-else class="empty-analysis">当前没有可展示的审计报告。</div>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.sandbox-page {
  --sandbox-panel-bg: rgba(5, 18, 35, 0.94);
  --sandbox-panel-bg-soft: rgba(9, 17, 34, 0.98);
  --sandbox-panel-border: rgba(71, 85, 105, 0.44);
  --sandbox-text-main: #f8fafc;
  --sandbox-text-soft: rgba(226, 232, 240, 0.88);
  --sandbox-text-muted: rgba(148, 163, 184, 0.92);
  min-height: 100%;
  padding: 24px;
  color: var(--sandbox-text-main);
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.12), transparent 32%),
    linear-gradient(180deg, #06111a, #02070d 55%);
}

.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;

  h1 {
    margin: 0 0 8px;
    font-size: 28px;
  }

  p {
    margin: 0;
    max-width: 760px;
    line-height: 1.7;
    color: var(--sandbox-text-soft);
  }
}

.warn-banner {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid rgba(251, 191, 36, 0.28);
  border-radius: 12px;
  background: rgba(120, 53, 15, 0.22);
  color: #fde68a;
}

.hud-sync,
.hud-ghost,
.link-btn,
.file-link {
  border: none;
  cursor: pointer;
}

.hud-sync {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  border-radius: 10px;
  color: #ecfeff;
  background: linear-gradient(135deg, rgba(8, 145, 178, 0.88), rgba(37, 99, 235, 0.9));
  box-shadow: 0 12px 28px rgba(14, 116, 144, 0.24);

  &:disabled {
    opacity: 0.7;
    cursor: wait;
  }

  &--sm {
    padding: 8px 12px;
  }
}

.hud-ghost {
  padding: 10px 14px;
  border-radius: 10px;
  color: rgba(226, 232, 240, 0.9);
  background: rgba(15, 23, 42, 0.72);
}

.spin {
  animation: spin 1s linear infinite;
}

.pipeline-track {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
  gap: 10px;
  margin-bottom: 18px;
}

.pipeline-step {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 12px;
  border: 1px solid rgba(51, 65, 85, 0.72);
  border-radius: 12px;
  background: rgba(15, 23, 42, 0.55);

  &.active {
    border-color: rgba(103, 232, 249, 0.8);
    background: rgba(8, 47, 73, 0.46);
  }

  &.done {
    border-color: rgba(34, 197, 94, 0.35);
  }

  &.pending {
    opacity: 0.65;
  }
}

.pipeline-step__idx {
  display: inline-flex;
  width: 26px;
  height: 26px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: rgba(15, 118, 110, 0.28);
  font-family: ui-monospace, monospace;
}

.sandbox-tabs {
  :deep(.el-tabs__item) {
    color: rgba(226, 232, 240, 0.62);
  }

  :deep(.el-tabs__item.is-active) {
    color: #67e8f9;
  }

  :deep(.el-tabs__active-bar) {
    background-color: #22d3ee;
  }
}

.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.toolbar-search {
  width: 340px;
}

.toolbar-risk {
  width: 150px;
}

.toolbar-meta {
  margin-left: auto;
  font-size: 13px;
  color: rgba(148, 163, 184, 0.92);
}

.file-link,
.link-btn {
  padding: 0;
  color: #67e8f9;
  background: transparent;
}

.file-link {
  text-align: left;
  font-weight: 600;
}

.subline {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: rgba(191, 219, 254, 0.82);
}

.row-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.danger {
  color: #fca5a5;
}

.analysis-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.stat-card {
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid rgba(34, 211, 238, 0.22);
  background: linear-gradient(180deg, rgba(5, 18, 35, 0.94), rgba(3, 10, 22, 0.9));

  &.danger {
    border-color: rgba(248, 113, 113, 0.28);
  }
}

.stat-label {
  font-size: 13px;
  color: rgba(191, 219, 254, 0.84);
}

.stat-num {
  margin-top: 8px;
  font-size: 26px;
  font-weight: 700;
}

.insight-panel,
.chart-card,
.capture-panel {
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-radius: 14px;
  background: linear-gradient(180deg, rgba(5, 18, 35, 0.94), rgba(3, 10, 22, 0.9));
  box-shadow: 0 18px 36px rgba(2, 6, 23, 0.3);
}

.insight-panel {
  padding: 16px;

  ul {
    margin: 12px 0 0;
    padding-left: 18px;
    line-height: 1.7;
  }
}

.insight-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: rgba(191, 219, 254, 0.86);
}

.charts-row {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 14px;

  @media (max-width: 960px) {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  padding: 16px;
}

.chart-title {
  margin-bottom: 10px;
  color: #7dd3fc;
}

.chart-box {
  width: 100%;
  height: 240px;

  &.pie {
    height: 260px;
  }
}

.narrative {
  padding: 14px;
  line-height: 1.7;
  white-space: pre-wrap;
  border-radius: 12px;
  background: var(--sandbox-panel-bg-soft);
  color: rgba(226, 232, 240, 0.95);
}

.brief-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 12px 0 16px;
}

.brief-item {
  padding: 12px;
  border-radius: 10px;
  background: rgba(4, 12, 24, 0.96);
  border: 1px solid rgba(51, 65, 85, 0.42);
}

.drawer-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.report-head {
  margin-bottom: 16px;
}

.report-file {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
}

.report-sub,
.report-time {
  margin: 8px 0 0;
  color: rgba(203, 213, 225, 0.82);
}

.report-time.sub {
  font-size: 12px;
}

.report-tags {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.report-tags--compact {
  margin-top: 10px;
}

.audit-summary {
  margin-bottom: 16px;
  padding: 14px;
  border-radius: 12px;
  background: var(--sandbox-panel-bg-soft);
  border: 1px solid var(--sandbox-panel-border);
}

.audit-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.audit-item {
  padding: 12px;
  border-radius: 10px;
  background: rgba(4, 12, 24, 0.96);
  border: 1px solid rgba(51, 65, 85, 0.42);
}

.audit-label {
  display: block;
  font-size: 12px;
  color: rgba(148, 163, 184, 0.9);
}

.audit-value {
  display: block;
  margin-top: 6px;
  font-weight: 700;
  color: #f8fafc;
}

.audit-paragraph {
  margin: 0;
  line-height: 1.7;
  color: rgba(226, 232, 240, 0.92);
}

.report-list-block,
.report-section {
  margin-bottom: 16px;
  padding: 14px;
  border-radius: 12px;
  background: var(--sandbox-panel-bg-soft);
  border: 1px solid rgba(51, 65, 85, 0.42);
}

.report-list-block--danger {
  border-color: rgba(248, 113, 113, 0.28);
  background: linear-gradient(180deg, rgba(60, 17, 17, 0.46), rgba(9, 17, 34, 0.98));
}

.report-list-block h4,
.report-section h4 {
  margin: 0 0 10px;
}

.report-plain {
  margin: 0;
  line-height: 1.7;
  color: rgba(226, 232, 240, 0.94);
  white-space: pre-wrap;
}

.report-list-block ul {
  margin: 0;
  padding-left: 18px;
  line-height: 1.7;
}

.report-section p {
  margin: 0;
  line-height: 1.7;
  white-space: pre-wrap;
}

.empty-analysis {
  padding: 24px;
  text-align: center;
  border-radius: 14px;
  color: rgba(226, 232, 240, 0.92);
  background: rgba(4, 12, 24, 0.96);
}

.capture-overlay {
  position: fixed;
  inset: 0;
  z-index: 4000;
  display: grid;
  place-items: center;
  background: rgba(2, 6, 23, 0.76);
  backdrop-filter: blur(8px);
}

.capture-panel {
  width: min(760px, calc(100vw - 32px));
  padding: 18px;
}

.capture-phase {
  font-size: 20px;
  font-weight: 700;
  color: #67e8f9;
}

.capture-hint {
  margin-top: 8px;
  color: rgba(186, 230, 253, 0.76);
}

.capture-terminal {
  margin-top: 16px;
  overflow: hidden;
  border-radius: 12px;
  background: rgba(2, 6, 23, 0.88);
}

.term-bar {
  display: flex;
  justify-content: space-between;
  padding: 10px 12px;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  background: rgba(15, 23, 42, 0.92);
}

.term-body {
  max-height: 280px;
  margin: 0;
  padding: 12px 16px 16px;
  overflow: auto;
  list-style: none;
  font-family: ui-monospace, monospace;
  font-size: 12px;
  line-height: 1.8;
}

.threat-pulse .capture-panel {
  box-shadow: 0 0 0 1px rgba(248, 113, 113, 0.35), 0 0 40px rgba(248, 113, 113, 0.18);
}

:deep(.is-new-capture) {
  --el-table-tr-bg-color: rgba(8, 145, 178, 0.18);
}

.sandbox-page :deep(.el-input__wrapper),
.sandbox-page :deep(.el-select__wrapper) {
  background: rgba(7, 14, 28, 0.96);
  box-shadow: 0 0 0 1px rgba(71, 85, 105, 0.52) inset;
}

.sandbox-page :deep(.el-input__inner),
.sandbox-page :deep(.el-select__placeholder),
.sandbox-page :deep(.el-select__selected-item),
.sandbox-page :deep(.el-input__icon),
.sandbox-page :deep(.el-select__caret) {
  color: var(--sandbox-text-soft);
}

.sandbox-page :deep(.el-input__inner::placeholder) {
  color: rgba(148, 163, 184, 0.88);
}

.sandbox-page :deep(.el-table) {
  --el-table-border-color: rgba(71, 85, 105, 0.42);
  --el-table-header-bg-color: rgba(15, 23, 42, 0.98);
  --el-table-tr-bg-color: rgba(5, 11, 24, 0.98);
  --el-table-row-hover-bg-color: rgba(17, 24, 39, 0.98);
  --el-table-current-row-bg-color: rgba(8, 47, 73, 0.76);
  --el-table-header-text-color: rgba(191, 219, 254, 0.88);
  --el-table-text-color: var(--sandbox-text-soft);
  --el-table-bg-color: rgba(5, 11, 24, 0.98);
  --el-fill-color-lighter: rgba(9, 17, 34, 0.98);
  background: transparent;
  color: var(--sandbox-text-soft);
}

.sandbox-page :deep(.el-table tr),
.sandbox-page :deep(.el-table__body tr.hover-row > td.el-table__cell),
.sandbox-page :deep(.el-table__body tr.current-row > td.el-table__cell),
.sandbox-page :deep(.el-table__body td.el-table__cell),
.sandbox-page :deep(.el-table__header th.el-table__cell) {
  background: transparent;
}

.sandbox-page :deep(.el-table td.el-table__cell),
.sandbox-page :deep(.el-table th.el-table__cell) {
  border-bottom-color: rgba(71, 85, 105, 0.42);
}

.sandbox-page :deep(.el-drawer__header) {
  margin-bottom: 0;
  padding-bottom: 14px;
  color: var(--sandbox-text-main);
  border-bottom: 1px solid rgba(51, 65, 85, 0.42);
}

.sandbox-page :deep(.el-drawer__body) {
  background: linear-gradient(180deg, rgba(4, 12, 24, 0.99), rgba(2, 8, 18, 0.98));
  color: var(--sandbox-text-soft);
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
</style>
