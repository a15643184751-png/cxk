<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Goods, Refresh } from '@element-plus/icons-vue'
import { confirmDeliveryReceive } from '@/api/delivery'
import type { Purchase } from '@/api/purchase'
import { orderFourState, orderStatusPillClass } from './teacherOrderUi'
import { mergeTeacherOrderList } from './teacherDemoOrders'
import { catalogImageForGoodsName } from './teacherDemoCatalog'

const router = useRouter()
const loading = ref(false)
const tableData = ref<Purchase[]>([])
const filterKey = ref<'all' | 'pending' | 'receiving' | 'completed'>('all')
const displayLimit = ref(10)

async function fetchData() {
  loading.value = true
  try {
    // 个人中心仅合并展示当前账号相关订单与本地缓存行
    tableData.value = mergeTeacherOrderList([])
  } catch {
    tableData.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void fetchData()
})

watch(filterKey, () => {
  displayLimit.value = 10
})

function matchesFilter(p: Purchase): boolean {
  const f = orderFourState(p)
  if (filterKey.value === 'all') return true
  if (filterKey.value === 'pending') return f === 'pending'
  if (filterKey.value === 'receiving') return f === 'receiving'
  if (filterKey.value === 'completed') return f === 'completed'
  return false
}

const filteredList = computed(() => tableData.value.filter((p) => matchesFilter(p)))

const visibleList = computed(() => filteredList.value.slice(0, displayLimit.value))

const hasMore = computed(() => filteredList.value.length > displayLimit.value)

function loadMore() {
  displayLimit.value += 8
}

function goDetail(p: Purchase) {
  router.push({ path: `/teacher/personal/order/${p.id}` })
}

async function handleReceive(row: Purchase) {
  if (row.id < 0) {
    ElMessage.info('该订单无需线上签收')
    return
  }
  if (!row.delivery_id) return
  try {
    await confirmDeliveryReceive(row.delivery_id)
    ElMessage.success('已确认收货')
    await fetchData()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '操作失败')
  }
}

function remind() {
  ElMessage.success('已通知后勤催单')
}

function repurchase(row: Purchase) {
  router.push({
    path: '/teacher/workbench',
    query: { prefill: `复购订单 ${row.order_no}` },
  })
}

type Act = 'detail' | 'remind' | 'receive' | 'repurchase'

function actionsFor(p: Purchase): Act[] {
  const f = orderFourState(p)
  if (f === 'cancelled') return ['detail']
  if (f === 'completed') return ['detail', 'repurchase']
  if (f === 'pending') return ['detail', 'remind']
  if (p.can_confirm_receive) return ['detail', 'receive']
  return ['detail', 'remind']
}

function runAction(p: Purchase, a: Act) {
  if (a === 'detail') goDetail(p)
  if (a === 'remind') remind()
  if (a === 'receive') void handleReceive(p)
  if (a === 'repurchase') repurchase(p)
}

function labelFor(a: Act) {
  const m: Record<Act, string> = {
    detail: '查看详情',
    remind: '催单',
    receive: '确认收货',
    repurchase: '复购',
  }
  return m[a]
}

function thumbSrc(p: Purchase): string | undefined {
  const first = p.items?.[0]
  if (!first) return undefined
  return first.image || catalogImageForGoodsName(first.goods_name)
}

function itemThumbs(p: Purchase): string[] {
  return (p.items || [])
    .map((it) => it.image || catalogImageForGoodsName(it.goods_name))
    .filter((src): src is string => Boolean(src))
}
</script>

