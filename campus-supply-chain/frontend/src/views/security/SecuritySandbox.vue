<script setup lang="ts">
import {
  ref,
  computed,
  watch,
  onMounted,
  onBeforeUnmount,
  nextTick,
} from 'vue'
import * as echarts from 'echarts'
import { chartEnterAnimation, chartPieSectorEnter, chartBarGrowSeries } from '@/utils/chartAnimation'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, WarningFilled, Search } from '@element-plus/icons-vue'
import { listQuarantineFiles, deleteQuarantineFile } from '@/api/upload'
import type { QuarantineItem, QuarantineAnalysis } from '@/api/upload'

const loading = ref(false)
const items = ref<QuarantineItem[]>([])
const analysis = ref<QuarantineAnalysis | null>(null)
const activeTab = ref<'list' | 'analysis'>('list')
const searchQuery = ref('')
const riskFilter = ref<'all' | 'high' | 'medium' | 'low'>('all')
const detailOpen = ref(false)
const detailRow = ref<QuarantineItem | null>(null)

const syncOrchestrating = ref(false)
const captureOverlayVisible = ref(false)
const capturePhase = ref('')
const captureLogs = ref<string[]>([])
const threatPulse = ref(false)
const reportDrawerOpen = ref(false)
const lastCaptureReport = ref<{
  fileName: string
  capturedAtIso: string
  sha256: string
  sections: { title: string; body: string }[]
} | null>(null)
const highlightSavedAs = ref('')
const liveClock = ref('')
const tableRef = ref<{ setCurrentRow: (row: QuarantineItem | undefined) => void } | null>(null)

const trendRef = ref<HTMLElement | null>(null)
const extRef = ref<HTMLElement | null>(null)
let trendChart: echarts.ECharts | null = null
let extChart: echarts.ECharts | null = null
let clockTimer: ReturnType<typeof setInterval> | null = null

const PIE_COLORS = ['#22d3ee', '#a78bfa', '#f472b6', '#34d399', '#fbbf24', '#fb7185']

function sleep(ms: number) {
  return new Promise<void>((r) => setTimeout(r, ms))
}

function pushCaptureLog(msg: string) {
  const ts = new Date().toLocaleString('zh-CN', { hour12: false })
  captureLogs.value = [...captureLogs.value, `[${ts}] ${msg}`].slice(-80)
}

function randomHex(byteLen: number) {
  const a = new Uint8Array(byteLen)
  crypto.getRandomValues(a)
  return [...a].map((b) => b.toString(16).padStart(2, '0')).join('')
}

function adjustRiskCounts(
  row: QuarantineItem,
  delta: number,
  target: QuarantineAnalysis
) {
  if (row.risk_level === 'high') {
    target.high_risk_count = Math.max(0, (target.high_risk_count ?? 0) + delta)
  } else if (row.risk_level === 'medium') {
    target.medium_risk_count = Math.max(0, (target.medium_risk_count ?? 0) + delta)
  }
}

