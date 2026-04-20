<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Connection,
  Lock,
  Plus,
  Search,
  WarningFilled,
} from '@element-plus/icons-vue'

import {
  addIDSBlockedIp,
  getIDSHTTPSession,
  listIDSBlockedIps,
  listIDSHTTPSessions,
  removeIDSBlockedIp,
} from '@/api/ids'
import type { IDSBlockedIPItem, IDSHTTPSessionItem } from '@/api/ids'

type ActivePane = 'request' | 'response' | 'gateway'

const loading = ref(false)
const detailLoading = ref(false)
const blocklistLoading = ref(false)
const manualBlockLoading = ref(false)
const initialized = ref(false)
const autoRefresh = ref(true)
const policyDrawerVisible = ref(false)
const activePane = ref<ActivePane>('request')

const sessions = ref<IDSHTTPSessionItem[]>([])
const blockedIps = ref<IDSBlockedIPItem[]>([])
const selectedSession = ref<IDSHTTPSessionItem | null>(null)
const total = ref(0)
const summary = ref({
  total: 0,
  blocked_count: 0,
  api_count: 0,
  frontend_count: 0,
  active_blocked_ips: 0,
})

const filters = reactive({
  client_ip: '',
  path_keyword: '',
  method: '',
  route_kind: '',
  blocked: '',
})

const manualBlockForm = reactive({
  ip: '',
  note: '',
})

const methodOptions = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
let refreshTimer: ReturnType<typeof setInterval> | null = null

const blockedIpSet = computed(() => new Set(blockedIps.value.map((item) => item.ip)))
const selectedSessionBlocked = computed(() => {
  if (!selectedSession.value) return false
  return blockedIpSet.value.has(selectedSession.value.client_ip)
})
const selectedBlockedItem = computed(() => {
  const clientIp = selectedSession.value?.client_ip
  if (!clientIp) return null
  return blockedIps.value.find((item) => item.ip === clientIp) || null
})

const summaryCards = computed(() => [
  { label: '会话总量', value: summary.value.total || total.value, tone: 'neutral' },
  { label: '已拦截', value: summary.value.blocked_count || 0, tone: 'danger' },
  { label: '接口流量', value: summary.value.api_count || 0, tone: 'accent' },
  { label: '封禁来源', value: blockedIps.value.length || summary.value.active_blocked_ips || 0, tone: 'primary' },
])

function unwrapResponse<T>(response: T | { data?: T }): T {
  return (((response as any) || {}).data ?? response) as T
}

function blockedParam() {
  if (filters.blocked === '') return undefined
  return Number(filters.blocked)
}

