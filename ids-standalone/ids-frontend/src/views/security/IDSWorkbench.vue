<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  analyzeIDSEventAI,
  getIDSEventInsight,
  getIDSEventReport,
  listIDSEvents,
  type IDSEventInsightResponse,
  type IDSEventItem,
} from '@/api/ids'

const route = useRoute()
const router = useRouter()

const listLoading = ref(false)
const detailLoading = ref(false)
const aiLoading = ref(false)
const exportLoading = ref(false)
const minScore = ref(60)
const onlyBlocked = ref(false)
const keyword = ref('')
const events = ref<IDSEventItem[]>([])
const selectedId = ref<number | null>(null)
const insight = ref<IDSEventInsightResponse | null>(null)

const filteredEvents = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return events.value
  return events.value.filter((item) => {
    return [
      item.client_ip,
      item.path,
      item.attack_type_label,
      item.attack_type,
      item.signature_matched,
    ]
      .join(' ')
      .toLowerCase()
      .includes(q)
  })
})

const currentItem = computed(() => insight.value?.item || null)
const currentProfile = computed(() => insight.value?.profile || null)
const currentTimeline = computed(() => insight.value?.timeline?.items || [])
const currentCluster = computed(() => insight.value?.cluster || null)
const currentFalsePositive = computed(() => insight.value?.false_positive_learning || null)
const currentHits = computed(() => currentItem.value?.matched_hits || [])
const currentPacket = computed(() => currentItem.value?.request_packet || null)

function riskTagType(score?: number | null) {
  const value = Number(score || 0)
  if (value >= 85) return 'danger'
  if (value >= 60) return 'warning'
  return 'info'
}

function formatTime(value?: string | null) {
  if (!value) return '--'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString('zh-CN', { hour12: false })
}

function openEventCenter() {
  if (!selectedId.value) return
  void router.push({ path: '/events', query: { event: String(selectedId.value) } })
}

function openSandbox() {
  void router.push('/sandbox')
}

async function exportReport() {
  if (!selectedId.value) return
  exportLoading.value = true
  try {
    const response: any = await getIDSEventReport(selectedId.value, false)
    const payload = response?.data ?? response
    const markdown = String(payload?.markdown || '')
    const blob = new Blob([markdown], { type: 'text/markdown;charset=utf-8' })
    const href = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = href
    anchor.download = `ids-event-${selectedId.value}-report.md`
    anchor.click()
    URL.revokeObjectURL(href)
  } catch {
    ElMessage.error('导出事件报告失败')
  } finally {
    exportLoading.value = false
  }
}

async function runAi() {
  if (!selectedId.value) return
  aiLoading.value = true
  try {
    await analyzeIDSEventAI(selectedId.value)
    await loadInsight(selectedId.value, false)
    ElMessage.success('AI 研判已刷新')
  } catch {
    ElMessage.error('AI 研判执行失败')
  } finally {
    aiLoading.value = false
  }
}

async function loadInsight(eventId: number, syncRoute = true) {
  detailLoading.value = true
  try {
    const response: any = await getIDSEventInsight(eventId)
    const payload = response?.data ?? response
    insight.value = payload ?? null
    selectedId.value = payload?.item?.id ?? eventId
    if (syncRoute) {
      await router.replace({ path: '/workbench', query: { event: String(selectedId.value) } })
    }
  } catch {
    ElMessage.error('加载分析工作台失败')
  } finally {
    detailLoading.value = false
  }
}

async function loadEvents() {
  listLoading.value = true
  try {
    const response: any = await listIDSEvents({
      limit: 30,
      offset: 0,
      archived: 0,
      min_score: minScore.value,
      blocked: onlyBlocked.value ? 1 : undefined,
    })
    const payload = response?.data ?? response
    events.value = payload?.items ?? []

    const routeEventId = Number(route.query.event || 0)
    const preferredId =
      (routeEventId && events.value.find((item) => item.id === routeEventId)?.id) ||
      selectedId.value ||
      events.value[0]?.id

    if (preferredId) {
      await loadInsight(preferredId, false)
    } else {
      selectedId.value = null
      insight.value = null
    }
  } catch {
    ElMessage.error('加载工作台事件列表失败')
  } finally {
    listLoading.value = false
  }
}

watch([minScore, onlyBlocked], () => {
  void loadEvents()
})

watch(
  () => route.query.event,
  (value) => {
    const nextId = Number(value || 0)
    if (nextId && nextId !== selectedId.value) {
      void loadInsight(nextId, false)
    }
  },
)

onMounted(() => {
  void loadEvents()
})
</script>

