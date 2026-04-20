<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import type { UploadFile, UploadRawFile } from 'element-plus'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { CircleCheckFilled } from '@element-plus/icons-vue'
import { listGoods } from '@/api/goods'
import { createPurchase, listPurchaseHistory, getPurchaseFavorites } from '@/api/purchase'
import type { GoodsItem } from '@/api/goods'
import type { Purchase } from '@/api/purchase'

const MAX_SIZE = 5 * 1024 * 1024
const ALLOW_TYPES = ['application/pdf','image/jpeg','image/png','image/jpg','application/msword','application/vnd.openxmlformats-officedocument.wordprocessingml.document']
const MATERIAL_TYPES = ['教学', '科研', '办公'] as const
type MaterialType = typeof MATERIAL_TYPES[number]

const router = useRouter()
const goodsList = ref<GoodsItem[]>([])
const loading = ref(false)
const fileList = ref<UploadFile[]>([])
const historyVisible = ref(false)
const historyList = ref<Purchase[]>([])
const historyLoading = ref(false)
const favorites = ref<Array<{goods_name:string;quantity:number;unit:string;material_type:string;material_spec:string;estimated_amount:number;count:number}>>([])
const favLoading = ref(false)
const submittedOrderNo = ref('')
const successVisible = ref(false)
const today = new Date().toISOString().split('T')[0]

const form = reactive({
  goods_id: null as number | null,
  quantity: 1,
  apply_reason: '',
  destination: '',
  receiver_name: '',
  material_type: '教学' as MaterialType,
  material_spec: '',
  estimated_amount: 0,
  delivery_date: null as string | null,
  is_draft: 0,
})

const currentGoods = computed(() => goodsList.value.find(g => g.id === form.goods_id) || null)
const deliveryDateDisabled = (ts: Date) => ts.getTime() < Date.now() - 86400000

const approvalHint = computed(() => {
  const amt = Number(form.estimated_amount || 0)
  if (form.material_type === '科研') return { role: '系统管理员审批（科研物资）', color: '#dc2626' }
  if (amt <= 500) return { role: '后勤管理员审批（≤500元）', color: '#16a34a' }
  if (amt <= 5000) return { role: '系统管理员审批（500–5000元）', color: '#d97706' }
  return { role: '系统管理员审批（大额）', color: '#dc2626' }
})

const isUrgent = computed(() => {
  if (!form.delivery_date) return false
  const diff = new Date(form.delivery_date).getTime() - Date.now()
  return diff > 0 && diff <= 48 * 3600 * 1000
})

onMounted(async () => {
  try { const list = await listGoods(); goodsList.value = Array.isArray(list) ? list : [] } catch { goodsList.value = [] }
  loadFavorites()
})

async function loadFavorites() {
  favLoading.value = true
  try { const res: any = await getPurchaseFavorites(); favorites.value = Array.isArray(res) ? res : res?.data ?? [] }
  catch { favorites.value = [] } finally { favLoading.value = false }
}

async function openHistory() {
  historyVisible.value = true
  historyLoading.value = true
  try { const res: any = await listPurchaseHistory(); historyList.value = Array.isArray(res) ? res : res?.data ?? [] }
  catch { historyList.value = [] } finally { historyLoading.value = false }
}

function applyFavorite(fav: typeof favorites.value[0]) {
  const matched = goodsList.value.find(g => g.name === fav.goods_name)
  if (matched) form.goods_id = matched.id
  form.material_type = (MATERIAL_TYPES.includes(fav.material_type as MaterialType) ? fav.material_type : '教学') as MaterialType
  form.material_spec = fav.material_spec || ''
  form.estimated_amount = fav.estimated_amount || 0
  form.quantity = fav.quantity || 1
  ElMessage.success(`已填充「${fav.goods_name}」信息`)
}

