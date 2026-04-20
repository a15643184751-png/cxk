<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { traceQuery } from '@/api/trace'
import type { TraceItem } from '@/api/trace'

const keyword = ref('')
const queryType = ref<'all' | 'batch' | 'order' | 'stock'>('all')
const traceResult = ref<TraceItem[] | null>(null)
const traceSummary = ref<any | null>(null)
const loading = ref(false)

// 无搜索结果时的溯源时间轴占位
const demoTimeline = [
  { stage: '申请', content: '教师 张三 提交采购申请 · 笔记本电脑 100台', time: '2026-03-18 09:00:00' },
  { stage: '审批', content: '后勤 李四 审批通过（AI 标记异常）', time: '2026-03-18 09:15:00' },
  { stage: '入库', content: '仓储 王五 执行入库', time: '2026-03-18 10:30:00' },
]

const placeholderMap: Record<typeof queryType.value, string> = {
  all: '输入关键字：申请单号/配送单号/交接码/批次号',
  batch: '输入批次号，如 BATCH2024001',
  order: '输入申请单号，如 PO202603120001',
  stock: '输入入库/出库单号，如 IN20260318 或 OUT20260318',
}

async function search() {
  if (!keyword.value.trim()) {
    ElMessage.warning('请输入查询关键字')
    return
  }
  loading.value = true
  try {
    const res: any = await traceQuery({
      keyword: keyword.value.trim(),
      query_type: queryType.value,
    })
    const data = res?.data ?? res
    traceSummary.value = data?.summary ?? null
    traceResult.value = data?.records ?? []
  } catch {
    traceSummary.value = null
    traceResult.value = []
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page trace-page">
    <div class="page-header">
      <h2>溯源查询</h2>
      <p class="page-desc">输入单号/交接码 · 10 秒查清责任 · 全链路可追溯</p>
    </div>
    <div class="query-card">
      <div class="query-type">
        <el-radio-group v-model="queryType" size="small">
          <el-radio-button label="all">全局</el-radio-button>
          <el-radio-button label="order">申请单号</el-radio-button>
          <el-radio-button label="batch">批次号</el-radio-button>
          <el-radio-button label="stock">入/出库单号</el-radio-button>
        </el-radio-group>
      </div>
      <div class="query-input">
        <el-input v-model="keyword" :placeholder="placeholderMap[queryType]" size="large" clearable @keyup.enter="search">
          <template #append>
            <el-button type="primary" :loading="loading" @click="search">溯源</el-button>
          </template>
        </el-input>
      </div>
      <template v-if="traceResult && traceResult.length === 0">
        <div class="empty-hint">未找到该批次号的溯源记录</div>
        <div class="demo-timeline-hint">溯源时间轴</div>
        <div class="timeline">
          <el-timeline>
            <el-timeline-item v-for="(item, i) in demoTimeline" :key="i" :timestamp="item.time">
              <div class="timeline-content">
                <span class="stage">{{ item.stage }}</span>
                <span class="content">{{ item.content }}</span>
              </div>
            </el-timeline-item>
          </el-timeline>
        </div>
      </template>
      <template v-else-if="traceResult && traceResult.length">
        <div v-if="traceSummary" class="responsibility-highlight">
          <strong>责任可追溯：</strong>以下记录完整保留操作人、时间、动作，便于快速定位问题
        </div>
        <div v-if="traceSummary" class="summary-grid">
          <div class="summary-card">
            <span class="label">申请单号</span>
            <strong>{{ traceSummary.order_no || '-' }}</strong>
          </div>
          <div class="summary-card">
            <span class="label">当前状态</span>
            <strong>{{ traceSummary.status_label || '-' }}</strong>
          </div>
          <div class="summary-card">
            <span class="label">交接码</span>
            <strong>{{ traceSummary.handoff_code || '-' }}</strong>
          </div>
          <div class="summary-card">
            <span class="label">收货人 / 地点</span>
            <strong>{{ traceSummary.receiver_name || '-' }} / {{ traceSummary.destination || '-' }}</strong>
          </div>
          <div class="summary-card">
            <span class="label">配送单</span>
            <strong>{{ traceSummary.delivery_no || '-' }}</strong>
          </div>
          <div class="summary-card">
            <span class="label">配送状态</span>
            <strong>{{ traceSummary.delivery_status_label || '-' }}</strong>
          </div>
        </div>
        <div class="timeline">
        <el-timeline>
          <el-timeline-item v-for="(item, i) in traceResult" :key="i" :timestamp="item.time">
            <div class="timeline-content">
              <span class="stage">{{ item.stage }}</span>
              <span class="content">{{ item.content }}</span>
            </div>
          </el-timeline-item>
        </el-timeline>
        </div>
      </template>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.trace-page { padding: 0; }
.page-desc { margin: 4px 0 0 0; font-size: 13px; color: var(--text-muted); }
.responsibility-highlight {
  padding: 12px 16px; margin-bottom: 16px; background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px;
  font-size: 13px; color: #065f46;
}
.query-card { padding: 32px; background: var(--bg-card); border-radius: 16px; box-shadow: var(--shadow-card); border: 1px solid var(--border-subtle); }
.query-type { margin-bottom: 14px; }
.query-input { max-width: 480px; margin-bottom: 32px; }
.summary-grid { display: grid; grid-template-columns: repeat(2, minmax(260px, 1fr)); gap: 12px; margin-bottom: 24px; }
.summary-card { padding: 14px 16px; background: var(--bg-hover); border: 1px solid var(--border-subtle); border-radius: 12px; }
.summary-card .label { display: block; font-size: 12px; color: var(--text-muted); margin-bottom: 6px; }
.timeline { max-width: 760px; }
.timeline-content { display: flex; gap: 16px; }
.stage { font-weight: 600; color: var(--primary); min-width: 60px; }
.content { color: var(--text-secondary); }
.empty-hint { margin-top: 16px; color: var(--text-muted); }
.demo-timeline-hint { margin: 8px 0 12px 0; font-size: 12px; color: var(--text-muted); }
</style>
