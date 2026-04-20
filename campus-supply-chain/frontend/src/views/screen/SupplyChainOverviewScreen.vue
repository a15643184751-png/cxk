<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { isIdsSecurityCenterPath, openIdsSecurityCenter } from '@/utils/openIdsSecurityCenter'

const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false })
import { getSupplyChainOverviewScreen } from '@/api/dashboard'
import type { SupplyChainOverviewScreenData } from '@/api/dashboard'

const router = useRouter()
const loading = ref(true)
const data = ref<SupplyChainOverviewScreenData | null>(null)
const now = ref(new Date())

let refreshTimer: ReturnType<typeof setInterval> | null = null
let clockTimer: ReturnType<typeof setInterval> | null = null

const attackTypeLabel: Record<string, string> = {
  sql_injection: '\u0053\u0051\u004c\u0020\u6ce8\u5165',
  xss: 'XSS',
  path_traversal: '\u8def\u5f84\u904d\u5386',
  cmd_injection: '\u547d\u4ee4\u6ce8\u5165',
  scanner: '\u626b\u63cf\u63a2\u6d4b',
  malformed: '\u7578\u5f62\u8bf7\u6c42',
  jndi_injection: 'JNDI/Log4j',
  prototype_pollution: '\u539f\u578b\u94fe\u6c61\u67d3',
}

const TXT = {
  title: '\u6821\u56ed\u4f9b\u5e94\u94fe\u5168\u666f\u5927\u5c4f',
  subtitle:
    '\u91c7\u8d2d \u2192 \u4ed3\u50a8 \u2192 \u914d\u9001 \u2192 \u6eaf\u6e90 \u2192 \u9884\u8b66 \u2192 \u5b89\u5168\u76d1\u6d4b',
  refresh: '\u6bcf 30 \u79d2\u5237\u65b0',
  unknown: '\u672a\u77e5\u7c7b\u578b',
  urgent: '\u7d27\u6025',
  focus: '\u5173\u6ce8',
  remind: '\u63d0\u9192',
  pipelineTitle: '\u4f9b\u5e94\u94fe\u95ed\u73af\u6d41\u7a0b',
  activeNodes: '\u6d3b\u8dc3\u8282\u70b9',
  riskTitle: '\u98ce\u9669\u6001\u52bf',
  pendingWarn: '\u5f85\u5904\u7406\u9884\u8b66',
  idsToday: '\u4eca\u65e5 IDS \u4e8b\u4ef6',
  blockedTotal: '\u7d2f\u8ba1\u62e6\u622a',
  noWarn: '\u6682\u65e0\u9884\u8b66',
  realtimeSec: '\u5b9e\u65f6\u5b89\u5168\u4e8b\u4ef6',
  blocked: '\u5df2\u62e6\u622a',
  recorded: '\u5df2\u8bb0\u5f55',
  noSec: '\u6682\u65e0\u5b89\u5168\u4e8b\u4ef6',
  latestFlow: '\u6700\u65b0\u4e1a\u52a1\u95ed\u73af\u8fdb\u5ea6',
  noOrders: '\u6682\u65e0\u8ba2\u5355',
  fallback:
    '\u6570\u636e\u83b7\u53d6\u5931\u8d25\uff0c\u8bf7\u786e\u8ba4\u540e\u7aef\u5df2\u542f\u52a8\u5e76\u5df2\u767b\u5f55',
} as const

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

const activeNodeCount = computed(() => {
  return (data.value?.pipeline || []).filter((item) => item.count > 0).length
})

async function load() {
  try {
    const res: unknown = await getSupplyChainOverviewScreen()
    const body = res && typeof res === 'object' && 'data' in (res as object)
      ? (res as { data: SupplyChainOverviewScreenData }).data
      : (res as SupplyChainOverviewScreenData)
    data.value = body ?? null
  } catch {
    data.value = null
  } finally {
    loading.value = false
  }
}

