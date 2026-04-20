<script setup lang="ts">
import { computed, reactive, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { DocumentCopy, Lock, WarningFilled, RefreshRight, Clock } from '@element-plus/icons-vue'
import { listIDSLogAudits } from '@/api/ids'
import type { IDSLogAuditItem, IDSLogAuditSeverity } from '@/api/ids'

const router = useRouter()
const loading = ref(false)
const items = ref<IDSLogAuditItem[]>([])
const total = ref(0)
const summary = ref<{ total: number } | null>(null)
const currentPage = ref(1)
const pageSize = ref(20)
const filters = reactive({
  action: '',
  target_type: '',
  user_name: '',
  severity: '' as IDSLogAuditSeverity | '',
})
const availableActions = ref<string[]>([])
const availableTargets = ref<string[]>([])
const availableSeverities = ref<IDSLogAuditSeverity[]>([])
const highlightActions = new Set([
  'ids_upload_quarantine',
  'ids_upload_rejected',
  'ids_event_block',
  'ids_event_unblock',
  'ids_source_sync',
  'ids_package_activate',
])

const offset = computed(() => (currentPage.value - 1) * pageSize.value)

const getSeverityTagType = (level?: string) => {
  if (!level) return 'info'
  if (level.toLowerCase() === 'critical') return 'danger'
  if (level.toLowerCase() === 'suspicious') return 'warning'
  return 'info'
}

const statCards = computed(() => {
  const baseSummary = summary.value
  const baseTotal = baseSummary?.total ?? total.value
  const critical = (baseSummary as any)?.critical ?? 0
  const suspicious = (baseSummary as any)?.suspicious ?? 0
  const informational = (baseSummary as any)?.informational ?? 0
  return [
    { label: '总审计记录', value: baseTotal, note: '持续收敛中的安全事件', icon: DocumentCopy },
    { label: '关键拦截', value: critical, note: '高危操作/拦截动作', icon: Lock },
    { label: '可疑行为', value: suspicious, note: '需要复核的异常操作', icon: WarningFilled },
    { label: '信息事件', value: informational, note: '系统审计和填报日志', icon: Clock },
  ]
})

const quickActions = computed(() => availableActions.value.slice(0, 6))

async function fetchLogs() {
  loading.value = true
  try {
    const params = {
      action: filters.action || undefined,
      target_type: filters.target_type || undefined,
      user_name: filters.user_name || undefined,
      severity: filters.severity || undefined,
      limit: pageSize.value,
      offset: offset.value,
    }
    const res = await listIDSLogAudits(params)
    const payload = (res as any)?.data ?? res
    items.value = payload.items ?? []
    total.value = payload.total ?? items.value.length
    summary.value = payload.summary ?? { total: payload.total ?? items.value.length }
    availableActions.value = payload.available_actions ?? []
    availableTargets.value = payload.available_targets ?? []
    availableSeverities.value = payload.available_severities ?? []
  } catch {
    ElMessage.error('拉取 IDS 日志审计失败')
  } finally {
    loading.value = false
  }
}

function applyFilters() {
  currentPage.value = 1
  fetchLogs()
}

function resetFilters() {
  filters.action = ''
  filters.target_type = ''
  filters.user_name = ''
  filters.severity = ''
  applyFilters()
}

function handlePageChange(page: number) {
  currentPage.value = page
  fetchLogs()
}

function handleSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  fetchLogs()
}

const paginationTotal = computed(() => total.value)

const rowClassName = ({ row }: { row: IDSLogAuditItem }) => {
  return highlightActions.has(row.action) ? 'log-row--highlight' : ''
}

function hasTargetLink(row: IDSLogAuditItem) {
  return ['public_upload', 'sandbox_file', 'ids_event', 'ids_source', 'source_package'].includes(row.target_type)
}

function targetLinkLabel(row: IDSLogAuditItem) {
  if (row.target_type === 'ids_event') return '打开事件'
  if (row.target_type === 'public_upload' || row.target_type === 'sandbox_file') return '打开沙箱'
  return '前往 IDS'
}

function openTarget(row: IDSLogAuditItem) {
  if (row.target_type === 'public_upload' || row.target_type === 'sandbox_file') {
    void router.push({
      path: '/sandbox',
      query: { saved_as: row.target_id, report: '1' },
    })
    return
  }

  if (row.target_type === 'ids_event') {
    void router.push({
      path: '/events',
      query: { event: row.target_id, report: '1' },
    })
    return
  }

  void router.push('/events')
}

onMounted(() => {
  fetchLogs()
})
</script>

