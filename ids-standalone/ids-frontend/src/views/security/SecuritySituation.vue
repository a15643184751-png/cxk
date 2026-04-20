<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import * as d3 from 'd3'
import * as topojson from 'topojson-client'
import { Lock } from '@element-plus/icons-vue'
import { getIDSSituation } from '@/api/ids'
import type { IDSSituationAttackItem, IDSSituationResponse } from '@/api/ids'

const DEFAULT_TARGET = {
  lat: 43.817,
  lng: 125.3235,
  city: '长春',
  country: '中国',
  ip: '202.198.16.1',
}

interface AttackEvent {
  id: string
  timestamp: string
  sourceIp: string
  sourceLocation: {
    lat: number
    lng: number
    city: string
    country: string
    derived?: boolean
  }
  targetIp: string
  targetLocation: {
    lat: number
    lng: number
  }
  attackType: string
  severity: string
  status: string
  blocked: boolean
  detectorName: string
}

const attacks = ref<AttackEvent[]>([])
const totalBlocked = ref(0)
const activeThreats = ref(0)
const uptime = ref('00:00:00')
const onlineSources = ref(0)
const disclaimer = ref('地图位置依据事件来源 IP 做稳定映射，仅用于态势展示与溯源辅助。')
const generatedAt = ref('')
const target = ref({ ...DEFAULT_TARGET })
const worldData = ref<GeoJSON.FeatureCollection | null>(null)
const mapContainerRef = ref<HTMLElement | null>(null)
let refreshTimer: ReturnType<typeof setInterval> | null = null

function formatDuration(totalSeconds: number) {
  const safe = Math.max(0, Math.floor(totalSeconds))
  const h = Math.floor(safe / 3600).toString().padStart(2, '0')
  const m = Math.floor((safe % 3600) / 60).toString().padStart(2, '0')
  const s = (safe % 60).toString().padStart(2, '0')
  return `${h}:${m}:${s}`
}

function mapAttack(item: IDSSituationAttackItem): AttackEvent {
  return {
    id: item.id,
    timestamp: item.timestamp,
    sourceIp: item.source_ip,
    sourceLocation: item.source_location,
    targetIp: item.target_ip,
    targetLocation: item.target_location,
    attackType: item.attack_type,
    severity: item.severity,
    status: item.status,
    blocked: item.blocked,
    detectorName: item.detector_name,
  }
}

function severityClass(severity: string) {
  if (severity === '致命') return 'fatal'
  if (severity === '高危') return 'high'
  if (severity === '中危') return 'medium'
  return 'low'
}

async function fetchSituation() {
  try {
    const response: any = await getIDSSituation()
    const data: IDSSituationResponse = response?.data ?? response
    totalBlocked.value = data?.metrics?.total_blocked ?? 0
    activeThreats.value = data?.metrics?.active_threats ?? 0
    uptime.value = formatDuration(data?.metrics?.uptime_seconds ?? 0)
    onlineSources.value = data?.metrics?.online_sources ?? 0
    disclaimer.value = data?.disclaimer || disclaimer.value
    generatedAt.value = data?.generated_at || ''
    target.value = data?.target ?? { ...DEFAULT_TARGET }
    attacks.value = (data?.attacks ?? []).map(mapAttack)
    renderScene()
  } catch {
    totalBlocked.value = 0
    activeThreats.value = 0
    uptime.value = '00:00:00'
    onlineSources.value = 0
    attacks.value = []
    renderScene()
  }
}