<template>
  <div class="orders-panel">
    <div class="panel-toolbar">
      <el-radio-group v-model="filterKey" size="default" class="filter-group">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="pending">待审批</el-radio-button>
        <el-radio-button value="receiving">待收货</el-radio-button>
        <el-radio-button value="completed">已完成</el-radio-button>
      </el-radio-group>
      <div class="toolbar-right">
        <el-button :icon="Refresh" circle @click="fetchData" title="刷新" />
        <el-button type="primary" @click="router.push('/teacher/workbench')">去申领</el-button>
      </div>
    </div>

    <div v-loading="loading" class="card-list">
      <p v-if="!loading && !filteredList.length" class="empty-hint">暂无订单</p>

      <article v-for="row in visibleList" :key="row.id" class="order-card">
        <div class="card-body" @click="goDetail(row)">
          <div class="goods-thumb goods-thumb--main">
            <img v-if="thumbSrc(row)" :src="thumbSrc(row)" alt="" class="thumb-img" />
            <el-icon v-else class="thumb-ph" :size="30"><Goods /></el-icon>
          </div>
          <div class="goods-main">
            <div class="meta-row">
              <span class="meta-item">申请人：{{ row.applicant_name || '当前账号' }}</span>
              <span class="meta-item">申请日期：{{ row.created_at ? row.created_at.slice(0, 10) : '—' }}</span>
            </div>
            <div class="goods-lines">
              <p v-for="(it, idx) in row.items || []" :key="idx" class="goods-line">
                {{ it.goods_name }} × {{ it.quantity }}{{ it.unit }}
              </p>
              <p v-if="!(row.items && row.items.length)" class="goods-line muted">暂无明细</p>
            </div>
            <div class="thumb-strip" v-if="itemThumbs(row).length">
              <div v-for="(src, i) in itemThumbs(row).slice(0, 4)" :key="i" class="goods-thumb goods-thumb--sub">
                <img :src="src" alt="" class="thumb-img" />
              </div>
              <div v-if="itemThumbs(row).length > 4" class="goods-thumb goods-thumb--more">
                +{{ itemThumbs(row).length - 4 }}
              </div>
            </div>
            <div class="status-row">
              <span class="status-label">状态</span>
              <span class="status-pill" :class="orderStatusPillClass(orderFourState(row)).class">
                {{ orderStatusPillClass(orderFourState(row)).label }}
              </span>
            </div>
          </div>
        </div>
        <footer class="card-actions">
          <el-button
            v-for="a in actionsFor(row)"
            :key="a"
            :type="a === 'receive' ? 'success' : a === 'repurchase' ? 'primary' : 'default'"
            round
            @click="runAction(row, a)"
          >
            {{ labelFor(a) }}
          </el-button>
        </footer>
      </article>

      <div v-if="hasMore" class="load-more-wrap">
        <el-button class="load-more" round @click="loadMore">加载更多</el-button>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.orders-panel {
  padding: 0;
}
.panel-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}
.filter-group {
  flex: 1;
  min-width: 0;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.card-list {
  min-height: 120px;
}
.empty-hint {
  text-align: center;
  color: var(--text-muted);
  font-size: 14px;
  padding: 48px 0;
}
.order-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-card);
}
.card-body {
  display: flex;
  gap: 20px;
  align-items: flex-start;
  cursor: pointer;
}
.goods-thumb {
  width: 96px;
  height: 96px;
  border-radius: 12px;
  background: #f4f4f5;
  border: 1px solid #e4e4e7;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  overflow: hidden;
}
.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.thumb-ph {
  color: #a1a1aa;
}
.goods-thumb--main {
  width: 110px;
  height: 110px;
}
.goods-thumb--sub {
  width: 56px;
  height: 56px;
}
.goods-thumb--more {
  width: 56px;
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  color: #52525b;
  background: #f4f4f5;
}
.goods-main {
  flex: 1;
  min-width: 0;
}
.meta-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
  margin-bottom: 10px;
}
.meta-item {
  font-size: 12px;
  color: var(--text-muted);
}
.goods-lines {
  margin-bottom: 12px;
}
.goods-line {
  margin: 0 0 6px;
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.45;
  word-break: break-all;
  &.muted {
    font-weight: 400;
    color: var(--text-muted);
  }
}
.thumb-strip {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.status-label {
  font-size: 13px;
  color: var(--text-muted);
}
.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 8px 18px;
  border-radius: 10px;
  font-size: 16px;
  font-weight: 800;
  letter-spacing: 0.03em;
}
.pill--pending {
  background: #fff7ed;
  color: #c2410c;
  border: 1px solid #fdba74;
}
.pill--receiving {
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #93c5fd;
}
.pill--completed {
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #6ee7b7;
}
.pill--cancelled {
  background: #f4f4f5;
  color: #52525b;
  border: 1px solid #d4d4d8;
}
.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
  padding-top: 16px;
  border-top: 1px solid var(--border-subtle);
}
.load-more-wrap {
  text-align: center;
  padding: 8px 0 24px;
}
.load-more {
  min-width: 200px;
}
@media (max-width: 520px) {
  .filter-group {
    width: 100%;
  }
  .card-body {
    gap: 12px;
  }
  .goods-thumb--main {
    width: 88px;
    height: 88px;
  }
  :deep(.el-radio-button__inner) {
    padding: 8px 12px;
    font-size: 13px;
  }
}
</style>