function goTo(path: string) {
  if (isIdsSecurityCenterPath(path)) {
    void openIdsSecurityCenter()
    return
  }
  router.push(path)
}

function toAttackLabel(type: string) {
  return attackTypeLabel[type] || type || TXT.unknown
}

function levelText(level: string) {
  if (level === 'high') return TXT.urgent
  if (level === 'medium') return TXT.focus
  return TXT.remind
}

onMounted(() => {
  load()
  refreshTimer = setInterval(load, 30000)
  clockTimer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onUnmounted(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<template>
  <div class="overview-screen" :class="{ 'is-embedded': props.embedded }" v-loading="loading">
    <div v-if="!props.embedded" class="bg-layer">
      <div class="bg-grid" />
      <div class="bg-halo" />
    </div>

    <header v-if="!props.embedded" class="header">
      <div class="title-wrap">
        <h1>{{ TXT.title }}</h1>
        <p>{{ TXT.subtitle }}</p>
      </div>
      <div class="meta-wrap">
        <span class="clock">{{ formattedTime }}</span>
        <span class="refresh">{{ TXT.refresh }}</span>
      </div>
    </header>

    <template v-if="data">
      <section class="stats-grid">
        <div
          v-for="(item, i) in data.stats"
          :key="i"
          class="stat-card"
          :class="item.accent"
          @click="goTo(item.path)"
        >
          <div class="stat-value">{{ item.value }}</div>
          <div class="stat-title">{{ item.title }}</div>
        </div>
      </section>

      <section class="pipeline-panel panel">
        <div class="panel-head">
          <span class="panel-title">{{ TXT.pipelineTitle }}</span>
          <span class="panel-sub">{{ TXT.activeNodes }} {{ activeNodeCount }} / {{ data.pipeline.length }}</span>
        </div>
        <div class="pipeline-wrap">
          <template v-for="(node, i) in data.pipeline" :key="node.key">
            <div
              class="pipeline-node"
              :class="{ active: node.count > 0, done: node.done }"
              @click="goTo(node.targetPath)"
            >
              <div class="node-title">{{ node.title }}</div>
              <div class="node-subtitle">{{ node.subtitle }}</div>
              <div class="node-count">{{ node.count }}</div>
            </div>
            <div v-if="i < data.pipeline.length - 1" class="pipeline-link" />
          </template>
        </div>
      </section>

      <section class="content-grid">
        <div class="panel">
          <div class="panel-head">
            <span class="panel-title">{{ TXT.riskTitle }}</span>
          </div>
          <div class="risk-metrics">
            <div class="risk-metric danger">
              <span class="label">{{ TXT.pendingWarn }}</span>
              <span class="value">{{ data.risk.warningPending }}</span>
            </div>
            <div class="risk-metric warning">
              <span class="label">{{ TXT.idsToday }}</span>
              <span class="value">{{ data.risk.idsToday }}</span>
            </div>
            <div class="risk-metric info">
              <span class="label">{{ TXT.blockedTotal }}</span>
              <span class="value">{{ data.risk.idsBlocked }}</span>
            </div>
          </div>
          <div class="risk-list">
            <div
              v-for="w in data.risk.recentWarnings"
              :key="`w-${w.id}`"
              class="risk-row"
              @click="goTo('/warning')"
            >
              <span class="tag" :class="w.level">{{ levelText(w.level) }}</span>
              <span class="txt">{{ w.material }}</span>
              <span class="desc">{{ w.desc || '-' }}</span>
            </div>
            <div v-if="!data.risk.recentWarnings.length" class="empty">{{ TXT.noWarn }}</div>
          </div>
        </div>

        <div class="panel">
          <div class="panel-head">
            <span class="panel-title">{{ TXT.realtimeSec }}</span>
          </div>
          <div class="event-list">
            <div
              v-for="e in data.risk.recentEvents"
              :key="`e-${e.id}`"
              class="event-row"
              @click="goTo('/security')"
            >
              <span class="event-type">{{ toAttackLabel(e.attack_type) }}</span>
              <span class="event-ip">{{ e.client_ip }}</span>
              <span class="event-path">{{ e.path }}</span>
              <span class="event-badge" :class="{ blocked: e.blocked === 1 }">
                {{ e.blocked === 1 ? TXT.blocked : TXT.recorded }}
              </span>
            </div>
            <div v-if="!data.risk.recentEvents.length" class="empty">{{ TXT.noSec }}</div>
          </div>
        </div>
      </section>

      <section class="panel order-panel">
        <div class="panel-head">
          <span class="panel-title">{{ TXT.latestFlow }}</span>
        </div>
        <div class="order-list">
          <div v-for="o in data.recentOrders" :key="o.id" class="order-row" @click="goTo('/purchase')">
            <span class="order-no">{{ o.order_no }}</span>
            <span class="order-status">{{ o.status_label }}</span>
            <span class="order-dest">{{ o.receiver_name }} &middot; {{ o.destination }}</span>
          </div>
          <div v-if="!data.recentOrders.length" class="empty">{{ TXT.noOrders }}</div>
        </div>
      </section>
    </template>

    <div v-else class="fallback">{{ TXT.fallback }}</div>
  </div>
</template>

<style scoped lang="scss">
.overview-screen {
  min-height: calc(100vh - 64px);
  padding: 20px 24px 28px;
  &.is-embedded {
    min-height: 520px;
    padding: 12px 0 20px;
  }
  color: #334155;
  position: relative;
  background:
    radial-gradient(1100px 360px at -12% -22%, rgba(139, 92, 246, 0.14), transparent 62%),
    radial-gradient(920px 340px at 110% -10%, rgba(76, 136, 255, 0.12), transparent 62%),
    linear-gradient(180deg, #f8f9ff 0%, #eef2ff 100%);
}

.bg-layer {
  pointer-events: none;
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.bg-grid {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(var(--screen-grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--screen-grid) 1px, transparent 1px);
  background-size: 26px 26px;
}

.bg-halo {
  position: absolute;
  width: 600px;
  height: 600px;
  right: -180px;
  top: -180px;
  border-radius: 50%;
  background: radial-gradient(circle, var(--screen-glow) 0%, transparent 68%);
}

.header {
  position: relative;
  z-index: 1;
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.title-wrap h1 {
  margin: 0;
  font-size: 30px;
  font-weight: 700;
  letter-spacing: 0.4px;
  color: #3b4ac8;
}

.title-wrap p {
  margin: 6px 0 0;
  color: #64759e;
  font-size: 13px;
}

.meta-wrap {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
}

.clock {
  font-size: 16px;
  color: #4d5dce;
}

.refresh {
  font-size: 12px;
  color: #7c8db1;
}

.panel {
  position: relative;
  z-index: 1;
  border: 1px solid #dde3ff;
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff 0%, #f7f9ff 100%);
}

.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  border-bottom: 1px solid #e6ebff;
}

.panel-title {
  font-weight: 700;
  color: #3f4fcb;
}

.panel-sub {
  color: #6a7bb0;
  font-size: 12px;
}

.stats-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.stat-card {
  border-radius: 10px;
  padding: 12px;
  cursor: pointer;
  border: 1px solid #e0e6ff;
  background: linear-gradient(180deg, #ffffff 0%, #f7f9ff 100%);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 10px 24px rgba(107, 110, 255, 0.12);
    border-color: rgba(107, 110, 255, 0.34);
  }

  &.blue { border-color: rgba(129, 140, 248, 0.4); }
  &.cyan { border-color: rgba(45, 212, 191, 0.35); }
  &.violet { border-color: rgba(167, 139, 250, 0.38); }
  &.emerald { border-color: rgba(52, 211, 153, 0.38); }
  &.amber { border-color: rgba(251, 191, 36, 0.4); }
  &.orange { border-color: rgba(251, 146, 60, 0.38); }
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  color: #4656d6;
  line-height: 1.1;
}

.stat-title {
  margin-top: 4px;
  color: #7382a8;
  font-size: 13px;
}

.pipeline-panel {
  margin-bottom: 12px;
}

.pipeline-wrap {
  padding: 14px;
  display: flex;
  align-items: center;
}

.pipeline-node {
  width: 180px;
  min-height: 118px;
  border-radius: 10px;
  border: 1px solid #dfe5ff;
  background: linear-gradient(180deg, #ffffff 0%, #f8faff 100%);
  padding: 10px;
  cursor: pointer;
  transition: all 0.2s ease;

  &:hover {
    border-color: rgba(107, 110, 255, 0.42);
    transform: translateY(-2px);
  }

  &.active {
    border-color: rgba(107, 110, 255, 0.72);
    box-shadow: 0 0 0 1px rgba(107, 110, 255, 0.14) inset;
  }

  &.done {
    border-color: rgba(52, 211, 153, 0.65);
  }
}

.node-title {
  font-weight: 700;
  color: #3f4fcb;
}

.node-subtitle {
  margin-top: 6px;
  color: #7583a8;
  font-size: 12px;
  min-height: 32px;
}

.node-count {
  margin-top: 12px;
  font-size: 30px;
  font-weight: 700;
  color: #4c5dd0;
}

.pipeline-link {
  flex: 1;
  height: 2px;
  margin: 0 8px;
  background: linear-gradient(
    90deg,
    rgba(107, 110, 255, 0.14),
    rgba(107, 110, 255, 0.5),
    rgba(107, 110, 255, 0.14)
  );
}

.content-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 12px;
}

.risk-metrics {
  padding: 12px 14px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.risk-metric {
  border-radius: 8px;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 6px;

  .label {
    color: #7583a8;
    font-size: 12px;
  }

  .value {
    font-size: 24px;
    font-weight: 700;
  }

  &.danger { background: rgba(239, 68, 68, 0.1); color: #b91c1c; }
  &.warning { background: rgba(245, 158, 11, 0.12); color: #b45309; }
  &.info { background: rgba(76, 136, 255, 0.12); color: #1d4ed8; }
}

.risk-list,
.event-list,
.order-list {
  padding: 0 14px 12px;
}

.risk-row,
.event-row,
.order-row {
  display: grid;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px dashed #dce4ff;
  cursor: pointer;

  &:hover {
    background: rgba(107, 110, 255, 0.05);
  }
}

.risk-row {
  grid-template-columns: 56px 120px 1fr;
}

.tag {
  text-align: center;
  border-radius: 999px;
  padding: 2px 6px;
  font-size: 12px;

  &.high { background: rgba(239, 68, 68, 0.12); color: #b91c1c; }
  &.medium { background: rgba(245, 158, 11, 0.14); color: #b45309; }
  &.low { background: rgba(59, 130, 246, 0.14); color: #1d4ed8; }
}

.txt {
  color: #334155;
  font-weight: 600;
}

.desc {
  color: #7382a8;
}

.event-row {
  grid-template-columns: 110px 132px 1fr 72px;
}

.event-type,
.event-ip,
.event-path {
  color: #4b5a82;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-badge {
  text-align: center;
  border-radius: 999px;
  padding: 2px 6px;
  font-size: 12px;
  background: rgba(76, 136, 255, 0.14);
  color: #1d4ed8;

  &.blocked {
    background: rgba(239, 68, 68, 0.12);
    color: #b91c1c;
  }
}

.order-row {
  grid-template-columns: 150px 110px 1fr;
}

.order-no,
.order-status,
.order-dest {
  color: #4b5a82;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty {
  text-align: center;
  color: #8d9abc;
  padding: 14px 0;
}

.fallback {
  text-align: center;
  margin-top: 120px;
  color: #8d9abc;
}

@media (max-width: 1600px) {
  .stats-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .pipeline-wrap {
    overflow-x: auto;
    gap: 8px;
  }

  .pipeline-link {
    width: 28px;
    min-width: 28px;
    flex: 0 0 28px;
  }
}
</style>