function renderScene() {
  if (!worldData.value || !mapContainerRef.value) return
  const svg = d3.select(mapContainerRef.value).select('svg')
  if (svg.empty()) return

  const width = mapContainerRef.value.clientWidth
  const height = mapContainerRef.value.clientHeight
  svg.selectAll('*').remove()

  const defs = svg.append('defs')
  const mapGrad = defs.append('radialGradient').attr('id', 'map-grad').attr('cx', '50%').attr('cy', '50%').attr('r', '60%')
  mapGrad.append('stop').attr('offset', '0%').attr('stop-color', '#0f172a')
  mapGrad.append('stop').attr('offset', '100%').attr('stop-color', '#020617')

  const glow = defs.append('filter').attr('id', 'glow').attr('x', '-20%').attr('y', '-20%').attr('width', '140%').attr('height', '140%')
  glow.append('feGaussianBlur').attr('stdDeviation', '2').attr('result', 'blur')
  glow.append('feComposite').attr('in', 'SourceGraphic').attr('in2', 'blur').attr('operator', 'over')

  svg.append('rect').attr('width', width).attr('height', height).attr('fill', 'url(#map-grad)')

  const projection = d3.geoMercator().scale(width / 6.2).translate([width / 2, height / 1.4])
  const path = d3.geoPath().projection(projection)
  const grid = svg.append('g')

  for (let x = 0; x <= width; x += 40) {
    grid
      .append('line')
      .attr('x1', x)
      .attr('y1', 0)
      .attr('x2', x)
      .attr('y2', height)
      .attr('stroke', 'rgba(255,255,255,0.03)')
      .attr('stroke-width', 1)
  }

  for (let y = 0; y <= height; y += 40) {
    grid
      .append('line')
      .attr('x1', 0)
      .attr('y1', y)
      .attr('x2', width)
      .attr('y2', y)
      .attr('stroke', 'rgba(255,255,255,0.03)')
      .attr('stroke-width', 1)
  }

  const graticule = d3.geoGraticule()
  svg
    .append('path')
    .datum(graticule())
    .attr('d', path as any)
    .attr('fill', 'none')
    .attr('stroke', 'rgba(255,255,255,0.05)')
    .attr('stroke-width', 0.5)

  svg
    .append('g')
    .selectAll('path')
    .data(worldData.value.features)
    .enter()
    .append('path')
    .attr('d', path as any)
    .attr('fill', '#0f172a')
    .attr('stroke', '#1e293b')
    .attr('stroke-width', 1)

  const targetPos = projection([target.value.lng, target.value.lat])
  if (targetPos) {
    const marker = svg.append('g')
    marker
      .append('circle')
      .attr('cx', targetPos[0])
      .attr('cy', targetPos[1])
      .attr('r', 15)
      .attr('fill', 'none')
      .attr('stroke', '#38bdf8')
      .attr('stroke-width', 1)
      .attr('opacity', 0.3)
      .append('animate')
      .attr('attributeName', 'r')
      .attr('from', '10')
      .attr('to', '25')
      .attr('dur', '2s')
      .attr('repeatCount', 'indefinite')
    marker.append('circle').attr('cx', targetPos[0]).attr('cy', targetPos[1]).attr('r', 5).attr('fill', '#38bdf8').attr('filter', 'url(#glow)')
    marker
      .append('text')
      .attr('x', targetPos[0] + 12)
      .attr('y', targetPos[1] - 12)
      .text('安全分析中心')
      .attr('fill', '#7dd3fc')
      .attr('font-size', '12px')
      .attr('font-weight', '900')
      .attr('filter', 'url(#glow)')
  }

  const lineGroup = svg.append('g')
  const labelGroup = svg.append('g')
  const impactGroup = svg.append('g')

  attacks.value.forEach((attack) => {
    const source = projection([attack.sourceLocation.lng, attack.sourceLocation.lat])
    const targetPoint = projection([attack.targetLocation.lng, attack.targetLocation.lat])
    if (!source || !targetPoint) return

    const [x1, y1] = source
    const [x2, y2] = targetPoint
    const color = attack.severity === '致命' ? '#ef4444' : attack.severity === '高危' ? '#f59e0b' : '#10b981'

    const label = labelGroup.append('g').attr('opacity', 0.94)
    label
      .append('rect')
      .attr('x', x1 - 56)
      .attr('y', y1 - 30)
      .attr('width', 112)
      .attr('height', 18)
      .attr('rx', 4)
      .attr('fill', 'rgba(0,0,0,0.6)')
    label
      .append('text')
      .attr('x', x1)
      .attr('y', y1 - 17)
      .attr('text-anchor', 'middle')
      .text(attack.sourceLocation.city)
      .attr('fill', '#fff')
      .attr('font-size', '11px')
      .attr('font-weight', 'bold')
      .attr('filter', 'url(#glow)')
    label.append('circle').attr('cx', x1).attr('cy', y1).attr('r', 4).attr('fill', '#fff').attr('filter', 'url(#glow)')

    const dx = x2 - x1
    const dy = y2 - y1
    const dr = Math.sqrt(dx * dx + dy * dy) * 1.25
    const pathData = `M${x1},${y1}A${dr},${dr} 0 0,1 ${x2},${y2}`
    const pathEl = lineGroup
      .append('path')
      .attr('d', pathData)
      .attr('fill', 'none')
      .attr('stroke', color)
      .attr('stroke-width', 2)
      .attr('filter', 'url(#glow)')
      .attr('opacity', 0.82)
      .attr('stroke-dasharray', function () { return (this as SVGPathElement).getTotalLength() })
      .attr('stroke-dashoffset', function () { return (this as SVGPathElement).getTotalLength() })

    pathEl.transition().duration(1800).ease(d3.easeCubicOut).attr('stroke-dashoffset', 0)
    impactGroup
      .append('circle')
      .attr('cx', x2)
      .attr('cy', y2)
      .attr('r', 2)
      .attr('fill', color)
      .attr('filter', 'url(#glow)')
      .transition()
      .delay(1200)
      .duration(900)
      .attr('r', 18)
      .attr('opacity', 0)
      .remove()
  })
}

