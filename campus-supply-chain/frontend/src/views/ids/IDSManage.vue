<script setup lang="ts">
import { ref, onMounted, watch, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { chartEnterAnimation, chartPieSectorEnter, chartBarGrowSeries } from '@/utils/chartAnimation'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listIDSEvents, getIDSStats, getIDSTrend, archiveIDSEvent, archiveIDSBatch } from '@/api/ids'
import type { IDSEventItem } from '@/api/ids'

const loading = ref(false)
const trendDays = ref(7)
const trendData = ref<{ dates: string[]; counts: number[] }>({ dates: [], counts: [] })
const stats = ref<{ total: number; blocked_count: number; by_type: { attack_type: string; attack_type_label: string; count: number }[] } | null>(null)
const tableData = ref<IDSEventItem[]>([])
const total = ref(0)
const attackTypeFilter = ref('')
const clientIpFilter = ref('')
const blockedFilter = ref<number | undefined>(undefined)
const archivedFilter = ref<number | undefined>(undefined)
const pageSize = ref(20)
const pageOffset = ref(0)
const selectedIds = ref<number[]>([])
const detailVisible = ref(false)
const currentRow = ref<IDSEventItem | null>(null)

async function fetchStats() {
  try {
    const res: any = await getIDSStats()
    stats.value = res?.data ?? res
    renderPieChart()
  } catch {
    stats.value = null
  }
}

async function fetchTrend() {
  try {
    const res: any = await getIDSTrend(trendDays.value)
    trendData.value = res?.data ?? res ?? { dates: [], counts: [] }
    renderTrendChart()
  } catch {
    trendData.value = { dates: [], counts: [] }
  }
}

let pieChartInstance: echarts.ECharts | null = null
let trendChartInstance: echarts.ECharts | null = null

const PIE_COLORS = ['#e34d59', '#f59a23', '#ffb547', '#00b42a', '#165dff', '#722ed1']

function renderPieChart() {
  const el = document.getElementById('ids-pie-chart')
  if (!el || !stats.value?.by_type?.length) return
  if (!pieChartInstance) pieChartInstance = echarts.init(el)
  pieChartInstance.setOption({
    ...chartEnterAnimation,
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    color: PIE_COLORS,
    series: [{
      type: 'pie',
      ...chartPieSectorEnter,
      radius: ['45%', '70%'],
      center: ['50%', '50%'],
      data: stats.value.by_type.map((t: { attack_type_label: string; count: number }) => ({
        name: t.attack_type_label,
        value: t.count,
      })),
      label: { fontSize: 11 },
      emphasis: { itemStyle: { shadowBlur: 10, shadowOffsetX: 0, shadowColor: 'rgba(0,0,0,0.3)' } },
    }],
  })
}

function renderTrendChart() {
  const el = document.getElementById('ids-trend-chart')
  if (!el) return
  if (!trendChartInstance) trendChartInstance = echarts.init(el)
  const { dates, counts } = trendData.value
  trendChartInstance.setOption({
    ...chartEnterAnimation,
    tooltip: { trigger: 'axis' },
    grid: { left: 48, right: 24, top: 24, bottom: 36 },
    xAxis: {
      type: 'category',
      data: dates?.length ? dates.map((d: string) => d.slice(5)) : [],
      axisLine: { lineStyle: { color: '#e5e6eb' } },
      axisLabel: { color: '#86909c', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#e5e6eb', type: 'dashed' } },
      axisLabel: { color: '#86909c', fontSize: 11 },
    },
    series: [{
      type: 'bar',
      data: counts ?? [],
      ...chartBarGrowSeries,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#165dff' },
          { offset: 1, color: '#4080ff' },
        ]),
      },
    }],
  })
}

function handleResize() {
  pieChartInstance?.resize()
  trendChartInstance?.resize()
}