<template>
  <section class="workbench-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">F2 Analysis Workbench</p>
        <h1>分析工作台</h1>
        <p class="subtitle">
          用于事件深度研判与证据整编，聚合攻击画像、攻击链时间线、相似事件聚类、误报学习和报告输出。
        </p>
      </div>
      <div class="header-actions">
        <el-button @click="openEventCenter">回到事件中心</el-button>
        <el-button @click="openSandbox">打开样本沙箱</el-button>
      </div>
    </header>

    <div class="workbench-layout">
      <aside class="event-sidebar">
        <div class="sidebar-toolbar">
          <el-input v-model="keyword" placeholder="搜索 IP、路径、攻击类型" clearable />
          <div class="toolbar-row">
            <el-select v-model="minScore" class="toolbar-select">
              <el-option :value="40" label="风险 >= 40" />
              <el-option :value="60" label="风险 >= 60" />
              <el-option :value="80" label="风险 >= 80" />
            </el-select>
            <el-switch v-model="onlyBlocked" inline-prompt active-text="仅拦截" inactive-text="全部" />
          </div>
        </div>

        <div v-loading="listLoading" class="event-list">
          <button
            v-for="item in filteredEvents"
            :key="item.id"
            type="button"
            class="event-item"
            :class="{ active: item.id === selectedId }"
            @click="loadInsight(item.id)"
          >
            <div class="event-item__head">
              <strong>#{{ item.id }}</strong>
              <el-tag size="small" :type="riskTagType(item.risk_score)">
                {{ item.risk_score || 0 }}
              </el-tag>
            </div>
            <div class="event-item__title">{{ item.attack_type_label || item.attack_type }}</div>
            <div class="event-item__meta">{{ item.client_ip }} · {{ item.method }} {{ item.path }}</div>
            <div class="event-item__time">{{ formatTime(item.created_at) }}</div>
          </button>
          <el-empty v-if="!listLoading && !filteredEvents.length" description="没有符合条件的事件" />
        </div>
      </aside>

      <main class="workbench-main" v-loading="detailLoading">
        <template v-if="currentItem && currentProfile && currentCluster && currentFalsePositive">
          <section class="hero-card">
            <div class="hero-main">
              <p class="hero-kicker">当前事件</p>
              <h2>#{{ currentItem.id }} {{ currentItem.attack_type_label || currentItem.attack_type }}</h2>
              <p class="hero-summary">
                {{ currentItem.method }} {{ currentItem.path }} · 来源 {{ currentItem.client_ip }} · 状态 {{ currentItem.status || 'investigating' }}
              </p>
            </div>
            <div class="hero-actions">
              <el-tag :type="riskTagType(currentItem.risk_score)">风险 {{ currentItem.risk_score || 0 }}</el-tag>
              <el-button type="primary" :loading="aiLoading" @click="runAi">AI 研判</el-button>
              <el-button :loading="exportLoading" @click="exportReport">导出报告</el-button>
            </div>
          </section>

          <div class="panel-grid">
            <section class="panel">
              <h3>攻击画像卡</h3>
              <div class="kv-grid">
                <div><span>来源 IP</span><strong>{{ currentProfile.client_ip }}</strong></div>
                <div><span>总事件数</span><strong>{{ currentProfile.total_events_from_ip }}</strong></div>
                <div><span>高风险事件</span><strong>{{ currentProfile.high_risk_events_from_ip }}</strong></div>
                <div><span>封禁事件</span><strong>{{ currentProfile.blocked_events_from_ip }}</strong></div>
                <div><span>首次出现</span><strong>{{ formatTime(currentProfile.first_seen_at) }}</strong></div>
                <div><span>最近出现</span><strong>{{ formatTime(currentProfile.last_seen_at) }}</strong></div>
              </div>
              <p class="panel-note">UA：{{ currentProfile.user_agent_sample || '-' }}</p>
              <p class="panel-note">Top 路径：{{ currentProfile.top_paths.map((item) => `${item.path} (${item.count})`).join('，') || '-' }}</p>
            </section>

            <section class="panel">
              <h3>AI 研判</h3>
              <p class="panel-note">
                模式：{{ currentItem.ai_status?.analysis_mode_label || '静态规则' }} ·
                已调用：{{ currentItem.ai_status?.llm_used ? '是' : '否' }}
              </p>
              <pre class="analysis-text">{{ currentItem.ai_analysis || '暂未生成 AI 研判结果，可手动触发或等待后台完成分析。' }}</pre>
            </section>
          </div>

          <div class="panel-grid panel-grid--wide">
            <section class="panel">
              <h3>攻击链时间线</h3>
              <div v-if="currentTimeline.length" class="timeline-list">
                <article v-for="item in currentTimeline" :key="item.id" class="timeline-item">
                  <strong>#{{ item.id }} {{ item.attack_type_label }}</strong>
                  <span>{{ formatTime(item.created_at) }}</span>
                  <p>{{ item.method }} {{ item.path }}</p>
                </article>
              </div>
              <el-empty v-else description="暂无攻击链时间线" />
            </section>

            <section class="panel">
              <h3>相似事件聚类</h3>
              <div class="kv-grid">
                <div><span>聚类总数</span><strong>{{ currentCluster.total }}</strong></div>
                <div><span>同类型</span><strong>{{ currentCluster.same_attack_type_total }}</strong></div>
                <div><span>同签名</span><strong>{{ currentCluster.same_signature_total }}</strong></div>
                <div><span>同路径</span><strong>{{ currentCluster.same_path_total }}</strong></div>
              </div>
              <p class="panel-note">{{ currentCluster.summary }}</p>
            </section>
          </div>

          <div class="panel-grid panel-grid--wide">
            <section class="panel">
              <h3>误报学习</h3>
              <p class="panel-note">命中学习样本：{{ currentFalsePositive.matched_learning_events }}</p>
              <p class="panel-note">{{ currentFalsePositive.recommendation }}</p>
              <div v-if="currentFalsePositive.signals.length" class="signal-list">
                <div v-for="signal in currentFalsePositive.signals" :key="`${signal.kind}-${signal.pattern}`" class="signal-item">
                  <strong>{{ signal.kind }}</strong>
                  <span>{{ signal.pattern }}</span>
                  <small>{{ signal.recommendation }}</small>
                </div>
              </div>
              <el-empty v-else description="当前没有误报学习信号" />
            </section>

            <section class="panel">
              <h3>命中规则链</h3>
              <div v-if="currentHits.length" class="hit-list">
                <div v-for="hit in currentHits" :key="`${hit.source_rule_id}-${hit.signature_matched}`" class="hit-item">
                  <strong>{{ hit.source_rule_name || hit.attack_type || hit.signature_matched }}</strong>
                  <span>{{ hit.source_rule_id || '-' }}</span>
                  <small>{{ hit.matched_value || hit.signature_matched }}</small>
                </div>
              </div>
              <el-empty v-else description="当前事件没有结构化规则链" />
            </section>
          </div>

          <section class="panel">
            <h3>请求包</h3>
            <pre class="packet-view">{{ currentPacket?.raw_request || currentItem.packet_preview || currentItem.body_snippet || '暂无请求包内容' }}</pre>
          </section>
        </template>

        <el-empty v-else description="请选择左侧事件进入分析工作台" />
      </main>
    </div>
  </section>
