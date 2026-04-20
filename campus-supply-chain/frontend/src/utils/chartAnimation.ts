/**
 * ECharts 进入/更新动效（对齐 Art Design Pro：柱自 0 生长、环/饼沿圆周展开）
 */
export const chartEnterAnimation = {
  animation: true,
  animationDuration: 1400,
  animationDurationUpdate: 1000,
  animationEasing: 'quarticOut',
  animationEasingUpdate: 'quarticOut',
} as const

/** 折线/面积：按数据点错开 */
export function seriesDataStaggerDelay(dataLength: number, base = 120, step = 45) {
  return (_dataIndex: number) => base + Math.min(_dataIndex, dataLength) * step
}

/**
 * 饼/环图系列：扇区从起始角沿圆周「展开」到完整（非整体缩放）
 * 对应 ECharts pie.animationType = 'expansion'
 */
export const chartPieSectorEnter = {
  animationType: 'expansion' as const,
  animationDuration: 1400,
  animationEasing: 'quarticOut' as const,
  /** 从 12 点方向开始展开，观感更接近 Art Design 环形动效 */
  startAngle: 90,
  clockwise: true,
}

/**
 * 柱状图系列：强调自基线生长（时长与根级 animationDuration 一致为佳）
 */
export const chartBarGrowSeries = {
  animationDuration: 1300,
  animationEasing: 'quarticOut' as const,
}

/**
 * 供应链大屏低饱和主题色（避免高饱和刺眼）
 */
export const chartSupplyPalette = {
  indigo: '#6B6EFF',
  blue: '#4C88FF',
  violet: '#8B5CF6',
  cyan: '#39A8FF',
  slate: '#6E7EA5',
  amber: '#D6A44A',
  rose: '#A86CFF',
} as const

export const chartSupplyAxis = {
  axisLine: 'rgba(107, 110, 255, 0.28)',
  axisLabel: 'rgba(98, 112, 150, 0.92)',
  splitLine: 'rgba(76, 136, 255, 0.14)',
} as const

export function chartMutedAreaGradient(top = 'rgba(107, 110, 255, 0.34)', bottom = 'rgba(76, 136, 255, 0.06)') {
  return {
    type: 'linear',
    x: 0,
    y: 0,
    x2: 0,
    y2: 1,
    colorStops: [
      { offset: 0, color: top },
      { offset: 1, color: bottom },
    ],
  } as const
}

/**
 * 图表数据加载动画（ECharts 原生 loading）
 */
export const chartLoadingOption = {
  text: '数据加载中...',
  color: '#6B6EFF',
  textColor: 'rgba(79, 70, 229, 0.9)',
  maskColor: 'rgba(248, 250, 255, 0.66)',
  zlevel: 0,
} as const
