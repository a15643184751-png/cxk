<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Share } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getDemoAsset, type DemoAsset } from './teacherAssetDemo'

const route = useRoute()
const router = useRouter()
const asset = ref<DemoAsset | null>(null)

const assetId = computed(() => Number(route.params.assetId))

onMounted(() => {
  const row = getDemoAsset(assetId.value)
  asset.value = row ?? null
  if (!row) ElMessage.warning('未找到该领用记录')
})

function tagFor(s: DemoAsset['status']) {
  if (s === 'ok') return { label: '正常使用', class: 'pill--ok' }
  if (s === 'soon') return { label: '即将到期', class: 'pill--soon' }
  if (s === 'overdue') return { label: '已逾期', class: 'pill--overdue' }
  return { label: '已归还', class: 'pill--returned' }
}

function copyShare() {
  const url = window.location.href
  void navigator.clipboard.writeText(url).then(
    () => ElMessage.success('链接已复制'),
    () => ElMessage.info('请手动复制地址栏链接')
  )
}

function demo(msg: string) {
  ElMessage.success(msg)
}
</script>

<template>
  <div class="asset-detail-page">
    <header class="ad-head">
      <el-button text :icon="ArrowLeft" @click="router.push('/teacher/personal?tab=assets')">返回领用</el-button>
      <el-button :icon="Share" @click="copyShare">分享</el-button>
    </header>

    <template v-if="asset">
      <section class="ad-hero">
        <div class="ad-title-row">
          <div class="ad-thumb" aria-hidden="true">
            <img :src="asset.image" :alt="asset.name" class="ad-thumb-img" />
          </div>
          <div>
            <h1 class="ad-title">{{ asset.name }}</h1>
            <p class="ad-spec">规格：{{ asset.spec }}</p>
          </div>
        </div>
        <div class="ad-status-row">
          <span class="ad-status-label">状态</span>
          <span class="status-pill" :class="tagFor(asset.status).class">{{ tagFor(asset.status).label }}</span>
        </div>
      </section>

      <section class="ad-block">
        <h2 class="ad-h">领用信息</h2>
        <ul class="ad-list">
          <li><span class="k">领用时间</span><span class="v">{{ asset.borrowedAt }}</span></li>
          <li><span class="k">到期时间</span><span class="v">{{ asset.dueAt }}</span></li>
          <li><span class="k">存放位置</span><span class="v">{{ asset.location }}</span></li>
        </ul>
      </section>

      <section v-if="asset.traceNote" class="ad-block">
        <h2 class="ad-h">台账说明</h2>
        <p class="ad-p">{{ asset.traceNote }}</p>
      </section>

      <section v-if="asset.historyLines?.length" class="ad-block">
        <h2 class="ad-h">历史借用记录</h2>
        <el-timeline>
          <el-timeline-item v-for="(line, i) in asset.historyLines" :key="i" :timestamp="''">
            {{ line }}
          </el-timeline-item>
        </el-timeline>
      </section>

      <footer class="ad-footer">
        <el-button v-if="asset.status !== 'returned'" @click="demo('续借')">续借</el-button>
        <el-button v-if="asset.status !== 'returned'" type="primary" @click="demo('归还')">归还</el-button>
      </footer>
    </template>

    <el-empty v-else description="记录不存在" />
  </div>
</template>

<style scoped lang="scss">
.asset-detail-page {
  max-width: 640px;
  margin: 0 auto;
  padding: 0 4px 48px;
}
.ad-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}
.ad-hero {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-card);
}
.ad-title-row {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.ad-thumb {
  width: 112px;
  height: 112px;
  border-radius: 12px;
  background: #f4f4f5;
  flex-shrink: 0;
  overflow: hidden;
  border: 1px solid var(--border-subtle);
}
.ad-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.ad-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
}
.ad-spec {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}
.ad-status-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.ad-status-label {
  font-size: 13px;
  color: var(--text-muted);
}
.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 8px 18px;
  border-radius: 10px;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: 0.02em;
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
  font-weight: 800;
}
.pill--returned {
  background: #f4f4f5;
  color: #52525b;
  border: 1px solid #d4d4d8;
}
.ad-block {
  margin-bottom: 24px;
}
.ad-h {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
}
.ad-list {
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: 14px;
  li {
    display: flex;
    gap: 12px;
    padding: 10px 0;
    border-bottom: 1px solid var(--border-subtle);
    &:last-child {
      border-bottom: none;
    }
  }
  .k {
    color: var(--text-muted);
    width: 88px;
    flex-shrink: 0;
  }
  .v {
    color: var(--text-primary);
    font-weight: 500;
  }
}
.ad-p {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-secondary);
}
.ad-footer {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding-top: 8px;
}
</style>
