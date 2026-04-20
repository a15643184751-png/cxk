<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getIDSNotificationSettings,
  testIDSNotifications,
  updateIDSNotificationSettings,
} from '@/api/ids'
import type {
  IDSNotificationDispatchResponse,
  IDSNotificationSettings,
} from '@/api/ids'

function createSettings(): IDSNotificationSettings {
  return {
    email: {
      enabled: false,
      smtp_host: '',
      smtp_port: 465,
      username: '',
      password: '',
      password_configured: false,
      from_addr: '',
      to_addrs: '',
      use_tls: false,
      use_ssl: true,
    },
    wecom: {
      enabled: false,
      webhook_url: '',
    },
    webhook: {
      enabled: false,
      url: '',
      secret: '',
      secret_configured: false,
    },
  }
}

type TestResultItem = {
  channel: string
  status: string
  detail?: string
  http_status?: number
}

const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const settings = reactive<IDSNotificationSettings>(createSettings())
const lastTestResult = ref<IDSNotificationDispatchResponse | null>(null)

const smtpModeLabel = computed(() => {
  if (settings.email.use_ssl) return 'SSL'
  if (settings.email.use_tls) return 'STARTTLS'
  return 'Plain SMTP'
})

const smtpAdvice = computed(() => {
  if (settings.email.use_ssl) return '推荐端口通常为 465'
  if (settings.email.use_tls) return '推荐端口通常为 587'
  return '未加密 SMTP 一般只建议在内网或测试环境使用'
})

const smtpReady = computed(() => {
  return Boolean(
    settings.email.smtp_host.trim() &&
    settings.email.to_addrs.trim() &&
    (settings.email.username.trim() || settings.email.from_addr.trim()),
  )
})

function applySettings(payload: IDSNotificationSettings) {
  Object.assign(settings.email, payload.email)
  Object.assign(settings.wecom, payload.wecom)
  Object.assign(settings.webhook, payload.webhook)
}

function resultType(status: string) {
  if (status === 'sent') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'skipped') return 'warning'
  return 'info'
}

function resultLabel(item: TestResultItem) {
  if (item.status === 'sent') return '发送成功'
  if (item.status === 'failed') return '发送失败'
  if (item.status === 'skipped') return '已跳过'
  if (item.status === 'disabled') return '未启用'
  return item.status || '未知状态'
}

function channelLabel(channel: string) {
  if (channel === 'email') return '邮件'
  if (channel === 'wecom') return '企业微信'
  if (channel === 'webhook') return 'Webhook'
  return channel || '未知通道'
}