<template>
  <section class="log-audit">
    <header class="log-audit__header">
      <div>
        <p class="eyebrow">IDS 控制台</p>
        <h2>日志审计中心</h2>
        <p class="subtitle">
          记录上传审计、事件审查、同步触发等关键动作，方便安全团队随需追责。
        </p>
      </div>
      <el-button type="primary" plain :loading="loading" @click="fetchLogs">
        <el-icon><RefreshRight /></el-icon>
        刷新日志
      </el-button>
    </header>

    <div class="log-audit__stats">
      <article class="stat-card" v-for="card in statCards" :key="card.label">
        <div class="stat-card__head">
          <div class="stat-card__icon">
            <el-icon :size="20"><component :is="card.icon" /></el-icon>
          </div>
          <div class="stat-card__label">{{ card.label }}</div>
        </div>
        <p class="stat-card__value">{{ card.value }}</p>
        <p class="stat-card__note">{{ card.note }}</p>
      </article>
    </div>

    <div class="log-audit__filters glass-panel">
      <div class="filter-row">
        <el-input v-model="filters.user_name" size="small" placeholder="操作者" />
        <el-select v-model="filters.severity" clearable size="small" placeholder="严重程度">
          <el-option
            v-for="severity in availableSeverities"
            :key="severity"
            :label="severity"
            :value="severity"
          />
        </el-select>
        <el-select v-model="filters.action" clearable size="small" placeholder="操作动作">
          <el-option
            v-for="action in availableActions"
            :key="action"
            :label="action"
            :value="action"
          />
        </el-select>
        <el-select v-model="filters.target_type" clearable size="small" placeholder="目标类型">
          <el-option
            v-for="target in availableTargets"
            :key="target"
            :label="target"
            :value="target"
          />
        </el-select>
      </div>
      <div class="filter-actions">
        <el-button size="small" type="primary" @click="applyFilters">筛选</el-button>
        <el-button size="small" type="text" @click="resetFilters">重置</el-button>
      </div>
      <div v-if="quickActions.length" class="filter-chips">
        <span class="chip-label">快捷动作</span>
        <el-tag
          v-for="action in quickActions"
          :key="action"
          class="chip-tag"
          type="success"
          @click="filters.action = action; applyFilters()"
        >
          {{ action }}
        </el-tag>
      </div>
    </div>

    <div class="log-audit__table">
      <el-table
        :data="items"
        height="460"
        border
        :row-class-name="rowClassName"
        v-loading="loading"
        element-loading-text="加载中..."
      >
        <el-table-column prop="action" label="操作" min-width="220">
          <template #default="{ row }">
            <span class="table-action">{{ row.action }}</span>
            <span v-if="row.target_type" class="table-context">[{{ row.target_type }}]</span>
          </template>
        </el-table-column>
        <el-table-column label="目标" min-width="220">
          <template #default="{ row }">
            <p>{{ row.target_id }}</p>
            <p class="table-context">{{ row.detail }}</p>
            <el-button
              v-if="hasTargetLink(row)"
              type="primary"
              link
              size="small"
              @click="openTarget(row)"
            >
              {{ targetLinkLabel(row) }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="user_name" label="操作者" min-width="180">
          <template #default="{ row }">
            <strong>{{ row.user_name || 'system' }}</strong>
            <p class="table-context">{{ row.user_role }}</p>
          </template>
        </el-table-column>
        <el-table-column prop="severity" label="严重程度" min-width="140">
          <template #default="{ row }">
            <el-tag :type="getSeverityTagType(row.severity)" size="small">{{ row.severity || 'informational' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" min-width="180">
          <template #default="{ row }">
            <span>{{ row.created_at || '-' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="log-audit__pagination">
      <el-pagination
        :total="paginationTotal"
        :current-page="currentPage"
        :page-size="pageSize"
        :page-sizes="[10, 20, 30]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>
  </section>
</template>

<style scoped>
.log-audit {
  --audit-panel-bg: linear-gradient(180deg, rgba(7, 14, 28, 0.96), rgba(5, 11, 24, 0.92));
  --audit-panel-border: rgba(96, 165, 250, 0.12);
  --audit-panel-shadow: 0 24px 48px rgba(2, 6, 23, 0.42);
  --audit-text-main: #f8fafc;
  --audit-text-soft: rgba(226, 232, 240, 0.84);
  --audit-text-muted: rgba(148, 163, 184, 0.92);
  --audit-table-bg: rgba(5, 11, 24, 0.98);
  --audit-table-bg-soft: rgba(15, 23, 42, 0.95);
  --audit-table-border: rgba(71, 85, 105, 0.42);
  --audit-row-hover: rgba(30, 41, 59, 0.94);
  display: flex;
  flex-direction: column;
  padding: 32px;
  gap: 20px;
}

.glass-panel {
  background: var(--audit-panel-bg);
  border: 1px solid var(--audit-panel-border);
  border-radius: 14px;
  padding: 16px;
  margin-bottom: 24px;
  box-shadow: var(--audit-panel-shadow);
}

.log-audit__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 20px;
}

.log-audit__header h2 {
  margin: 0;
  font-size: 24px;
  color: var(--audit-text-main);
}

.log-audit__header .subtitle {
  margin: 4px 0 0;
  color: var(--audit-text-soft);
  max-width: 520px;
}

.log-audit__stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.stat-card {
  padding: 20px;
  border-radius: 16px;
  background: linear-gradient(135deg, rgba(14, 165, 233, 0.08), rgba(5, 11, 24, 0.96));
  border: 1px solid rgba(96, 165, 250, 0.14);
  box-shadow: inset 0 1px 0 rgba(148, 163, 184, 0.04);
}

.stat-card__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stat-card__label {
  color: rgba(191, 219, 254, 0.82);
  font-size: 12px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.stat-card__value {
  margin: 12px 0 4px;
  font-size: 28px;
  font-weight: 700;
  color: #fff;
}

.stat-card__note {
  margin: 0;
  color: var(--audit-text-soft);
  font-size: 12px;
}

.stat-card__icon {
  color: rgba(96, 165, 250, 0.94);
}

.log-audit__filters {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.filter-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.filter-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: var(--audit-text-soft);
}

.chip-label {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.chip-tag {
  cursor: pointer;
}

.log-audit__table {
  background: linear-gradient(180deg, rgba(3, 9, 20, 0.99), rgba(5, 11, 24, 0.94));
  border-radius: 16px;
  border: 1px solid var(--audit-panel-border);
  padding: 12px;
  box-shadow: var(--audit-panel-shadow);
}

.table-action {
  font-weight: 600;
  color: var(--audit-text-main);
}

.table-context {
  color: var(--audit-text-muted);
  font-size: 12px;
}

.log-row--highlight {
  background: rgba(14, 165, 233, 0.12) !important;
}

.log-audit__pagination {
  display: flex;
  justify-content: flex-end;
}

.log-audit :deep(.el-input__wrapper),
.log-audit :deep(.el-select__wrapper) {
  background: rgba(7, 14, 28, 0.96);
  box-shadow: 0 0 0 1px rgba(71, 85, 105, 0.52) inset;
}

.log-audit :deep(.el-input__inner),
.log-audit :deep(.el-select__placeholder),
.log-audit :deep(.el-select__selected-item),
.log-audit :deep(.el-input__icon),
.log-audit :deep(.el-select__caret) {
  color: var(--audit-text-soft);
}

.log-audit :deep(.el-input__inner::placeholder) {
  color: rgba(148, 163, 184, 0.88);
}

.log-audit :deep(.el-button--text) {
  color: rgba(125, 211, 252, 0.94);
}

.log-audit :deep(.el-tag--success.el-tag--light) {
  color: #dcfce7;
  background: rgba(22, 101, 52, 0.34);
  border-color: rgba(74, 222, 128, 0.26);
}

.log-audit :deep(.el-table) {
  --el-table-border-color: var(--audit-table-border);
  --el-table-header-bg-color: rgba(15, 23, 42, 0.98);
  --el-table-tr-bg-color: var(--audit-table-bg);
  --el-table-row-hover-bg-color: var(--audit-row-hover);
  --el-table-current-row-bg-color: rgba(8, 47, 73, 0.72);
  --el-table-header-text-color: rgba(191, 219, 254, 0.88);
  --el-table-text-color: var(--audit-text-soft);
  --el-table-bg-color: var(--audit-table-bg);
  --el-fill-color-lighter: var(--audit-table-bg-soft);
  background: transparent;
  color: var(--audit-text-soft);
}

.log-audit :deep(.el-table tr),
.log-audit :deep(.el-table__body tr.hover-row > td.el-table__cell),
.log-audit :deep(.el-table__body tr.current-row > td.el-table__cell),
.log-audit :deep(.el-table__body td.el-table__cell),
.log-audit :deep(.el-table__header th.el-table__cell) {
  background: transparent;
}

.log-audit :deep(.el-table td.el-table__cell),
.log-audit :deep(.el-table th.el-table__cell) {
  border-bottom-color: var(--audit-table-border);
}

.log-audit :deep(.el-pagination) {
  --el-pagination-bg-color: transparent;
  --el-pagination-text-color: var(--audit-text-soft);
  --el-pagination-button-disabled-bg-color: rgba(15, 23, 42, 0.72);
  --el-pagination-button-bg-color: rgba(15, 23, 42, 0.95);
  --el-pagination-hover-color: #93c5fd;
}

.log-audit :deep(.el-pagination .btn-prev),
.log-audit :deep(.el-pagination .btn-next),
.log-audit :deep(.el-pagination .el-pager li) {
  background: rgba(15, 23, 42, 0.95);
  color: var(--audit-text-soft);
}

.log-audit :deep(.el-pagination .el-pager li.is-active) {
  background: linear-gradient(135deg, rgba(37, 99, 235, 0.94), rgba(14, 165, 233, 0.96));
  color: #eff6ff;
}
</style>