function formatTime(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function requestLine(session?: IDSHTTPSessionItem | null) {
  if (!session) return ''
  return `${session.method} ${session.path}${session.query_string ? `?${session.query_string}` : ''}`
}

function routeKindLabel(routeKind: string) {
  return routeKind === 'api' ? '接口' : '页面'
}

function sessionTone(session: IDSHTTPSessionItem) {
  if (session.blocked) return 'blocked'
  if (blockedIpSet.value.has(session.client_ip)) return 'policy'
  if (session.response_status >= 500) return 'danger'
  if (session.response_status >= 400) return 'warning'
  return 'ok'
}

function sessionBadge(session: IDSHTTPSessionItem) {
  if (session.attack_type === 'blocked_ip') return '封禁拒绝'
  if (session.blocked) return '已拦截'
  if (blockedIpSet.value.has(session.client_ip)) return '策略命中'
  if (session.response_status >= 400) return '异常响应'
  return '已放行'
}

function riskLabel(session: IDSHTTPSessionItem) {
  const score = Number(session.risk_score || 0)
  if (score >= 80) return '高危'
  if (score >= 60) return '中危'
  if (score > 0) return '低危'
  return '正常'
}

function requestTarget(session: IDSHTTPSessionItem) {
  const line = requestLine(session)
  return line.length > 120 ? `${line.slice(0, 117)}...` : line
}

function responseSummary(session: IDSHTTPSessionItem) {
  return `${session.response_status} · ${sessionBadge(session)}`
}

function openPolicyDrawer(prefillIp?: string) {
  manualBlockForm.ip = prefillIp || selectedSession.value?.client_ip || ''
  if (!manualBlockForm.note && selectedSession.value) {
    manualBlockForm.note = `会话 #${selectedSession.value.id} 策略标记`
  }
  policyDrawerVisible.value = true
}

async function loadBlocklist(options: { silent?: boolean } = {}) {
  if (!options.silent) blocklistLoading.value = true
  try {
    const payload = unwrapResponse(await listIDSBlockedIps())
    blockedIps.value = payload.items ?? []
    summary.value = {
      ...summary.value,
      active_blocked_ips: blockedIps.value.length,
    }
  } catch {
    if (!options.silent) ElMessage.error('封禁策略加载失败')
  } finally {
    if (!options.silent) blocklistLoading.value = false
  }
}

async function fetchSessionDetail(sessionId: number, withSpinner = true) {
  if (withSpinner) detailLoading.value = true
  try {
    selectedSession.value = unwrapResponse(await getIDSHTTPSession(sessionId))
  } catch {
    ElMessage.error('通信详情加载失败')
  } finally {
    if (withSpinner) detailLoading.value = false
  }
}

async function fetchSessions(preferredId?: number, options: { silent?: boolean } = {}) {
  if (!options.silent) loading.value = true

  try {
    const payload = unwrapResponse(
      await listIDSHTTPSessions({
        client_ip: filters.client_ip || undefined,
        path_keyword: filters.path_keyword || undefined,
        method: filters.method || undefined,
        route_kind: filters.route_kind || undefined,
        blocked: blockedParam(),
        limit: 120,
        offset: 0,
      }),
    )

    sessions.value = payload.items ?? []
    total.value = payload.total ?? sessions.value.length
    summary.value = {
      ...summary.value,
      ...(payload.summary ?? {}),
      active_blocked_ips: blockedIps.value.length || payload.summary?.active_blocked_ips || 0,
    }

    const nextId = preferredId ?? selectedSession.value?.id ?? sessions.value[0]?.id
    if (!nextId) {
      selectedSession.value = null
      return
    }

    const matched = sessions.value.find((item) => item.id === nextId)
    if (matched) {
      await fetchSessionDetail(matched.id, false)
    } else if (sessions.value[0]) {
      await fetchSessionDetail(sessions.value[0].id, false)
    } else {
      selectedSession.value = null
    }
  } catch {
    if (!options.silent) ElMessage.error('通信总览加载失败')
  } finally {
    initialized.value = true
    if (!options.silent) loading.value = false
  }
}

async function refreshAll(preferredId?: number, options: { silent?: boolean } = {}) {
  await loadBlocklist(options)
  await fetchSessions(preferredId, options)
}

function pickSession(session: IDSHTTPSessionItem) {
  void fetchSessionDetail(session.id)
}

function applyFilters() {
  void refreshAll()
}

function resetFilters() {
  filters.client_ip = ''
  filters.path_keyword = ''
  filters.method = ''
  filters.route_kind = ''
  filters.blocked = ''
  void refreshAll()
}

async function submitManualBlock() {
  const ip = manualBlockForm.ip.trim()
  if (!ip) {
    ElMessage.warning('请先输入要封禁的 IP')
    return
  }

  manualBlockLoading.value = true
  try {
    const payload = unwrapResponse(
      await addIDSBlockedIp({
        ip,
        note: manualBlockForm.note.trim() || undefined,
      }),
    )
    ElMessage.success(payload.message || 'IP 已加入封禁策略')
    manualBlockForm.note = ''
    await refreshAll(selectedSession.value?.id)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '封禁失败')
  } finally {
    manualBlockLoading.value = false
  }
}

