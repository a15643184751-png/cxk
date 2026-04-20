<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  detectIDSRequest,
  type IDSRequestDetectResponse,
} from '@/api/ids'
import {
  getUploadAuditRuntime,
  submitDetectionSample,
  type UploadAuditMode,
  type UploadResult,
} from '@/api/upload'

const router = useRouter()

const runtimeLoading = ref(false)
const runtimeMode = ref<UploadAuditMode>('static_only')
const runtimeMessage = ref('后端审计状态尚未加载。')

const requestLoading = ref(false)
const requestResult = ref<IDSRequestDetectResponse | null>(null)
const requestForm = reactive({
  client_ip: '203.0.113.10',
  method: 'GET',
  path: '/',
  query: '',
  user_agent: 'IDS Replay Workbench/1.0',
  headersText: 'Host: protected.local\nAccept: */*',
  body: '',
})

const sampleLoading = ref(false)
const sampleResult = ref<UploadResult | null>(null)
const selectedSample = ref<File | null>(null)

const runtimeModeLabel = computed(() =>
  runtimeMode.value === 'llm_assisted' ? 'AI 审计已启用' : '静态审计运行中',
)

const linkedSampleEventId = computed(() => sampleResult.value?.audit?.linked_event_id || null)

function parseHeaders(raw: string) {
  const headers: Record<string, string> = {}
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const [name, ...rest] = trimmed.split(':')
    const key = String(name || '').trim()
    const value = rest.join(':').trim()
    if (key) {
      headers[key] = value
    }
  }
  return headers
}

function onSampleChange(event: Event) {
  const files = (event.target as HTMLInputElement)?.files
  selectedSample.value = files?.[0] || null
}

async function refreshRuntime() {
  runtimeLoading.value = true
  try {
    const response: any = await getUploadAuditRuntime()
    const payload = response?.data ?? response
    runtimeMode.value = payload?.ids_upload_audit_mode || 'static_only'
    runtimeMessage.value = payload?.ids_upload_audit_message || '后端未返回审计状态说明。'
  } catch {
    runtimeMode.value = 'static_only'
    runtimeMessage.value = '无法读取后端审计状态，请确认安全分析服务已启动。'
  } finally {
    runtimeLoading.value = false
  }
}

async function submitRequestReplay() {
  requestLoading.value = true
  try {
    const response: any = await detectIDSRequest({
      client_ip: requestForm.client_ip,
      method: requestForm.method,
      path: requestForm.path,
      query: requestForm.query,
      body: requestForm.body,
      user_agent: requestForm.user_agent,
      headers: parseHeaders(requestForm.headersText),
    })
    const payload = response?.data ?? response
    requestResult.value = payload
    if (payload?.matched) {
      ElMessage.success('请求检测完成，已生成研判事件。')
    } else {
      ElMessage.success('请求检测完成，当前未命中规则。')
    }
  } catch {
    ElMessage.error('请求攻击检测失败')
  } finally {
    requestLoading.value = false
  }
}

async function submitSample() {
  if (!selectedSample.value) {
    ElMessage.warning('请先选择样本文件')
    return
  }

  sampleLoading.value = true
  try {
    const response: any = await submitDetectionSample(selectedSample.value)
    const payload = response?.data ?? response
    sampleResult.value = payload
    ElMessage.success(payload?.quarantined ? '样本已转入安全沙箱' : '样本送检通过')
  } catch {
    ElMessage.error('样本送检失败')
  } finally {
    sampleLoading.value = false
  }
}

function openEvent(eventId?: number | null) {
  if (!eventId) return
  void router.push({ path: '/events', query: { event: String(eventId) } })
}

function openWorkbench(eventId?: number | null) {
  if (!eventId) return
  void router.push({ path: '/workbench', query: { event: String(eventId) } })
}

onMounted(() => {
  void refreshRuntime()
})
</script>