</template>

<style scoped lang="scss">
.workbench-page {
  min-height: 100%;
  padding: 28px;
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.08), transparent 24%),
    linear-gradient(180deg, #040b16, #07111f 46%, #0b1325 100%);
}

.page-header,
.hero-card,
.panel,
.event-sidebar {
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(8, 15, 28, 0.84);
  box-shadow: 0 24px 48px rgba(2, 6, 23, 0.24);
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 28px;
  margin-bottom: 18px;
}

.eyebrow {
  margin: 0 0 10px;
  color: #67e8f9;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-size: 12px;
}

.page-header h1,
.panel h3,
.hero-card h2 {
  margin: 0;
  color: #f8fafc;
}

.subtitle,
.panel-note,
.event-item__meta,
.event-item__time,
.hero-summary,
.hero-kicker {
  color: rgba(203, 213, 225, 0.8);
}

.subtitle {
  margin: 12px 0 0;
  max-width: 760px;
  line-height: 1.8;
}

.header-actions,
.hero-actions {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.workbench-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 18px;
}

.event-sidebar {
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sidebar-toolbar {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.toolbar-row {
  display: flex;
  gap: 10px;
  align-items: center;
}

.toolbar-select {
  width: 140px;
}

.event-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 420px;
}

.event-item {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(15, 23, 42, 0.76);
  border-radius: 16px;
  padding: 14px;
  text-align: left;
  cursor: pointer;
  color: #e2e8f0;
}

.event-item.active {
  border-color: rgba(56, 189, 248, 0.42);
  box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.18);
}

.event-item__head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.event-item__title {
  font-weight: 700;
  margin-bottom: 6px;
}

.workbench-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 24px;
}

.hero-kicker {
  margin: 0 0 10px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  font-size: 12px;
}

.hero-summary {
  margin: 12px 0 0;
}

.panel-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel-grid--wide {
  grid-template-columns: 1.2fr 1fr;
}

.panel {
  padding: 22px;
}

.panel h3 {
  margin-bottom: 14px;
}

.kv-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.kv-grid div {
  padding: 12px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.kv-grid span {
  display: block;
  margin-bottom: 6px;
  color: rgba(148, 163, 184, 0.8);
  font-size: 12px;
}

.kv-grid strong {
  color: #f8fafc;
}

.timeline-list,
.signal-list,
.hit-list {
  display: grid;
  gap: 10px;
}

.timeline-item,
.signal-item,
.hit-item {
  padding: 14px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.12);
  color: #e2e8f0;
}

.timeline-item strong,
.signal-item strong,
.hit-item strong {
  display: block;
  margin-bottom: 6px;
}

.timeline-item span,
.signal-item span,
.hit-item span,
.signal-item small,
.hit-item small {
  display: block;
  color: rgba(203, 213, 225, 0.78);
}

.analysis-text,
.packet-view {
  margin: 0;
  padding: 16px;
  border-radius: 16px;
  background: rgba(2, 6, 23, 0.84);
  border: 1px solid rgba(148, 163, 184, 0.12);
  color: #dbeafe;
  white-space: pre-wrap;
  line-height: 1.7;
  overflow: auto;
}

@media (max-width: 1180px) {
  .workbench-layout {
    grid-template-columns: 1fr;
  }

  .panel-grid,
  .panel-grid--wide {
    grid-template-columns: 1fr;
  }

  .page-header,
  .hero-card {
    flex-direction: column;
  }
}
</style>
