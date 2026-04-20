<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as d3 from 'd3'
import * as topojson from 'topojson-client'
import { Lock } from '@element-plus/icons-vue'

const TARGET_LOCATION = { lat: 43.817, lng: 125.3235 }

interface AttackEvent {
  id: string
  timestamp: Date
  sourceIp: string
  sourceLocation: { lat: number; lng: number; city: string; country: string }
  targetIp: string
  targetLocation: { lat: number; lng: number }
  attackType: string
  severity: '低危' | '中危' | '高危' | '致命'
  status: '已拦截' | '监控中'
}

const GEODATA = [
  { country: '美国', cities: [{ name: '纽约', lat: 40.7128, lng: -74.006 }, { name: '洛杉矶', lat: 34.0522, lng: -118.2437 }, { name: '芝加哥', lat: 41.8781, lng: -87.6298 }, { name: '华盛顿', lat: 38.9072, lng: -77.0369 }, { name: '旧金山', lat: 37.7749, lng: -122.4194 }] },
  { country: '俄罗斯', cities: [{ name: '莫斯科', lat: 55.7558, lng: 37.6173 }, { name: '圣彼得堡', lat: 59.9343, lng: 30.3351 }, { name: '新西伯利亚', lat: 55.0084, lng: 82.9357 }] },
  { country: '德国', cities: [{ name: '柏林', lat: 52.52, lng: 13.405 }, { name: '慕尼黑', lat: 48.1351, lng: 11.582 }, { name: '法兰克福', lat: 50.1109, lng: 8.6821 }] },
  { country: '日本', cities: [{ name: '东京', lat: 35.6762, lng: 139.6503 }, { name: '大阪', lat: 34.6937, lng: 135.5023 }, { name: '京都', lat: 35.0116, lng: 135.7681 }] },
  { country: '英国', cities: [{ name: '伦敦', lat: 51.5074, lng: -0.1278 }, { name: '曼彻斯特', lat: 53.4808, lng: -2.2426 }, { name: '爱丁堡', lat: 55.9533, lng: -3.1883 }] },
  { country: '法国', cities: [{ name: '巴黎', lat: 48.8566, lng: 2.3522 }, { name: '里昂', lat: 45.764, lng: 4.8357 }, { name: '马赛', lat: 43.2965, lng: 5.3698 }] },
  { country: '巴西', cities: [{ name: '圣保罗', lat: -23.5505, lng: -46.6333 }, { name: '里约热内卢', lat: -22.9068, lng: -43.1729 }, { name: '巴西利亚', lat: -15.7975, lng: -47.8919 }] },
  { country: '韩国', cities: [{ name: '首尔', lat: 37.5665, lng: 126.978 }, { name: '釜山', lat: 35.1796, lng: 129.0756 }, { name: '仁川', lat: 37.4563, lng: 126.7052 }] },
  { country: '加拿大', cities: [{ name: '多伦多', lat: 43.6532, lng: -79.3832 }, { name: '温哥华', lat: 49.2827, lng: -123.1207 }, { name: '蒙特利尔', lat: 45.5017, lng: -73.5673 }] },
  { country: '澳大利亚', cities: [{ name: '悉尼', lat: -33.8688, lng: 151.2093 }, { name: '墨尔本', lat: -37.8136, lng: 144.9631 }, { name: '布里斯班', lat: -27.4698, lng: 153.0251 }] },
  { country: '印度', cities: [{ name: '孟买', lat: 19.076, lng: 72.8777 }, { name: '德里', lat: 28.6139, lng: 77.209 }, { name: '班加罗尔', lat: 12.9716, lng: 77.5946 }] },
  { country: '新加坡', cities: [{ name: '新加坡', lat: 1.3521, lng: 103.8198 }] },
  { country: '荷兰', cities: [{ name: '阿姆斯特丹', lat: 52.3676, lng: 4.9041 }] },
]

const ATTACK_TYPES = ['DDoS 攻击', 'SQL 注入', '暴力破解', '跨站脚本', '恶意软件', '端口扫描'] as const
const SEVERITIES = ['低危', '中危', '高危', '致命'] as const