function copyFromHistory(row: Purchase) {
  const matched = goodsList.value.find(g => (row.items || []).some(i => i.goods_name === g.name))
  if (matched) form.goods_id = matched.id
  form.material_type = (MATERIAL_TYPES.includes((row.material_type || '') as MaterialType) ? row.material_type! : '教学') as MaterialType
  form.material_spec = row.material_spec || ''
  form.estimated_amount = row.estimated_amount || 0
  historyVisible.value = false
  ElMessage.success('已复用历史申请信息')
}

function beforeUpload(file: UploadRawFile) {
  if (!ALLOW_TYPES.includes(file.type)) { ElMessage.error('仅支持 PDF、Word、JPG、PNG 格式'); return false }
  if (file.size > MAX_SIZE) { ElMessage.error('文件不能超过 5MB'); return false }
  return true
}

function handleFileChange(_f: UploadFile, files: UploadFile[]) {
  fileList.value = files.filter(f => {
    const raw = f.raw; if (!raw) return true
    if (!ALLOW_TYPES.includes(raw.type)) { ElMessage.error(`"${f.name}" 格式不支持`); return false }
    if (raw.size > MAX_SIZE) { ElMessage.error(`"${f.name}" 超过 5MB`); return false }
    return true
  })
}

function validate(): boolean {
  if (!form.goods_id) { ElMessage.warning('请选择物资'); return false }
  if (form.quantity < 1) { ElMessage.warning('数量至少为 1'); return false }
  if (form.estimated_amount < 0) { ElMessage.warning('预估金额不能为负数'); return false }
  if (form.delivery_date && form.delivery_date < today) { ElMessage.warning('交付时间不能早于当前日期'); return false }
  return true
}

async function doSubmit(isDraft: number) {
  if (!isDraft && !validate()) return
  if (isDraft && !form.goods_id) { ElMessage.warning('请至少选择物资后再保存草稿'); return }
  loading.value = true
  try {
    const res: any = await createPurchase({
      goods_id: form.goods_id!,
      quantity: form.quantity,
      apply_reason: form.apply_reason,
      destination: form.destination,
      receiver_name: form.receiver_name,
      material_type: form.material_type,
      material_spec: form.material_spec,
      estimated_amount: form.estimated_amount,
      delivery_date: form.delivery_date || undefined,
      attachment_names: fileList.value.map(f => f.name),
      is_draft: isDraft,
    })
    const data = res?.data ?? res
    if (isDraft) { ElMessage.success('草稿已保存') }
    else { submittedOrderNo.value = data?.order_no || ''; successVisible.value = true; loadFavorites() }
  } catch { /* handled by interceptor */ } finally { loading.value = false }
}

function toProgress() {
  successVisible.value = false
  router.push('/teacher/personal?tab=orders')
}
function resetForm() {
  form.goods_id = null; form.quantity = 1; form.apply_reason = ''
  form.destination = ''; form.receiver_name = ''; form.material_type = '教学'
  form.material_spec = ''; form.estimated_amount = 0; form.delivery_date = null
  fileList.value = []; successVisible.value = false
}

function getStatusLabel(s: string) {
  return ({pending:'待审批',approved:'待接单',confirmed:'待发货',shipped:'待入库',stocked_in:'待出库',stocked_out:'待配送',delivering:'配送中',completed:'已完成',rejected:'已驳回'} as Record<string,string>)[s] || s
}

function getStatusType(s: string) {
  return ({pending:'warning',approved:'primary',completed:'success',rejected:'danger'} as Record<string,string>)[s] || 'info'
}
</script>