async function loadSettings() {
  loading.value = true
  try {
    const response: any = await getIDSNotificationSettings()
    applySettings(response?.data ?? response)
  } catch {
    ElMessage.error('通知配置加载失败')
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const response: any = await updateIDSNotificationSettings({
      email: { ...settings.email },
      wecom: { ...settings.wecom },
      webhook: { ...settings.webhook },
    })
    applySettings(response?.data ?? response)
    settings.email.password = ''
    settings.webhook.secret = ''
    ElMessage.success('通知配置已保存')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function runTest() {
  testing.value = true
  try {
    const response: any = await testIDSNotifications()
    const payload = (response?.data ?? response) as IDSNotificationDispatchResponse
    lastTestResult.value = payload
    const results = payload?.results ?? []
    const sent = results.filter((item) => item.status === 'sent').length
    if (sent > 0) {
      ElMessage.success(`测试通知已发出，成功通道 ${sent} 个`)
    } else {
      ElMessage.warning('测试已执行，但当前没有成功发送的外部通知通道')
    }
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '测试失败')
  } finally {
    testing.value = false
  }
}

watch(
  () => settings.email.use_ssl,
  (enabled) => {
    if (!enabled) return
    settings.email.use_tls = false
    if (!settings.email.smtp_port || settings.email.smtp_port === 587) {
      settings.email.smtp_port = 465
    }
  },
)

watch(
  () => settings.email.use_tls,
  (enabled) => {
    if (!enabled) return
    settings.email.use_ssl = false
    if (!settings.email.smtp_port || settings.email.smtp_port === 465) {
      settings.email.smtp_port = 587
    }
  },
)

onMounted(() => {
  void loadSettings()
})
</script>

<template>
  <section class="notifications-page" v-loading="loading">
    <header class="page-head">
      <div>
        <p class="eyebrow">Alert Routing</p>
        <h1>通知配置中心</h1>
        <p class="desc">
          这里负责系统的邮件、企业微信和 Webhook。页面弹窗、声音和桌面通知仍由事件中心本地触发，外部消息转发则由后端负责。
        </p>
      </div>
      <div class="head-actions">
        <el-button @click="loadSettings">刷新</el-button>
        <el-button type="warning" :loading="testing" @click="runTest">发送测试</el-button>
        <el-button type="primary" :loading="saving" @click="saveSettings">保存配置</el-button>
      </div>
    </header>

    <section class="guide-grid">
      <article class="guide-card">
        <span class="guide-kicker">邮件怎么发</span>
        <h2>一般不需要自建邮件服务器</h2>
        <p>
          这套 IDS 走的是标准 SMTP。最省事的做法是直接用你现成的企业邮箱、云邮箱或第三方 SMTP 服务，不用为了发告警邮件单独再搭一套邮件服务器。
        </p>
      </article>

      <article class="guide-card">
        <span class="guide-kicker">端口规则</span>
        <h2>{{ smtpModeLabel }}</h2>
        <p>{{ smtpAdvice }}</p>
        <p>通常只开一种加密方式，不建议同时勾选 `SSL` 和 `STARTTLS`。</p>
      </article>

      <article class="guide-card">
        <span class="guide-kicker">配置建议</span>
        <h2>先保存，再发送测试</h2>
        <p>
          邮件至少要填 `SMTP Host`、`收件地址`，以及可用的 `用户名/发件地址`。如果服务商要求授权码，就把授权码填在密码栏，不一定是邮箱登录密码。
        </p>
      </article>
    </section>

    <div class="section-grid">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>邮件通知</h2>
            <p class="panel-subtitle">后端会直接连接你配置的 SMTP 服务并发送事件摘要邮件。</p>
          </div>
          <el-switch v-model="settings.email.enabled" />
        </div>

        <div class="form-grid">
          <el-input v-model="settings.email.smtp_host" placeholder="smtp.example.com" />
          <el-input-number v-model="settings.email.smtp_port" :min="1" :max="65535" />
          <el-input v-model="settings.email.username" placeholder="SMTP 用户名 / 邮箱账号" />
          <el-input
            v-model="settings.email.password"
            type="password"
            show-password
            :placeholder="settings.email.password_configured ? '已保存旧密码，留空则不改' : 'SMTP 密码 / 授权码'"
          />
          <el-input v-model="settings.email.from_addr" placeholder="发件地址，例如 ids@example.com" />
          <el-input v-model="settings.email.to_addrs" placeholder="收件地址，多个用英文逗号分隔" />
        </div>

        <div class="switch-row">
          <el-switch v-model="settings.email.use_ssl" />
          <span>使用 SSL</span>
          <el-switch v-model="settings.email.use_tls" />
          <span>使用 STARTTLS</span>
        </div>

        <div class="tips-box">
          <p>当前模式：{{ smtpModeLabel }} / 端口 {{ settings.email.smtp_port }}</p>
          <p>常见搭法：`465 + SSL` 或 `587 + STARTTLS`。</p>
          <p>准备情况：{{ smtpReady ? '基础字段已填，可以先保存再发测试' : '基础字段还没填全' }}</p>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>企业微信</h2>
            <p class="panel-subtitle">适合把高危事件直接推到群机器人。</p>
          </div>
          <el-switch v-model="settings.wecom.enabled" />
        </div>
        <el-input
          v-model="settings.wecom.webhook_url"
          type="textarea"
          :rows="6"
          placeholder="企业微信机器人 Webhook URL"
        />
      </section>
    </div>

    <section class="panel">
      <div class="panel-head">
        <div>
          <h2>Webhook</h2>
          <p class="panel-subtitle">适合把事件推到你自己的告警平台、SIEM 或自动化服务。</p>
        </div>
        <el-switch v-model="settings.webhook.enabled" />
      </div>
      <div class="form-grid">
        <el-input v-model="settings.webhook.url" placeholder="https://example.com/ids-hook" />
        <el-input
          v-model="settings.webhook.secret"
          type="password"
          show-password
          :placeholder="settings.webhook.secret_configured ? '已保存旧密钥，留空则不改' : 'Webhook Secret'"
        />
      </div>
      <p class="hint">IDS 会在请求头里带上 `X-IDS-Webhook-Secret`。</p>
    </section>

    <section v-if="lastTestResult" class="panel">
      <div class="panel-head">
        <div>
          <h2>最近一次测试结果</h2>
          <p class="panel-subtitle">这里会把每条通道的真实发送结果列出来，方便你定位是哪一环没通。</p>
        </div>
      </div>

      <div class="test-summary">
        <strong>{{ lastTestResult.payload.title }}</strong>
        <span>{{ lastTestResult.payload.body }}</span>
      </div>

      <div class="result-grid">
        <article
          v-for="item in lastTestResult.results"
          :key="item.channel"
          class="result-card"
        >
          <div class="result-head">
            <strong>{{ channelLabel(item.channel) }}</strong>
            <el-tag :type="resultType(item.status)">{{ resultLabel(item) }}</el-tag>
          </div>
          <p>状态：{{ item.status }}</p>
          <p v-if="item.http_status">HTTP：{{ item.http_status }}</p>
          <p v-if="item.detail">详情：{{ item.detail }}</p>
        </article>
      </div>
    </section>
  </section>
</template>

<style scoped lang="scss">
.notifications-page {
  min-height: 100%;
  padding: 28px;
  background:
    radial-gradient(circle at top right, rgba(34, 211, 238, 0.08), transparent 24%),
    linear-gradient(180deg, #040b16, #07111f 46%, #0b1325 100%);
}

.page-head,
.panel,
.guide-card {
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.14);
  background: rgba(8, 15, 28, 0.82);
  box-shadow: 0 24px 48px rgba(2, 6, 23, 0.24);
}

.page-head {
  display: flex;
  justify-content: space-between;
  gap: 24px;
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

.page-head h1,
.panel h2,
.guide-card h2 {
  margin: 0;
  color: #f8fafc;
  text-shadow: 0 2px 12px rgba(15, 23, 42, 0.32);
}

.desc,
.hint,
.panel-subtitle,
.guide-card p,
.tips-box p,
.test-summary span,
.result-card p {
  color: #eaf2ff;
  font-weight: 500;
}

.desc {
  margin: 12px 0 0;
  max-width: 760px;
  line-height: 1.8;
  font-size: 15px;
}

.head-actions {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.guide-grid,
.section-grid,
.result-grid {
  display: grid;
  gap: 18px;
}

.guide-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  margin-bottom: 18px;
}

.guide-card {
  padding: 22px;
}

.guide-kicker {
  display: inline-block;
  margin-bottom: 12px;
  color: #cffafe;
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
}

.guide-card p {
  margin: 12px 0 0;
  line-height: 1.75;
  font-size: 15px;
}

.section-grid {
  grid-template-columns: 1.4fr 1fr;
  margin-bottom: 18px;
}

.panel {
  padding: 22px;
  --el-input-bg-color: rgba(9, 17, 32, 0.98);
  --el-fill-color-blank: rgba(9, 17, 32, 0.98);
  --el-fill-color-light: rgba(15, 23, 42, 0.98);
  --el-text-color-primary: #f8fafc;
  --el-text-color-regular: #eaf2ff;
  --el-text-color-placeholder: rgba(219, 234, 254, 0.84);
  --el-border-color: rgba(148, 163, 184, 0.2);
  --el-border-color-hover: rgba(125, 211, 252, 0.38);
  --el-disabled-bg-color: rgba(9, 17, 32, 0.98);
  --el-disabled-text-color: #eaf2ff;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.panel-subtitle {
  margin: 8px 0 0;
  line-height: 1.7;
  font-size: 14px;
}

.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 16px;
  color: rgba(241, 245, 249, 0.96);
  font-weight: 600;
  flex-wrap: wrap;
}

.tips-box,
.test-summary,
.result-card {
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(15, 23, 42, 0.9);
}

.tips-box {
  margin-top: 16px;
  padding: 14px 16px;
}

.tips-box p,
.result-card p {
  margin: 0 0 8px;
  line-height: 1.7;
}

.tips-box p:last-child,
.result-card p:last-child {
  margin-bottom: 0;
}

.hint {
  margin: 14px 0 0;
  line-height: 1.7;
}

.test-summary {
  padding: 16px;
  margin-bottom: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.test-summary strong {
  color: #f8fafc;
}

.result-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.result-card {
  padding: 16px;
}

.result-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.result-head strong {
  color: #f8fafc;
}

.panel :deep(.el-input),
.panel :deep(.el-input-number),
.panel :deep(.el-textarea) {
  --el-input-bg-color: rgba(9, 17, 32, 0.98) !important;
  --el-fill-color-blank: rgba(9, 17, 32, 0.98) !important;
  --el-disabled-bg-color: rgba(9, 17, 32, 0.98) !important;
  --el-disabled-text-color: #eaf2ff !important;
  --el-text-color-placeholder: rgba(219, 234, 254, 0.84) !important;
  --el-border-color: rgba(148, 163, 184, 0.2) !important;
  --el-border-color-hover: rgba(125, 211, 252, 0.38) !important;
}

.panel :deep(.el-input__wrapper),
.panel :deep(.el-input-number),
.panel :deep(.el-input-number .el-input__wrapper),
.panel :deep(.el-textarea__inner) {
  background: linear-gradient(180deg, rgba(10, 18, 34, 0.98), rgba(12, 22, 40, 0.98)) !important;
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.22) inset !important;
  border-radius: 12px !important;
}

.panel :deep(.el-input.is-disabled .el-input__wrapper),
.panel :deep(.el-input-number.is-disabled .el-input__wrapper),
.panel :deep(.el-textarea.is-disabled .el-textarea__inner) {
  background: linear-gradient(180deg, rgba(10, 18, 34, 0.98), rgba(12, 22, 40, 0.98)) !important;
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.2) inset !important;
}