function handleResize() {
  renderScene()
}

onMounted(() => {
  fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
    .then((response) => response.json())
    .then((data: any) => {
      worldData.value = topojson.feature(data, data.objects.countries) as unknown as GeoJSON.FeatureCollection
      renderScene()
    })
    .catch(() => {
      worldData.value = null
    })
  void fetchSituation()
  refreshTimer = setInterval(() => {
    void fetchSituation()
  }, 15000)
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
  window.removeEventListener('resize', handleResize)
})
</script>

<template>
  <div class="situation-page">
    <header class="situation-header">
      <div class="header-bg" />
      <div class="header-left">
        <div class="logo-box">
          <el-icon :size="28" class="logo-icon"><Lock /></el-icon>
        </div>
        <div class="logo-meta">
          <span class="meta-label">REAL INCIDENT FEED</span>
          <span class="meta-ver">SECURITY CENTER LIVE</span>
        </div>
      </div>
      <div class="header-center">
        <h1 class="title">安全态势感知</h1>
        <div class="title-deco">
          <div class="line" />
          <p class="subtitle">SECURITY THREAT SITUATION</p>
          <div class="line" />
        </div>
        <p class="demo-disclaimer">{{ disclaimer }}</p>
      </div>
      <div class="header-right">
        <div class="stat-inline">
          <span class="stat-label">最近刷新</span>
          <span class="stat-val">{{ generatedAt || '--' }}</span>
        </div>
      </div>
    </header>

    <main class="situation-main">
      <div class="situation-center">
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-icon emerald"><span class="i-shield" /></div>
            <div>
              <p class="stat-label">累计阻断攻击</p>
              <p class="stat-value">{{ totalBlocked.toLocaleString() }}</p>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon amber"><span class="i-zap" /></div>
            <div>
              <p class="stat-label">当前活跃威胁</p>
              <p class="stat-value">{{ activeThreats }}</p>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon blue"><span class="i-clock" /></div>
            <div>
              <p class="stat-label">服务运行时间</p>
              <p class="stat-value">{{ uptime }}</p>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon purple"><span class="i-globe" /></div>
            <div>
              <p class="stat-label">在线检测源</p>
              <p class="stat-value">{{ onlineSources }}</p>
            </div>
          </div>
        </div>

        <div class="map-section">
          <div ref="mapContainerRef" class="map-wrapper">
            <svg class="map-svg" />
          </div>
          <div class="map-overlay">
            <div class="overlay-card">
              <div class="overlay-header">
                <div class="dot" />
                <h3>核心受保护节点</h3>
                <span class="badge">CVIT-HQ-01</span>
              </div>
              <div class="overlay-body">
                <div class="target-info">
                  <div class="pulse-dot" />
                  <div>
                      <span class="target-name">安全分析中心</span>
                      <span class="target-en">Security Analysis Center</span>
                  </div>
                </div>
                <div class="info-grid">
                  <div class="info-item">
                    <span class="info-label">网络标识</span>
                    <span class="info-val">{{ target.ip }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-label">物理位置</span>
                    <span class="info-val">{{ target.country }} / {{ target.city }}</span>
                  </div>
                </div>
                <div class="info-grid">
                  <div class="info-item">
                    <span class="info-label">地理坐标</span>
                    <span class="info-val">{{ target.lat }}N / {{ target.lng }}E</span>
                  </div>
                  <div class="status-badge">
                    <span class="status-dot" />
                    <span>事件驱动刷新中</span>
                  </div>
                </div>
                <p class="map-note">地图攻击轨迹基于事件来源 IP 的稳定映射生成，用于态势展示与定位辅助。</p>
              </div>
            </div>
          </div>
          <div class="corner-tl" />
          <div class="corner-br" />
        </div>
      </div>

      <aside class="attack-sidebar">
        <div class="sidebar-header">
          <h2>最近事件链路</h2>
          <span class="online-badge"><span class="dot" /> 实时</span>
        </div>
        <div v-if="attacks.length" class="attack-list">
          <div v-for="attack in attacks" :key="attack.id" class="attack-item" :class="severityClass(attack.severity)">
            <div class="attack-head">
              <span class="source-ip">{{ attack.sourceIp }}</span>
              <span class="severity-tag" :class="severityClass(attack.severity)">{{ attack.severity }}</span>
            </div>
            <div class="attack-meta">
              <span>{{ attack.sourceLocation.country }} / {{ attack.sourceLocation.city }}</span>
              <span class="type">{{ attack.attackType }}</span>
            </div>
            <div class="attack-foot">
              <span class="time">{{ attack.timestamp || '--' }}</span>
              <span class="status">{{ attack.status }}</span>
            </div>
            <div class="attack-extra">
              <span>检测器：{{ attack.detectorName || '-' }}</span>
              <span>{{ attack.blocked ? '已阻断' : '仅记录' }}</span>
            </div>
          </div>
        </div>
        <div v-else class="attack-empty">当前暂无可展示的事件链路，待新告警进入后将自动刷新。</div>
      </aside>
    </main>

    <footer class="situation-footer">
      <div class="footer-left">
        <span class="status-ok"><span class="dot" /> 真实事件驱动</span>
        <span class="status-warn"><span class="dot warn" /> 地图位置为近似映射</span>
      </div>
      <div class="footer-right">
        <span>IDS 安全态势页</span>
        <span class="secure">SECURITY CENTER LIVE VIEW</span>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.situation-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: #020617;
  color: #fff;
  overflow: hidden;
}

