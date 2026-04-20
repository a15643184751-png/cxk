<script setup lang="ts">
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { chartEnterAnimation, seriesDataStaggerDelay } from '@/utils/chartAnimation'

const props = defineProps<{
  show: boolean
  chartData: { x: string[]; purchase: number[]; output: number[] }
}>()

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const primaryColor = '#4f46e5'
const successColor = '#0d9488'

function render() {
  if (!props.show) return
  const el = chartRef.value
  if (!el) return
  const { x, purchase, output } = props.chartData
  if (!x?.length) return
  if (!chart) chart = echarts.init(el)
  chart.setOption({
    ...chartEnterAnimation,
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: {
      data: ['采购金额', '出库量'],
      textStyle: { color: '#86909c', fontSize: 12 },
      top: 0,
    },
    grid: { left: 48, right: 24, top: 40, bottom: 24 },
    xAxis: {
      type: 'category',
      data: x,
      axisLine: { lineStyle: { color: '#f2f3f5' } },
      axisLabel: { color: '#86909c', fontSize: 11 },
    },
    yAxis: [
      {
        type: 'value',
        axisLine: { show: false },
        splitLine: { lineStyle: { color: '#f2f3f5' } },
        axisLabel: { color: '#86909c', fontSize: 11 },
      },
      {
        type: 'value',
        axisLine: { show: false },
        splitLine: { show: false },
        axisLabel: { color: '#86909c', fontSize: 11 },
      },
    ],
    series: [
      {
        name: '采购金额',
        type: 'line',
        smooth: true,
        data: purchase,
        animationDelay: seriesDataStaggerDelay(purchase.length),
        itemStyle: { color: primaryColor },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(79, 70, 229, 0.22)' },
              { offset: 1, color: 'rgba(79, 70, 229, 0.02)' },
            ],
          },
        },
      },
      {
        name: '出库量',
        type: 'line',
        smooth: true,
        yAxisIndex: 1,
        data: output,
        animationDelay: seriesDataStaggerDelay(output.length, 200, 50),
        itemStyle: { color: successColor },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(13, 148, 136, 0.2)' },
              { offset: 1, color: 'rgba(13, 148, 136, 0.02)' },
            ],
          },
        },
      },
    ],
  })
}

let ro: ResizeObserver | null = null

onMounted(() => {
  ro = new ResizeObserver(() => chart?.resize())
  if (chartRef.value) ro.observe(chartRef.value)
  render()
})

onBeforeUnmount(() => {
  ro?.disconnect()
  chart?.dispose()
  chart = null
})

watch(
  () => [props.show, props.chartData],
  () => {
    if (props.show) {
      if (!chart && chartRef.value) chart = echarts.init(chartRef.value)
      render()
    }
  },
  { deep: true }
)
</script>

<template>
  <div v-show="show" class="dcc-card dcc-line">
    <div class="hdr">
      <div>
        <h4>采购额与出库量趋势</h4>
        <p class="sub">后勤 / 仓储双视角 · 与业务列表同源聚合（可按周扩展维度）</p>
      </div>
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
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.chart {
  height: calc(100% - 52px);
  min-height: 240px;
  width: 100%;
}
</style>