.panel :deep(.el-input__inner),
.panel :deep(.el-input-number .el-input__inner),
.panel :deep(.el-textarea__inner) {
  color: #f8fafc !important;
  -webkit-text-fill-color: #f8fafc !important;
  font-weight: 600;
  font-size: 14px;
  opacity: 1;
  caret-color: #f8fafc;
}

.panel :deep(.el-input__inner::placeholder),
.panel :deep(.el-input-number .el-input__inner::placeholder),
.panel :deep(.el-textarea__inner::placeholder) {
  color: rgba(219, 234, 254, 0.84) !important;
  -webkit-text-fill-color: rgba(219, 234, 254, 0.84) !important;
  opacity: 1 !important;
}

.panel :deep(.el-input__inner:-webkit-autofill),
.panel :deep(.el-input__inner:-webkit-autofill:hover),
.panel :deep(.el-input__inner:-webkit-autofill:focus),
.panel :deep(.el-textarea__inner:-webkit-autofill),
.panel :deep(.el-textarea__inner:-webkit-autofill:hover),
.panel :deep(.el-textarea__inner:-webkit-autofill:focus) {
  -webkit-text-fill-color: #f8fafc !important;
  caret-color: #f8fafc;
  box-shadow: 0 0 0 1000px rgba(9, 17, 32, 0.98) inset !important;
  -webkit-box-shadow: 0 0 0 1000px rgba(9, 17, 32, 0.98) inset !important;
  transition: background-color 9999s ease-out 0s;
}