function generateRandomAttack(targetLat: number, targetLng: number): AttackEvent {
  const countryData = GEODATA[Math.floor(Math.random() * GEODATA.length)]
  const city = countryData.cities[Math.floor(Math.random() * countryData.cities.length)]
  const severity = SEVERITIES[Math.floor(Math.random() * SEVERITIES.length)]
  return {
    id: Math.random().toString(36).slice(2, 11),
    timestamp: new Date(),
    sourceIp: `${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}.${Math.floor(Math.random() * 255)}`,
    sourceLocation: { lat: city.lat, lng: city.lng, city: city.name, country: countryData.country },
    targetIp: '202.198.16.1',
    targetLocation: { lat: targetLat, lng: targetLng },
    attackType: ATTACK_TYPES[Math.floor(Math.random() * ATTACK_TYPES.length)],
    severity,
    status: '已拦截',
  }
}

const attacks = ref<AttackEvent[]>([])
const totalBlocked = ref(5200)
const activeThreats = ref(0)
const uptime = ref('00:00:00')
const worldData = ref<GeoJSON.FeatureCollection | null>(null)
const mapContainerRef = ref<HTMLElement | null>(null)
const animatedIds = ref<Set<string>>(new Set())
let simTimer: ReturnType<typeof setTimeout> | null = null
let uptimeTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')
    .then((r) => r.json())
    .then((data: any) => {
      worldData.value = topojson.feature(data, data.objects.countries) as unknown as GeoJSON.FeatureCollection
    })
  startUptime()
  startSimulation()
})

onBeforeUnmount(() => {
  if (simTimer) clearTimeout(simTimer)
  if (uptimeTimer) clearInterval(uptimeTimer)
})

function startUptime() {
  const baseSeconds = 24 * 3600 + 2 * 60 + 52
  const startTime = Date.now()
  uptimeTimer = setInterval(() => {
    const elapsed = Math.floor((Date.now() - startTime) / 1000)
    const total = baseSeconds + elapsed
    const h = Math.floor(total / 3600).toString().padStart(2, '0')
    const m = Math.floor((total % 3600) / 60).toString().padStart(2, '0')
    const s = (total % 60).toString().padStart(2, '0')
    uptime.value = `${h}:${m}:${s}`
  }, 1000)
}

function addAttackBatch() {
  const r = Math.random()
  const batchSize = r < 0.3 ? Math.floor(Math.random() * 3) + 1 : r < 0.6 ? Math.floor(Math.random() * 2) + 7 : Math.floor(Math.random() * 3) + 4
  for (let i = 0; i < batchSize; i++) {
    setTimeout(() => {
      if (attacks.value.length >= 30) return
      const newAttack = generateRandomAttack(TARGET_LOCATION.lat, TARGET_LOCATION.lng)
      attacks.value = [newAttack, ...attacks.value]
      totalBlocked.value += Math.floor(Math.random() * 3) + 1
      activeThreats.value = Math.min(activeThreats.value + 1, 100)
      setTimeout(() => {
        activeThreats.value = Math.max(activeThreats.value - 1, 0)
        attacks.value = attacks.value.slice(0, -1)
      }, 6000 + Math.random() * 4000)
    }, i * 400)
  }
}

function startSimulation() {
  const run = () => {
    addAttackBatch()
    simTimer = setTimeout(run, 4000 + Math.random() * 6000)
  }
  simTimer = setTimeout(run, 1000)
}

