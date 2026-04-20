<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getIDSCommunicationSettings,
  updateIDSCommunicationSettings,
} from '@/api/ids'
import type {
  IDSCommunicationDisplaySettings,
  IDSCommunicationRealSettings,
  IDSCommunicationSettings,
} from '@/api/ids'

function createSettings(): IDSCommunicationSettings {
  return {
    real: {
      gateway_port: 8188,
      frontend_ip: '',
      frontend_port: 5173,
      backend_ip: '',
      backend_port: 8166,
    },
    display: {
      site_label: '校园供应链主站',
      domain_code: 'Campus-Link-A',
      link_template: '教学业务链路',
      routing_profile: '双向会话镜像',
      packet_profile: 'HTTP 会话包',
      signal_band: '基础频段',
      coordination_group: '校内联防单元',
      display_mode: '总控视图',
      session_track_mode: '连续轮转',
      trace_color_mode: '分层染色',
      link_sync_clock: '边界同步时钟',
      relay_group: 'north-gateway',
      auto_rotate: true,
      popup_broadcast: true,
      packet_shadow: true,
      link_keepalive: true,
    },
    derived: {
      frontend_upstream_url: '',
      backend_upstream_url: '',
      gateway_port: 8188,
      restart_required: true,
      effective_scope: '',
      effective_hint: '',
      env_path: '',
    },
    updated_at: null,
  }
}

const loading = ref(false)
const saving = ref(false)
const settings = reactive<IDSCommunicationSettings>(createSettings())

const linkTemplateOptions = ['教学业务链路', '采购审批链路', '仓储协同链路', '边界访问链路']
const routingProfileOptions = ['双向会话镜像', '入口旁路审计', '单向聚束转发', '会话聚束回放']
const packetProfileOptions = ['HTTP 会话包', '业务对象包', '轻量回放包', '通信归档包']
const signalBandOptions = ['基础频段', '教学频段', '仓储频段', '采购频段']
const displayModeOptions = ['总控视图', '联动面板', '通信沙盘', '事件指挥席']
const sessionTrackOptions = ['连续轮转', '突发优先', '按风险切换', '按源地址切换']
const traceColorOptions = ['分层染色', '风险染色', '业务染色', '统一冷色']
const coordinationOptions = ['校内联防单元', '边界协同单元', '审计联动单元', '实训协同单元']
const syncClockOptions = ['边界同步时钟', '主控时钟 A', '主控时钟 B', '巡检时钟']

const frontendPreview = computed(
  () => `http://${settings.real.frontend_ip || '<前端IP>'}:${settings.real.frontend_port}`,
)
const backendPreview = computed(
  () => `http://${settings.real.backend_ip || '<后端IP>'}:${settings.real.backend_port}`,
)
const gatewayPreview = computed(
  () => `http://<IDS 主机 IP>:${settings.real.gateway_port}`,
)

const scopeCards = computed(() => [
  {
    label: '前端上游',
    value: frontendPreview.value,
    note: '主站回源',
    tone: 'accent',
  },
  {
    label: '后端上游',
    value: backendPreview.value,
    note: '接口回源',
    tone: 'accent',
  },
  {
    label: '网关入口',
    value: gatewayPreview.value,
    note: '统一接入',
    tone: 'warning',
  },
  {
    label: '配置落点',
    value: settings.derived.env_path || 'ids-backend/.env',
    note: '本地配置',
    tone: 'neutral',
  },
])

const displaySignals = computed(() => [
  {
    label: '通信域标识',
    value: settings.display.domain_code,
  },
  {
    label: '链路模板',
    value: settings.display.link_template,
  },
  {
    label: '展示模式',
    value: settings.display.display_mode,
  },
  {
    label: '轮转方式',
    value: settings.display.session_track_mode,
  },
])

function applySettings(payload: IDSCommunicationSettings) {
  Object.assign(settings.real, payload.real as IDSCommunicationRealSettings)
  Object.assign(settings.display, payload.display as IDSCommunicationDisplaySettings)
  Object.assign(settings.derived, payload.derived)
  settings.updated_at = payload.updated_at || null
}