.panel :deep(.el-input__wrapper:hover),
.panel :deep(.el-textarea__inner:hover),
.panel :deep(.el-input-number:hover),
.panel :deep(.el-input-number .el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.34) inset !important;
}

.panel :deep(.el-input__wrapper.is-focus),
.panel :deep(.el-textarea__inner:focus),
.panel :deep(.el-input-number.is-controls-right .el-input__wrapper.is-focus),
.panel :deep(.el-input-number .el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.58) inset, 0 0 0 4px rgba(56, 189, 248, 0.14) !important;
}

.panel :deep(.el-input-number__increase),
.panel :deep(.el-input-number__decrease) {
  background: rgba(15, 23, 42, 0.98);
  color: #f8fafc;
  border-left: 1px solid rgba(148, 163, 184, 0.18);
}

.panel :deep(.el-input-number__increase:hover),
.panel :deep(.el-input-number__decrease:hover) {
  color: #67e8f9;
}

.panel :deep(.el-input-number .el-input__inner) {
  color: #f8fafc;
  -webkit-text-fill-color: #f8fafc;
  font-weight: 700;
}

.panel :deep(.el-switch) {
  --el-switch-on-color: #3b82f6;
  --el-switch-off-color: rgba(148, 163, 184, 0.35);
}

.panel :deep(.el-switch__core) {
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.18) inset;
}

.panel :deep(.el-switch__label) {
  color: rgba(241, 245, 249, 0.95);
}

@media (max-width: 1180px) {
  .page-head,
  .guide-grid,
  .section-grid,
  .form-grid,
  .result-grid {
    grid-template-columns: 1fr;
  }

  .page-head {
    flex-direction: column;
  }

  .head-actions {
    flex-wrap: wrap;
  }
}
</style>