function drawMap() {
  if (!worldData.value || !mapContainerRef.value) return
  const svg = d3.select(mapContainerRef.value).select('svg')
  if (svg.empty()) return
  const width = mapContainerRef.value.clientWidth
  const height = mapContainerRef.value.clientHeight
  svg.selectAll('*').remove()

  const defs = svg.append('defs')
  defs.append('radialGradient').attr('id', 'map-grad').attr('cx', '50%').attr('cy', '50%').attr('r', '50%')
    .append('stop').attr('offset', '0%').attr('stop-color', '#1e293b')
  defs.select('#map-grad').append('stop').attr('offset', '100%').attr('stop-color', '#020617')

  svg.append('rect').attr('width', width).attr('height', height).attr('fill', 'url(#map-grad)')

  const glow = defs.append('filter').attr('id', 'glow').attr('x', '-20%').attr('y', '-20%').attr('width', '140%').attr('height', '140%')
  glow.append('feGaussianBlur').attr('stdDeviation', '2').attr('result', 'blur')
  glow.append('feComposite').attr('in', 'SourceGraphic').attr('in2', 'blur').attr('operator', 'over')

  const projection = d3.geoMercator().scale(width / 6.2).translate([width / 2, height / 1.4])
  const path = d3.geoPath().projection(projection)

  const grid = svg.append('g')
  for (let x = 0; x <= width; x += 40) grid.append('line').attr('x1', x).attr('y1', 0).attr('x2', x).attr('y2', height).attr('stroke', 'rgba(255,255,255,0.03)').attr('stroke-width', 1)
  for (let y = 0; y <= height; y += 40) grid.append('line').attr('x1', 0).attr('y1', y).attr('x2', width).attr('y2', y).attr('stroke', 'rgba(255,255,255,0.03)').attr('stroke-width', 1)

  const graticule = d3.geoGraticule()
  svg.append('path').datum(graticule()).attr('d', path as any).attr('fill', 'none').attr('stroke', 'rgba(255,255,255,0.05)').attr('stroke-width', 0.5)

  svg.append('g').selectAll('path').data(worldData.value!.features).enter().append('path')
    .attr('d', path as any).attr('fill', '#0f172a').attr('stroke', '#1e293b').attr('stroke-width', 1)
    .on('mouseover', function() { d3.select(this).attr('fill', '#1e293b').attr('stroke', '#3b82f6') })
    .on('mouseout', function() { d3.select(this).attr('fill', '#0f172a').attr('stroke', '#1e293b') })

  const targetPos = projection([TARGET_LOCATION.lng, TARGET_LOCATION.lat])
  if (targetPos) {
    const g = svg.append('g')
    g.append('circle').attr('cx', targetPos[0]).attr('cy', targetPos[1]).attr('r', 15).attr('fill', 'none').attr('stroke', '#3b82f6').attr('stroke-width', 1).attr('opacity', 0.3)
      .append('animate').attr('attributeName', 'r').attr('from', '10').attr('to', '25').attr('dur', '2s').attr('repeatCount', 'indefinite')
    g.append('circle').attr('cx', targetPos[0]).attr('cy', targetPos[1]).attr('r', 5).attr('fill', '#3b82f6').attr('filter', 'url(#glow)')
    g.append('text').attr('x', targetPos[0] + 12).attr('y', targetPos[1] - 12).text('校园物资供应链安全中心').attr('fill', '#60a5fa').attr('font-size', '12px').attr('font-weight', '900').attr('filter', 'url(#glow)')
  }

  svg.append('g').attr('class', 'lines-layer')
  svg.append('g').attr('class', 'labels-layer')
  svg.append('g').attr('class', 'impact-layer')
}

function drawAttackLines() {
  if (!worldData.value || !mapContainerRef.value) return
  const svg = d3.select(mapContainerRef.value).select('svg')
  if (svg.empty()) return
  const width = mapContainerRef.value.clientWidth
  const height = mapContainerRef.value.clientHeight
  const projection = d3.geoMercator().scale(width / 6.2).translate([width / 2, height / 1.4])
  const lineGroup = svg.select('.lines-layer')
  const labelGroup = svg.select('.labels-layer')
  const impactGroup = svg.select('.impact-layer')

  attacks.value.forEach((attack) => {
    if (animatedIds.value.has(attack.id)) return
    animatedIds.value.add(attack.id)

    const source = projection([attack.sourceLocation.lng, attack.sourceLocation.lat])
    const target = projection([attack.targetLocation.lng, attack.targetLocation.lat])
    if (!source || !target) return

    const [x1, y1] = source
    const [x2, y2] = target
    const color = attack.severity === '致命' ? '#ef4444' : attack.severity === '高危' ? '#f59e0b' : '#10b981'

    const sl = labelGroup.append('g').attr('opacity', 0)
    sl.append('rect').attr('x', x1 - 40).attr('y', y1 - 28).attr('width', 80).attr('height', 16).attr('rx', 4).attr('fill', 'rgba(0,0,0,0.6)')
    sl.append('text').attr('x', x1).attr('y', y1 - 16).attr('text-anchor', 'middle').text(attack.sourceLocation.city).attr('fill', '#fff').attr('font-size', '11px').attr('font-weight', 'bold').attr('filter', 'url(#glow)')
    sl.append('circle').attr('cx', x1).attr('cy', y1).attr('r', 4).attr('fill', '#fff').attr('filter', 'url(#glow)')

    const dx = x2 - x1
    const dy = y2 - y1
    const dr = Math.sqrt(dx * dx + dy * dy) * (1 + Math.random())
    const pathData = `M${x1},${y1}A${dr},${dr} 0 0,1 ${x2},${y2}`

    const pathEl = lineGroup.append('path').attr('d', pathData).attr('fill', 'none').attr('stroke', color).attr('stroke-width', 2).attr('filter', 'url(#glow)').attr('opacity', 0.8)
      .attr('stroke-dasharray', function() { return (this as SVGPathElement).getTotalLength() })
      .attr('stroke-dashoffset', function() { return (this as SVGPathElement).getTotalLength() })

    const duration = 2500 + Math.random() * 1500
    const delay = Math.random() * 500
    sl.transition().delay(delay).duration(500).attr('opacity', 1)
      .transition().delay(duration).duration(500).attr('opacity', 0).remove()

    pathEl.transition().delay(delay).duration(duration).ease(d3.easeCubicOut).attr('stroke-dashoffset', 0)
      .on('end', () => {
        impactGroup.append('circle').attr('cx', x2).attr('cy', y2).attr('r', 2).attr('fill', color).attr('filter', 'url(#glow)')
          .transition().duration(800).attr('r', 20).attr('opacity', 0).remove()
        pathEl.transition().delay(1000).duration(1000).attr('opacity', 0).remove()
        setTimeout(() => {
          const next = new Set(animatedIds.value)
          next.delete(attack.id)
          animatedIds.value = next
        }, 3000)
      })
  })
}