async function fetchData() {
  loading.value = true
  try {
    const res: any = await listIDSEvents({
      attack_type: attackTypeFilter.value || undefined,
      client_ip: clientIpFilter.value || undefined,
      blocked: blockedFilter.value,
      archived: archivedFilter.value,
      limit: pageSize.value,
      offset: pageOffset.value,
    })
    const data = res?.data ?? res
    tableData.value = data?.items ?? []
    total.value = data?.total ?? 0
  } catch {
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  pageOffset.value = 0
  fetchData()
}

async function handleArchive(row: IDSEventItem) {
  try {
    await archiveIDSEvent(row.id)
    ElMessage.success('已归档')
    fetchData()
    fetchStats()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '归档失败')
  }
}

async function handleBatchArchive() {
  if (!selectedIds.value.length) {
    ElMessage.warning('请选择要归档的事件')
    return
  }
  try {
    await ElMessageBox.confirm(`确定归档选中的 ${selectedIds.value.length} 条记录？`, '批量归档')
    await archiveIDSBatch(selectedIds.value)
    ElMessage.success('批量归档成功')
    selectedIds.value = []
    fetchData()
    fetchStats()
  } catch (e: any) {
    if (e !== 'cancel') ElMessage.error(e?.response?.data?.detail || e?.message || '归档失败')
  }
}

function handleSelectionChange(rows: IDSEventItem[]) {
  selectedIds.value = rows.map((r) => r.id)
}

function showDetail(row: IDSEventItem) {
  currentRow.value = row
  detailVisible.value = true
}

