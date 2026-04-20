<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { chartEnterAnimation, seriesDataStaggerDelay, chartBarGrowSeries } from '@/utils/chartAnimation'

const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const xAxisLabels = ['1月', '2月', '3月', '4月', '5月', '6月', '7月', '8月', '9月']
const barData = [160, 100, 150, 80, 190, 100, 175, 120, 160]

const list = [
  { name: '在册供应商', num: '48' },
  { name: '在途配送单', num: '126' },
  { name: '今日入库行', num: '1.2k' },
  { name: '周同比', num: '+12%' },
]

function render() {
  const el = chartRef.value
  if (!el) return
  if (!chart) chart = echarts.init(el)
  chart.setOption({
    ...chartEnterAnimation,
    backgroundColor: 'transparent',
    grid: { left: 8, right: 8, top: 8, bottom: 8 },
    xAxis: {
      type: 'category',
      data: xAxisLabels,
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: '#86909c', fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      show: false,
    },
    series: [
      {
        type: 'bar',
        data: barData,
        barWidth: '50%',
        ...chartBarGrowSeries,
        itemStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: '#6366f1' },
              { offset: 1, color: 'rgba(99, 102, 241, 0.15)' },
            ],
          },
          borderRadius: [6, 6, 0, 0],
        },
        animationDelay: seriesDataStaggerDelay(barData.length),
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
  <div class="dcc-card dcc-user">
    <div ref="chartRef" class="chart" />
    <h3 class="title">仓储与采购活跃概览</h3>
    <p class="desc">周环比 <span class="ok">+23%</span> · 仓内作业、采购审批与门户登录综合热度</p>
    <div class="stats">
      <div v-for="item in list" :key="item.name" class="cell">
        <p class="num">{{ item.num }}</p>
        <p class="name">{{ item.name }}</p>
      </div>
    </div>
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
  min-height: 280px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.chart {
  height: 200px;
  width: 100%;
}
.title {
  margin: 12px 0 0;
  font-size: 17px;
  font-weight: 600;
}
.desc {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  .ok {
    color: var(--el-color-success);
    font-weight: 600;
  }
}
.stats {
  display: flex;
  margin-top: 16px;
  gap: 8px;
}
.cell {
  flex: 1;
  text-align: center;
  .num {
    margin: 0;
    font-size: 20px;
    font-weight: 600;
  }
  .name {
    margin: 4px 0 0;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}
</style>
