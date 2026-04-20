<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import { ZoomIn, ZoomOut, Van } from '@element-plus/icons-vue'
import {
  MAP_W,
  MAP_H,
  MAP_BASE_W,
  MAP_BASE_H,
  WAREHOUSE_ID,
  campusPlaces,
  mockDeliveryOrders,
  warehouseCenter,
  centerOfPlace,
  type CampusPlace,
  type MockDeliveryOrder,
  type DelStatus,
} from './deliveryMapMock'

type FilterKey = 'all' | DelStatus

const stageRef = ref<HTMLElement | null>(null)
const listRef = ref<HTMLElement | null>(null)

const panX = ref(0)
const panY = ref(0)
const scale = ref(1)
const dragging = ref(false)
/** 最大缩放（相对「整图刚好塞进视口」的基准） */
const ZOOM_MAX = 2.35
let dragStartX = 0
let dragStartY = 0
let panStartX = 0
let panStartY = 0

const filterKey = ref<FilterKey>('all')
const selectedId = ref<string | null>(null)
const pulseBuildingId = ref<string | null>(null)
let pulseTimer: ReturnType<typeof setTimeout> | null = null

const buildingPopup = ref<{ place: CampusPlace; taskCount: number } | null>(null)

const basemapInnerTransform = computed(
  () => `scale(${MAP_W / MAP_BASE_W}, ${MAP_H / MAP_BASE_H})`,
)

function stageSize() {
  const el = stageRef.value
  let vw = el?.clientWidth ?? 0
  let vh = el?.clientHeight ?? 0
  if (!vw || !vh) {
    vw = 960
    vh = 640
  }
  return { vw: Math.max(1, vw), vh: Math.max(1, vh) }
}

/** 最小缩放：整幅地图必须落在视口内（contain），不能再缩小露出画布外 */
function scaleMinForStage() {
  const { vw, vh } = stageSize()
  return Math.min(vw / MAP_W, vh / MAP_H)
}

function scaleMaxForStage() {
  return scaleMinForStage() * ZOOM_MAX
}

function clampView() {
  const el = stageRef.value
  if (!el) return
  const { vw, vh } = stageSize()
  const sMin = scaleMinForStage()
  const sMax = scaleMaxForStage()
  scale.value = Math.min(sMax, Math.max(sMin, scale.value))
  const s = scale.value
  const sw = MAP_W * s
  const sh = MAP_H * s
  let px = panX.value
  let py = panY.value
  if (sw <= vw) px = (vw - sw) / 2
  else px = Math.min(0, Math.max(vw - sw, px))
  if (sh <= vh) py = (vh - sh) / 2
  else py = Math.min(0, Math.max(vh - sh, py))
  panX.value = px
  panY.value = py
}

const placeMap = computed(() => {
  const m = new Map<string, CampusPlace>()
  campusPlaces.forEach((p) => m.set(p.id, p))
  return m
})

const orders = ref<MockDeliveryOrder[]>([...mockDeliveryOrders])

const filteredOrders = computed(() => {
  if (filterKey.value === 'all') return orders.value
  return orders.value.filter((o) => o.status === filterKey.value)
})

const stats = computed(() => {
  const o = orders.value
  return {
    total: o.length,
    pending: o.filter((x) => x.status === 'pending').length,
    onWay: o.filter((x) => x.status === 'on_way').length,
    received: o.filter((x) => x.status === 'received').length,
    exception: o.filter((x) => x.status === 'exception').length,
  }
})

const whCenter = computed(() => warehouseCenter())

const selectedOrder = computed(() => orders.value.find((x) => x.id === selectedId.value) ?? null)

const visibleRoutes = computed(() => {
  return filteredOrders.value.filter((o) => o.status === 'on_way')
})

const destinationMarkers = computed(() => {
  return filteredOrders.value.map((o) => {
    const p = placeMap.value.get(o.buildingId)
    if (!p) return null
    const c = centerOfPlace(p)
    return { order: o, cx: c.cx, cy: c.cy, place: p }
  }).filter(Boolean) as { order: MockDeliveryOrder; cx: number; cy: number; place: CampusPlace }[]
})

const vehicleMarkers = computed(() => {
  return visibleRoutes.value.map((o) => {
    const p = placeMap.value.get(o.buildingId)
    if (!p) return null
    const dest = centerOfPlace(p)
    const t = 0.56
    const vx = whCenter.value.cx + (dest.cx - whCenter.value.cx) * t
    const vy = whCenter.value.cy + (dest.cy - whCenter.value.cy) * t
    return { order: o, vx, vy }
  }).filter(Boolean) as { order: MockDeliveryOrder; vx: number; vy: number }[]
})