onMounted(() => {
  fetchStats()
  fetchTrend()
  fetchData()
  window.addEventListener('resize', handleResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  pieChartInstance?.dispose()
  trendChartInstance?.dispose()
})
watch([pageOffset, pageSize], fetchData)
watch(trendDays, () => fetchTrend())
</script>

<template>
  <div class="page">
    <div class="page-header">
      <h2>IDS 入侵检测</h2>
      <p class="page-desc">抓包解析 HTTP、特征匹配、攻击识别、留痕封禁、归档管理</p>
    </div>

    <div v-if="stats" class="stats-row">
      <div class="stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">检测事件总数</div>
      </div>
      <div class="stat-card danger">
        <div class="stat-value">{{ stats.blocked_count }}</div>
        <div class="stat-label">已封禁 IP</div>
      </div>
      <div v-for="t in stats.by_type" :key="t.attack_type" class="stat-card small">
        <div class="stat-value">{{ t.count }}</div>
        <div class="stat-label">{{ t.attack_type_label }}</div>
      </div>
    </div>

    <div class="chart-row">
      <div class="chart-card">
        <div class="chart-title">攻击类型分布</div>
        <div id="ids-pie-chart" class="chart-arena" />
      </div>
      <div class="chart-card chart-card-wide">
        <div class="chart-title">
          事件趋势
          <el-select v-model="trendDays" size="small" style="width: 90px; margin-left: 8px">
            <el-option label="近7天" :value="7" />
            <el-option label="近14天" :value="14" />
            <el-option label="近30天" :value="30" />
          </el-select>
        </div>
        <div id="ids-trend-chart" class="chart-arena" />
      </div>
    </div>

    <div class="filter-bar">
      <el-input v-model="clientIpFilter" placeholder="来源 IP" clearable style="width: 140px" />
      <el-select v-model="attackTypeFilter" placeholder="攻击类型" clearable style="width: 140px">
        <el-option label="SQL 注入" value="sql_injection" />
        <el-option label="XSS" value="xss" />
        <el-option label="路径遍历" value="path_traversal" />
        <el-option label="命令注入" value="cmd_injection" />
        <el-option label="扫描器" value="scanner" />
        <el-option label="畸形请求" value="malformed" />
      </el-select>
      <el-select v-model="blockedFilter" placeholder="封禁状态" clearable style="width: 120px">
        <el-option label="已封禁" :value="1" />
        <el-option label="仅记录" :value="0" />
      </el-select>
      <el-select v-model="archivedFilter" placeholder="归档状态" clearable style="width: 120px">
        <el-option label="未归档" :value="0" />
        <el-option label="已归档" :value="1" />
      </el-select>
      <el-button type="primary" @click="handleSearch">查询</el-button>
      <el-button type="success" :disabled="!selectedIds.length" @click="handleBatchArchive">
        批量归档 ({{ selectedIds.length }})
      </el-button>
    </div>

    <div class="table-card">
      <el-table
        :data="tableData"
        v-loading="loading"
        stripe
        style="width: 100%"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="45" />
        <el-table-column prop="created_at" label="时间" width="170" />
        <el-table-column prop="client_ip" label="来源 IP" width="130" />
        <el-table-column prop="attack_type_label" label="攻击类型" width="120">
          <template #default="{ row }">
            <el-tag :type="row.attack_type === 'sql_injection' ? 'danger' : 'warning'" size="small">
              {{ row.attack_type_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="method" label="方法" width="70" />
        <el-table-column prop="path" label="路径" min-width="180" show-overflow-tooltip />
        <el-table-column prop="blocked" label="封禁" width="70">
          <template #default="{ row }">
            <el-tag :type="row.blocked ? 'success' : 'info'" size="small">
              {{ row.blocked ? '已封禁' : '仅记录' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="firewall_rule" label="防火墙规则" width="140" show-overflow-tooltip />
        <el-table-column prop="archived" label="归档" width="70">
          <template #default="{ row }">{{ row.archived ? '已归档' : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="showDetail(row)">查看</el-button>
            <el-button v-if="!row.archived" link type="success" size="small" @click="handleArchive(row)">
              归档
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        :current-page="Math.floor(pageOffset / pageSize) + 1"
        @current-change="(p: number) => { pageOffset = (p - 1) * pageSize; fetchData() }"
      />
    </div>

    <el-drawer v-model="detailVisible" title="事件详情" size="480">
      <template v-if="currentRow">
        <p><strong>时间：</strong>{{ currentRow.created_at }}</p>
        <p><strong>来源 IP：</strong>{{ currentRow.client_ip }}</p>
        <p><strong>攻击类型：</strong>{{ currentRow.attack_type_label }}</p>
        <p><strong>匹配特征：</strong>{{ currentRow.signature_matched }}</p>
        <p><strong>方法：</strong>{{ currentRow.method }}</p>
        <p><strong>路径：</strong>{{ currentRow.path }}</p>
        <p><strong>Query 片段：</strong>{{ currentRow.query_snippet || '-' }}</p>
        <p><strong>Body 片段：</strong>{{ currentRow.body_snippet || '-' }}</p>
        <p><strong>User-Agent：</strong>{{ currentRow.user_agent || '-' }}</p>
        <p><strong>封禁：</strong>{{ currentRow.blocked ? '是' : '否' }}</p>
        <p><strong>防火墙规则：</strong>{{ currentRow.firewall_rule || '-' }}</p>
      </template>
    </el-drawer>
  </div>
</template>

<style lang="scss" scoped>
.page { padding: 0; }
.page-header { margin-bottom: 20px; }
.page-header h2 { margin: 0 0 6px; font-size: 18px; font-weight: 600; }
.page-desc { margin: 0; font-size: 13px; color: var(--text-muted); }

.stats-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 20px;
}
.stat-card {
  padding: 16px 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  min-width: 120px;
  &.danger .stat-value { color: var(--el-color-danger); }
  &.small .stat-value { font-size: 20px; }
}
.stat-value { font-size: 28px; font-weight: 700; color: var(--primary); }
.stat-label { font-size: 12px; color: var(--text-muted); margin-top: 4px; }

.chart-row {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
  margin-bottom: 20px;
}
.chart-card {
  flex: 0 0 320px;
  padding: 20px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  &.chart-card-wide { flex: 1; min-width: 360px; }
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  display: flex;
  align-items: center;
}
.chart-arena { height: 220px; }

.filter-bar { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
.table-card {
  padding: 20px;
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-subtle);
}
.table-card :deep(.el-pagination) { margin-top: 16px; }
</style>