async function loadSettings() {
  loading.value = true
  try {
    const response: any = await getIDSCommunicationSettings()
    applySettings((response?.data ?? response) as IDSCommunicationSettings)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '通信配置加载失败')
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const response: any = await updateIDSCommunicationSettings({
      real: { ...settings.real },
      display: { ...settings.display },
    })
    applySettings((response?.data ?? response) as IDSCommunicationSettings)
    ElMessage.success('通信配置已保存，网关重启后将使用新的接入配置')
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.detail || error?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  void loadSettings()
})
</script>

<template>
  <section class="communication-config-page" v-loading="loading">
    <header class="page-head">
      <div>
        <p class="eyebrow">Communication Profile</p>
        <h1>通信配置中心</h1>
        <p class="desc">
          这里统一维护 IDS 的链路接入、通信域标识和控制台编排参数。核心接入地址决定网关回源，其余参数用于链路命名、会话分组和控制台视图管理。
        </p>
      </div>

      <div class="head-actions">
        <el-button @click="loadSettings">刷新</el-button>
        <el-button type="primary" :loading="saving" @click="saveSettings">保存配置</el-button>
      </div>
    </header>

    <section class="hero-grid">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>核心接入参数</h2>
            <p class="panel-subtitle">用于配置当前链路的网关入口、业务前端回源和业务后端回源。</p>
          </div>
          <el-tag type="danger">保存后重启网关生效</el-tag>
        </div>

        <div class="real-form-grid">
          <div class="field-block field-block--wide">
            <span class="field-label">网关接入端口</span>
            <el-input-number v-model="settings.real.gateway_port" :min="1" :max="65535" />
          </div>

          <div class="field-block">
            <span class="field-label">业务前端 IP</span>
            <el-input v-model="settings.real.frontend_ip" placeholder="例如 10.134.32.153" />
          </div>
          <div class="field-block">
            <span class="field-label">业务前端端口</span>
            <el-input-number v-model="settings.real.frontend_port" :min="1" :max="65535" />
          </div>

          <div class="field-block">
            <span class="field-label">业务后端 IP</span>
            <el-input v-model="settings.real.backend_ip" placeholder="例如 10.134.32.153" />
          </div>
          <div class="field-block">
            <span class="field-label">业务后端端口</span>
            <el-input-number v-model="settings.real.backend_port" :min="1" :max="65535" />
          </div>
        </div>

        <div class="tips-box">
          <p>当前接入链路：网关入口 + 业务前端回源 + 业务后端回源。</p>
          <p>{{ settings.derived.effective_hint || '保存后系统会自动回写网关转发配置。' }}</p>
          <p v-if="settings.updated_at">最近保存时间：{{ settings.updated_at }}</p>
        </div>
      </section>

      <section class="panel preview-panel">
        <div class="panel-head">
          <div>
            <h2>自动生成结果</h2>
            <p class="panel-subtitle">保存后系统会自动拼接上游地址、网关入口和本地配置落点。</p>
          </div>
        </div>

        <div class="scope-grid">
          <article
            v-for="card in scopeCards"
            :key="card.label"
            class="scope-card"
            :class="card.tone"
          >
            <span>{{ card.label }}</span>
            <strong>{{ card.value }}</strong>
            <small>{{ card.note }}</small>
          </article>
        </div>

        <div class="signal-ribbon">
          <article v-for="item in displaySignals" :key="item.label" class="signal-card">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </section>
    </section>

    <section class="display-grid">
      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>通信域标识</h2>
            <p class="panel-subtitle">用于通信域命名和链路标识，便于会话归类与控制台识别。</p>
          </div>
        </div>

        <div class="form-grid">
          <div class="field-block">
            <span class="field-label">站点名称</span>
            <el-input v-model="settings.display.site_label" />
          </div>
          <div class="field-block">
            <span class="field-label">通信域编号</span>
            <el-input v-model="settings.display.domain_code" />
          </div>
          <div class="field-block">
            <span class="field-label">链路模板</span>
            <el-select v-model="settings.display.link_template" placeholder="选择链路模板">
              <el-option v-for="item in linkTemplateOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </div>
          <div class="field-block">
            <span class="field-label">协同分组</span>
            <el-select v-model="settings.display.coordination_group" placeholder="选择协同分组">
              <el-option v-for="item in coordinationOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>链路编排</h2>
            <p class="panel-subtitle">用于统一说明会话如何归束、转发和进入审计视图。</p>
          </div>
        </div>

        <div class="form-grid">
          <div class="field-block">
            <span class="field-label">路由编排</span>
            <el-select v-model="settings.display.routing_profile" placeholder="选择路由编排">
              <el-option v-for="item in routingProfileOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </div>
          <div class="field-block">
            <span class="field-label">会话封装</span>
            <el-select v-model="settings.display.packet_profile" placeholder="选择会话封装">
              <el-option v-for="item in packetProfileOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </div>
          <div class="field-block">
            <span class="field-label">频段标签</span>
            <el-select v-model="settings.display.signal_band" placeholder="选择频段标签">
              <el-option v-for="item in signalBandOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </div>
          <div class="field-block">
            <span class="field-label">同步时钟</span>
            <el-select v-model="settings.display.link_sync_clock" placeholder="选择同步时钟">
              <el-option v-for="item in syncClockOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <div>
            <h2>控制台编排</h2>
            <p class="panel-subtitle">用于控制标签、轮转方式和界面播报状态。</p>
          </div>
        </div>

        <div class="form-grid">
          <div class="field-block">
            <span class="field-label">展示模式</span>
            <el-select v-model="settings.display.display_mode" placeholder="选择展示模式">
              <el-option v-for="item in displayModeOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </div>
          <div class="field-block">
            <span class="field-label">会话轮转</span>
            <el-select v-model="settings.display.session_track_mode" placeholder="选择会话轮转">
              <el-option v-for="item in sessionTrackOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </div>
          <div class="field-block">
            <span class="field-label">轨迹染色</span>
            <el-select v-model="settings.display.trace_color_mode" placeholder="选择轨迹染色">
              <el-option v-for="item in traceColorOptions" :key="item" :label="item" :value="item" />
            </el-select>
          </div>
          <div class="field-block">
            <span class="field-label">中继分组</span>
            <el-input v-model="settings.display.relay_group" />
          </div>
        </div>

        <div class="switch-grid">
          <div class="switch-item">
            <span>自动轮转</span>
            <el-switch v-model="settings.display.auto_rotate" />
          </div>
          <div class="switch-item">
            <span>弹窗播报</span>
            <el-switch v-model="settings.display.popup_broadcast" />
          </div>
          <div class="switch-item">
            <span>数据包影子副本</span>
            <el-switch v-model="settings.display.packet_shadow" />
          </div>
          <div class="switch-item">
            <span>链路保活</span>
            <el-switch v-model="settings.display.link_keepalive" />
          </div>
        </div>
      </section>
    </section>
  </section>