async function unblockIp(ip: string) {
  try {
    await ElMessageBox.confirm(`确认解除 ${ip} 的封禁策略？`, '解除封禁', {
      type: 'warning',
      confirmButtonText: '确认解除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    const payload = unwrapResponse(await removeIDSBlockedIp({ ip }))
    ElMessage.success(payload.message || 'IP 已解除封禁')
    await refreshAll(selectedSession.value?.id)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '解除封禁失败')
  }
}

async function toggleSelectedIpPolicy() {
  const ip = selectedSession.value?.client_ip
  if (!ip) return

  if (blockedIpSet.value.has(ip)) {
    await unblockIp(ip)
    return
  }

  manualBlockForm.ip = ip
  manualBlockForm.note = `会话 #${selectedSession.value?.id} 手动封禁`
  await submitManualBlock()
}

function restartRefreshTimer() {
  if (refreshTimer) clearInterval(refreshTimer)
  if (!autoRefresh.value) return
  refreshTimer = setInterval(() => {
    void refreshAll(selectedSession.value?.id, { silent: true })
  }, 4000)
}

watch(autoRefresh, () => {
  restartRefreshTimer()
})

onMounted(() => {
  void refreshAll()
  restartRefreshTimer()
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<template>
  <section class="traffic-shell">
    <header class="top-panel">
      <div class="top-copy">
        <p class="eyebrow">HTTP Session Analyzer</p>
        <h1>HTTP 会话分析</h1>
        <p class="subtitle">
          以分析工作台的方式展示进入校园供应链入口的真实访问请求、接口调用和拦截处置记录。
        </p>
      </div>
    </header>

    <section class="summary-strip">
      <article
        v-for="card in summaryCards"
        :key="card.label"
        class="summary-card"
        :class="card.tone"
      >
        <span class="summary-label">{{ card.label }}</span>
        <strong class="summary-value">{{ card.value }}</strong>
      </article>
    </section>

    <section class="filter-panel">
      <el-input v-model="filters.client_ip" placeholder="来源 IP" clearable />
      <el-input v-model="filters.path_keyword" placeholder="路径关键字" clearable />
      <el-select v-model="filters.method" placeholder="请求方法" clearable>
        <el-option v-for="item in methodOptions" :key="item" :label="item" :value="item" />
      </el-select>
      <el-select v-model="filters.route_kind" placeholder="链路类型" clearable>
        <el-option label="页面链路" value="frontend" />
        <el-option label="接口链路" value="api" />
      </el-select>
      <el-select v-model="filters.blocked" placeholder="处置结果" clearable>
        <el-option label="已拦截" value="1" />
        <el-option label="已放行" value="0" />
      </el-select>
      <div class="filter-actions">
        <el-button :icon="Search" type="primary" @click="applyFilters">筛选</el-button>
        <el-button @click="resetFilters">重置</el-button>
      </div>
    </section>

    <section class="console-grid">
      <section class="cabinet-panel">
        <div class="history-frame">
          <div class="panel-head panel-head--history">
            <div>
              <h2>会话历史</h2>
              <p>采用分析工具式列表，按时序追踪入口请求和拦截结果。</p>
            </div>
            <span class="panel-count">{{ total }} records</span>
          </div>

          <div class="history-head">
            <span>时间</span>
            <span>来源</span>
            <span>方法</span>
            <span>目标</span>
            <span>类型</span>
            <span>结果</span>
          </div>

          <div class="cabinet-scroller" v-loading="loading && !initialized">
            <button
              v-for="session in sessions"
              :key="session.id"
              type="button"
              class="history-row"
              :class="[sessionTone(session), { active: selectedSession?.id === session.id }]"
              @click="pickSession(session)"
            >
              <span class="history-time">{{ formatTime(session.created_at) }}</span>
              <span class="history-source">{{ session.client_ip }}</span>
              <span class="history-method">{{ session.method }}</span>

              <div class="history-target">
                <strong>{{ requestTarget(session) }}</strong>
                <small>
                  {{ session.upstream_base || 'gateway local' }}
                  · {{ session.duration_ms }} ms
                  · {{ riskLabel(session) }}
                  <template v-if="session.attack_type">
                    · {{ session.attack_type }}
                  </template>
                </small>
              </div>

              <span class="history-kind">{{ routeKindLabel(session.route_kind) }}</span>
              <span class="history-status" :class="sessionTone(session)">
                {{ responseSummary(session) }}
              </span>
            </button>

            <div v-if="!sessions.length && !loading" class="empty-block">
              <el-icon :size="32"><Connection /></el-icon>
              <p>暂时没有会话记录，请先通过 IDS 网关访问校园供应链。</p>
            </div>
          </div>
        </div>
      </section>

      <section class="inspector-panel" v-loading="detailLoading">
        <template v-if="selectedSession">
          <div class="inspector-head">
            <div class="inspector-copy">
              <p class="inspector-line">{{ requestLine(selectedSession) }}</p>
              <div class="inspector-tags">
                <span class="chip chip--status" :class="sessionTone(selectedSession)">
                  {{ sessionBadge(selectedSession) }}
                </span>
                <span class="chip">{{ routeKindLabel(selectedSession.route_kind) }}</span>
                <span class="chip">会话 #{{ selectedSession.id }}</span>
                <span v-if="selectedSession.attack_type" class="chip chip--warn">
                  {{ selectedSession.attack_type }}
                </span>
                <span v-if="selectedSessionBlocked" class="chip chip--ban">
                  IP 已封禁
                </span>
              </div>
            </div>

            <div class="inspector-actions">
              <div class="metric-row">
                <article class="metric-chip">
                  <span>上游节点</span>
                  <strong>{{ selectedSession.upstream_base || '-' }}</strong>
                </article>
                <article class="metric-chip">
                  <span>耗时</span>
                  <strong>{{ selectedSession.duration_ms }} ms</strong>
                </article>
                <article class="metric-chip">
                  <span>响应码</span>
                  <strong>{{ selectedSession.response_status }}</strong>
                </article>
              </div>

              <div class="action-row">
                <el-button :type="selectedSessionBlocked ? 'success' : 'danger'" @click="toggleSelectedIpPolicy">
                  {{ selectedSessionBlocked ? '解除封禁' : '封禁该 IP' }}
                </el-button>
                <el-button plain @click="openPolicyDrawer(selectedSession.client_ip)">
                  查看策略
                </el-button>
              </div>
            </div>
          </div>

          <div class="segment-bar">
            <button
              type="button"
              class="segment-chip"
              :class="{ active: activePane === 'request' }"
              @click="activePane = 'request'"
            >
              Request
            </button>
            <button
              type="button"
              class="segment-chip"
              :class="{ active: activePane === 'response' }"
              @click="activePane = 'response'"
            >
              Response
            </button>
            <button
              type="button"
              class="segment-chip"
              :class="{ active: activePane === 'gateway' }"
              @click="activePane = 'gateway'"
            >
              Gateway
            </button>
          </div>

          <div v-if="activePane === 'request'" class="detail-panel">
            <div class="detail-meta">
              <span><el-icon><Connection /></el-icon> 来源地址：{{ selectedSession.client_ip }}</span>
              <span>主机：{{ selectedSession.host || '-' }}</span>
              <span>大小：{{ selectedSession.request_size }} bytes</span>
              <span>时间：{{ formatTime(selectedSession.created_at) }}</span>
            </div>
            <pre class="raw-block">{{ selectedSession.raw_request }}</pre>
          </div>

          <div v-else-if="activePane === 'response'" class="detail-panel">
            <div class="detail-meta">
              <span><el-icon><WarningFilled /></el-icon> 响应码：{{ selectedSession.response_status }}</span>
              <span>类型：{{ selectedSession.content_type || '-' }}</span>
              <span>大小：{{ selectedSession.response_size }} bytes</span>
            </div>
            <pre class="raw-block">{{ selectedSession.raw_response }}</pre>
          </div>

          <div v-else class="detail-panel">
            <div class="gateway-sheet">
              <div class="gateway-row">
                <span>转发说明</span>
                <strong>{{ selectedSession.response_note || 'proxied_by_ids_gateway' }}</strong>
              </div>
              <div class="gateway-row">
                <span>上游地址</span>
                <strong>{{ selectedSession.upstream_url || '-' }}</strong>
              </div>
              <div class="gateway-row">
                <span>风控评分</span>
                <strong>{{ selectedSession.risk_score || 0 }}</strong>
              </div>
              <div class="gateway-row">
                <span>关联事件</span>
                <strong>{{ selectedSession.incident_id || '-' }}</strong>
              </div>
              <div class="gateway-row">
                <span>来源策略</span>
                <strong>{{ selectedSessionBlocked ? '当前 IP 已命中封禁名单' : '当前 IP 未命中封禁策略' }}</strong>
              </div>
              <div class="gateway-row">
                <span>策略说明</span>
                <strong>{{ selectedBlockedItem?.note || '当前会话按实时检测规则处置' }}</strong>
              </div>
            </div>
          </div>
        </template>

        <div v-else class="empty-block empty-block--inspector">
          <el-icon :size="32"><Connection /></el-icon>
          <p>从左侧选择一条会话记录，即可查看完整数据包细节。</p>
        </div>
      </section>
    </section>

    <el-drawer
      v-model="policyDrawerVisible"
      title="IP 封禁策略"
      size="42%"
      destroy-on-close
    >
      <div class="policy-shell">
        <section class="policy-intro">
          <strong>封禁名单</strong>
          <p>命中名单的来源地址再次访问由 IDS 网关监管的站点时，会直接返回 403。</p>
        </section>

        <section class="policy-form">
          <el-input v-model="manualBlockForm.ip" placeholder="输入来源 IP，例如 10.134.32.197" clearable />
          <el-input v-model="manualBlockForm.note" placeholder="标记说明，可选填" clearable />
          <el-button type="danger" :icon="Plus" :loading="manualBlockLoading" @click="submitManualBlock">
            加入封禁
          </el-button>
        </section>

        <section class="policy-board">
          <div class="panel-head panel-head--drawer">
            <div>
              <h2>当前封禁名单</h2>
              <p>封禁来源会统一在网关入口生效。</p>
            </div>
            <span class="panel-count">{{ blockedIps.length }} 条</span>
          </div>

          <div class="policy-scroller" v-loading="blocklistLoading">
            <article v-for="item in blockedIps" :key="item.ip" class="policy-card">
              <div class="policy-card__top">
                <strong>{{ item.ip }}</strong>
                <button type="button" class="policy-remove" @click="unblockIp(item.ip)">
                  解除
                </button>
              </div>
              <div class="policy-card__meta">
                <span>来源：{{ item.source || '-' }}</span>
                <span>标记人：{{ item.actor || '-' }}</span>
              </div>
              <p class="policy-note">{{ item.note || item.last_path || '暂无额外说明' }}</p>
              <div class="policy-card__foot">
                <span>最近命中：{{ formatTime(item.last_seen_at || item.updated_at) }}</span>
                <span>最近状态：{{ item.last_status || 0 }}</span>
              </div>
            </article>

            <div v-if="!blockedIps.length && !blocklistLoading" class="empty-block empty-block--drawer">
              <el-icon :size="32"><Lock /></el-icon>
              <p>当前没有封禁 IP，点击上方按钮即可手动加入策略。</p>
            </div>
          </div>
        </section>
      </div>
    </el-drawer>
  </section>
</template>

<style scoped>
.traffic-shell {
  --panel-height: calc(100vh - 258px);
  min-height: 100%;
  padding: 18px;
  background:
    linear-gradient(180deg, #030712 0%, #050b16 48%, #050914 100%);
  color: #e5eefb;
}

.top-panel,
.filter-panel,
.cabinet-panel,
.inspector-panel {
  border: 1px solid rgba(71, 85, 105, 0.34);
  background: rgba(5, 10, 18, 0.98);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.28);
}

.top-panel {
  display: block;
  padding: 16px 18px;
  border-radius: 12px;
  margin-bottom: 10px;
}

.top-copy {
  max-width: 900px;
}

.eyebrow {
  margin: 0 0 6px;
  color: #7dd3fc;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.top-panel h1 {
  margin: 0;
  font-size: 24px;
  line-height: 1.12;
  color: #f8fbff;
}

.subtitle {
  margin: 8px 0 0;
  color: rgba(191, 219, 254, 0.72);
  line-height: 1.55;
  font-size: 13px;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 10px;
}

.summary-card {
  min-height: 84px;
  border: 1px solid rgba(71, 85, 105, 0.34);
  border-radius: 10px;
  padding: 12px 14px;
  background: linear-gradient(180deg, rgba(7, 12, 21, 0.98), rgba(5, 9, 17, 0.98));
}

.summary-card.danger {
  border-color: rgba(248, 113, 113, 0.34);
}

.summary-card.primary {
  border-color: rgba(96, 165, 250, 0.34);
}

.summary-card.accent {
  border-color: rgba(34, 211, 238, 0.3);
}

.summary-label {
  display: block;
  color: rgba(191, 219, 254, 0.72);
  font-size: 12px;
}

.summary-value {
  display: block;
  margin-top: 12px;
  font-size: 30px;
  color: #ffffff;
  line-height: 1;
}

.filter-panel {
  display: grid;
  grid-template-columns: 1fr 1.2fr 140px 150px 150px auto;
  gap: 10px;
  padding: 10px;
  border-radius: 10px;
  margin-bottom: 10px;
}

.filter-actions {
  display: flex;
  gap: 10px;
}

.console-grid {
  display: grid;
  grid-template-columns: minmax(420px, 0.96fr) minmax(560px, 1.14fr);
  gap: 10px;
  min-height: var(--panel-height);
  align-items: stretch;
}

.cabinet-panel,
.inspector-panel {
  border-radius: 12px;
  display: flex;
  flex-direction: column;
}

.cabinet-panel {
  height: var(--panel-height);
  min-height: var(--panel-height);
  border: none;
  background: transparent;
  box-shadow: none;
  overflow: hidden;
}

.inspector-panel {
  height: var(--panel-height);
  min-height: var(--panel-height);
  overflow: hidden;
}

.panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px 12px;
  border-bottom: 1px solid rgba(71, 85, 105, 0.28);
}

.panel-head h2 {
  margin: 0;
  font-size: 16px;
  color: #ffffff;
}

.panel-head p {
  margin: 6px 0 0;
  color: rgba(148, 163, 184, 0.84);
  font-size: 12px;
}

.panel-count {
  color: #93c5fd;
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}

.history-frame {
  border: 1px solid rgba(71, 85, 105, 0.32);
  border-radius: 10px;
  background: rgba(7, 12, 21, 0.94);
  overflow: hidden;
  display: flex;
  flex: 1;
  height: 100%;
  min-height: 0;
  flex-direction: column;
}

.panel-head--history {
  margin: 0;
  border-bottom: 1px solid rgba(71, 85, 105, 0.28);
  background: linear-gradient(180deg, rgba(9, 17, 29, 0.98), rgba(7, 12, 21, 0.98));
}

.history-head {
  display: grid;
  grid-template-columns: 140px 132px 74px minmax(0, 1fr) 72px 118px;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid rgba(71, 85, 105, 0.28);
  background: #0a1320;
  color: rgba(148, 163, 184, 0.84);
  font-size: 11px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.cabinet-scroller {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: rgba(5, 10, 18, 0.98);
}

.history-row {
  width: 100%;
  display: grid;
  grid-template-columns: 140px 132px 74px minmax(0, 1fr) 72px 118px;
  gap: 12px;
  align-items: center;
  padding: 12px 14px;
  border: none;
  border-bottom: 1px solid rgba(30, 41, 59, 0.88);
  background: transparent;
  color: #dbeafe;
  text-align: left;
  cursor: pointer;
  transition: background 0.14s ease, box-shadow 0.14s ease;
}

.history-row:hover {
  background: rgba(14, 165, 233, 0.06);
}

.history-row.active {
  background:
    linear-gradient(90deg, rgba(8, 145, 178, 0.16), rgba(37, 99, 235, 0.08));
  box-shadow: inset 2px 0 0 #38bdf8;
}

.history-row.blocked {
  box-shadow: inset 2px 0 0 rgba(248, 113, 113, 0.82);
}

.history-row.policy {
  box-shadow: inset 2px 0 0 rgba(251, 191, 36, 0.82);
}

.history-time,
.history-source,
.history-kind {
  color: rgba(226, 232, 240, 0.86);
  font-size: 12px;
}

.history-method {
  display: inline-flex;
  justify-content: center;
  width: fit-content;
  padding: 4px 8px;
  border-radius: 4px;
  background: rgba(14, 165, 233, 0.14);
  color: #7dd3fc;
  font-size: 12px;
  font-weight: 700;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}

.history-target {
  min-width: 0;
}

.history-target strong {
  display: block;
  color: #ffffff;
  font-size: 13px;
  line-height: 1.45;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-target small {
  display: block;
  margin-top: 4px;
  color: rgba(148, 163, 184, 0.84);
  font-size: 11px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-status {
  justify-self: end;
  display: inline-flex;
  align-items: center;
  padding: 5px 8px;
  border-radius: 4px;
  background: rgba(34, 197, 94, 0.1);
  color: #bbf7d0;
  font-size: 12px;
}

.history-status.blocked,
.history-status.danger {
  background: rgba(248, 113, 113, 0.12);
  color: #fecaca;
}

.history-status.policy,
.history-status.warning {
  background: rgba(251, 191, 36, 0.12);
  color: #fde68a;
}

.inspector-head {
  padding: 16px;
  border-bottom: 1px solid rgba(71, 85, 105, 0.28);
}

.inspector-line {
  margin: 0 0 10px;
  color: #ffffff;
  font-size: 18px;
  line-height: 1.5;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}

.inspector-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border: 1px solid rgba(71, 85, 105, 0.34);
  border-radius: 4px;
  background: #09111d;
  color: #dbeafe;
  font-size: 12px;
}

.chip--status.ok {
  color: #bbf7d0;
}

.chip--status.blocked,
.chip--ban {
  color: #fecaca;
  border-color: rgba(248, 113, 113, 0.34);
}

.chip--status.policy,
.chip--status.warning,
.chip--status.danger,
.chip--warn {
  color: #fde68a;
  border-color: rgba(251, 191, 36, 0.28);
}

.inspector-actions {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.metric-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.metric-chip {
  padding: 12px 14px;
  border: 1px solid rgba(71, 85, 105, 0.34);
  border-radius: 8px;
  background: #08111d;
}

.metric-chip span {
  display: block;
  color: rgba(148, 163, 184, 0.82);
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.metric-chip strong {
  display: block;
  margin-top: 6px;
  color: #ffffff;
  line-height: 1.45;
  font-size: 14px;
  word-break: break-all;
}

.action-row {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.segment-bar {
  display: flex;
  gap: 6px;
  padding: 10px 16px 0;
}

.segment-chip {
  appearance: none;
  border: 1px solid rgba(71, 85, 105, 0.34);
  border-bottom: none;
  border-radius: 6px 6px 0 0;
  padding: 8px 12px;
  background: #08111d;
  color: rgba(191, 219, 254, 0.8);
  cursor: pointer;
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}

.segment-chip.active {
  background: #0b1624;
  color: #ffffff;
  border-color: rgba(56, 189, 248, 0.34);
}

.detail-panel {
  padding: 0 16px 16px;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.detail-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  padding: 12px 0;
  color: rgba(191, 219, 254, 0.9);
  font-size: 12px;
  border-bottom: 1px solid rgba(71, 85, 105, 0.28);
}

.detail-meta span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.raw-block {
  margin: 0;
  flex: 1;
  min-height: 0;
  overflow: auto;
  padding: 16px;
  border-radius: 0 8px 8px 8px;
  border: 1px solid rgba(71, 85, 105, 0.34);
  background:
    linear-gradient(180deg, rgba(7, 12, 21, 0.98), rgba(5, 9, 16, 0.98)),
    repeating-linear-gradient(
      180deg,
      rgba(148, 163, 184, 0.05),
      rgba(148, 163, 184, 0.05) 1px,
      transparent 1px,
      transparent 26px
    );
  color: #f1f5f9;
  font-size: 13px;
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
}

.gateway-sheet {
  border: 1px solid rgba(71, 85, 105, 0.34);
  border-radius: 0 8px 8px 8px;
  overflow: hidden;
  margin-top: 0;
}

.gateway-row {
  display: grid;
  grid-template-columns: 160px minmax(0, 1fr);
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid rgba(30, 41, 59, 0.88);
  background: rgba(7, 12, 21, 0.98);
}

.gateway-row:last-child {
  border-bottom: none;
}

.gateway-row span {
  color: rgba(148, 163, 184, 0.84);
  font-size: 12px;
}

.gateway-row strong {
  color: #ffffff;
  font-size: 13px;
  line-height: 1.6;
  word-break: break-word;
}

.empty-block {
  min-height: 240px;
  display: grid;
  place-items: center;
  gap: 12px;
  padding: 24px;
  text-align: center;
  color: rgba(191, 219, 254, 0.86);
}

.empty-block--inspector {
  min-height: 100%;
  flex: 1;
}

.policy-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding-bottom: 8px;
}

.policy-intro,
.policy-board {
  border: 1px solid rgba(71, 85, 105, 0.34);
  border-radius: 10px;
  background: rgba(7, 12, 21, 0.98);
}

.policy-intro {
  padding: 16px;
}

.policy-intro strong {
  display: block;
  color: #ffffff;
  font-size: 15px;
}

.policy-intro p {
  margin: 8px 0 0;
  color: rgba(191, 219, 254, 0.78);
  line-height: 1.6;
  font-size: 13px;
}

.policy-form {
  display: grid;
  grid-template-columns: 1.1fr 1.4fr auto;
  gap: 10px;
}

.panel-head--drawer {
  padding-bottom: 12px;
}

.policy-scroller {
  max-height: calc(100vh - 320px);
  overflow-y: auto;
  padding: 0 16px 16px;
  display: grid;
  gap: 10px;
}

.policy-card {
  padding: 14px;
  border: 1px solid rgba(71, 85, 105, 0.34);
  border-radius: 8px;
  background: #08111d;
}

.policy-card__top,
.policy-card__meta,
.policy-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.policy-card strong {
  color: #ffffff;
  font-size: 15px;
}

.policy-remove {
  appearance: none;
  border: none;
  border-radius: 4px;
  padding: 6px 10px;
  background: rgba(239, 68, 68, 0.16);
  color: #fecaca;
  cursor: pointer;
}

.policy-card__meta,
.policy-card__foot {
  margin-top: 10px;
  color: rgba(191, 219, 254, 0.84);
  font-size: 12px;
}

.policy-note {
  margin: 10px 0 0;
  color: #f8fafc;
  line-height: 1.6;
  font-size: 13px;
}

.empty-block--drawer {
  min-height: 220px;
}

:deep(.el-input__wrapper),
:deep(.el-select__wrapper) {
  background: #09111d;
  box-shadow: inset 0 0 0 1px rgba(71, 85, 105, 0.34);
}

:deep(.el-input__wrapper.is-focus),
:deep(.el-select__wrapper.is-focused) {
  box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.38);
}

:deep(.el-input__inner),
:deep(.el-select__selected-item) {
  color: #eef4ff;
}

:deep(.el-input__inner::placeholder),
:deep(.el-input__wrapper input::placeholder),
:deep(.el-select__placeholder) {
  color: rgba(226, 232, 240, 0.76) !important;
}

:deep(.el-button),
:deep(.el-drawer__title),
:deep(.el-switch__label) {
  color: inherit;
}

:deep(.el-drawer) {
  background: linear-gradient(180deg, #040914, #09111d 52%, #07101b);
}

:deep(.el-drawer__header) {
  margin-bottom: 0;
  padding: 18px 20px 14px;
  border-bottom: 1px solid rgba(71, 85, 105, 0.34);
  color: #ffffff;
}

:deep(.el-drawer__headerbtn .el-drawer__close-btn) {
  color: rgba(226, 232, 240, 0.92);
}

:deep(.el-drawer__body) {
  padding: 16px 20px 20px;
  background: transparent;
}

:deep(.el-overlay) {
  backdrop-filter: blur(8px);
}

@media (max-width: 1480px) {
  .summary-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .filter-panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .console-grid {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .traffic-shell {
    --panel-height: 560px;
  }

  .cabinet-panel,
  .inspector-panel {
    height: var(--panel-height);
    min-height: var(--panel-height);
  }

  .history-head,
  .history-row {
    grid-template-columns: 132px 122px 70px minmax(0, 1fr) 64px 108px;
  }
}

@media (max-width: 1100px) {
  .traffic-shell {
    padding: 14px;
  }

  .top-panel {
    display: block;
  }

  .action-row {
    flex-wrap: wrap;
  }

  .metric-row {
    grid-template-columns: 1fr;
  }

  .policy-form {
    grid-template-columns: 1fr;
  }
}
</style>
