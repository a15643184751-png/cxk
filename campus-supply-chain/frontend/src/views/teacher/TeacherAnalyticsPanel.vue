<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { Bell } from '@element-plus/icons-vue'

const router = useRouter()
const trendRef = ref<HTMLElement>()
let trendChart: echarts.ECharts | null = null

const metrics = ref([
  { key: 'm1', label: '本月采购金额', value: '¥ 3,280', hint: '' },
  { key: 'm2', label: '本月领用物资数', value: '12 类', hint: '' },
  { key: 'm3', label: '待归还', value: '2 件', hint: '含借还' },
  { key: 'm4', label: '逾期', value: '1 件', hint: '请尽快处理' },
])

const aiTips = ref([
  '您的 A4 纸本月消耗约 80%，可一键复购常用规格。',
  '有 1 台投影仪将在 30 天内到期，如需续借请提前申请。',
])

function initTrend() {
  if (!trendRef.value) return
  trendChart = echarts.init(trendRef.value)
  trendChart.setOption({
    title: { text: '近 3 个月耗材消耗趋势', left: 'center', textStyle: { fontSize: 14 } },
    grid: { left: 48, right: 24, top: 48, bottom: 32 },
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, data: ['A4 纸', '硒鼓/墨盒'] },
    xAxis: { type: 'category', data: ['近 3 月', '近 2 月', '本月'] },
    yAxis: { type: 'value', name: '包 / 个' },
    series: [
      { name: 'A4 纸', type: 'line', smooth: true, data: [18, 22, 24], itemStyle: { color: '#6366f1' } },
      { name: '硒鼓/墨盒', type: 'line', smooth: true, data: [2, 3, 2], itemStyle: { color: '#f97316' } },
    ],
  })
}

function resize() {
  trendChart?.resize()
}

onMounted(() => {
  initTrend()
  window.addEventListener('resize', resize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', resize)
  trendChart?.dispose()
  trendChart = null
})

function goWorkbench() {
  router.push('/teacher/workbench')
}
</script>

<template>
  <div class="analytics-panel">
    <div class="metric-grid">
      <div v-for="m in metrics" :key="m.key" class="metric-card">
        <p class="metric-label">{{ m.label }}</p>
        <p class="metric-value">{{ m.value }}</p>
        <p v-if="m.hint" class="metric-hint">{{ m.hint }}</p>
      </div>
    </div>

    <div class="ai-banner">
      <el-icon class="ai-icon"><Bell /></el-icon>
      <div class="ai-text">
        <p v-for="(t, i) in aiTips" :key="i" class="ai-line">{{ t }}</p>
      </div>
    </div>

    <div ref="trendRef" class="trend-box" />

    <div class="actions">
      <el-button @click="goWorkbench">生成采购计划</el-button>
      <el-button type="primary" plain disabled>查看详细报告（对接数据中）</el-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.analytics-panel {
  padding: 0;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
.metric-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 14px 16px;
  box-shadow: var(--shadow-card);
}
.metric-label {
  margin: 0;
  font-size: 12px;
  color: var(--text-muted);
}
.metric-value {
  margin: 8px 0 4px;
  font-size: 22px;
  font-weight: 700;
  color: var(--el-color-primary);
}
.metric-hint {
  margin: 0;
  font-size: 11px;
  color: var(--text-muted);
}
.ai-banner {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  margin-bottom: 16px;
  border-radius: 12px;
  background: linear-gradient(135deg, #fef3c7 0%, #fde68a 33%, transparent 100%);
  border: 1px solid #fcd34d;
}
.ai-icon {
  font-size: 22px;
  color: #d97706;
  flex-shrink: 0;
}
.ai-line {
  margin: 0 0 6px;
  font-size: 13px;
  color: #78350f;
  line-height: 1.5;
  &:last-child {
    margin-bottom: 0;
  }
}
.trend-box {
  height: 300px;
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  padding: 8px;
  margin-bottom: 16px;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
@media (max-width: 960px) {
  .metric-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 480px) {
  .metric-grid {
    grid-template-columns: 1fr;
  }
}
</style>