function statusLabel(s: DelStatus) {
  const map: Record<DelStatus, string> = {
    pending: '待配送',
    on_way: '配送中',
    received: '已签收',
    exception: '异常',
  }
  return map[s]
}

function statusColorClass(s: DelStatus) {
  return `is-${s}`
}

const routeSegments = computed(() => {
  return visibleRoutes.value
    .map((o) => {
      const p = placeMap.value.get(o.buildingId)
      if (!p) return null
      const d = centerOfPlace(p)
      return {
        oid: o.id,
        x1: whCenter.value.cx,
        y1: whCenter.value.cy,
        x2: d.cx,
        y2: d.cy,
      }
    })
    .filter((x): x is { oid: string; x1: number; y1: number; x2: number; y2: number } => !!x)
})

function orderCountAtPlace(placeId: string) {
  return filteredOrders.value.filter((o) => o.buildingId === placeId).length
}

function selectOrder(id: string, fromMap = false) {
  selectedId.value = id
  const o = orders.value.find((x) => x.id === id)
  if (!o) return
  const p = placeMap.value.get(o.buildingId)
  if (p) {
    centerOnPoint(centerOfPlace(p).cx, centerOfPlace(p).cy)
    pulseBuildingId.value = o.buildingId
    if (pulseTimer) clearTimeout(pulseTimer)
    pulseTimer = setTimeout(() => {
      pulseBuildingId.value = null
      pulseTimer = null
    }, 1600)
  }
  if (!fromMap) return
  nextTick(() => {
    const el = listRef.value?.querySelector(`[data-order-id="${id}"]`)
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
  })
}

function centerOnPoint(cx: number, cy: number) {
  const { vw, vh } = stageSize()
  const s = scale.value
  panX.value = vw / 2 - cx * s
  panY.value = vh / 2 - cy * s
  clampView()
}

function onWheel(e: WheelEvent) {
  const { vw, vh } = stageSize()
  const oldS = scale.value
  const sMin = scaleMinForStage()
  const sMax = scaleMaxForStage()
  const factor = e.deltaY > 0 ? 0.92 : 1.08
  const newS = Math.min(sMax, Math.max(sMin, oldS * factor))
  if (newS === oldS) return
  const wx = (vw / 2 - panX.value) / oldS
  const wy = (vh / 2 - panY.value) / oldS
  scale.value = newS
  panX.value = vw / 2 - wx * newS
  panY.value = vh / 2 - wy * newS
  clampView()
}

function zoom(delta: number) {
  const { vw, vh } = stageSize()
  const oldS = scale.value
  const sMin = scaleMinForStage()
  const sMax = scaleMaxForStage()
  const newS = Math.min(sMax, Math.max(sMin, oldS * delta))
  if (newS === oldS) return
  const wx = (vw / 2 - panX.value) / oldS
  const wy = (vh / 2 - panY.value) / oldS
  scale.value = newS
  panX.value = vw / 2 - wx * newS
  panY.value = vh / 2 - wy * newS
  clampView()
}

function onMouseDown(e: MouseEvent) {
  const t = e.target as HTMLElement
  if (t.closest('.dm-zoom') || t.closest('button') || t.closest('.dm-pop') || t.closest('.dm-sel-hud')) return
  dragging.value = true
  dragStartX = e.clientX
  dragStartY = e.clientY
  panStartX = panX.value
  panStartY = panY.value
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
}

function onMouseMove(e: MouseEvent) {
  if (!dragging.value) return
  panX.value = panStartX + (e.clientX - dragStartX)
  panY.value = panStartY + (e.clientY - dragStartY)
  clampView()
}

function onMouseUp() {
  dragging.value = false
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  clampView()
}

function onPlaceClick(p: CampusPlace, e: MouseEvent) {
  e.stopPropagation()
  buildingPopup.value = { place: p, taskCount: orderCountAtPlace(p.id) }
}

function clearBuildingPopup() {
  buildingPopup.value = null
}

function onVehicleClick(o: MockDeliveryOrder, e: MouseEvent) {
  e.stopPropagation()
  selectOrder(o.id, true)
}

function onDestClick(o: MockDeliveryOrder, e: MouseEvent) {
  e.stopPropagation()
  selectOrder(o.id, true)
}

function blockStyle(p: CampusPlace) {
  return {
    left: `${p.x}px`,
    top: `${p.y}px`,
    width: `${p.w}px`,
    height: `${p.h}px`,
  }
}

function kindClass(p: CampusPlace) {
  return `dm-bld--${p.kind}`
}

let stageResizeObserver: ResizeObserver | null = null

onUnmounted(() => {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  if (pulseTimer) clearTimeout(pulseTimer)
  stageResizeObserver?.disconnect()
  stageResizeObserver = null
})