.situation-header {
  height: 112px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 48px;
  background: rgba(10, 10, 10, 0.95);
  backdrop-filter: blur(24px);
  position: relative;
}

.header-bg {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 50% -20%, rgba(34, 211, 238, 0.08), transparent 55%),
    radial-gradient(circle at 50% -20%, rgba(59, 130, 246, 0.08), transparent);
  pointer-events: none;
}

.header-left,
.header-center,
.header-right {
  position: relative;
  z-index: 1;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 24px;
}

.logo-box {
  width: 56px;
  height: 56px;
  background: rgba(59, 130, 246, 0.1);
  border-radius: 16px;
  border: 1px solid rgba(59, 130, 246, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
}

.logo-icon {
  color: #3b82f6;
}

.logo-meta {
  display: flex;
  flex-direction: column;
}

.meta-label {
  font-size: 10px;
  font-family: monospace;
  color: rgba(255, 255, 255, 0.28);
  letter-spacing: 0.2em;
}

.meta-ver {
  font-size: 12px;
  font-family: monospace;
  color: rgba(255, 255, 255, 0.72);
  font-weight: 700;
}

.header-center {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  width: min(920px, calc(100vw - 360px));
}

.title {
  font-size: 2.4rem;
  font-weight: 900;
  letter-spacing: 0.24em;
  margin: 0;
  background: linear-gradient(to bottom, #fff 40%, #cbd5e1 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.title-deco {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-top: 12px;
  width: 100%;
  justify-content: center;
}

.title-deco .line {
  flex: 1;
  height: 1px;
  background: linear-gradient(to right, transparent, rgba(34, 211, 238, 0.45), transparent);
}

.subtitle {
  font-size: 13px;
  font-family: ui-monospace, monospace;
  color: rgba(165, 243, 252, 0.88);
  letter-spacing: 0.24em;
  white-space: nowrap;
  font-weight: 700;
  margin: 0;
}

.demo-disclaimer {
  margin: 10px 0 0;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.62);
  text-align: center;
  max-width: 720px;
  line-height: 1.6;
}

.stat-inline {
  padding: 0 40px;
  border-left: 1px solid rgba(255, 255, 255, 0.05);
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  text-align: right;
}

.stat-inline .stat-label {
  display: block;
  font-size: 10px;
  font-family: monospace;
  color: rgba(255, 255, 255, 0.28);
  letter-spacing: 0.2em;
  margin-bottom: 4px;
}

.stat-inline .stat-val {
  font-size: 13px;
  font-family: monospace;
  color: rgba(255, 255, 255, 0.82);
  font-weight: 700;
}

.situation-main {
  flex: 1;
  display: flex;
  overflow: hidden;
  background: radial-gradient(circle at center, rgba(59, 130, 246, 0.04) 0%, transparent 70%);
}

.situation-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 32px;
  gap: 28px;
  overflow: hidden;
  min-width: 0;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.stat-card {
  background: #0a0a0a;
  border: 1px solid rgba(255, 255, 255, 0.05);
  padding: 20px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  gap: 20px;
}

.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.05);
}