<template>
  <section class="tools-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Controlled Detection Tools</p>
        <h1>检测工具</h1>
        <p class="subtitle">
          面向验证复核的检测工具页，提供请求重放检测与样本送检能力，用于补充证据和验证防护策略。
        </p>
      </div>
      <div class="runtime-card">
        <strong>{{ runtimeModeLabel }}</strong>
        <span>{{ runtimeLoading ? '正在读取后端状态...' : runtimeMessage }}</span>
      </div>
    </header>

    <div class="tool-grid">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>请求攻击检测</h2>
            <p>将捕获到的原始请求重新送入 IDS 规则链，验证命中情况、风险评分与阻断动作。</p>
          </div>
          <el-button type="primary" :loading="requestLoading" @click="submitRequestReplay">
            开始检测
          </el-button>
        </div>

        <div class="form-grid">
          <el-input v-model="requestForm.client_ip" placeholder="来源 IP" />
          <el-select v-model="requestForm.method">
            <el-option label="GET" value="GET" />
            <el-option label="POST" value="POST" />
            <el-option label="PUT" value="PUT" />
            <el-option label="DELETE" value="DELETE" />
          </el-select>
          <el-input v-model="requestForm.path" placeholder="/api/order/list" />
          <el-input v-model="requestForm.query" placeholder="id=1%20or%201=1" />
          <el-input v-model="requestForm.user_agent" placeholder="User-Agent" />
        </div>

        <div class="text-grid">
          <el-input
            v-model="requestForm.headersText"
            type="textarea"
            :rows="6"
            placeholder="Host: protected.local&#10;Accept: */*"
          />
          <el-input
            v-model="requestForm.body"
            type="textarea"
            :rows="6"
            placeholder="username=admin' or '1'='1"
          />
        </div>

        <div v-if="requestResult" class="result-card">
          <div class="result-head">
            <strong>{{ requestResult.matched ? '已命中规则' : '未命中规则' }}</strong>
            <el-tag :type="requestResult.matched ? (requestResult.would_block ? 'danger' : 'warning') : 'info'">
              风险 {{ requestResult.risk_score }}
            </el-tag>
          </div>
          <p>攻击类型：{{ requestResult.attack_type || '-' }}</p>
          <p>是否会拦截：{{ requestResult.would_block ? '会' : '不会' }}</p>
          <p>说明：{{ requestResult.detail || '-' }}</p>
          <div v-if="requestResult.event_id" class="result-actions">
            <el-button @click="openEvent(requestResult.event_id)">打开事件中心</el-button>
            <el-button type="primary" @click="openWorkbench(requestResult.event_id)">打开工作台</el-button>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>样本送检</h2>
            <p>用于提交可疑文件、WebShell 样本和恶意附件，执行审计、隔离与关联事件留痕。</p>
          </div>
          <el-button type="primary" :loading="sampleLoading" @click="submitSample">提交送检</el-button>
        </div>

        <label class="sample-picker">
          <input type="file" class="sample-input" @change="onSampleChange" />
          <span>{{ selectedSample?.name || '选择待审计样本' }}</span>
        </label>

        <div v-if="sampleResult" class="result-card">
          <div class="result-head">
            <strong>{{ sampleResult.quarantined ? '样本已隔离' : '样本送检通过' }}</strong>
            <el-tag :type="sampleResult.quarantined ? 'danger' : 'success'">
              {{ sampleResult.audit.verdict }}
            </el-tag>
          </div>
          <p>文件名：{{ sampleResult.filename }}</p>
          <p>风险等级：{{ sampleResult.audit.risk_level }}</p>
          <p>分析模式：{{ sampleResult.audit.analysis_mode || runtimeMode }}</p>
          <p>摘要：{{ sampleResult.audit.summary }}</p>
          <div class="result-actions">
            <el-button v-if="linkedSampleEventId" @click="openEvent(linkedSampleEventId)">查看事件</el-button>
            <el-button v-if="linkedSampleEventId" type="primary" @click="openWorkbench(linkedSampleEventId)">
              进入工作台
            </el-button>
            <el-button v-if="sampleResult.quarantined" @click="router.push('/sandbox')">打开样本沙箱</el-button>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped lang="scss">
.tools-page {
  min-height: 100%;
  padding: 28px;
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.08), transparent 24%),
    linear-gradient(180deg, #040b16, #07111f 46%, #0b1325 100%);
}

.page-header,
.panel,
.runtime-card {
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(8, 15, 28, 0.84);
  box-shadow: 0 24px 48px rgba(2, 6, 23, 0.24);
}

.page-header {
  display: flex;
  justify-content: space-between;
  gap: 18px;
  padding: 28px;
  margin-bottom: 18px;
}

.eyebrow {
  margin: 0 0 10px;
  color: #67e8f9;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  font-size: 12px;
}

.page-header h1,
.panel h2 {
  margin: 0;
  color: #f8fafc;
}

.subtitle,
.runtime-card span,
.panel-head p,
.result-card p {
  color: rgba(203, 213, 225, 0.8);
}

.subtitle {
  margin: 12px 0 0;
  max-width: 760px;
  line-height: 1.8;
}

.runtime-card {
  min-width: 260px;
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.runtime-card strong {
  color: #f8fafc;
}

.tool-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.panel {
  padding: 22px;
}

.panel-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.panel-head h2 {
  margin-bottom: 8px;
}

.form-grid,
.text-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.text-grid {
  grid-template-columns: 1fr;
}

.sample-picker {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 120px;
  border: 1px dashed rgba(56, 189, 248, 0.35);
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.72);
  color: #dbeafe;
  cursor: pointer;
  margin-bottom: 14px;
}

.sample-input {
  display: none;
}

.result-card {
  padding: 16px;
  border-radius: 18px;
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(148, 163, 184, 0.12);
}

.result-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  color: #f8fafc;
}

.result-actions {
  display: flex;
  gap: 10px;
  margin-top: 12px;
  flex-wrap: wrap;
}

@media (max-width: 1080px) {
  .page-header,
  .panel-head {
    flex-direction: column;
  }

  .tool-grid,
  .form-grid {
    grid-template-columns: 1fr;
  }
}
</style>
