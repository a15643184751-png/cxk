<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { DEMO_ASSETS, type DemoAsset, type DemoAssetStatus } from './teacherAssetDemo'

const router = useRouter()

const filterKey = ref<'all' | DemoAssetStatus>('all')

const filtered = computed(() =>
  DEMO_ASSETS.filter((r) => {
    if (filterKey.value === 'all') return true
    return r.status === filterKey.value
  })
)

function tagFor(s: DemoAssetStatus) {
  if (s === 'ok') return { label: '正常使用', class: 'pill--ok' }
  if (s === 'soon') return { label: '即将到期', class: 'pill--soon' }
  if (s === 'overdue') return { label: '已逾期', class: 'pill--overdue' }
  return { label: '已归还', class: 'pill--returned' }
}

function goDetail(row: DemoAsset) {
  router.push({ path: `/teacher/personal/asset/${row.id}` })
}

function demo(msg: string) {
  ElMessage.success(msg)
}

function actionsFor(row: DemoAsset): Array<'detail' | 'renew' | 'return'> {
  if (row.status === 'returned') return ['detail']
  return ['detail', 'renew', 'return']
}

function run(row: DemoAsset, a: 'detail' | 'renew' | 'return') {
  if (a === 'detail') goDetail(row)
  if (a === 'renew') demo('续借')
  if (a === 'return') demo('归还')
}

function label(a: 'detail' | 'renew' | 'return') {
  return { detail: '详情', renew: '续借', return: '归还' }[a]
}
</script>

<template>
  <div class="assets-panel">
    <div class="panel-toolbar">
      <el-radio-group v-model="filterKey" size="default" class="filter-group">
        <el-radio-button value="all">全部</el-radio-button>
        <el-radio-button value="ok">正常使用</el-radio-button>
        <el-radio-button value="soon">即将到期</el-radio-button>
        <el-radio-button value="overdue">已逾期</el-radio-button>
        <el-radio-button value="returned">已归还</el-radio-button>
      </el-radio-group>
      <el-button :icon="Refresh" circle title="刷新" @click="demo('列表已刷新')" />
    </div>

    <div class="card-list">
      <p v-if="!filtered.length" class="empty-hint">暂无领用记录</p>

      <article v-for="row in filtered" :key="row.id" class="asset-card">
        <div class="card-body" @click="goDetail(row)">
          <div class="goods-thumb">
            <img :src="row.image" :alt="row.name" class="thumb-img" />
          </div>
          <div class="goods-main">
            <p class="asset-name">{{ row.name }}</p>
            <p class="asset-spec">规格：{{ row.spec }}</p>
            <p class="asset-meta">领用时间：{{ row.borrowedAt }}</p>
            <p class="asset-meta">到期时间：{{ row.dueAt }}</p>
            <div class="status-row">
              <span class="status-label">状态</span>
              <span class="status-pill" :class="tagFor(row.status).class">{{ tagFor(row.status).label }}</span>
            </div>
          </div>
        </div>
        <footer class="card-actions" @click.stop>
          <el-button
            v-for="a in actionsFor(row)"
            :key="a"
            :type="a === 'return' ? 'primary' : 'default'"
            round
            @click="run(row, a)"
          >
            {{ label(a) }}
          </el-button>
        </footer>
      </article>
    </div>
  </div>
</template>

<style scoped lang="scss">
.assets-panel {
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
.card-list {
  min-height: 80px;
}
.empty-hint {
  text-align: center;
  color: var(--text-muted);
  padding: 48px 0;
  font-size: 14px;
}
.asset-card {
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
  width: 110px;
  height: 110px;
  border-radius: 12px;
  background: #f4f4f5;
  flex-shrink: 0;
  border: 1px solid var(--border-subtle);
  overflow: hidden;
}
.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.goods-main {
  flex: 1;
  min-width: 0;
}
.asset-name {
  margin: 0 0 6px;
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}
.asset-spec,
.asset-meta {
  margin: 0 0 4px;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.45;
}
.status-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 12px;
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
.pill--ok {
  background: #ecfdf5;
  color: #047857;
  border: 1px solid #6ee7b7;
}
.pill--soon {
  background: #fffbeb;
  color: #b45309;
  border: 1px solid #fcd34d;
}
.pill--overdue {
  background: #fef2f2;
  color: #b91c1c;
  border: 2px solid #f87171;
  font-weight: 900;
}
.pill--returned {
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
@media (max-width: 560px) {
  .card-body {
    gap: 12px;
  }
  .goods-thumb {
    width: 88px;
    height: 88px;
  }
  :deep(.el-radio-button__inner) {
    padding: 8px 10px;
    font-size: 12px;
  }
}
</style>