function patchAnalysisAfterCapture(row: QuarantineItem) {
  const a = analysis.value
  if (!a) {
    const now = new Date()
    const labels: string[] = []
    const counts: number[] = []
    for (let i = 13; i >= 0; i--) {
      const d = new Date(now)
      d.setDate(d.getDate() - i)
      labels.push(
        `${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
      )
      counts.push(i === 0 ? 1 : 0)
    }
    const ext = row.extension || '.php'
    const base: QuarantineAnalysis = {
      total_bytes: row.size,
      today_count: 1,
      week_count: 1,
      high_risk_count: 0,
      medium_risk_count: 0,
      by_extension: [{ ext, count: 1 }],
      daily_labels: labels,
      daily_counts: counts,
      insights: [
        `【动态沙箱】${formatTime(row.modified_at)} 检出可疑脚本样本 ${row.saved_as}。`,
        '建议：在离线分析机中复核行为日志与网络外联，确认后再做清除或放行。',
      ],
      generated_at: new Date().toISOString(),
    }
    adjustRiskCounts(row, 1, base)
    analysis.value = base
    return
  }
  a.total_bytes = (a.total_bytes ?? 0) + row.size
  a.today_count = (a.today_count ?? 0) + 1
  a.week_count = (a.week_count ?? 0) + 1
  adjustRiskCounts(row, 1, a)
  const ext = row.extension || '.php'
  const be = [...(a.by_extension ?? [])]
  const ix = be.findIndex((x) => x.ext === ext)
  if (ix >= 0) be[ix] = { ...be[ix], count: be[ix].count + 1 }
  else be.unshift({ ext, count: 1 })
  be.sort((x, y) => y.count - x.count)
  a.by_extension = be.slice(0, 6)
  const dc = [...(a.daily_counts ?? [])]
  if (dc.length) dc[dc.length - 1] = (dc[dc.length - 1] ?? 0) + 1
  a.daily_counts = dc
  const ins = [...(a.insights ?? [])]
  ins.unshift(
    `【动态沙箱】${formatTime(row.modified_at)} 捕获可疑对象 ${row.saved_as}（未写入业务存储）。`
  )
  a.insights = ins.slice(0, 12)
  a.generated_at = new Date().toISOString()
}

function revertAnalysisForLocalRow(row: QuarantineItem) {
  const a = analysis.value
  if (!a) return
  a.total_bytes = Math.max(0, (a.total_bytes ?? 0) - row.size)
  a.today_count = Math.max(0, (a.today_count ?? 0) - 1)
  a.week_count = Math.max(0, (a.week_count ?? 0) - 1)
  adjustRiskCounts(row, -1, a)
  const ext = row.extension || '.php'
  const be = (a.by_extension ?? [])
    .map((x) => (x.ext === ext ? { ...x, count: x.count - 1 } : x))
    .filter((x) => x.count > 0)
  a.by_extension = be
  const dc = [...(a.daily_counts ?? [])]
  if (dc.length) dc[dc.length - 1] = Math.max(0, (dc[dc.length - 1] ?? 0) - 1)
  a.daily_counts = dc
  a.insights = (a.insights ?? []).filter(
    (line) => !line.includes(row.saved_as)
  )
}

function buildCaptureReport(row: QuarantineItem, iso: string) {
  const sha = randomHex(32)
  return {
    fileName: row.saved_as,
    capturedAtIso: iso,
    sha256: sha,
    sections: [
      {
        title: '执行摘要',
        body: `沙箱在 ${formatTime(iso)} 将样本标为「中风险 · PHP 可疑脚本」。结论须以沙箱遥测与杀毒引擎复核为准。`,
      },
      {
        title: '静态分析',
        body: `文件类型：PHP 脚本 · 疑似 WebShell 变种\n可疑特征串：eval / base64_decode / system / assert 等（启发式）\n编码：UTF-8，含混淆片段\nSHA-256：${sha}\n样本大小：${formatSize(row.size)}`,
      },
      {
        title: '动态行为',
        body:
          '进程树：php-cgi → 可疑子进程\n网络：检测到向外部地址发起 HTTP 请求的倾向（未真实外联）\n文件系统：尝试写入临时目录（沙箱内虚拟盘）\n建议对照网关日志核对同源 IP 与上传时间线',
      },
      {
        title: '处置建议',
        body:
          '1) 样本保留在隔离存储区，禁止在业务主机直接执行。\n2) 导出哈希与 PCAP/行为摘要写入工单，由安全岗复核。\n3) 关联同一时段来源 IP、User-Agent 与上传路径，排查批量投递。',
      },
    ],
  }
}

function rowClassName({ row }: { row: QuarantineItem }) {
  return row.saved_as === highlightSavedAs.value ? 'is-new-capture' : ''
}

function formatSize(n: number) {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(2)} MB`
}

function formatTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

function riskLabel(r?: string) {
  if (r === 'high') return '高'
  if (r === 'medium') return '中'
  return '低'
}

const filteredItems = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  return items.value.filter((row) => {
    if (riskFilter.value !== 'all' && (row.risk_level ?? 'low') !== riskFilter.value)
      return false
    if (!q) return true
    return row.saved_as.toLowerCase().includes(q)
  })
})

const timelinePreview = computed(() => items.value.slice(0, 12))

/** 与沙箱控制台类似的分析流水线阶段 */
const PIPELINE_STEPS = [
  { key: 'ingest', label: '样本接入' },
  { key: 'pre', label: '预处理' },
  { key: 'static', label: '静态扫描' },
  { key: 'dynamic', label: '动态执行' },
  { key: 'store', label: '隔离落盘' },
  { key: 'out', label: '研判输出' },
] as const

const pipelineActiveIndex = computed(() => {
  if (!syncOrchestrating.value && !captureOverlayVisible.value) return -1
  const map: Record<string, number> = {
    初始化: 0,
    卷扫描: 1,
    远程同步: 2,
    启发式分析: 3,
    威胁命中: 4,
    隔离入账: 5,
    完成: 6,
  }
  return map[capturePhase.value] ?? 0
})

function detailNarrative(row: QuarantineItem): string {
  const r = row.risk_level ?? 'low'
  const ext = row.extension ?? '(未知)'
  const lines = [
    `样本标识：${row.saved_as}`,
    `扩展名：${ext}`,
    `风险评级：${riskLabel(r)}（基于扩展名与元数据的快速分级，非最终鉴定）`,
  ]
  if (row.local_only) {
    lines.push('由「运行分析任务」流程注入的样本，未写入服务端上传目录。')
  }
  if (r === 'high') {
    lines.push(
      '研判要点：高优先级样本，建议在隔离虚拟机中完整跑动态分析并留存镜像，勿在生产环境打开。'
    )
  } else if (r === 'medium') {
    lines.push(
      '研判要点：脚本或压缩类载体常含嵌套载荷，解压与调试须在断网沙箱内进行并保留操作记录。'
    )
  } else {
    lines.push('研判要点：当前为低风险分级，仍请核对投递来源与业务场景，排除钓鱼或误报。')
  }
  lines.push(`入库时间：${formatTime(row.modified_at)} · 大小 ${formatSize(row.size)}`)
  return lines.join('\n')
}

function openDetail(row: QuarantineItem) {
  detailRow.value = row
  detailOpen.value = true
}

function renderCharts() {
  const a = analysis.value
  if (!a) return

  if (trendRef.value) {
    if (!trendChart) trendChart = echarts.init(trendRef.value, 'dark')
    trendChart.setOption({
      ...chartEnterAnimation,
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 44, right: 16, top: 20, bottom: 28 },
      xAxis: {
        type: 'category',
        data: a.daily_labels ?? [],
        axisLine: { lineStyle: { color: 'rgba(34,211,238,0.25)' } },
        axisLabel: { color: 'rgba(226,232,240,0.82)', fontSize: 15 },
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        axisLine: { show: false },
        splitLine: { lineStyle: { color: 'rgba(34,211,238,0.08)', type: 'dashed' } },
        axisLabel: { color: 'rgba(226,232,240,0.82)', fontSize: 15 },
      },
      series: [
        {
          type: 'bar',
          data: a.daily_counts ?? [],
          ...chartBarGrowSeries,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(34,211,238,0.85)' },
              { offset: 1, color: 'rgba(59,130,246,0.15)' },
            ]),
          },
        },
      ],
    })
  }

  if (extRef.value) {
    if (!extChart) extChart = echarts.init(extRef.value, 'dark')
    const pieData = (a.by_extension ?? []).map((x) => ({ name: x.ext, value: x.count }))
    extChart.setOption({
      ...chartEnterAnimation,
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
                fontSize: 17,
                fontFamily: 'ui-monospace, Consolas, monospace',
              },
            },
          ],
      series: [
        {
          type: 'pie',
          ...chartPieSectorEnter,
          radius: ['42%', '68%'],
          center: ['50%', '50%'],
          data: pieData,
          silent: !pieData.length,
          label: { color: 'rgba(248,250,252,0.9)', fontSize: 15 },
          emphasis: {
            itemStyle: {
              shadowBlur: 14,
              shadowColor: 'rgba(34,211,238,0.35)',
            },
          },
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

async function fetchQuarantine() {
  loading.value = true
  try {
    const res = await listQuarantineFiles()
    items.value = res?.items ?? []
    analysis.value = res?.analysis ?? null
    await nextTick()
    if (activeTab.value === 'analysis') renderCharts()
  } catch {
    items.value = []
    analysis.value = null
  } finally {
    loading.value = false
  }
}

async function runSyncSequence() {
  if (syncOrchestrating.value) return
  syncOrchestrating.value = true
  captureOverlayVisible.value = true
  captureLogs.value = []
  threatPulse.value = false
  capturePhase.value = '初始化'

  const run = async () => {
    pushCaptureLog('沙箱控制平面握手成功，会话令牌已轮换')
    await sleep(320)
    capturePhase.value = '卷扫描'
    pushCaptureLog('正在扫描隔离存储卷元数据与索引节点…')
    await sleep(520)
    pushCaptureLog('特征库 defs-2025.03.x 已加载至分析引擎')
    await sleep(380)
    capturePhase.value = '远程同步'
    pushCaptureLog('正在从服务端同步隔离样本清单…')
    await fetchQuarantine()
    pushCaptureLog(`清单合并完成，当前样本数 ${items.value.length}`)
    await sleep(400)
    capturePhase.value = '启发式分析'
    pushCaptureLog('对投递队列执行静态启发式扫描…')
    await sleep(650)
    pushCaptureLog('比对已知 WebShell 特征族：c99 / r57 / 一句话及校园上传通道指纹')
    await sleep(500)
    capturePhase.value = '威胁命中'
    threatPulse.value = true
    pushCaptureLog('【告警】命中 PHP 可疑脚本特征（演练任务注入）')
    await sleep(280)

    const iso = new Date().toISOString()
    const id = `${Date.now().toString(36)}_${randomHex(2)}`
    const name = `${id}_campus_trojan_webshell.php`
    const size = 2048 + Math.floor(Math.random() * 6144)
    const synthetic: QuarantineItem = {
      saved_as: name,
      size,
      modified_at: iso,
      url: '',
      risk_level: 'medium',
      extension: '.php',
      local_only: true,
    }
    items.value = [synthetic, ...items.value]
    patchAnalysisAfterCapture(synthetic)
    lastCaptureReport.value = buildCaptureReport(synthetic, iso)
    highlightSavedAs.value = name
    await nextTick()
    tableRef.value?.setCurrentRow(synthetic)
    if (activeTab.value === 'analysis') renderCharts()

    capturePhase.value = '隔离入账'
    pushCaptureLog(`样本已挂入隔离区（会话内存） » ${name}`)
    await sleep(400)
    threatPulse.value = false
    capturePhase.value = '完成'
    pushCaptureLog('动态分析报告已生成，已打开报告侧栏')
    captureOverlayVisible.value = false
    syncOrchestrating.value = false
    activeTab.value = 'list'
    reportDrawerOpen.value = true
    ElMessage.warning({
      message: `沙箱检出新的中风险 PHP 样本：${name}`,
      duration: 5000,
    })
    window.setTimeout(() => {
      if (highlightSavedAs.value === name) highlightSavedAs.value = ''
    }, 10000)
  }

  try {
    await run()
  } catch {
    captureOverlayVisible.value = false
    syncOrchestrating.value = false
    capturePhase.value = ''
    ElMessage.error('分析任务异常中断')
  }
}

watch(activeTab, async (t) => {
  if (t === 'analysis') {
    await nextTick()
    renderCharts()
    onResize()
  }
})

watch(
  () => analysis.value,
  async () => {
    if (activeTab.value === 'analysis') {
      await nextTick()
      renderCharts()
    }
  },
  { deep: true }
)

function openFile(row: QuarantineItem) {
  if (row.local_only || !row.url?.trim()) {
    ElMessage.info('该条为演练样本，无可下载实体链接。')
    return
  }
  window.open(row.url, '_blank', 'noopener,noreferrer')
}

async function removeRow(row: QuarantineItem) {
  try {
    await ElMessageBox.confirm(
      `确定从隔离区永久删除「${row.saved_as}」？删除后不可恢复。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
    if (row.local_only) {
      revertAnalysisForLocalRow(row)
      items.value = items.value.filter((i) => i.saved_as !== row.saved_as)
      if (detailRow.value?.saved_as === row.saved_as) detailOpen.value = false
      ElMessage.success('已移除该条目')
      await nextTick()
      if (activeTab.value === 'analysis') renderCharts()
      return
    }
    await deleteQuarantineFile(row.saved_as)
    ElMessage.success('已删除')
    fetchQuarantine()
  } catch {
    /* cancel */
  }
}

function tickClock() {
  liveClock.value = new Date().toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => {
  tickClock()
  clockTimer = setInterval(tickClock, 1000)
  fetchQuarantine()
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
    <div class="grid-bg" aria-hidden="true" />
    <div class="scanline" aria-hidden="true" />

    <Teleport to="body">
      <Transition name="capture-fade">
        <div
          v-if="captureOverlayVisible"
          class="capture-overlay"
          :class="{ 'threat-pulse': threatPulse }"
          role="dialog"
          aria-modal="true"
          aria-label="沙箱分析任务"
        >
          <div class="capture-panel">
            <div class="capture-radar" aria-hidden="true">
              <div class="radar-ring" />
              <div class="radar-sweep" />
              <div class="radar-core" />
            </div>
            <div class="capture-meta">
              <p class="capture-phase">{{ capturePhase }}</p>
              <p class="capture-hint">任务时钟与系统时间同步</p>
            </div>
            <div class="capture-terminal">
              <div class="term-bar">
                <span>沙箱任务.log</span>
                <span class="term-live">{{ liveClock }}</span>
              </div>
              <ul class="term-body">
                <li v-for="(line, idx) in captureLogs" :key="idx + line">{{ line }}</li>
              </ul>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport>

    <header class="page-head">
      <div class="title-block">
        <div class="status-rail">
          <span class="pulse-dot" />
          <span class="status-rail-zh">沙箱链路已建立 · 隔离执行环境在线</span>
          <span class="status-split" />
          <span class="mono-tiny clock-live">系统时间 {{ liveClock }}</span>
          <span class="cursor-blink">_</span>
        </div>
        <h1>动态分析沙箱</h1>
        <p class="title-tagline">虚拟机隔离执行 · 行为与静态联合分析 · 样本仅驻留隔离存储</p>
      </div>
      <button
        type="button"
        class="hud-sync hud-sync--zh"
        :disabled="syncOrchestrating"
        @click="runSyncSequence"
      >
        <el-icon class="hud-sync-ico" :class="{ spin: syncOrchestrating }"><Refresh /></el-icon>
        <span>{{ syncOrchestrating ? '分析任务执行中…' : '运行分析任务' }}</span>
      </button>
    </header>

    <section class="sb-console" aria-label="沙箱运行概览">
      <div class="sb-runtime-grid">
        <div class="sb-runtime-card">
          <div class="sb-runtime-card__label">分析虚拟机</div>
          <div class="sb-runtime-card__value mono-tiny">SB-VM-01 · KVM</div>
          <div class="sb-runtime-card__state sb-runtime-card__state--ok">运行中</div>
        </div>
        <div class="sb-runtime-card">
          <div class="sb-runtime-card__label">沙箱网络</div>
          <div class="sb-runtime-card__value mono-tiny">NAT · 外联观测</div>
          <div class="sb-runtime-card__state sb-runtime-card__state--ok">已限制</div>
        </div>
        <div class="sb-runtime-card">
          <div class="sb-runtime-card__label">待分析队列</div>
          <div class="sb-runtime-card__value mono-tiny">{{ items.length }} 个样本</div>
          <div class="sb-runtime-card__state">隔离区</div>
        </div>
        <div class="sb-runtime-card">
          <div class="sb-runtime-card__label">特征库版本</div>
          <div class="sb-runtime-card__value mono-tiny">defs-2025.03.x</div>
          <div class="sb-runtime-card__state sb-runtime-card__state--ok">已加载</div>
        </div>
      </div>
      <div class="sb-pipeline" aria-label="分析流水线阶段">
        <div class="sb-pipeline__track">
          <div
            v-for="(step, i) in PIPELINE_STEPS"
            :key="step.key"
            class="sb-pipeline__step"
            :class="{
              'sb-pipeline__step--idle': pipelineActiveIndex < 0,
              'sb-pipeline__step--done': pipelineActiveIndex > i,
              'sb-pipeline__step--active':
                pipelineActiveIndex === i && (syncOrchestrating || captureOverlayVisible),
              'sb-pipeline__step--pending':
                pipelineActiveIndex >= 0 &&
                i > pipelineActiveIndex &&
                (syncOrchestrating || captureOverlayVisible),
            }"
          >
            <span class="sb-pipeline__idx">{{ i + 1 }}</span>
            <span class="sb-pipeline__name">{{ step.label }}</span>
          </div>
        </div>
      </div>
    </section>

    <div class="warn-banner hud-warn">
      <el-icon class="warn-icon"><WarningFilled /></el-icon>
      <span>
        沙箱内文件可能包含恶意内容，请在受控环境中打开；删除前请确认已完成取证或不再需要保留。
      </span>
    </div>

    <el-tabs v-model="activeTab" class="sandbox-tabs">
      <el-tab-pane name="list">
        <template #label>
          <span class="tab-label tab-label--zh"><span class="tab-dot" />隔离样本库</span>
        </template>
        <div class="hud-panel">
          <div class="hud-corners" aria-hidden="true">
            <span class="c c-tl" /><span class="c c-tr" /><span class="c c-bl" /><span class="c c-br" />
          </div>
          <div class="hud-panel-bar">
            <span class="hud-panel-id hud-panel-id--zh">节点 · 隔离样本索引</span>
            <span class="hud-panel-line" />
          </div>
          <div class="toolbar">
            <el-input
              v-model="searchQuery"
              clearable
              placeholder="按文件名筛选…"
              class="search-inp hud-field"
              :prefix-icon="Search"
            />
            <el-select
              v-model="riskFilter"
              placeholder="风险"
              class="risk-sel hud-field"
              popper-class="sandbox-quarantine-popper"
            >
              <el-option label="全部风险" value="all" />
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
            </el-select>
            <span class="toolbar-meta toolbar-meta--zh">
              显示 {{ filteredItems.length }} / 共 {{ items.length }} 条
            </span>
          </div>

          <div class="table-wrap">
            <el-table
              ref="tableRef"
              v-loading="loading && !captureOverlayVisible"
              :data="filteredItems"
              row-key="saved_as"
              class="sandbox-table"
              empty-text="暂无符合条件的样本"
              highlight-current-row
              :row-class-name="rowClassName"
              element-loading-background="rgba(3, 8, 14, 0.92)"
              element-loading-text="正在加载隔离样本…"
              @row-dblclick="openDetail"
            >
              <el-table-column prop="saved_as" label="样本文件" min-width="240">
                <template #default="{ row }">
                  <span class="mono file-cell">{{ row.saved_as }}</span>
                  <span v-if="row.local_only" class="demo-badge">演练</span>
                </template>
              </el-table-column>
              <el-table-column label="风险" width="112" align="center">
                <template #default="{ row }">
                  <span
                    class="risk-pill"
                    :class="'risk-pill--' + (row.risk_level || 'low')"
                  >
                    {{ riskLabel(row.risk_level) }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="大小" width="100">
                <template #default="{ row }">
                  <span class="cell-dim mono-tiny">{{ formatSize(row.size) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="入库时间" min-width="220">
                <template #default="{ row }">
                  <span class="cell-dim mono-tiny">{{ formatTime(row.modified_at) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="268" fixed="right" align="right">
                <template #default="{ row }">
                  <div class="row-actions">
                    <button type="button" class="act" @click="openDetail(row)">研判简报</button>
                    <span class="act-sep">·</span>
                    <button type="button" class="act" @click="openFile(row)">打开文件</button>
                    <span class="act-sep">·</span>
                    <button type="button" class="act act-purge" @click="removeRow(row)">
                      删除
                    </button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane name="analysis">
        <template #label>
          <span class="tab-label tab-label--zh"><span class="tab-dot dim-dot" />统计与遥测</span>
        </template>
        <div v-if="analysis" class="analysis-layout">
          <div class="stat-row">
            <div class="stat-card" style="animation-delay: 0ms">
              <div class="stat-label">隔离样本总数</div>
              <div class="stat-num">{{ items.length }}</div>
            </div>
            <div class="stat-card" style="animation-delay: 60ms">
              <div class="stat-label">占用空间</div>
              <div class="stat-num">{{ formatSize(analysis.total_bytes) }}</div>
            </div>
            <div class="stat-card accent" style="animation-delay: 120ms">
              <div class="stat-label">今日新增</div>
              <div class="stat-num">{{ analysis.today_count }}</div>
            </div>
            <div class="stat-card" style="animation-delay: 180ms">
              <div class="stat-label">近 7 日</div>
              <div class="stat-num">{{ analysis.week_count }}</div>
            </div>
            <div class="stat-card danger-glow" style="animation-delay: 240ms">
              <div class="stat-label">高 / 中 风险计数</div>
              <div class="stat-num sm">
                {{ analysis.high_risk_count }} / {{ analysis.medium_risk_count }}
              </div>
            </div>
          </div>

          <div class="insight-panel">
            <div class="insight-head">
              <span class="insight-head-zh">分析事件流</span>
              <span v-if="analysis.generated_at" class="mono-tiny dim">
                {{ formatTime(analysis.generated_at) }}
              </span>
            </div>
            <ul class="insight-list">
              <li v-for="(line, i) in analysis.insights" :key="i" :style="{ animationDelay: `${i * 80}ms` }">
                {{ line }}
              </li>
            </ul>
          </div>

          <div class="charts-row">
            <div class="chart-card">
              <div class="chart-title">近 14 日样本入库趋势</div>
              <div ref="trendRef" class="chart-box" />
            </div>
            <div class="chart-card">
              <div class="chart-title">扩展名分布（Top 6）</div>
              <div ref="extRef" class="chart-box pie" />
            </div>
          </div>

          <div class="timeline-card">
            <div class="chart-title">最近样本时间线（双击表格行可打开研判简报）</div>
            <div class="timeline">
              <div
                v-for="(row, idx) in timelinePreview"
                :key="row.saved_as + idx"
                class="tl-node"
                :style="{ animationDelay: `${idx * 50}ms` }"
                @click="openDetail(row)"
              >
                <div class="tl-dot" />
                <div class="tl-body">
                  <div class="tl-time mono-tiny">{{ formatTime(row.modified_at) }}</div>
                  <div class="tl-name mono">{{ row.saved_as }}</div>
                  <span
                    class="risk-pill tl-tag"
                    :class="'risk-pill--' + (row.risk_level || 'low')"
                  >
                    {{ riskLabel(row.risk_level) }}
                  </span>
                </div>
              </div>
              <p v-if="!timelinePreview.length" class="empty-tl mono-tiny">暂无时间线数据</p>
            </div>
          </div>
        </div>
        <div v-else class="empty-analysis">暂无统计数据，请刷新页面或先向沙箱投递样本。</div>
      </el-tab-pane>
    </el-tabs>

    <p class="foot-note">数据来自隔离文件接口；实体样本位于服务端隔离目录，与业务数据隔离。</p>

    <el-drawer
      v-model="detailOpen"
      title="样本研判简报"
      direction="rtl"
      size="460px"
      class="sandbox-drawer"
    >
      <template v-if="detailRow">
        <pre class="narrative">{{ detailNarrative(detailRow) }}</pre>
        <div class="drawer-actions">
          <button type="button" class="hud-sync hud-sync--sm hud-sync--zh" @click="openFile(detailRow)">
            新窗口打开
          </button>
          <button type="button" class="hud-ghost" @click="detailOpen = false">关闭</button>
        </div>
      </template>
    </el-drawer>

    <el-drawer
      v-model="reportDrawerOpen"
      title="动态分析报告"
      direction="rtl"
      size="520px"
      class="sandbox-drawer report-drawer"
    >
      <template v-if="lastCaptureReport">
        <div class="report-head">
          <p class="report-file mono">{{ lastCaptureReport.fileName }}</p>
          <p class="report-time">
            分析完成时间 <span class="mono">{{ formatTime(lastCaptureReport.capturedAtIso) }}</span>
          </p>
          <p class="report-time sub">
            当前查看时间 <span class="mono">{{ liveClock }}</span>
          </p>
        </div>
        <div
          v-for="(sec, i) in lastCaptureReport.sections"
          :key="i"
          class="report-section"
        >
          <h3 class="report-sec-title">{{ sec.title }}</h3>
          <pre class="report-sec-body">{{ sec.body }}</pre>
        </div>
        <p class="report-foot">
          本报告由演练任务生成；须对接沙箱遥测与杀毒引擎结论复核。
        </p>
        <div class="drawer-actions">
          <button type="button" class="hud-ghost" @click="reportDrawerOpen = false">
            关闭报告
          </button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.sandbox-page {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 24px 28px;
  overflow: auto;
  color-scheme: dark;
  background: var(--sec-hud-page-bg);
  color: rgba(255, 255, 255, 0.94);
  font-size: 16px;
}

.sandbox-page::after {
  pointer-events: none;
  content: '';
  position: fixed;
  inset: 0;
  z-index: 0;
  opacity: 0.04;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
}

.grid-bg {
  pointer-events: none;
  position: fixed;
  inset: 0;
  z-index: 0;
  opacity: 0.35;
  background-image:
    linear-gradient(rgba(34, 211, 238, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(34, 211, 238, 0.06) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(ellipse 80% 60% at 50% 20%, black 20%, transparent 70%);
}

.scanline {
  pointer-events: none;
  position: fixed;
  inset: 0;
  z-index: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.03) 2px,
    rgba(0, 0, 0, 0.03) 4px
  );
  animation: scan-drift 14s linear infinite;
}

@keyframes scan-drift {
  0% {
    transform: translateY(0);
  }
  100% {
    transform: translateY(48px);
  }
}

.page-head,
.sb-console,
.warn-banner,
.sandbox-tabs,
.foot-note {
  position: relative;
  z-index: 1;
}

.capture-fade-enter-active,
.capture-fade-leave-active {
  transition: opacity 0.35s ease;
}

.capture-fade-enter-from,
.capture-fade-leave-to {
  opacity: 0;
}

.capture-overlay {
  position: fixed;
  inset: 0;
  z-index: 10000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(1, 4, 10, 0.88);
  backdrop-filter: blur(10px);
}

.capture-overlay.threat-pulse {
  animation: threat-glow 0.85s ease-in-out 2;
}

@keyframes threat-glow {
  0%,
  100% {
    box-shadow: inset 0 0 0 0 transparent;
  }
  50% {
    box-shadow: inset 0 0 120px rgba(239, 68, 68, 0.25);
  }
}

.capture-panel {
  width: min(560px, 100%);
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 28px 28px 24px;
  border: 1px solid rgba(34, 211, 238, 0.35);
  border-radius: 4px;
  background: rgba(3, 10, 18, 0.95);
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.6),
    0 32px 80px rgba(0, 0, 0, 0.55),
    0 0 40px rgba(34, 211, 238, 0.08);
}

.capture-radar {
  position: relative;
  width: 120px;
  height: 120px;
  margin: 0 auto;
}

.radar-ring {
  position: absolute;
  inset: 0;
  border: 1px solid rgba(34, 211, 238, 0.25);
  border-radius: 50%;
  animation: radar-pulse 2.2s ease-in-out infinite;
}

.radar-ring::after {
  content: '';
  position: absolute;
  inset: 18px;
  border: 1px dashed rgba(34, 211, 238, 0.15);
  border-radius: 50%;
}

@keyframes radar-pulse {
  0%,
  100% {
    opacity: 0.7;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.03);
  }
}

.radar-sweep {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: conic-gradient(
    transparent 0deg,
    transparent 260deg,
    rgba(34, 211, 238, 0.25) 310deg,
    rgba(103, 232, 249, 0.45) 360deg
  );
  animation: sweep 2.8s linear infinite;
  mask-image: radial-gradient(circle, transparent 42%, black 44%);
}

@keyframes sweep {
  to {
    transform: rotate(360deg);
  }
}

.radar-core {
  position: absolute;
  inset: 36px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(34, 211, 238, 0.35), transparent 70%);
  box-shadow: 0 0 24px rgba(34, 211, 238, 0.4);
}

.capture-meta {
  text-align: center;
}

.capture-phase {
  margin: 0 0 6px;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.2em;
  color: #7dd3fc;
  text-shadow: 0 0 20px rgba(34, 211, 238, 0.35);
}

.capture-hint {
  margin: 0;
  font-size: 16px;
  color: rgba(203, 213, 225, 0.88);
}

.capture-terminal {
  border: 1px solid rgba(34, 211, 238, 0.2);
  border-radius: 4px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.45);
}

.term-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 15px;
  letter-spacing: 0.06em;
  color: rgba(186, 230, 253, 0.95);
  background: rgba(34, 211, 238, 0.08);
  border-bottom: 1px solid rgba(34, 211, 238, 0.12);
}

.term-live {
  color: rgba(226, 232, 240, 0.9);
  font-weight: 600;
}

.term-body {
  margin: 0;
  padding: 14px 16px;
  max-height: 220px;
  overflow-y: auto;
  list-style: none;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 16px;
  line-height: 1.6;
  color: rgba(241, 245, 249, 0.94);
}

.term-body li {
  margin-bottom: 4px;
  word-break: break-all;
}

.status-split {
  width: 1px;
  height: 14px;
  background: rgba(34, 211, 238, 0.25);
  margin: 0 4px;
}

.clock-live {
  color: rgba(248, 250, 252, 0.95);
  font-weight: 600;
}

.demo-badge {
  display: inline-block;
  margin-left: 8px;
  padding: 3px 9px;
  font-family:
    'Segoe UI',
    system-ui,
    sans-serif;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.06em;
  vertical-align: middle;
  color: rgba(251, 191, 36, 0.95);
  border: 1px solid rgba(251, 191, 36, 0.45);
  border-radius: 2px;
  background: rgba(120, 53, 15, 0.35);
}

.report-head {
  margin-bottom: 18px;
  padding-bottom: 14px;
  border-bottom: 1px solid rgba(34, 211, 238, 0.15);
}

.report-file {
  margin: 0 0 10px;
  font-size: 17px;
  font-weight: 600;
  color: #bae6fd;
  word-break: break-all;
  line-height: 1.55;
}

.report-time {
  margin: 0 0 6px;
  font-size: 17px;
  color: rgba(241, 245, 249, 0.94);
  line-height: 1.55;
}

.report-time.sub {
  font-size: 16px;
  color: rgba(203, 213, 225, 0.88);
}

.report-section {
  margin-bottom: 16px;
}

.report-sec-title {
  margin: 0 0 10px;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #7dd3fc;
}

.report-sec-body {
  margin: 0;
  white-space: pre-wrap;
  font-family: ui-monospace, 'Cascadia Mono', Consolas, monospace;
  font-size: 16px;
  line-height: 1.72;
  color: rgba(248, 250, 252, 0.96);
  background: rgba(0, 0, 0, 0.42);
  padding: 14px 16px;
  border-radius: 4px;
  border: 1px solid rgba(34, 211, 238, 0.14);
}

.report-foot {
  margin: 20px 0 16px;
  font-size: 15px;
  line-height: 1.65;
  color: rgba(203, 213, 225, 0.88);
}

.hud-sync {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 14px 24px;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 17px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #7dd3fc;
  background: rgba(3, 12, 22, 0.85);
  border: 1px solid rgba(34, 211, 238, 0.45);
  border-radius: 2px;
  cursor: pointer;
  box-shadow:
    0 0 20px rgba(34, 211, 238, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  transition:
    border-color 0.2s,
    box-shadow 0.2s,
    color 0.2s;
}

.hud-sync:hover:not(:disabled) {
  border-color: rgba(103, 232, 249, 0.75);
  box-shadow:
    0 0 28px rgba(34, 211, 238, 0.22),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
  color: #a5f3fc;
}

.hud-sync:disabled {
  opacity: 0.55;
  cursor: wait;
}

.hud-sync-ico {
  font-size: 20px;
}

.hud-sync-ico.spin {
  animation: ico-spin 0.9s linear infinite;
}

@keyframes ico-spin {
  to {
    transform: rotate(360deg);
  }
}

.hud-sync--sm {
  padding: 12px 20px;
  font-size: 15px;
  letter-spacing: 0.08em;
  text-transform: none;
}

.hud-sync--zh {
  text-transform: none;
  letter-spacing: 0.08em;
  font-size: 17px;
  font-family:
    'Segoe UI',
    system-ui,
    -apple-system,
    sans-serif;
}

.hud-ghost {
  padding: 12px 20px;
  font-size: 17px;
  font-family: ui-monospace, Consolas, monospace;
  color: rgba(203, 213, 225, 0.75);
  background: transparent;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 2px;
  cursor: pointer;
  transition:
    border-color 0.2s,
    color 0.2s;
}

.hud-ghost:hover {
  border-color: rgba(255, 255, 255, 0.28);
  color: rgba(255, 255, 255, 0.75);
}

.tab-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 17px;
  letter-spacing: 0.06em;
}

.tab-label--zh {
  font-family:
    'Segoe UI',
    system-ui,
    -apple-system,
    sans-serif;
  letter-spacing: 0.04em;
}

.tab-dot {
  width: 6px;
  height: 6px;
  border-radius: 1px;
  background: #22d3ee;
  box-shadow: 0 0 10px rgba(34, 211, 238, 0.7);
}

.tab-dot.dim-dot {
  background: rgba(34, 211, 238, 0.35);
  box-shadow: none;
}

.hud-panel {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 14px 16px 16px;
  border-radius: 2px;
  background: rgba(2, 8, 14, 0.72);
  border: 1px solid rgba(34, 211, 238, 0.18);
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.5),
    0 24px 48px rgba(0, 0, 0, 0.35),
    inset 0 1px 0 rgba(34, 211, 238, 0.06);
}

.hud-corners .c {
  position: absolute;
  width: 14px;
  height: 14px;
  border-color: rgba(103, 232, 249, 0.55);
  border-style: solid;
  pointer-events: none;
  z-index: 2;
}

.hud-corners .c-tl {
  top: -1px;
  left: -1px;
  border-width: 2px 0 0 2px;
}

.hud-corners .c-tr {
  top: -1px;
  right: -1px;
  border-width: 2px 2px 0 0;
}

.hud-corners .c-bl {
  bottom: -1px;
  left: -1px;
  border-width: 0 0 2px 2px;
}

.hud-corners .c-br {
  bottom: -1px;
  right: -1px;
  border-width: 0 2px 2px 0;
}

.hud-panel-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.hud-panel-id {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 14px;
  letter-spacing: 0.14em;
  color: rgba(34, 211, 238, 0.55);
  white-space: nowrap;
}

.hud-panel-id--zh {
  font-family:
    'Segoe UI',
    system-ui,
    -apple-system,
    sans-serif;
  letter-spacing: 0.1em;
  font-size: 14px;
  font-weight: 600;
  color: rgba(125, 211, 252, 0.88);
}

.hud-panel-line {
  flex: 1;
  height: 1px;
  background: linear-gradient(
    90deg,
    rgba(34, 211, 238, 0.35),
    rgba(34, 211, 238, 0.04) 70%,
    transparent
  );
}

.hud-warn {
  background: rgba(180, 83, 9, 0.08) !important;
  border-color: rgba(251, 191, 36, 0.18) !important;
  backdrop-filter: blur(6px);
}

.risk-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 2em;
  padding: 6px 14px;
  font-family:
    'Segoe UI',
    system-ui,
    -apple-system,
    sans-serif;
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.08em;
  border-radius: 1px;
  border: 1px solid;
}

.risk-pill--low {
  color: rgba(148, 163, 184, 0.95);
  border-color: rgba(100, 116, 139, 0.45);
  background: rgba(15, 23, 42, 0.65);
}

.risk-pill--medium {
  color: #fde68a;
  border-color: rgba(251, 191, 36, 0.5);
  background: rgba(120, 53, 15, 0.2);
  box-shadow: 0 0 14px rgba(251, 191, 36, 0.08);
}

.risk-pill--high {
  color: #fecaca;
  border-color: rgba(248, 113, 113, 0.55);
  background: rgba(127, 29, 29, 0.22);
  box-shadow: 0 0 16px rgba(239, 68, 68, 0.12);
}

.row-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  flex-wrap: wrap;
}

.act {
  margin: 0;
  padding: 6px 10px;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 16px;
  letter-spacing: 0.06em;
  color: rgba(125, 211, 252, 0.95);
  background: transparent;
  border: none;
  border-radius: 2px;
  cursor: pointer;
  transition:
    color 0.15s,
    text-shadow 0.15s,
    background 0.15s;
}

.act:hover {
  color: #cffafe;
  text-shadow: 0 0 14px rgba(34, 211, 238, 0.5);
  background: rgba(34, 211, 238, 0.08);
}

.act-purge {
  color: rgba(248, 113, 113, 0.65);
}

.act-purge:hover {
  color: #fecaca;
  text-shadow: 0 0 12px rgba(239, 68, 68, 0.4);
  background: rgba(248, 113, 113, 0.08);
}

.act-sep {
  color: rgba(255, 255, 255, 0.12);
  font-size: 14px;
  user-select: none;
  padding: 0 1px;
}

.cell-dim {
  font-size: 16px;
  color: rgba(241, 245, 249, 0.9);
}

.status-rail {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 16px;
  color: rgba(103, 232, 249, 0.88);
  letter-spacing: 0.08em;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #22d3ee;
  box-shadow: 0 0 12px #22d3ee;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.5;
    transform: scale(0.85);
  }
}

.cursor-blink {
  animation: blink 1.1s step-end infinite;
  color: #22d3ee;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}

.mono-tiny {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 16px;
  color: rgba(241, 245, 249, 0.92);
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.title-block h1 {
  margin: 0 0 6px;
  font-size: 30px;
  font-weight: 700;
  color: #fff;
  letter-spacing: 0.06em;
  text-shadow: 0 0 24px rgba(34, 211, 238, 0.15);
}

.title-tagline {
  margin: 0;
  font-size: 16px;
  color: rgba(224, 242, 254, 0.9);
  max-width: 640px;
  line-height: 1.6;
  letter-spacing: 0.02em;
}

.status-rail-zh {
  font-size: 14px;
  font-weight: 600;
  color: rgba(165, 243, 252, 0.92);
  letter-spacing: 0.04em;
}

.sb-console {
  margin-bottom: 18px;
  padding: 16px 18px;
  border-radius: 4px;
  border: 1px solid rgba(34, 211, 238, 0.2);
  background: linear-gradient(165deg, rgba(6, 18, 32, 0.92), rgba(2, 8, 16, 0.88));
  box-shadow:
    0 0 0 1px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(34, 211, 238, 0.06);
}

.sb-runtime-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

@media (max-width: 1100px) {
  .sb-runtime-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 560px) {
  .sb-runtime-grid {
    grid-template-columns: 1fr;
  }
}

.sb-runtime-card {
  padding: 12px 14px;
  border-radius: 2px;
  border: 1px solid rgba(34, 211, 238, 0.12);
  background: rgba(0, 0, 0, 0.28);
}

.sb-runtime-card__label {
  font-size: 13px;
  font-weight: 600;
  color: rgba(203, 213, 225, 0.92);
  letter-spacing: 0.06em;
  margin-bottom: 6px;
}

.sb-runtime-card__value {
  font-size: 15px;
  color: rgba(248, 250, 252, 0.96);
  margin-bottom: 8px;
  line-height: 1.45;
}

.sb-runtime-card__state {
  font-size: 13px;
  color: rgba(186, 230, 253, 0.85);
}

.sb-runtime-card__state--ok {
  color: #34d399;
  font-weight: 600;
}

.sb-pipeline__track {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch;
  gap: 8px;
}

.sb-pipeline__step {
  flex: 1;
  min-width: 96px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: 2px;
  border: 1px solid rgba(51, 65, 85, 0.5);
  background: rgba(15, 23, 42, 0.5);
  transition:
    border-color 0.25s,
    box-shadow 0.25s,
    background 0.25s;
}

.sb-pipeline__idx {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 13px;
  font-weight: 700;
  color: rgba(148, 163, 184, 0.9);
  border: 1px solid rgba(71, 85, 105, 0.6);
  border-radius: 2px;
  background: rgba(0, 0, 0, 0.35);
}

.sb-pipeline__name {
  font-size: 14px;
  font-weight: 600;
  color: rgba(226, 232, 240, 0.88);
  letter-spacing: 0.02em;
  line-height: 1.35;
}

.sb-pipeline__step--idle {
  opacity: 0.85;
}

.sb-pipeline__step--pending {
  opacity: 0.55;
}

.sb-pipeline__step--done {
  border-color: rgba(34, 211, 238, 0.25);
  background: rgba(34, 211, 238, 0.06);
}

.sb-pipeline__step--done .sb-pipeline__idx {
  border-color: rgba(34, 211, 238, 0.4);
  color: #67e8f9;
}

.sb-pipeline__step--done .sb-pipeline__name {
  color: rgba(226, 232, 240, 0.88);
}

.sb-pipeline__step--active {
  border-color: rgba(103, 232, 249, 0.65);
  background: rgba(8, 47, 73, 0.45);
  box-shadow: 0 0 20px rgba(34, 211, 238, 0.12);
}

.sb-pipeline__step--active .sb-pipeline__idx {
  border-color: rgba(103, 232, 249, 0.85);
  color: #fff;
  box-shadow: 0 0 12px rgba(34, 211, 238, 0.35);
}

.sb-pipeline__step--active .sb-pipeline__name {
  color: #e0f2fe;
}

.warn-banner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 14px 18px;
  margin-bottom: 16px;
  border-radius: 10px;
  background: rgba(245, 158, 11, 0.08);
  border: 1px solid rgba(245, 158, 11, 0.28);
  font-size: 16px;
  font-weight: 500;
  color: #fde68a;
  line-height: 1.6;
}

.warn-icon {
  flex-shrink: 0;
  margin-top: 2px;
  font-size: 24px;
}

.sandbox-tabs {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;

  :deep(.el-tabs__header) {
    margin-bottom: 14px;
  }

  :deep(.el-tabs__nav-wrap::after) {
    background-color: rgba(34, 211, 238, 0.12);
  }

  :deep(.el-tabs__item) {
    color: rgba(255, 255, 255, 0.55);
    font-size: 18px;
    font-weight: 500;
  }

  :deep(.el-tabs__item.is-active) {
    color: #22d3ee;
  }

  :deep(.el-tabs__active-bar) {
    background-color: #22d3ee;
    box-shadow: 0 0 12px rgba(34, 211, 238, 0.5);
  }

  :deep(.el-tabs__content),
  :deep(.el-tab-pane) {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.hud-field.search-inp {
  width: 300px;

  :deep(.el-input__wrapper) {
    background: rgba(0, 0, 0, 0.45);
    box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.2);
    border-radius: 2px;
  }

  :deep(.el-input__inner) {
    color: rgba(248, 250, 252, 0.96);
    font-family: ui-monospace, Consolas, monospace;
    font-size: 17px;
    letter-spacing: 0.04em;
  }

  :deep(.el-input__inner::placeholder) {
    color: rgba(148, 163, 184, 0.55);
  }

  :deep(.el-input__prefix) {
    color: rgba(34, 211, 238, 0.45);
  }
}

.hud-field.risk-sel {
  width: 144px;

  :deep(.el-select__wrapper) {
    background: rgba(0, 0, 0, 0.45);
    box-shadow: 0 0 0 1px rgba(34, 211, 238, 0.18);
    border-radius: 2px;
  }

  :deep(.el-select__placeholder) {
    color: rgba(148, 163, 184, 0.58);
    font-family: ui-monospace, Consolas, monospace;
    font-size: 17px;
  }

  :deep(.el-select__selected-item) {
    color: rgba(248, 250, 252, 0.95);
    font-family: ui-monospace, Consolas, monospace;
    font-size: 17px;
  }
}

.toolbar-meta {
  color: rgba(255, 255, 255, 0.35);
  margin-left: auto;
}

.toolbar-meta--zh {
  font-family:
    'Segoe UI',
    system-ui,
    -apple-system,
    sans-serif;
  font-size: 15px;
  color: rgba(186, 230, 253, 0.72);
  letter-spacing: 0.02em;
}

.insight-head-zh {
  font-size: 16px;
  font-weight: 700;
  color: #7dd3fc;
  letter-spacing: 0.06em;
}

.table-wrap {
  position: relative;
  flex: 1;
  min-height: 240px;
  border-radius: 2px;
  border: 1px solid rgba(34, 211, 238, 0.12);
  overflow: hidden;
  background: rgba(1, 6, 12, 0.9);
  box-shadow: inset 0 0 32px rgba(0, 0, 0, 0.45);
}

.table-wrap :deep(.el-loading-mask) {
  background-color: rgba(3, 8, 14, 0.94) !important;
}

.file-cell {
  cursor: pointer;

  &:hover {
    color: #67e8f9;
    text-decoration: underline;
    text-underline-offset: 3px;
  }
}

.mono {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 17px;
  color: rgba(224, 242, 254, 0.98);
}

.foot-note {
  margin-top: 14px;
  font-size: 15px;
  color: rgba(203, 213, 225, 0.55);
}

.analysis-layout {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stat-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 12px;
}

.stat-card {
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid rgba(34, 211, 238, 0.14);
  background: rgba(0, 0, 0, 0.35);
  animation: card-in 0.5s ease backwards;

  &.accent {
    border-color: rgba(34, 211, 238, 0.35);
    box-shadow: 0 0 20px rgba(34, 211, 238, 0.08);
  }

  &.danger-glow {
    border-color: rgba(248, 113, 113, 0.25);
    box-shadow: 0 0 18px rgba(239, 68, 68, 0.06);
  }
}

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.stat-label {
  font-size: 16px;
  color: rgba(226, 232, 240, 0.72);
  margin-bottom: 6px;
}

.stat-num {
  font-size: 30px;
  font-weight: 700;
  font-family: ui-monospace, Consolas, monospace;
  color: #f0f9ff;

  &.sm {
    font-size: 24px;
  }
}

.insight-panel {
  border-radius: 10px;
  border: 1px solid rgba(34, 211, 238, 0.12);
  background: rgba(0, 0, 0, 0.4);
  padding: 14px 18px;
}

.insight-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  border-bottom: 1px solid rgba(34, 211, 238, 0.1);
  padding-bottom: 8px;
}

.dim {
  color: rgba(203, 213, 225, 0.65);
}

.insight-list {
  margin: 0;
  padding-left: 18px;
  color: rgba(248, 250, 252, 0.94);
  font-size: 17px;
  line-height: 1.78;

  li {
    animation: card-in 0.45s ease backwards;
  }
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
  border-radius: 10px;
  border: 1px solid rgba(34, 211, 238, 0.12);
  background: rgba(0, 0, 0, 0.35);
  padding: 12px 14px 8px;
  min-height: 260px;
}

.chart-title {
  font-size: 17px;
  font-weight: 600;
  color: rgba(125, 211, 252, 0.95);
  letter-spacing: 0.05em;
  margin-bottom: 6px;
}

.chart-box {
  height: 220px;
  width: 100%;

  &.pie {
    height: 240px;
  }
}

.timeline-card {
  border-radius: 10px;
  border: 1px solid rgba(34, 211, 238, 0.1);
  background: rgba(0, 0, 0, 0.3);
  padding: 14px 16px 18px;
}

.timeline {
  position: relative;
  margin-top: 12px;
  padding-left: 18px;
  border-left: 1px solid rgba(34, 211, 238, 0.2);
}

.tl-node {
  position: relative;
  margin-bottom: 16px;
  padding-left: 14px;
  cursor: pointer;
  animation: card-in 0.4s ease backwards;
  transition: transform 0.2s ease;

  &:hover {
    transform: translateX(4px);
  }
}

.tl-dot {
  position: absolute;
  left: -23px;
  top: 6px;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: #22d3ee;
  box-shadow: 0 0 10px rgba(34, 211, 238, 0.6);
}

.tl-time {
  font-size: 16px;
  color: rgba(203, 213, 225, 0.85);
  margin-bottom: 2px;
}

.tl-name {
  font-size: 17px;
  color: rgba(240, 249, 255, 0.98);
  word-break: break-all;
}

.tl-tag {
  margin-top: 6px;
}

.empty-tl {
  color: rgba(203, 213, 225, 0.55);
  margin: 8px 0 0;
  font-size: 16px;
}

.empty-analysis {
  padding: 40px;
  text-align: center;
  font-size: 18px;
  color: rgba(203, 213, 225, 0.75);
}

.narrative {
  margin: 0 0 20px;
  white-space: pre-wrap;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 17px;
  line-height: 1.78;
  color: rgba(248, 250, 252, 0.96);
  background: rgba(0, 0, 0, 0.4);
  padding: 16px;
  border-radius: 8px;
  border: 1px solid rgba(34, 211, 238, 0.14);
}

.drawer-actions {
  display: flex;
  gap: 10px;
}

:deep(.sandbox-table.el-table) {
  --el-bg-color: #03080e;
  --el-fill-color-blank: #03080e;
  --el-fill-color-light: #050f18;
  --el-table-bg-color: #03080e;
  --el-table-tr-bg-color: #03080e;
  --el-table-header-bg-color: #050c14;
  --el-table-header-text-color: rgba(165, 243, 252, 0.95);
  --el-table-text-color: rgba(248, 250, 252, 0.96);
  --el-table-row-hover-bg-color: rgba(34, 211, 238, 0.08);
  --el-table-border-color: rgba(34, 211, 238, 0.1);
  --el-table-current-row-bg-color: rgba(10, 28, 40, 0.95);
  --el-table-expanded-cell-bg-color: #050c14;
  background: #03080e !important;
  color: rgba(248, 250, 252, 0.96);
  font-family: ui-monospace, Consolas, monospace;
  font-size: 17px;
}

:deep(.sandbox-table .el-table__inner-wrapper::before) {
  display: none;
}

:deep(.sandbox-table .el-table__body-wrapper),
:deep(.sandbox-table .el-scrollbar__wrap),
:deep(.sandbox-table .el-scrollbar__view) {
  background-color: #03080e !important;
}

:deep(.sandbox-table th.el-table__cell) {
  background-color: #050c14 !important;
  color: rgba(186, 230, 253, 0.98) !important;
  font-weight: 600;
  font-size: 15px;
  letter-spacing: 0.06em;
  text-transform: none;
  border-bottom: 1px solid rgba(34, 211, 238, 0.15) !important;
  padding: 14px 14px !important;
}

:deep(.sandbox-table td.el-table__cell) {
  background-color: #03080e !important;
  color: rgba(248, 250, 252, 0.98) !important;
  border-color: rgba(34, 211, 238, 0.06) !important;
  padding: 16px 14px !important;
  font-size: 17px;
}

:deep(.sandbox-table .cell) {
  font-size: 17px;
  line-height: 1.55;
}

:deep(.sandbox-table tr:hover > td.el-table__cell) {
  background-color: rgba(34, 211, 238, 0.09) !important;
  color: #f8fafc !important;
}

:deep(.sandbox-table tr.current-row > td.el-table__cell) {
  background-color: rgba(8, 32, 48, 0.92) !important;
  color: #f8fafc !important;
  box-shadow: inset 4px 0 0 rgba(34, 211, 238, 0.9);
}

:deep(.sandbox-table tr.is-new-capture > td.el-table__cell) {
  background-color: rgba(60, 20, 24, 0.55) !important;
  color: #fef2f2 !important;
  box-shadow: inset 0 0 0 1px rgba(248, 113, 113, 0.35);
  animation: row-capture-pulse 2s ease-in-out 3;
}

@keyframes row-capture-pulse {
  0%,
  100% {
    box-shadow: inset 0 0 0 1px rgba(248, 113, 113, 0.2);
  }
  50% {
    box-shadow: inset 0 0 0 1px rgba(248, 113, 113, 0.55);
  }
}

:deep(.sandbox-table .el-table__fixed-right),
:deep(.sandbox-table .el-table__fixed) {
  background: #03080e !important;
  box-shadow: -12px 0 24px rgba(0, 0, 0, 0.55);
}

:deep(.sandbox-table .el-table__fixed-right-patch) {
  background: #03080e !important;
}

:deep(.sandbox-table .el-table__empty-text) {
  color: rgba(203, 213, 225, 0.65);
  font-family: ui-monospace, Consolas, monospace;
  font-size: 17px;
  letter-spacing: 0.06em;
}

:deep(.sandbox-table + .el-loading-mask),
:deep(.el-loading-mask) {
  background-color: rgba(3, 8, 14, 0.92) !important;
}

:deep(.el-loading-text) {
  color: rgba(125, 211, 252, 0.9) !important;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 17px !important;
  letter-spacing: 0.06em;
}

:deep(.el-loading-spinner .path) {
  stroke: rgba(34, 211, 238, 0.65) !important;
}
</style>

<style lang="scss">
.sandbox-drawer.el-drawer {
  --el-drawer-bg-color: #0c1220;
}

.sandbox-drawer .el-drawer__header {
  color: #f0f9ff;
  margin-bottom: 12px;
}

.sandbox-drawer .el-drawer__title {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #e0f2fe;
  line-height: 1.4;
}

.sandbox-drawer .el-drawer__body {
  font-size: 16px;
  color: rgba(241, 245, 249, 0.95);
}

.report-drawer .el-drawer__title {
  color: #fecaca;
  text-shadow: 0 0 20px rgba(239, 68, 68, 0.25);
}
</style>

<style lang="scss">
/* 下拉挂载在 body，需非 scoped */
.sandbox-quarantine-popper.el-select__popper {
  background: #070f18 !important;
  border: 1px solid rgba(34, 211, 238, 0.22) !important;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.55) !important;
}

.sandbox-quarantine-popper .el-select-dropdown__item {
  font-family: ui-monospace, Consolas, monospace;
  font-size: 16px;
  color: rgba(226, 232, 240, 0.85);
}

.sandbox-quarantine-popper .el-select-dropdown__item.is-hovering,
.sandbox-quarantine-popper .el-select-dropdown__item:hover {
  background: rgba(34, 211, 238, 0.12) !important;
}

.sandbox-quarantine-popper .el-select-dropdown__item.is-selected {
  color: #67e8f9 !important;
  font-weight: 600;
}

.sandbox-quarantine-popper .el-popper__arrow::before {
  background: #070f18 !important;
  border-color: rgba(34, 211, 238, 0.22) !important;
}
</style>
