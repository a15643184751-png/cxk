<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getIDSHeatboard, getIDSStats } from '@/api/ids'
import { getUploadAuditRuntime } from '@/api/upload'

type OverviewCard = {
  label: string
  value: string | number
  note: string
}

const loading = ref(false)
const cards = ref<OverviewCard[]>([])
const attackTypes = ref<Array<{ attack_type_label: string; count: number }>>([])
const hotIps = ref<Array<{ client_ip: string; count: number }>>([])
const busyHours = ref<Array<{ hour: string; total: number; high_risk: number }>>([])
const uploadMode = ref('static_only')
const uploadModeLabel = ref('静态审计')
const generatedAt = ref('')

const quickLinks = computed(() => [
  { title: '事件中心', desc: '查看 IDS 事件列表、筛选、处置和归档', to: '/events' },
  { title: '分析工作台', desc: '进入事件验证台、攻击画像、时间线和聚类研判', to: '/workbench' },
  { title: '检测工具', desc: '执行样本送检和请求攻击检测', to: '/detection' },
  { title: '通知配置', desc: '配置邮件、企业微信、Webhook 与告警联动', to: '/notifications' },
  { title: '审计中心', desc: '查看 IDS 审计记录与关键操作留痕', to: '/audit' },
  { title: '攻击态势', desc: '查看热力看板与攻击趋势映射', to: '/situation' },
  { title: '样本沙箱', desc: '复核隔离样本、审计报告与关联事件', to: '/sandbox' },
])