watch(filterKey, () => {
  buildingPopup.value = null
})

watch(filteredOrders, () => {
  if (selectedId.value && !filteredOrders.value.some((o) => o.id === selectedId.value)) {
    selectedId.value = null
  }
})

/** 行道树 / 绿化点（伪随机可复现） */
const treeDots = ref<{ x: number; y: number; r: number }[]>([])
function initTreeDots() {
  const out: { x: number; y: number; r: number }[] = []
  let seed = 20260415
  function rnd() {
    seed = (seed * 48271) % 2147483647
    return seed / 2147483647
  }
  function cluster(x0: number, y0: number, w: number, h: number, n: number) {
    for (let i = 0; i < n; i++) {
      out.push({
        x: x0 + rnd() * w,
        y: y0 + rnd() * h,
        r: 2.2 + rnd() * 2.8,
      })
    }
  }
  /* 绿化点落在草地地块内，避开 SVG 主路带（约 y470–542、652–712） */
  cluster(56, 118, 292, 300, 48)
  cluster(418, 118, 430, 300, 62)
  cluster(938, 118, 300, 300, 52)
  cluster(1320, 118, 300, 280, 36)
  cluster(418, 788, 820, 200, 42)
  treeDots.value = out
}

onMounted(() => {
  initTreeDots()
  const el = stageRef.value
  if (el && typeof ResizeObserver !== 'undefined') {
    stageResizeObserver = new ResizeObserver(() => clampView())
    stageResizeObserver.observe(el)
  }
  nextTick(() => {
    scale.value = scaleMinForStage()
    clampView()
    centerOnPoint(whCenter.value.cx, whCenter.value.cy)
  })
})
</script>

