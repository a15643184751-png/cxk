<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { chartEnterAnimation, seriesDataStaggerDelay } from '@/utils/chartAnimation'

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const xAxisData = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月']
const data = [50, 25, 40, 20, 70, 35, 65, 30, 35, 20, 40, 44]

function render() {
  const el = chartRef.value
  if (!el) return
  if (!chart) chart = echarts.init(el)
  chart.setOption({
    ...chartEnterAnimation,
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 8, right: 8, top: 32, bottom: 8 },
    xAxis: {
      type: 'category',
      data: xAxisData,
      axisLine: { lineStyle: { color: '#f2f3f5' } },
      axisLabel: { color: '#86909c', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#f2f3f5' } },
      axisLabel: { color: '#86909c', fontSize: 11 },
    },
    series: [
      {
        type: 'line',
        smooth: true,
        data,
        itemStyle: { color: '#4f46e5' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(79, 70, 229, 0.25)' },
              { offset: 1, color: 'rgba(79, 70, 229, 0.02)' },
            ],
          },
        },
        animationDelay: seriesDataStaggerDelay(data.length),
      },
    ],
  })
}

let ro: ResizeObserver | null = null

onMounted(() => {
  render()
  ro = new ResizeObserver(() => chart?.resize())
  if (chartRef.value) ro.observe(chartRef.value)
})

onBeforeUnmount(() => {
  ro?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div class="dcc-card dcc-visit">
    <div class="hdr">
      <h4>控制台访问趋势</h4>
      <p class="sub">供应链采供门户 · 本年访问较同期 <span class="ok">+15.2%</span></p>
    </div>
    <div ref="chartRef" class="chart" />
  </div>
</template>

<style scoped lang="scss">
.dcc-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 22px;
  margin-bottom: 20px;
  box-sizing: border-box;
  min-height: 320px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.hdr h4 {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}
.sub {
  margin: 6px 0 16px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  .ok {
    color: var(--el-color-success);
    font-weight: 600;
  }
}
.chart {
  height: calc(100% - 56px);
  min-height: 220px;
  width: 100%;
}
</style>