</template>

<style scoped lang="scss">
.communication-config-page {
  min-height: 100%;
  padding: 28px;
  background:
    radial-gradient(circle at top right, rgba(34, 211, 238, 0.08), transparent 24%),
    linear-gradient(180deg, #040b16, #07111f 46%, #0b1325 100%);
}

.page-head,
.panel {
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
.panel h2 {
  margin: 0;
  color: #f8fafc;
  text-shadow: 0 2px 12px rgba(15, 23, 42, 0.32);
}

.desc,
.field-label,
.panel-subtitle,
.tips-box p,
.scope-card span,
.scope-card small,
.signal-card span {
  color: #eaf2ff;
  font-weight: 500;
}

.desc {
  margin: 12px 0 0;
  max-width: 780px;
  line-height: 1.8;
  font-size: 15px;
}

.head-actions {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.hero-grid,
.display-grid,
.scope-grid,
.signal-ribbon,
.form-grid,
.switch-grid {
  display: grid;
  gap: 18px;
}

.hero-grid {
  grid-template-columns: 1.35fr 1fr;
  margin-bottom: 18px;
}

.display-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
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
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
}

.panel-subtitle {
  margin: 8px 0 0;
  line-height: 1.7;
  font-size: 14px;
}

.real-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.field-block--wide {
  grid-column: 1 / -1;
}

.field-label {
  font-size: 13px;
  letter-spacing: 0.03em;
}

.tips-box,
.scope-card,
.signal-card,
.switch-item {
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(15, 23, 42, 0.9);
}

.tips-box {
  margin-top: 18px;
  padding: 14px 16px;
}

.tips-box p {
  margin: 0 0 8px;
  line-height: 1.7;
}

.tips-box p:last-child {
  margin-bottom: 0;
}

.scope-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.scope-card {
  padding: 16px;
}

.scope-card strong,
.signal-card strong {
  display: block;
  margin-top: 8px;
  color: #f8fafc;
  line-height: 1.55;
  word-break: break-word;
}

.scope-card small {
  display: block;
  margin-top: 8px;
  font-size: 12px;
}

.scope-card.accent strong {
  color: #67e8f9;
}

.scope-card.warning strong {
  color: #fbbf24;
}

.scope-card.neutral strong {
  color: #cbd5f5;
}

.signal-ribbon {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 18px;
}

.signal-card {
  padding: 14px 16px;
}

.signal-card strong {
  font-size: 15px;
}

.form-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.switch-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  margin-top: 18px;
}

.switch-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  color: #f8fafc;
  font-weight: 600;
}