<template>
  <div class="dm-page">
    <header class="dm-top">
      <div>
        <h1 class="dm-title">配送地图</h1>
        <p class="dm-sub">
          华东理工大学徐汇校区 · 校园配送手绘平面图 · 画布 1920×1200 · 视图范围已锁定
        </p>
      </div>
    </header>

    <section class="dm-stats">
      <div class="dm-stat dm-stat--blue">
        <span class="dm-stat__val">{{ stats.total }}</span>
        <span class="dm-stat__lab">今日总配送单</span>
      </div>
      <div class="dm-stat dm-stat--amber">
        <span class="dm-stat__val">{{ stats.pending }}</span>
        <span class="dm-stat__lab">待配送订单</span>
      </div>
      <div class="dm-stat dm-stat--cyan">
        <span class="dm-stat__val">{{ stats.onWay }}</span>
        <span class="dm-stat__lab">配送中订单</span>
      </div>
      <div class="dm-stat dm-stat--green">
        <span class="dm-stat__val">{{ stats.received }}</span>
        <span class="dm-stat__lab">已签收订单</span>
      </div>
      <div class="dm-stat dm-stat--rose">
        <span class="dm-stat__val">{{ stats.exception }}</span>
        <span class="dm-stat__lab">异常 / 预警订单</span>
      </div>
    </section>

    <div class="dm-body">
      <aside class="dm-side">
        <div class="dm-filters">
          <span class="dm-filters__lab">状态</span>
          <el-radio-group v-model="filterKey" size="small" class="dm-filters__rg">
            <el-radio-button label="all">全部</el-radio-button>
            <el-radio-button label="pending">待配送</el-radio-button>
            <el-radio-button label="on_way">配送中</el-radio-button>
            <el-radio-button label="received">已签收</el-radio-button>
            <el-radio-button label="exception">异常</el-radio-button>
          </el-radio-group>
        </div>
        <div ref="listRef" class="dm-list">
          <div
            v-for="o in filteredOrders"
            :key="o.id"
            class="dm-li"
            :class="[statusColorClass(o.status), { active: selectedId === o.id }]"
            :data-order-id="o.id"
            @click="selectOrder(o.id, true)"
          >
            <div class="dm-li__row">
              <span class="dm-li__no">{{ o.delivery_no }}</span>
              <span class="dm-li__tag" :class="statusColorClass(o.status)">{{ statusLabel(o.status) }}</span>
            </div>
            <div class="dm-li__dest">{{ o.destination }}</div>
            <div class="dm-li__meta">收货人：{{ o.receiver }} · 交接码 <code>{{ o.handoff_code }}</code></div>
          </div>
          <div v-if="!filteredOrders.length" class="dm-list__empty">当前筛选下暂无订单</div>
        </div>
      </aside>

      <section class="dm-map-wrap">
        <div class="dm-map-chrome" aria-hidden="true">
          <div class="dm-compass">
            <span class="dm-compass__n">N</span>
            <span class="dm-compass__sub">上北下南</span>
          </div>
          <div class="dm-scale">比例示意 · 约 1 : 2500</div>
        </div>
        <div
          ref="stageRef"
          class="dm-stage"
          :class="{ dragging }"
          @wheel.prevent="onWheel"
          @mousedown="onMouseDown"
        >
          <div
            class="dm-world"
            :style="{
              width: MAP_W + 'px',
              height: MAP_H + 'px',
              transform: `translate(${panX}px, ${panY}px) scale(${scale})`,
            }"
          >
            <!-- 底图：点击空白处关闭建筑气泡 -->
            <div class="dm-bg" @click="clearBuildingPopup" />

            <!-- 校园平面图基底（水体 / 绿化 / 道路 / 操场） -->
            <svg class="dm-basemap" :width="MAP_W" :height="MAP_H" aria-hidden="true">
              <defs>
                <pattern id="dm-grass-dots" width="16" height="16" patternUnits="userSpaceOnUse">
                  <rect width="16" height="16" fill="#1a2e22" />
                  <circle cx="4" cy="5" r="1.6" fill="#2f6b42" opacity="0.72" />
                  <circle cx="12" cy="11" r="1.3" fill="#225c36" opacity="0.62" />
                  <circle cx="8" cy="3" r="1" fill="#4a8c55" opacity="0.45" />
                </pattern>
                <linearGradient id="dm-paper" x1="0" y1="0" :x2="MAP_W" :y2="MAP_H" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stop-color="#2a3d52" />
                  <stop offset="40%" stop-color="#1e2d3f" />
                  <stop offset="100%" stop-color="#141d2a" />
                </linearGradient>
                <linearGradient id="dm-lake" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stop-color="#2a5f8f" />
                  <stop offset="50%" stop-color="#153a5c" />
                  <stop offset="100%" stop-color="#0c1f33" />
                </linearGradient>
                <linearGradient id="dm-road" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stop-color="#6b7588" />
                  <stop offset="100%" stop-color="#4a5568" />
                </linearGradient>
              </defs>

              <rect x="0" y="0" :width="MAP_W" :height="MAP_H" fill="url(#dm-paper)" />
              <rect
                :x="20"
                :y="22"
                :width="MAP_W - 40"
                :height="MAP_H - 44"
                rx="12"
                fill="none"
                stroke="#7c8ca0"
                stroke-width="2"
                opacity="0.42"
              />
              <rect
                :x="28"
                :y="30"
                :width="MAP_W - 56"
                :height="MAP_H - 60"
                rx="9"
                fill="none"
                stroke="#475569"
                stroke-width="1"
                opacity="0.5"
                stroke-dasharray="12 8"
              />

              <g :transform="basemapInnerTransform">
                <!-- 大草坪区 -->
                <path
                  d="M 40 300 Q 120 260 260 280 L 620 300 Q 720 310 780 360 L 760 520 Q 700 560 520 560 L 180 540 Q 60 520 40 400 Z"
                  fill="url(#dm-grass-dots)"
                  opacity="0.9"
                />
                <path
                  d="M 820 120 Q 980 100 1180 140 L 1560 180 Q 1640 200 1650 280 L 1620 420 Q 1500 460 1280 440 L 900 400 Q 820 360 820 120 Z"
                  fill="url(#dm-grass-dots)"
                  opacity="0.86"
                />
                <path
                  d="M 480 680 Q 720 640 1120 700 L 1580 720 Q 1660 740 1670 820 L 1650 1000 L 500 980 Q 420 920 480 680 Z"
                  fill="url(#dm-grass-dots)"
                  opacity="0.88"
                />

                <ellipse cx="1220" cy="640" rx="118" ry="58" fill="url(#dm-lake)" stroke="#3d5a73" stroke-width="2" opacity="0.92" />
                <ellipse cx="1220" cy="640" rx="78" ry="34" fill="#0a1624" opacity="0.4" />

                <path
                  d="M -20 508 L 720 498 Q 900 492 1100 502 L 1700 512"
                  stroke="#0f172a"
                  stroke-width="46"
                  stroke-linecap="round"
                  fill="none"
                  opacity="0.88"
                />
                <path
                  d="M -20 508 L 720 498 Q 900 492 1100 502 L 1700 512"
                  stroke="url(#dm-road)"
                  stroke-width="34"
                  stroke-linecap="round"
                  fill="none"
                />
                <path
                  d="M -20 508 L 720 498 Q 900 492 1100 502 L 1700 512"
                  stroke="#fde68a"
                  stroke-width="2"
                  stroke-dasharray="10 16"
                  fill="none"
                  opacity="0.42"
                />

                <path
                  d="M -20 678 L 1680 688"
                  stroke="#0f172a"
                  stroke-width="34"
                  stroke-linecap="round"
                  fill="none"
                  opacity="0.78"
                />
                <path d="M -20 678 L 1680 688" stroke="url(#dm-road)" stroke-width="24" stroke-linecap="round" fill="none" />
                <path d="M -20 678 L 1680 688" stroke="#fde68a" stroke-width="1.5" stroke-dasharray="8 14" fill="none" opacity="0.32" />

                <path d="M 392 -20 L 382 1060" stroke="#0f172a" stroke-width="38" stroke-linecap="round" opacity="0.82" />
                <path d="M 392 -20 L 382 1060" stroke="url(#dm-road)" stroke-width="28" stroke-linecap="round" />
                <path d="M 908 -20 L 898 1060" stroke="#0f172a" stroke-width="36" stroke-linecap="round" opacity="0.78" />
                <path d="M 908 -20 L 898 1060" stroke="url(#dm-road)" stroke-width="26" stroke-linecap="round" />
                <path d="M 1288 -20 L 1278 1060" stroke="#0f172a" stroke-width="28" stroke-linecap="round" opacity="0.7" />
                <path d="M 1288 -20 L 1278 1060" stroke="url(#dm-road)" stroke-width="18" stroke-linecap="round" />

                <path
                  d="M 520 420 Q 680 380 880 430"
                  stroke="#cbd5e1"
                  stroke-width="5"
                  stroke-dasharray="4 8"
                  fill="none"
                  opacity="0.2"
                />
                <path
                  d="M 600 560 Q 820 520 1040 580"
                  stroke="#cbd5e1"
                  stroke-width="4"
                  stroke-dasharray="3 7"
                  fill="none"
                  opacity="0.18"
                />

                <ellipse cx="1390" cy="128" rx="138" ry="72" fill="none" stroke="#5c6b82" stroke-width="14" opacity="0.5" />
                <ellipse cx="1390" cy="128" rx="138" ry="72" fill="none" stroke="#94a3b8" stroke-width="3" stroke-dasharray="8 10" opacity="0.38" />
                <ellipse cx="1390" cy="128" rx="92" ry="46" fill="#0f172a" opacity="0.32" />

                <circle v-for="(t, i) in treeDots" :key="'tr' + i" :cx="t.x" :cy="t.y" :r="t.r" fill="#166534" opacity="0.52" />
              </g>
            </svg>

            <!-- 建筑 -->
            <button
              v-for="p in campusPlaces"
              :key="p.id"
              type="button"
              class="dm-bld"
              :class="[kindClass(p), { 'is-pulse': pulseBuildingId === p.id, 'is-hub': p.id === WAREHOUSE_ID }]"
              :style="blockStyle(p)"
              @click="onPlaceClick(p, $event)"
            >
              <span class="dm-bld__roof" aria-hidden="true" />
              <span class="dm-bld__mid">{{ p.short }}</span>
              <span class="dm-bld__cap">{{ p.name }}</span>
            </button>

            <!-- 路线 -->
            <svg class="dm-svg" :width="MAP_W" :height="MAP_H" aria-hidden="true">
              <line
                v-for="seg in routeSegments"
                :key="'ln-' + seg.oid"
                :x1="seg.x1"
                :y1="seg.y1"
                :x2="seg.x2"
                :y2="seg.y2"
                class="dm-line"
              />
            </svg>

            <!-- 目的地点位 -->
            <button
              v-for="m in destinationMarkers"
              :key="'mk-' + m.order.id"
              type="button"
              class="dm-pin"
              :class="[statusColorClass(m.order.status), { active: selectedId === m.order.id }]"
              :style="{ left: m.cx + 'px', top: m.cy + 'px' }"
              @click="onDestClick(m.order, $event)"
            />

            <!-- 配送车 -->
            <button
              v-for="v in vehicleMarkers"
              :key="'vh-' + v.order.id"
              type="button"
              class="dm-van"
              :class="{ active: selectedId === v.order.id }"
              :style="{ left: v.vx + 'px', top: v.vy + 'px' }"
              title="配送中"
              @click="onVehicleClick(v.order, $event)"
            >
              <el-icon><Van /></el-icon>
            </button>

            <!-- 建筑信息气泡（地图坐标系内） -->
            <div
              v-if="buildingPopup"
              class="dm-pop"
              :style="{
                left: buildingPopup.place.x + buildingPopup.place.w / 2 + 'px',
                top: buildingPopup.place.y - 8 + 'px',
              }"
              @click.stop
            >
              <strong>{{ buildingPopup.place.name }}</strong>
              <p>当前筛选下配送任务：<b>{{ buildingPopup.taskCount }}</b> 单</p>
              <el-button size="small" text type="primary" @click="buildingPopup = null">关闭</el-button>
            </div>

            <!-- 选中订单简要（地图内） -->
            <div v-if="selectedOrder" class="dm-sel-hud" @click.stop>
              <div class="dm-sel-hud__t">{{ selectedOrder.delivery_no }}</div>
              <div>{{ selectedOrder.destination }}</div>
              <div class="dm-sel-hud__m">
                物资：{{ selectedOrder.materialType }} · 数量 {{ selectedOrder.qty }}
              </div>
              <div>状态：{{ statusLabel(selectedOrder.status) }}</div>
              <div v-if="selectedOrder.signedAt">签收：{{ selectedOrder.signedAt }}</div>
              <div v-else>签收：—</div>
            </div>
          </div>

          <div class="dm-zoom">
            <el-button class="dm-zoom__btn" circle size="small" @click.stop="zoom(1.12)">
              <el-icon><ZoomIn /></el-icon>
            </el-button>
            <el-button class="dm-zoom__btn" circle size="small" @click.stop="zoom(1 / 1.12)">
              <el-icon><ZoomOut /></el-icon>
            </el-button>
          </div>

          <div class="dm-legend">
            <span><i class="dot dot--blue" />配送中</span>
            <span><i class="dot dot--amber" />待配送</span>
            <span><i class="dot dot--green" />已签收</span>
            <span><i class="dot dot--rose" />异常</span>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.dm-page {
  min-height: calc(100vh - 100px);
  padding: 16px 20px 24px;
  background: linear-gradient(165deg, #0b1220 0%, #111827 42%, #0f172a 100%);
  color: #e2e8f0;
}

.dm-top {
  margin-bottom: 14px;
}
.dm-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: 0.02em;
  color: #f8fafc;
}
.dm-sub {
  margin: 6px 0 0;
  font-size: 12px;
  color: #94a3b8;
}