.stat-icon.emerald { color: #10b981; }
.stat-icon.amber { color: #f59e0b; }
.stat-icon.blue { color: #3b82f6; }
.stat-icon.purple { color: #8b5cf6; }

.stat-icon .i-shield,
.stat-icon .i-zap,
.stat-icon .i-clock,
.stat-icon .i-globe {
  display: inline-block;
  width: 24px;
  height: 24px;
  background: currentColor;
  mask-size: contain;
  mask-repeat: no-repeat;
  mask-position: center;
}

.stat-icon .i-shield { mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpath d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/%3E%3C/svg%3E"); }
.stat-icon .i-zap { mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpath d='M13 2L3 14h9l-1 8 10-12h-9l1-8z'/%3E%3C/svg%3E"); }
.stat-icon .i-clock { mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cpath d='M12 6v6l4 2'/%3E%3C/svg%3E"); }
.stat-icon .i-globe { mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cpath d='M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'/%3E%3C/svg%3E"); }

.stat-label {
  font-size: 10px;
  font-family: monospace;
  color: rgba(255, 255, 255, 0.3);
  letter-spacing: 0.2em;
  text-transform: uppercase;
  margin: 0 0 6px 0;
}

.stat-value {
  font-size: 1.5rem;
  font-family: monospace;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.9);
  margin: 0;
}

.map-section {
  flex: 1;
  position: relative;
  min-height: 0;
  border-radius: 16px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: #0f172a;
}

.map-wrapper,
.map-svg {
  width: 100%;
  height: 100%;
}

.map-wrapper {
  position: absolute;
  inset: 0;
}

.map-overlay {
  position: absolute;
  bottom: 32px;
  left: 32px;
}

.overlay-card {
  background: rgba(10, 10, 10, 0.9);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(59, 130, 246, 0.2);
  padding: 28px;
  border-radius: 24px;
  min-width: 360px;
}

.overlay-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.overlay-header .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #3b82f6;
}

.overlay-header h3 {
  font-size: 11px;
  font-family: monospace;
  letter-spacing: 0.3em;
  color: rgba(96, 165, 250, 0.82);
  margin: 0;
}

.badge {
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(59, 130, 246, 0.1);
  border: 1px solid rgba(59, 130, 246, 0.2);
  font-size: 9px;
  font-family: monospace;
  color: rgba(96, 165, 250, 1);
}

.overlay-body {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.target-info {
  display: flex;
  align-items: center;
  gap: 24px;
}

.pulse-dot {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #3b82f6;
  box-shadow: 0 0 25px rgba(59, 130, 246, 0.8);
  animation: pulse 2s ease-in-out infinite;
}

.target-name {
  display: block;
  font-size: 1.4rem;
  font-family: monospace;
  font-weight: 900;
}

.target-en {
  font-size: 10px;
  font-family: monospace;
  color: rgba(255, 255, 255, 0.28);
  margin-top: 4px;
  display: block;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 16px;
  align-items: center;
}

.info-item {
  background: rgba(255, 255, 255, 0.05);
  padding: 18px;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.info-label {
  display: block;
  font-size: 10px;
  font-family: monospace;
  color: rgba(255, 255, 255, 0.34);
  letter-spacing: 0.18em;
  margin-bottom: 4px;
}

.info-val {
  font-size: 1rem;
  font-family: monospace;
  color: rgba(96, 165, 250, 1);
  font-weight: 900;
}

.status-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 10px;
  font-family: monospace;
  color: #10b981;
  font-weight: 700;
  letter-spacing: 0.18em;
}

.status-dot,
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #10b981;
  animation: pulse 2s ease-in-out infinite;
}

.map-note {
  margin: 0;
  color: rgba(148, 163, 184, 0.92);
  font-size: 12px;
  line-height: 1.6;
}

.corner-tl,
.corner-br {
  position: absolute;
  width: 80px;
  height: 80px;
  pointer-events: none;
}

.corner-tl {
  top: 0;
  right: 0;
  border-top: 2px solid rgba(255, 255, 255, 0.1);
  border-right: 2px solid rgba(255, 255, 255, 0.1);
}

.corner-br {
  bottom: 0;
  left: 0;
  border-bottom: 2px solid rgba(255, 255, 255, 0.1);
  border-left: 2px solid rgba(255, 255, 255, 0.1);
}

.attack-sidebar {
  width: 360px;
  padding: 24px 24px 24px 0;
  display: flex;
  flex-direction: column;
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  h2 {
    margin: 0;
    font-size: 18px;
  }
}

.online-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #10b981;
}

.attack-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: auto;
}

.attack-item {
  padding: 16px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.88);
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.attack-item.fatal {
  border-color: rgba(239, 68, 68, 0.35);
}

.attack-item.high {
  border-color: rgba(245, 158, 11, 0.35);
}

.attack-head,
.attack-meta,
.attack-foot,
.attack-extra {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.attack-head {
  align-items: center;
}

.attack-meta,
.attack-foot,
.attack-extra {
  margin-top: 10px;
  color: rgba(203, 213, 225, 0.82);
  font-size: 13px;
}

.attack-extra {
  color: rgba(148, 163, 184, 0.8);
  font-size: 12px;
}

.source-ip {
  font-family: ui-monospace, monospace;
  font-size: 14px;
  font-weight: 700;
}

.severity-tag {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.severity-tag.fatal {
  background: rgba(239, 68, 68, 0.16);
  color: #fca5a5;
}

.severity-tag.high {
  background: rgba(245, 158, 11, 0.16);
  color: #fcd34d;
}

.severity-tag.medium {
  background: rgba(16, 185, 129, 0.16);
  color: #6ee7b7;
}

.severity-tag.low {
  background: rgba(59, 130, 246, 0.16);
  color: #93c5fd;
}

.type {
  color: #7dd3fc;
}

.attack-empty {
  margin-top: 12px;
  padding: 20px;
  border-radius: 16px;
  border: 1px dashed rgba(148, 163, 184, 0.32);
  color: rgba(148, 163, 184, 0.92);
  line-height: 1.7;
  background: rgba(15, 23, 42, 0.5);
}

.situation-footer {
  height: 56px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
  font-size: 12px;
  color: rgba(203, 213, 225, 0.82);
  background: rgba(2, 6, 23, 0.92);
}

.footer-left,
.footer-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.status-ok,
.status-warn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.status-warn .warn {
  background: #f59e0b;
}

.secure {
  color: #7dd3fc;
}

@keyframes pulse {
  0% { transform: scale(1); opacity: 0.9; }
  70% { transform: scale(1.18); opacity: 0.35; }
  100% { transform: scale(1); opacity: 0.9; }
}

@media (max-width: 1400px) {
  .stats-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .attack-sidebar {
    width: 320px;
  }
}

@media (max-width: 1180px) {
  .situation-main {
    flex-direction: column;
    overflow: auto;
  }

  .attack-sidebar {
    width: auto;
    padding: 0 32px 24px;
  }

  .map-section {
    min-height: 540px;
  }
}
</style>