<template>
  <div class="apply-page">
    <div class="apply-header">
      <div>
        <h2>物资采购申请</h2>
        <p class="subtitle">30 秒完成申请 · 草稿保存 · 历史复用</p>
      </div>
      <div class="header-actions">
        <el-button @click="openHistory">历史记录</el-button>
        <el-button @click="router.push('/teacher/personal?tab=orders')">进度查询</el-button>
        <el-button @click="router.back()">返回</el-button>
      </div>
    </div>

    <!-- 常用物资快捷入口 -->
    <div class="section-card">
      <div class="section-title">
        <span>常用物资快捷申请</span>
        <span class="section-hint">点击自动填充申请信息</span>
      </div>
      <div v-if="favLoading" class="fav-empty">加载中...</div>
      <div v-else-if="favorites.length === 0" class="fav-empty">暂无常用记录，提交申请后自动积累</div>
      <div v-else class="fav-grid">
        <div v-for="fav in favorites" :key="fav.goods_name" class="fav-card" @click="applyFavorite(fav)">
          <div class="fav-name">{{ fav.goods_name }}</div>
          <div class="fav-detail">
            <span class="fav-badge">{{ fav.material_type }}</span>
            <span v-if="fav.material_spec" class="fav-spec">{{ fav.material_spec }}</span>
          </div>
          <div class="fav-meta">
            <span>已申请 {{ fav.count }} 次</span>
            <span v-if="fav.estimated_amount > 0">¥{{ fav.estimated_amount }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 申请表单 -->
    <div class="section-card">
      <div class="section-title">
        <span>填写申请信息</span>
        <div v-if="form.goods_id" class="approval-hint" :style="{ color: approvalHint.color }">
          审批路径：{{ approvalHint.role }}
        </div>
      </div>

      <el-form :model="form" label-width="100px" class="apply-form">
        <el-form-item label="物资类型">
          <el-radio-group v-model="form.material_type">
            <el-radio-button v-for="t in MATERIAL_TYPES" :key="t" :label="t">{{ t }}</el-radio-button>
          </el-radio-group>
        </el-form-item>

        <div class="form-two-col">
          <el-form-item label="物资">
            <el-select v-model="form.goods_id" placeholder="搜索选择物资" filterable style="width:100%">
              <el-option-group
                v-for="cat in ['教学','科研','办公','防疫','茶歇','设备','食材','实验','饮品'].filter(c => goodsList.some(g => g.category === c))"
                :key="cat" :label="cat"
              >
                <el-option
                  v-for="g in goodsList.filter(g => g.category === cat)"
                  :key="g.id"
                  :label="`${g.name}${g.spec ? ' — ' + g.spec : ''}`"
                  :value="g.id"
                />
              </el-option-group>
            </el-select>
          </el-form-item>
          <el-form-item label="规格">
            <el-input v-model="form.material_spec" :placeholder="currentGoods?.spec || '如：25kg/袋'" />
          </el-form-item>
        </div>

        <div class="form-two-col">
          <el-form-item label="数量">
            <el-input-number v-model="form.quantity" :min="1" :max="9999" style="width:100%" />
          </el-form-item>
          <el-form-item label="预估金额">
            <el-input-number v-model="form.estimated_amount" :min="0" :precision="2" :step="10" style="width:100%" />
          </el-form-item>
        </div>

        <div class="form-two-col">
          <el-form-item label="交付时间">
            <el-date-picker
              v-model="form.delivery_date"
              type="date"
              value-format="YYYY-MM-DD"
              :disabled-date="deliveryDateDisabled"
              placeholder="期望交付日期"
              style="width:100%"
            />
            <div v-if="isUrgent" class="urgent-tip">⚡ 48h 内交付，标记为紧急</div>
          </el-form-item>
          <el-form-item label="收货地点">
            <el-input v-model="form.destination" placeholder="如：教学楼A栋302" />
          </el-form-item>
        </div>

        <div class="form-two-col">
          <el-form-item label="收货人">
            <el-input v-model="form.receiver_name" placeholder="默认当前教师" />
          </el-form-item>
          <el-form-item label="申请理由">
            <el-input v-model="form.apply_reason" placeholder="选填" />
          </el-form-item>
        </div>

        <el-form-item label="附件">
          <el-upload
            v-model:file-list="fileList"
            :auto-upload="false"
            :before-upload="beforeUpload"
            :limit="3"
            multiple
            @change="handleFileChange"
          >
            <el-button>选择文件</el-button>
            <template #tip>
              <div class="upload-tip">支持 PDF、Word、JPG、PNG，单个 ≤5MB，最多 3 个</div>
            </template>
          </el-upload>
        </el-form-item>

        <el-form-item>
          <div class="form-actions">
            <el-button type="primary" :loading="loading" @click="doSubmit(0)">一键提交</el-button>
            <el-button :loading="loading" @click="doSubmit(1)">保存草稿</el-button>
            <el-button link @click="openHistory">历史记录</el-button>
          </div>
        </el-form-item>
      </el-form>
    </div>

    <!-- 提交成功弹窗 -->
    <el-dialog v-model="successVisible" title="申请提交成功" width="420px" :close-on-click-modal="false">
      <div class="success-body">
        <el-icon class="success-icon"><CircleCheckFilled /></el-icon>
        <div class="success-order">申请单号：{{ submittedOrderNo }}</div>
        <div class="success-hint">已进入审批流程，可在「进度查询」中实时跟踪状态。</div>
      </div>
      <template #footer>
        <el-button type="primary" @click="toProgress">查看进度</el-button>
        <el-button @click="resetForm">继续申请</el-button>
      </template>
    </el-dialog>

    <!-- 历史记录弹窗 -->
    <el-dialog v-model="historyVisible" title="申请历史记录" width="700px">
      <el-table :data="historyList" v-loading="historyLoading" style="width:100%">
        <el-table-column prop="order_no" label="申请单号" width="180" />
        <el-table-column prop="material_type" label="类型" width="70" />
        <el-table-column prop="goods_summary" label="物资" min-width="160" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)" size="small">{{ getStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="申请时间" width="110">
          <template #default="{ row }">{{ row.created_at?.slice(0, 10) || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="copyFromHistory(row)">复用</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="historyVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.apply-page { padding: 0; }