.dm-stats {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}
@media (max-width: 1100px) {
  .dm-stats {
    grid-template-columns: repeat(2, 1fr);
  }
}
.dm-stat {
  border-radius: 12px;
  padding: 14px 16px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(30, 41, 59, 0.55);
  backdrop-filter: blur(8px);
}
.dm-stat__val {
  display: block;
  font-size: 28px;
  font-weight: 800;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}
.dm-stat__lab {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 4px;
  display: block;
}
.dm-stat--blue .dm-stat__val {
  color: #60a5fa;
}
.dm-stat--amber .dm-stat__val {
  color: #fbbf24;
}
.dm-stat--cyan .dm-stat__val {
  color: #38bdf8;
}
.dm-stat--green .dm-stat__val {
  color: #4ade80;
}
.dm-stat--rose .dm-stat__val {
  color: #fb7185;
}

.dm-body {
  display: grid;
  grid-template-columns: minmax(260px, 26%) 1fr;
  gap: 16px;
  min-height: 640px;
}
@media (max-width: 960px) {
  .dm-body {
    grid-template-columns: 1fr;
  }
}

.dm-side {
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: rgba(15, 23, 42, 0.65);
  border: 1px solid rgba(71, 85, 105, 0.45);
  border-radius: 14px;
  padding: 12px;
}
.dm-filters {
  margin-bottom: 10px;
}
.dm-filters__lab {
  display: block;
  font-size: 11px;
  color: #64748b;
  margin-bottom: 6px;
}
.dm-filters__rg {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.dm-list {
  flex: 1;
  overflow-y: auto;
  scrollbar-width: thin;
  padding-right: 4px;
}
.dm-list__empty {
  padding: 24px;
  text-align: center;
  color: #64748b;
  font-size: 13px;
}
.dm-li {
  padding: 10px 12px;
  margin-bottom: 8px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: rgba(30, 41, 59, 0.5);
  cursor: pointer;
  transition:
    border-color 0.15s,
    background 0.15s;
}
.dm-li:hover {
  border-color: rgba(96, 165, 250, 0.35);
}
.dm-li.active {
  border-color: rgba(56, 189, 248, 0.85);
  background: rgba(14, 116, 144, 0.25);
}
.dm-li__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.dm-li__no {
  font-weight: 700;
  font-size: 13px;
  color: #7dd3fc;
}
.dm-li__tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  font-weight: 600;
}
.dm-li__tag.is-pending {
  background: rgba(251, 191, 36, 0.2);
  color: #fcd34d;
}
.dm-li__tag.is-on_way {
  background: rgba(59, 130, 246, 0.25);
  color: #93c5fd;
}
.dm-li__tag.is-received {
  background: rgba(34, 197, 94, 0.2);
  color: #86efac;
}
.dm-li__tag.is-exception {
  background: rgba(244, 63, 94, 0.2);
  color: #fda4af;
}
.dm-li__dest {
  margin-top: 6px;
  font-size: 12px;
  color: #cbd5e1;
  line-height: 1.45;
}
.dm-li__meta {
  margin-top: 4px;
  font-size: 11px;
  color: #64748b;
}
.dm-li__meta code {
  color: #a5b4fc;
  font-weight: 600;
}