.panel :deep(.el-input),
.panel :deep(.el-input-number),
.panel :deep(.el-textarea),
.panel :deep(.el-select) {
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
.panel :deep(.el-textarea__inner),
.panel :deep(.el-select__wrapper) {
  background: linear-gradient(180deg, rgba(10, 18, 34, 0.98), rgba(12, 22, 40, 0.98)) !important;
  box-shadow: 0 0 0 1px rgba(148, 163, 184, 0.22) inset !important;
  border-radius: 12px !important;
}

.panel :deep(.el-input__inner),
.panel :deep(.el-input-number .el-input__inner),
.panel :deep(.el-textarea__inner),
.panel :deep(.el-select__placeholder),
.panel :deep(.el-select__selected-item) {
  color: #f8fafc !important;
  -webkit-text-fill-color: #f8fafc !important;
  font-weight: 600;
  font-size: 14px;
  opacity: 1;
}

.panel :deep(.el-input__inner::placeholder),
.panel :deep(.el-input-number .el-input__inner::placeholder),
.panel :deep(.el-textarea__inner::placeholder) {
  color: rgba(219, 234, 254, 0.84) !important;
  -webkit-text-fill-color: rgba(219, 234, 254, 0.84) !important;
  opacity: 1 !important;
}

.panel :deep(.el-input__wrapper:hover),
.panel :deep(.el-textarea__inner:hover),
.panel :deep(.el-input-number:hover),
.panel :deep(.el-input-number .el-input__wrapper:hover),
.panel :deep(.el-select__wrapper:hover) {
  box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.34) inset !important;
}

.panel :deep(.el-input__wrapper.is-focus),
.panel :deep(.el-textarea__inner:focus),
.panel :deep(.el-input-number .el-input__wrapper.is-focus),
.panel :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1px rgba(56, 189, 248, 0.58) inset, 0 0 0 4px rgba(56, 189, 248, 0.14) !important;
}

.panel :deep(.el-input-number__increase),
.panel :deep(.el-input-number__decrease) {
  background: rgba(15, 23, 42, 0.98);
  color: #f8fafc;
  border-left: 1px solid rgba(148, 163, 184, 0.18);
}

.panel :deep(.el-switch) {
  --el-switch-on-color: #3b82f6;
  --el-switch-off-color: rgba(148, 163, 184, 0.35);
}

@media (max-width: 1280px) {
  .page-head,
  .hero-grid,
  .display-grid,
  .real-form-grid,
  .form-grid,
  .scope-grid,
  .signal-ribbon,
  .switch-grid {
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