watch(worldData, (v) => { if (v) drawMap() })
watch(attacks, () => { if (worldData.value && mapContainerRef.value) drawAttackLines() }, { deep: true })
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
          <span class="meta-label">系统版本</span>
          <span class="meta-ver">V4.5.0 PRO</span>
        </div>
      </div>
      <div class="header-center">
        <h1 class="title">安全态势感知</h1>
        <div class="title-deco">
          <div class="line" />
          <p class="subtitle">SECURITY SITUATION AWARENESS SYSTEM</p>
          <div class="line" />
        </div>
      </div>
      <div class="header-right">
        <div class="stat-inline">
          <span class="stat-label">实时吞吐量</span>
          <span class="stat-val">2.48 <span class="stat-unit">TB/s</span></span>
        </div>
      </div>
    </header>

    <main class="situation-main">
      <div class="situation-center">
        <div class="stats-row">
          <div class="stat-card">
            <div class="stat-icon emerald"><span class="i-shield" /></div>
            <div>
              <p class="stat-label">累计拦截攻击</p>
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
              <p class="stat-label">系统运行时间</p>
              <p class="stat-value">{{ uptime }}</p>
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-icon purple"><span class="i-globe" /></div>
            <div>
              <p class="stat-label">全球防护节点</p>
              <p class="stat-value">24</p>
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
                    <span class="target-name">校园物资供应链安全中心</span>
                    <span class="target-en">Campus Supply Chain Security Center</span>
                  </div>
                </div>
                <div class="info-grid">
                  <div class="info-item">
                    <span class="info-label">网络标识 (IP Address)</span>
                    <span class="info-val">202.198.16.1</span>
                  </div>
                  <div class="info-item">
                    <span class="info-label">物理位置</span>
                    <span class="info-val">吉林 · 长春</span>
                  </div>
                </div>
                <div class="info-grid">
                  <div class="info-item">
                    <span class="info-label">地理坐标</span>
                    <span class="info-val">{{ TARGET_LOCATION.lat }}N / {{ TARGET_LOCATION.lng }}E</span>
                  </div>
                  <div class="status-badge">
                    <span class="status-dot" />
                    <span>实时防护中</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <div class="corner-tl" />
          <div class="corner-br" />
        </div>
      </div>

      <aside class="attack-sidebar">
        <div class="sidebar-header">
          <h2><span class="i-clock" /> 实时威胁监控</h2>
          <span class="online-badge"><span class="dot" /> 在线</span>
        </div>
        <div class="attack-list">
          <div
            v-for="a in attacks"
            :key="a.id"
            class="attack-item"
            :class="{ fatal: a.severity === '致命', high: a.severity === '高危' }"
          >
            <div class="attack-head">
              <span class="source-ip">{{ a.sourceIp }}</span>
              <span class="severity-tag" :class="a.severity">{{ a.severity }}</span>
            </div>
            <div class="attack-meta">
              <span>{{ a.sourceLocation.country }} • {{ a.sourceLocation.city }}</span>
              <span class="type">{{ a.attackType }}</span>
            </div>
            <div class="attack-foot">
              <span class="time">{{ a.timestamp.toLocaleTimeString() }}</span>
              <span class="status">{{ a.status }}</span>
            </div>
          </div>
        </div>
      </aside>
    </main>

    <footer class="situation-footer">
      <div class="footer-left">
        <span class="status-ok"><span class="dot" /> 系统运行正常</span>
        <span class="status-warn"><span class="dot warn" /> 风险等级: 中等</span>
        <span class="sep" />
        <span><span class="dot blue" /> 加密通道: AES-256-GCM</span>
        <span><span class="dot purple" /> 量子防护: ACTIVE</span>
      </div>
      <div class="footer-right">
        <span>© 2026 安全态势感知系统架构</span>
        <span class="secure">SECURE CONNECTION ESTABLISHED</span>
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
  background: var(--sec-hud-page-bg);
  color: #fff;
  font-family: inherit;
  overflow: hidden;
}