.dm-map-wrap {
  position: relative;
  border-radius: 14px;
  border: 1px solid rgba(71, 85, 105, 0.45);
  background: rgba(15, 23, 42, 0.45);
  overflow: hidden;
  min-height: 640px;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.04),
    0 20px 50px rgba(0, 0, 0, 0.35);
}

.dm-map-chrome {
  position: absolute;
  top: 10px;
  right: 12px;
  z-index: 25;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  pointer-events: none;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.65);
}
.dm-compass {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: 2px solid rgba(148, 163, 184, 0.45);
  background: rgba(15, 23, 42, 0.75);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  line-height: 1;
}
.dm-compass__n {
  font-size: 18px;
  font-weight: 800;
  color: #fca5a5;
}
.dm-compass__sub {
  font-size: 8px;
  color: #94a3b8;
  margin-top: 2px;
}
.dm-scale {
  font-size: 10px;
  color: #94a3b8;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.75);
  border: 1px solid rgba(71, 85, 105, 0.55);
}

.dm-stage {
  position: relative;
  width: 100%;
  height: min(72vh, 720px);
  min-height: 560px;
  overflow: hidden;
  cursor: grab;
  background: radial-gradient(ellipse 80% 60% at 50% 40%, #1a2332 0%, #0f141c 100%);
}
.dm-stage.dragging {
  cursor: grabbing;
}

.dm-world {
  position: absolute;
  left: 0;
  top: 0;
  transform-origin: 0 0;
  will-change: transform;
}

.dm-bg {
  position: absolute;
  inset: 0;
  z-index: 0;
  cursor: default;
  background:
    radial-gradient(ellipse 55% 40% at 50% 0%, rgba(148, 163, 184, 0.08), transparent 55%),
    radial-gradient(ellipse 45% 35% at 12% 88%, rgba(52, 211, 153, 0.05), transparent 50%),
    linear-gradient(188deg, #1c2736 0%, #141c28 45%, #0c1018 100%);
  border-radius: 4px;
}

.dm-basemap {
  position: absolute;
  left: 0;
  top: 0;
  z-index: 1;
  pointer-events: none;
  filter: saturate(1.05);
}

.dm-bld {
  position: absolute;
  z-index: 5;
  margin: 0;
  padding: 0 0 38px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  box-sizing: border-box;
  text-align: center;
  transition:
    filter 0.15s,
    transform 0.15s;
}
.dm-bld:hover {
  filter: brightness(1.06);
  transform: translateY(-0.5px);
}
.dm-bld:focus-visible {
  outline: 2px solid #38bdf8;
  outline-offset: 2px;
}
.dm-bld__roof {
  height: 10px;
  border-radius: 7px 7px 0 0;
  background: linear-gradient(90deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.04));
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-bottom: none;
  flex-shrink: 0;
}
.dm-bld__mid {
  flex: 1;
  min-height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 800;
  letter-spacing: 0.03em;
  color: #f8fafc;
  text-shadow:
    0 1px 2px rgba(0, 0, 0, 0.85),
    0 0 12px rgba(0, 0, 0, 0.35);
  border-radius: 0 0 10px 10px;
  border: 1px solid rgba(148, 163, 184, 0.45);
  border-top: none;
  box-shadow:
    0 4px 10px rgba(0, 0, 0, 0.38),
    inset 0 1px 0 rgba(255, 255, 255, 0.08);
}
.dm-bld__cap {
  position: absolute;
  left: 50%;
  bottom: 0;
  transform: translateX(-50%);
  width: max-content;
  max-width: min(220px, 155%);
  font-size: 12px;
  line-height: 1.3;
  font-weight: 600;
  color: #f1f5f9;
  background: rgba(15, 23, 42, 0.96);
  padding: 4px 10px;
  border-radius: 7px;
  white-space: normal;
  text-align: center;
  word-break: keep-all;
  border: 1px solid rgba(71, 85, 105, 0.85);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
  pointer-events: none;
}
.dm-bld--hub .dm-bld__mid {
  background: linear-gradient(165deg, #3b82f6 0%, #1d4ed8 55%, #172554 100%);
  border-color: rgba(147, 197, 253, 0.55);
  box-shadow:
    0 0 12px rgba(37, 99, 235, 0.28),
    0 5px 12px rgba(0, 0, 0, 0.4),
    inset 0 1px 0 rgba(255, 255, 255, 0.12);
  z-index: 6;
}
.dm-bld--hub {
  z-index: 6;
}
.dm-bld--admin .dm-bld__mid {
  background: linear-gradient(180deg, #64748b, #475569 70%, #334155);
}
.dm-bld--college .dm-bld__mid {
  background: linear-gradient(180deg, #6366f1 0%, #4338ca 100%);
}
.dm-bld--teach .dm-bld__mid {
  background: linear-gradient(180deg, #0ea5e9, #0369a1);
}
.dm-bld--lab .dm-bld__mid {
  background: linear-gradient(180deg, #10b981, #047857);
}
.dm-bld--life .dm-bld__mid {
  background: linear-gradient(180deg, #f59e0b, #b45309);
  color: #fffbeb;
}
.dm-bld--sport .dm-bld__mid {
  background: linear-gradient(180deg, #ec4899, #9d174d);
}
.dm-bld--service .dm-bld__mid {
  background: linear-gradient(180deg, #64748b, #334155);
}
.dm-bld--plaza .dm-bld__mid {
  background: linear-gradient(180deg, rgba(148, 163, 184, 0.35), rgba(51, 65, 85, 0.55));
  border-style: dashed;
  color: #e2e8f0;
}
.dm-bld.is-pulse .dm-bld__mid {
  animation: dm-pulse 0.9s ease-in-out 2;
}
@keyframes dm-pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.45);
  }
  70% {
    box-shadow: 0 0 0 14px rgba(56, 189, 248, 0);
  }
  100% {
    box-shadow: 0 0 0 0 rgba(56, 189, 248, 0);
  }
}

.dm-svg {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
  z-index: 4;
}
.dm-line {
  stroke: rgba(56, 189, 248, 0.55);
  stroke-width: 3;
  stroke-dasharray: 10 8;
}

.dm-pin {
  position: absolute;
  width: 16px;
  height: 16px;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  cursor: pointer;
  z-index: 6;
  box-shadow: 0 0 0 2px rgba(15, 23, 42, 0.9);
}
.dm-pin.is-pending {
  background: #fbbf24;
}
.dm-pin.is-on_way {
  background: #38bdf8;
}
.dm-pin.is-received {
  background: #4ade80;
}
.dm-pin.is-exception {
  background: #fb7185;
}
.dm-pin.active {
  box-shadow: 0 0 0 3px #fff;
}

.dm-van {
  position: absolute;
  width: 36px;
  height: 36px;
  margin: 0;
  padding: 0;
  border: none;
  border-radius: 10px;
  transform: translate(-50%, -50%);
  background: rgba(37, 99, 235, 0.92);
  color: #e0f2fe;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 7;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
  animation: dm-van-float 2.4s ease-in-out infinite;
}
.dm-van:hover {
  filter: brightness(1.1);
}
.dm-van.active {
  outline: 2px solid #fbbf24;
}
@keyframes dm-van-float {
  0%,
  100% {
    transform: translate(-50%, -50%) translateY(0);
  }
  50% {
    transform: translate(-50%, -50%) translateY(-3px);
  }
}

.dm-pop {
  position: absolute;
  transform: translate(-50%, -100%);
  z-index: 12;
  min-width: 200px;
  max-width: 260px;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.95);
  border: 1px solid rgba(125, 211, 252, 0.35);
  font-size: 12px;
  color: #cbd5e1;
  box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
}
.dm-pop p {
  margin: 6px 0 0;
  line-height: 1.4;
}

.dm-sel-hud {
  position: absolute;
  right: 12px;
  bottom: 12px;
  width: 260px;
  z-index: 11;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.35);
  font-size: 11px;
  line-height: 1.45;
  color: #cbd5e1;
}
.dm-sel-hud__t {
  font-weight: 700;
  color: #7dd3fc;
  margin-bottom: 4px;
  font-size: 12px;
}
.dm-sel-hud__m {
  margin: 4px 0;
  color: #94a3b8;
}

.dm-zoom {
  position: absolute;
  right: 12px;
  bottom: 52px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 20;
}
.dm-zoom__btn {
  background: rgba(30, 41, 59, 0.9) !important;
  border: 1px solid rgba(148, 163, 184, 0.35) !important;
  color: #e2e8f0 !important;
}

.dm-legend {
  position: absolute;
  left: 12px;
  bottom: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 11px;
  color: #94a3b8;
  z-index: 20;
}
.dm-legend .dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}
.dot--blue {
  background: #38bdf8;
}
.dot--amber {
  background: #fbbf24;
}
.dot--green {
  background: #4ade80;
}
.dot--rose {
  background: #fb7185;
}
</style>
