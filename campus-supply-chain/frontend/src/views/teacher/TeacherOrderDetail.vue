<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { ArrowLeft, Share } from '@element-plus/icons-vue'
import { listMyPurchases, getPurchaseTimeline, type Purchase, type PurchaseTimelineItem } from '@/api/purchase'
import { confirmDeliveryReceive } from '@/api/delivery'
import { orderFourState, orderStatusPillClass } from './teacherOrderUi'
import { getDemoPurchaseById, getDemoTimelineForOrder } from './teacherDemoOrders'
import { catalogImageForGoodsName } from './teacherDemoCatalog'

const route = useRoute()
const router = useRouter()

const loading = ref(true)
const purchase = ref<Purchase | null>(null)
const timeline = ref<PurchaseTimelineItem[]>([])
const evalVisible = ref(false)
const evalForm = ref({ rating: 5, comment: '' })

const orderId = computed(() => Number(route.params.orderId))

function enrichItems(p: Purchase): Purchase {
  return {
    ...p,
    items: (p.items || []).map((i) => ({
      ...i,
      image: i.image || catalogImageForGoodsName(i.goods_name),
    })),
  }
}

async function load() {
  loading.value = true
  try {
    const id = orderId.value
    if (id < 0) {
      const demo = getDemoPurchaseById(id)
      if (!demo) {
        purchase.value = null
        ElMessage.warning('未找到该订单')
        return
      }
      purchase.value = enrichItems({
        ...demo,
        goods_summary:
          demo.goods_summary ||
          (demo.items || []).map((i) => `${i.goods_name}${i.quantity}${i.unit}`).join('、'),
      })
      timeline.value = getDemoTimelineForOrder(id)
      return
    }

    const res: any = await listMyPurchases()
    const list = (Array.isArray(res) ? res : res?.data ?? []) as Purchase[]
    const row = list.find((p) => p.id === id)
    if (!row) {
      purchase.value = null
      ElMessage.warning('未找到该订单或无权查看')
      return
    }
    purchase.value = enrichItems({
      ...row,
      goods_summary:
        row.goods_summary ||
        (row.items || []).map((i) => `${i.goods_name}${i.quantity}${i.unit}`).join('、'),
    })
    try {
      const tl: any = await getPurchaseTimeline(row.id)
      timeline.value = tl?.timeline || []
    } catch {
      timeline.value = []
    }
  } catch (e: any) {
    purchase.value = null
    ElMessage.error(e?.response?.data?.detail || e?.message || '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function handleReceive() {
  const p = purchase.value
  if (!p) return
  if (p.id < 0) {
    ElMessage.info('该订单无需线上签收')
    return
  }
  if (!p.delivery_id) return
  try {
    await confirmDeliveryReceive(p.delivery_id)
    ElMessage.success('已确认签收')
    await load()
    evalForm.value = { rating: 5, comment: '' }
    evalVisible.value = true
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '操作失败')
  }
}

function remind() {
  ElMessage.success('已通知后勤催单')
}

function submitEval() {
  ElMessage.success('感谢您的评价')
  evalVisible.value = false
}

function cancelApplyDemo() {
  ElMessage.info('取消申请需联系审批人')
}

function repurchase() {
  const no = purchase.value?.order_no || ''
  router.push({ path: '/teacher/workbench', query: { prefill: no ? `复购 ${no}` : '复购' } })
}

function copyShare() {
  const url = window.location.href
  void navigator.clipboard.writeText(url).then(
    () => ElMessage.success('链接已复制，可发给后勤或同事'),
    () => ElMessage.info('请手动复制地址栏链接')
  )
}
</script>

<template>
  <div class="order-detail-page" v-loading="loading">
    <header class="od-head">
      <el-button text :icon="ArrowLeft" @click="router.push('/teacher/personal?tab=orders')">返回订单</el-button>
      <div class="od-actions">
        <el-button :icon="Share" @click="copyShare">分享</el-button>
      </div>
    </header>

    <template v-if="purchase">
      <section class="od-hero">
        <div class="od-hero-row">
          <span class="od-no">{{ purchase.order_no }}</span>
          <span class="status-pill od-pill" :class="orderStatusPillClass(orderFourState(purchase)).class">
            {{ orderStatusPillClass(orderFourState(purchase)).label }}
          </span>
        </div>
        <p class="od-time">
          下单时间：{{ purchase.created_at ? purchase.created_at.slice(0, 19).replace('T', ' ') : '—' }}
        </p>
        <p class="od-addr">
          送至：<strong>{{ purchase.destination || '—' }}</strong>
          <span v-if="purchase.receiver_name" class="od-rcv">· 收货人 {{ purchase.receiver_name }}</span>
        </p>
        <p v-if="purchase.handoff_code" class="od-code">交接码：{{ purchase.handoff_code }}</p>
      </section>

      <section class="od-block">
        <h3 class="od-h">订单信息</h3>
        <ul class="od-info-list">
          <li><span class="k">申请人</span><span class="v">{{ purchase.applicant_name || '当前账号' }}</span></li>
          <li><span class="k">申请日期</span><span class="v">{{ purchase.created_at ? purchase.created_at.slice(0, 16).replace('T', ' ') : '—' }}</span></li>
          <li><span class="k">审批状态</span><span class="v">{{ orderStatusPillClass(orderFourState(purchase)).label }}</span></li>
          <li><span class="k">仓储/配送</span><span class="v">{{ purchase.delivery_status_label || '待仓储处理' }}</span></li>
          <li><span class="k">配送单号</span><span class="v">{{ purchase.delivery_no || '—' }}</span></li>
        </ul>
      </section>

      <section class="od-block">
        <h3 class="od-h">物资明细</h3>
        <el-table :data="purchase.items || []" size="small" border class="od-table">
          <el-table-column label="图" width="76" align="center">
            <template #default="{ row }">
              <div class="cell-thumb">
                <img v-if="row.image" :src="row.image" alt="" class="cell-thumb-img" />
                <span v-else class="cell-thumb-ph">—</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="goods_name" label="物资" min-width="160" />
          <el-table-column prop="quantity" label="数量" width="88" />
          <el-table-column prop="unit" label="单位" width="72" />
        </el-table>
        <p v-if="purchase.estimated_amount != null && purchase.estimated_amount > 0" class="od-sum">
          预估金额：<span class="od-sum-num">¥{{ Number(purchase.estimated_amount).toFixed(2) }}</span>
        </p>
      </section>

      <section class="od-block">
        <h3 class="od-h">全链路进度</h3>
        <p class="od-hint">申请、审批、仓储与配送节点。</p>
        <el-timeline v-if="timeline.length">
          <el-timeline-item
            v-for="(ev, idx) in timeline"
            :key="idx"
            :timestamp="ev.time"
            placement="top"
            :type="idx === timeline.length - 1 ? 'primary' : 'success'"
          >
            <div class="tl-stage">{{ ev.stage }}</div>
            <div class="tl-content">{{ ev.content }}</div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无进度记录" />
      </section>

      <footer class="od-footer">
        <el-button v-if="purchase.can_confirm_receive" type="success" size="large" @click="handleReceive">
          确认签收
        </el-button>
        <el-button v-if="!['completed', 'rejected'].includes(purchase.status)" @click="remind">催单</el-button>
        <el-button v-if="purchase.status === 'pending'" @click="cancelApplyDemo">取消申请</el-button>
        <el-button v-if="purchase.status === 'completed'" @click="evalVisible = true">评价</el-button>
        <el-button v-if="purchase.status === 'completed'" type="primary" @click="repurchase">复购</el-button>
      </footer>
    </template>

    <el-empty v-else-if="!loading" description="订单不存在" />

    <el-dialog v-model="evalVisible" title="评价订单" width="480px" destroy-on-close align-center>
      <p v-if="purchase" class="eval-order">单号 {{ purchase.order_no }}</p>
      <el-form label-position="top">
        <el-form-item label="满意度（1–5）">
          <el-rate v-model="evalForm.rating" :max="5" show-score />
        </el-form-item>
        <el-form-item label="意见（选填）">
          <el-input v-model="evalForm.comment" type="textarea" :rows="4" placeholder="物资质量、配送速度等" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="evalVisible = false">取消</el-button>
        <el-button type="primary" @click="submitEval">提交评价</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.order-detail-page {
  max-width: 800px;
  margin: 0 auto;
  padding: 0 4px 48px;
}
.od-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.od-hero {
  background: linear-gradient(135deg, #f8fafc 0%, #eef2ff 100%);
  border: 1px solid #e2e8f0;
  border-radius: 16px;
  padding: 18px 20px;
  margin-bottom: 20px;
}
.od-hero-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.od-pill {
  font-size: 15px;
  padding: 8px 16px;
}
.status-pill {
  display: inline-flex;
  align-items: center;
  border-radius: 10px;
  font-weight: 800;
  letter-spacing: 0.02em;
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
.od-no {
  font-size: 16px;
  font-weight: 700;
  color: var(--el-color-primary);
}
.od-time,
.od-addr,
.od-code {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}
.od-rcv {
  color: var(--text-muted);
}
.od-block {
  margin-bottom: 24px;
}
.od-h {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 600;
}
.od-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 12px;
}
.od-info-list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--border-subtle);
  border-radius: 12px;
  overflow: hidden;
  li {
    display: flex;
    gap: 12px;
    padding: 12px 14px;
    border-bottom: 1px solid var(--border-subtle);
    &:last-child {
      border-bottom: none;
    }
  }
  .k {
    width: 92px;
    flex-shrink: 0;
    color: var(--text-muted);
    font-size: 13px;
  }
  .v {
    color: var(--text-primary);
    font-size: 13px;
    font-weight: 500;
  }
}
.cell-thumb {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 48px;
}
.cell-thumb-img {
  width: 48px;
  height: 48px;
  border-radius: 8px;
  object-fit: cover;
  border: 1px solid var(--border-subtle);
}
.cell-thumb-ph {
  font-size: 12px;
  color: var(--text-muted);
}
.od-sum {
  margin: 12px 0 0;
  text-align: right;
  font-size: 13px;
}
.od-sum-num {
  font-weight: 700;
  color: #ea580c;
  font-size: 16px;
}
.tl-stage {
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 4px;
}
.tl-content {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  white-space: pre-wrap;
}
.od-footer {
  position: sticky;
  bottom: 0;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  padding: 16px 0;
  background: linear-gradient(180deg, transparent, var(--el-bg-color) 30%);
}
.eval-order {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 16px 0;
}
</style>