async function loadOverview() {
  loading.value = true
  try {
    const [statsResponse, heatboardResponse, runtimeResponse] = await Promise.all([
      getIDSStats(),
      getIDSHeatboard(),
      getUploadAuditRuntime(),
    ])

    const stats = (statsResponse as any)?.data ?? statsResponse
    const heatboard = (heatboardResponse as any)?.data ?? heatboardResponse
    const runtime = (runtimeResponse as any)?.data ?? runtimeResponse

    uploadMode.value = runtime?.ids_upload_audit_mode || 'static_only'
    uploadModeLabel.value = runtime?.ids_upload_audit_label || '静态审计'
    generatedAt.value = heatboard?.generated_at || ''

    cards.value = [
      {
        label: '事件总量',
        value: stats?.total ?? 0,
        note: '当前纳管流量沉淀的安全事件总数',
      },
      {
        label: '已拦截事件',
        value: stats?.blocked_count ?? 0,
        note: '已触发阻断策略并进入处置闭环的攻击事件',
      },
      {
        label: '高危事件',
        value: stats?.high_risk_count ?? 0,
        note: '风险评分达到高危阈值的安全事件',
      },
      {
        label: '今日高危',
        value: heatboard?.today_high_risk_total ?? 0,
        note: '今日识别出的高危攻击数量',
      },
      {
        label: '今日拦截',
        value: heatboard?.today_blocked_total ?? 0,
        note: '今日实际执行阻断的次数',
      },
      {
        label: '送检审计模式',
        value: uploadModeLabel.value,
        note: uploadMode.value === 'llm_assisted' ? '静态规则与 AI 协同审计' : '当前运行静态规则审计',
      },
    ]

    attackTypes.value = stats?.by_type ?? []
    hotIps.value = heatboard?.hot_ips ?? []
    busyHours.value = [...(heatboard?.hourly ?? [])]
      .filter((item) => Number(item.total || 0) > 0 || Number(item.high_risk || 0) > 0)
      .sort((a, b) => Number(b.total || 0) - Number(a.total || 0))
      .slice(0, 6)
  } catch {
    ElMessage.error('IDS 总览加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadOverview()
})
</script>

<template>
  <section class="overview-page" v-loading="loading">
    <header class="overview-hero">
      <div>
        <p class="eyebrow">IDS Console</p>
        <h1>IDS 总览</h1>
        <p class="subtitle">
          统一展示 IDS 的事件态势、阻断结果、攻击分析能力与审计状态，便于快速复核当前防护效果与攻击面。
        </p>
      </div>
      <div class="hero-meta">
        <span>送检审计：{{ uploadModeLabel }}</span>
        <span>最近生成：{{ generatedAt || '--' }}</span>
      </div>
    </header>

    <div class="metric-grid">
      <article v-for="card in cards" :key="card.label" class="metric-card">
        <span class="metric-label">{{ card.label }}</span>
        <strong class="metric-value">{{ card.value }}</strong>
        <p class="metric-note">{{ card.note }}</p>
      </article>
    </div>

    <section class="quick-links">
      <div class="section-head">
        <h2>快速入口</h2>
        <p>按事件复核流程整理分析、检测、通知、审计与样本处置入口。</p>
      </div>
      <div class="quick-grid">
        <router-link v-for="item in quickLinks" :key="item.to" :to="item.to" class="quick-card">
          <span class="quick-title">{{ item.title }}</span>
          <span class="quick-desc">{{ item.desc }}</span>
        </router-link>
      </div>
    </section>

    <div class="analysis-grid">
      <section class="panel">
        <div class="section-head">
          <h2>高频攻击类型</h2>
          <p>来自当前 IDS 事件统计。</p>
        </div>
        <div v-if="attackTypes.length" class="rank-list">
          <div v-for="item in attackTypes.slice(0, 8)" :key="item.attack_type_label" class="rank-row">
            <span>{{ item.attack_type_label }}</span>
            <strong>{{ item.count }}</strong>
          </div>
        </div>
        <div v-else class="empty-state">暂无攻击类型数据</div>
      </section>

      <section class="panel">
        <div class="section-head">
          <h2>热点来源 IP</h2>
          <p>用于快速定位当前攻击来源。</p>
        </div>
        <div v-if="hotIps.length" class="rank-list">
          <div v-for="item in hotIps" :key="item.client_ip" class="rank-row">
            <span>{{ item.client_ip }}</span>
            <strong>{{ item.count }}</strong>
          </div>
        </div>
        <div v-else class="empty-state">暂无热点 IP 数据</div>
      </section>
    </div>

    <section class="panel">
      <div class="section-head">
        <h2>高峰小时段</h2>
        <p>用小时分布快速查看当前攻击峰值与拦截压力。</p>
      </div>
      <div v-if="busyHours.length" class="busy-grid">
        <article v-for="item in busyHours" :key="item.hour" class="busy-card">
          <span class="busy-hour">{{ item.hour }}:00</span>
          <strong>{{ item.total }}</strong>
          <small>高危 {{ item.high_risk }}</small>
        </article>
      </div>
      <div v-else class="empty-state">暂无高峰小时段数据</div>
    </section>
  </section>
</template>

<style scoped lang="scss">
.overview-page {
  min-height: 100%;
  padding: 28px;
  background:
    radial-gradient(circle at top left, rgba(34, 211, 238, 0.08), transparent 24%),
    linear-gradient(180deg, #040b16, #07111f 46%, #0b1325 100%);
}

.overview-hero,
.panel,
.quick-links {
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(8, 15, 28, 0.82);
  box-shadow: 0 24px 48px rgba(2, 6, 23, 0.24);
}

.overview-hero {
  display: flex;
  justify-content: space-between;
  gap: 24px;
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

.overview-hero h1,
.section-head h2 {
  margin: 0;
  color: #f8fafc;
}

.subtitle,
.section-head p,
.metric-note,
.quick-desc,
.hero-meta {
  color: rgba(203, 213, 225, 0.8);
}

.subtitle {
  margin: 12px 0 0;
  max-width: 720px;
  line-height: 1.8;
}

.hero-meta {
  min-width: 220px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}

.metric-card,
.quick-card,
.busy-card {
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(8, 15, 28, 0.86);
}

.metric-card {
  padding: 20px;
}

.metric-label {
  display: block;
  margin-bottom: 10px;
  color: rgba(148, 163, 184, 0.86);
  font-size: 13px;
}

.metric-value {
  display: block;
  margin-bottom: 10px;
  color: #f8fafc;
  font-size: 30px;
}

.quick-links,
.panel {
  padding: 24px;
}

.section-head {
  margin-bottom: 14px;
}

.quick-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.quick-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 18px;
  color: inherit;
  text-decoration: none;
}

.quick-title {
  color: #f8fafc;
  font-weight: 700;
}

.analysis-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin: 18px 0;
}

.rank-list {
  display: grid;
  gap: 10px;
}

.rank-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.12);
  color: #e2e8f0;
}

.busy-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
}

.busy-card {
  padding: 16px;
  text-align: center;
}

.busy-hour,
.busy-card small,
.empty-state {
  color: rgba(203, 213, 225, 0.76);
}

.busy-card strong {
  display: block;
  margin: 10px 0 6px;
  color: #f8fafc;
  font-size: 24px;
}

.empty-state {
  padding: 18px 0 8px;
}

@media (max-width: 1180px) {
  .overview-hero,
  .analysis-grid,
  .metric-grid,
  .quick-grid,
  .busy-grid {
    grid-template-columns: 1fr;
  }
}
</style>