.situation-header {
  height: 112px;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 48px;
  background: rgba(10,10,10,0.95);
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
.header-left, .header-center, .header-right {
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
  background: rgba(59,130,246,0.1);
  border-radius: 16px;
  border: 1px solid rgba(59,130,246,0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 30px rgba(59,130,246,0.15);
}
.logo-icon { color: #3b82f6; }
.logo-meta { display: flex; flex-direction: column; }
.meta-label { font-size: 10px; font-family: monospace; color: rgba(255,255,255,0.2); letter-spacing: 0.2em; text-transform: uppercase; }
.meta-ver { font-size: 12px; font-family: monospace; color: rgba(255,255,255,0.6); font-weight: 700; }
.header-center {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  flex-direction: column;
  align-items: center;
}
.title {
  font-size: 2.5rem;
  font-weight: 900;
  letter-spacing: 0.35em;
  margin: 0;
  background: linear-gradient(to bottom, #fff 40%, #cbd5e1 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.title-deco {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-top: 12px;
  width: 100%;
  justify-content: center;
}
.title-deco .line { flex: 1; height: 1px; background: linear-gradient(to right, transparent, rgba(34,211,238,0.45), transparent); }
.subtitle {
  font-size: 13px;
  font-family: ui-monospace, monospace;
  color: rgba(165, 243, 252, 0.88);
  letter-spacing: 0.42em;
  white-space: nowrap;
  font-weight: 700;
  margin: 0;
  text-shadow: 0 0 14px rgba(34, 211, 238, 0.35);
}
.header-right { display: flex; align-items: center; }
.stat-inline { padding: 0 40px; border-left: 1px solid rgba(255,255,255,0.05); border-right: 1px solid rgba(255,255,255,0.05); text-align: right; }
.stat-inline .stat-label { display: block; font-size: 10px; font-family: monospace; color: rgba(255,255,255,0.2); letter-spacing: 0.2em; margin-bottom: 4px; }
.stat-inline .stat-val { font-size: 14px; font-family: monospace; color: rgba(255,255,255,0.8); font-weight: 700; }
.stat-inline .stat-unit { font-size: 10px; color: rgba(255,255,255,0.4); }

.situation-main {
  flex: 1;
  display: flex;
  overflow: hidden;
  background: radial-gradient(circle at center, rgba(59,130,246,0.04) 0%, transparent 70%);
}

.situation-center {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 40px;
  gap: 40px;
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
  border: 1px solid rgba(255,255,255,0.05);
  padding: 20px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  gap: 20px;
  transition: all 0.2s;
}
.stat-card:hover { border-color: rgba(255,255,255,0.1); }
.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255,255,255,0.05);
}
.stat-icon.emerald { color: #10b981; box-shadow: 0 0 20px rgba(16,185,129,0.2); }
.stat-icon.amber { color: #f59e0b; box-shadow: 0 0 20px rgba(245,158,11,0.2); }
.stat-icon.blue { color: #3b82f6; box-shadow: 0 0 20px rgba(59,130,246,0.2); }
.stat-icon.purple { color: #8b5cf6; box-shadow: 0 0 20px rgba(139,92,246,0.2); }
.stat-icon .i-shield, .stat-icon .i-zap, .stat-icon .i-clock, .stat-icon .i-globe {
  display: inline-block;
  width: 24px; height: 24px;
  background: currentColor;
  mask-size: contain; mask-repeat: no-repeat; mask-position: center;
}
.stat-icon .i-shield { mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpath d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/%3E%3C/svg%3E"); -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpath d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/%3E%3C/svg%3E"); }
.stat-icon .i-zap { mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpath d='M13 2L3 14h9l-1 8 10-12h-9l1-8z'/%3E%3C/svg%3E"); -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Cpath d='M13 2L3 14h9l-1 8 10-12h-9l1-8z'/%3E%3C/svg%3E"); }
.stat-icon .i-clock { mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cpath d='M12 6v6l4 2'/%3E%3C/svg%3E"); -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cpath d='M12 6v6l4 2'/%3E%3C/svg%3E"); }
.stat-icon .i-globe { mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cpath d='M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'/%3E%3C/svg%3E"); -webkit-mask-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2'%3E%3Ccircle cx='12' cy='12' r='10'/%3E%3Cpath d='M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z'/%3E%3C/svg%3E"); }
.stat-label { font-size: 10px; font-family: monospace; color: rgba(255,255,255,0.3); letter-spacing: 0.2em; text-transform: uppercase; margin: 0 0 6px 0; }
.stat-value { font-size: 1.5rem; font-family: monospace; font-weight: 700; color: rgba(255,255,255,0.9); margin: 0; letter-spacing: -0.02em; }

.map-section {
  flex: 1;
  position: relative;
  min-height: 0;
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,0.1);
  box-shadow: 0 0 50px rgba(0,0,0,0.5);
  background: #0f172a;
}
.map-wrapper {
  width: 100%;
  height: 100%;
  position: absolute;
  inset: 0;
}
.map-svg { width: 100%; height: 100%; }
.map-overlay {
  position: absolute;
  bottom: 40px;
  left: 40px;
  pointer-events: none;
}
.overlay-card {
  background: rgba(10,10,10,0.9);
  backdrop-filter: blur(24px);
  border: 1px solid rgba(59,130,246,0.2);
  padding: 32px;
  border-radius: 32px;
  box-shadow: 0 0 50px rgba(0,0,0,0.6);
  min-width: 360px;
}
.overlay-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}
.overlay-header .dot { width: 8px; height: 8px; border-radius: 50%; background: #3b82f6; box-shadow: 0 0 10px rgba(59,130,246,0.5); }
.overlay-header h3 { font-size: 11px; font-family: monospace; letter-spacing: 0.5em; text-transform: uppercase; color: rgba(96,165,250,0.8); font-weight: 700; margin: 0; }
.badge { padding: 2px 8px; border-radius: 4px; background: rgba(59,130,246,0.1); border: 1px solid rgba(59,130,246,0.2); font-size: 9px; font-family: monospace; color: rgba(96,165,250,1); }
.overlay-body { display: flex; flex-direction: column; gap: 24px; }
.target-info { display: flex; align-items: center; gap: 24px; margin-bottom: 8px; }
.pulse-dot {
  width: 24px; height: 24px;
  border-radius: 50%;
  background: #3b82f6;
  box-shadow: 0 0 25px rgba(59,130,246,0.8);
  animation: pulse 2s ease-in-out infinite;
}
@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.1); opacity: 0.8; }
}
.target-name { display: block; font-size: 1.5rem; font-family: monospace; font-weight: 900; color: #fff; letter-spacing: -0.02em; }
.target-en { font-size: 10px; font-family: monospace; color: rgba(255,255,255,0.2); margin-top: 4px; display: block; letter-spacing: 0.2em; text-transform: uppercase; }
.info-grid { display: grid; grid-template-columns: 1fr auto; gap: 16px; align-items: center; }
.info-item { background: rgba(255,255,255,0.05); padding: 20px; border-radius: 16px; border: 1px solid rgba(255,255,255,0.05); }
.info-label { display: block; font-size: 10px; font-family: monospace; color: rgba(255,255,255,0.3); letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 4px; }
.info-val { font-size: 1rem; font-family: monospace; color: rgba(96,165,250,1); font-weight: 900; }
.info-item:last-child .info-val { color: rgba(255,255,255,0.8); font-size: 14px; }
.status-badge { display: flex; align-items: center; gap: 8px; font-size: 10px; font-family: monospace; color: #10b981; font-weight: 700; letter-spacing: 0.2em; }
.status-dot { width: 8px; height: 8px; border-radius: 50%; background: #10b981; animation: pulse 2s ease-in-out infinite; }
.corner-tl { position: absolute; top: 0; right: 0; width: 80px; height: 80px; border-top: 2px solid rgba(255,255,255,0.1); border-right: 2px solid rgba(255,255,255,0.1); border-radius: 0 24px 0 0; pointer-events: none; }
.corner-br { position: absolute; bottom: 0; left: 0; width: 80px; height: 80px; border-bottom: 2px solid rgba(255,255,255,0.1); border-left: 2px solid rgba(255,255,255,0.1); border-radius: 0 0 0 24px; pointer-events: none; }

.attack-sidebar {
  width: 420px;
  border-left: 1px solid rgba(255,255,255,0.05);
  display: flex;
  flex-direction: column;
  background: #0a0a0a;
  overflow: hidden;
}
.sidebar-header {
  padding: 16px;
  border-bottom: 1px solid rgba(255,255,255,0.05);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: rgba(0,0,0,0.2);
}
.sidebar-header h2 {
  font-size: 12px;
  font-family: monospace;
  letter-spacing: 0.2em;
  color: rgba(255,255,255,0.6);
  margin: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.sidebar-header .i-clock { color: #3b82f6; }
.online-badge { font-size: 10px; font-family: monospace; color: #10b981; display: flex; align-items: center; gap: 4px; animation: pulse 2s ease-in-out infinite; }
.online-badge .dot { width: 6px; height: 6px; border-radius: 50%; background: #10b981; }
.attack-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.attack-item {
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(255,255,255,0.05);
  background: rgba(255,255,255,0.05);
  transition: all 0.2s;
}
.attack-item:hover { background: rgba(255,255,255,0.1); }
.attack-item.fatal { border-color: rgba(239,68,68,0.3); background: rgba(239,68,68,0.05); }
.attack-item.high { border-color: rgba(245,158,11,0.3); background: rgba(245,158,11,0.05); }
.attack-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.source-ip { font-size: 11px; font-family: monospace; font-weight: 700; color: rgba(255,255,255,0.9); }
.severity-tag {
  font-size: 9px;
  padding: 2px 6px;
  border-radius: 4px;
  font-family: monospace;
  font-weight: 700;
  text-transform: uppercase;
}
.severity-tag.低危, .severity-tag.中危 { background: rgba(255,255,255,0.1); color: rgba(255,255,255,0.6); }
.severity-tag.高危 { background: rgba(245,158,11,0.2); color: #f59e0b; }
.severity-tag.致命 { background: rgba(239,68,68,0.2); color: #ef4444; }
.attack-meta { display: flex; flex-direction: column; gap: 4px; font-size: 10px; color: rgba(255,255,255,0.4); }
.attack-meta .type { color: rgba(255,255,255,0.7); font-weight: 500; }
.attack-foot {
  margin-top: 12px;
  padding-top: 8px;
  border-top: 1px solid rgba(255,255,255,0.05);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.attack-foot .time { font-size: 9px; font-family: monospace; color: rgba(255,255,255,0.2); }
.attack-foot .status {
  font-size: 9px;
  font-family: monospace;
  text-transform: uppercase;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(16,185,129,0.1);
  color: rgba(16,185,129,0.8);
}

.situation-footer {
  height: 48px;
  border-top: 1px solid rgba(255,255,255,0.1);
  background: #0a0a0a;
  padding: 0 48px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 10px;
  font-family: monospace;
  color: rgba(255,255,255,0.3);
  letter-spacing: 0.25em;
  text-transform: uppercase;
}
.footer-left { display: flex; align-items: center; gap: 48px; }
.status-ok .dot, .status-ok { color: #10b981; }
.status-warn .dot.warn { background: #f59e0b; }
.status-warn { color: #f59e0b; }
.sep { width: 1px; height: 16px; background: rgba(255,255,255,0.1); }
.dot.blue { background: #3b82f6; }
.dot.purple { background: #8b5cf6; }
.footer-right { display: flex; align-items: center; gap: 32px; }
.secure { color: rgba(59,130,246,0.5); font-weight: 700; }
</style>