.apply-header {
  display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 20px;
  h2 { margin: 0; font-size: 18px; font-weight: 600; }
  .subtitle { margin: 4px 0 0; font-size: 13px; color: var(--text-muted); }
}
.header-actions { display: flex; gap: 8px; }
.section-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 14px;
  padding: 20px 24px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-card);
}
.section-title {
  display: flex; align-items: center; justify-content: space-between;
  font-size: 14px; font-weight: 600; color: var(--text-primary);
  margin-bottom: 16px;
  .section-hint { font-size: 12px; color: var(--text-muted); font-weight: 400; }
}
.fav-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
}
.fav-card {
  background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
  border: 1px solid #bae6fd;
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.18s;
  &:hover { transform: translateY(-2px); box-shadow: 0 6px 20px rgba(14,165,233,0.18); border-color: #38bdf8; }
  .fav-name { font-size: 14px; font-weight: 600; color: #0369a1; margin-bottom: 6px; }
  .fav-detail { display: flex; gap: 6px; align-items: center; margin-bottom: 4px; }
  .fav-badge { background: #0ea5e9; color: #fff; font-size: 10px; padding: 1px 6px; border-radius: 4px; }
  .fav-spec { font-size: 11px; color: #64748b; }
  .fav-meta { display: flex; justify-content: space-between; font-size: 11px; color: #94a3b8; }
}
.fav-empty { color: var(--text-muted); font-size: 13px; text-align: center; padding: 12px 0; }
.apply-form { max-width: 800px; }
.form-two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 24px;
}
.approval-hint { font-size: 12px; font-weight: 500; }
.urgent-tip {
  font-size: 11px; color: #d97706; margin-top: 4px;
  background: #fef3c7; padding: 2px 8px; border-radius: 4px; display: inline-block;
}
.upload-tip { font-size: 12px; color: var(--text-muted); margin-top: 6px; }
.form-actions { display: flex; gap: 10px; }
.success-body {
  text-align: center; padding: 16px 0;
  .success-icon { font-size: 52px; color: var(--el-color-success); margin-bottom: 12px; }
  .success-order { font-size: 15px; font-weight: 600; color: var(--text-primary); margin-bottom: 8px; }
  .success-hint { font-size: 13px; color: var(--text-muted); }
}
</style>
