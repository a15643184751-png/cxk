<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'

export interface UploadResponse {
  ok: boolean
  filename?: string
  saved_as?: string
  size?: number
  url?: string
  via_ids_standalone?: boolean
  upload_state?: 'accepted' | 'quarantined'
  quarantined?: boolean
  stored_in?: 'accepted' | 'quarantine'
  ids_forward_error?: string
  audit?: {
    verdict?: string
    risk_level?: string
    confidence?: number
    summary?: string
    analysis_mode?: string
    llm_used?: boolean
    linked_event_id?: number | null
    evidence?: string[]
    recommended_actions?: string[]
  }
  security_alert?: {
    style?: string
    http_status_hint?: number
    title?: string
    message?: string
    detail?: string
  }
}

const loading = ref(false)
const fileList = ref<File[]>([])
const lastResult = ref<UploadResponse | null>(null)

function onFileChange(files: FileList | null) {
  fileList.value = files ? Array.from(files) : []
}

function auditModeLabel(result: UploadResponse | null): string {
  if (!result?.audit) return '基础审计'
  return result.audit.llm_used || result.audit.analysis_mode === 'llm_assisted'
    ? 'AI 审计'
    : '静态审计'
}

function dispositionLabel(result: UploadResponse | null): string {
  if (!result) return '-'
  if (result.quarantined) return '已转入安全沙箱'
  if (result.stored_in === 'accepted') return '已进入内部样本库'
  return '已完成接收'
}

/**
 * 上传接口地址：
 * - 默认同源 `/api/upload`（Vite 代理或 Nginx 反代）
 * - 若配置了 `VITE_PUBLIC_UPLOAD_URL` 则优先（完整 URL）
 * - 若 `VITE_API_BASE` 为完整 URL（如局域网直连后端 http://192.168.x.x:8166/api），则使用 `${VITE_API_BASE}/upload`
 */
function resolveUploadUrl(): string {
  const custom = import.meta.env.VITE_PUBLIC_UPLOAD_URL as string | undefined
  if (custom?.trim()) return custom.trim()
  const apiBase = import.meta.env.VITE_API_BASE as string | undefined
  if (apiBase?.trim()) {
    const b = apiBase.replace(/\/$/, '')
    return `${b}/upload`
  }
  return '/api/upload'
}

/**
 * 上传成功落盘，但不弹「上传成功」；
 * 若响应含 security_alert，弹 403 风格 + 木马告警浮窗。
 */
async function handleUpload() {
  if (fileList.value.length === 0) {
    ElMessage.warning('请选择文件')
    return
  }
  const file = fileList.value[0]
  loading.value = true
  lastResult.value = null
  try {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(resolveUploadUrl(), {
      method: 'POST',
      body: form,
      credentials: 'include',
    })
    const j = (await res.json().catch(() => ({}))) as UploadResponse
    if (!res.ok) {
      const detail =
        typeof (j as any).detail === 'string'
          ? (j as any).detail
          : `请求失败 (${res.status})`
      ElMessage.error(detail)
      return
    }
    if (j.ok && j.security_alert) {
      lastResult.value = j
      const sa = j.security_alert
      const body = [sa.message, sa.detail].filter(Boolean).join('\n\n')
      await ElMessageBox.alert(body, sa.title || '403 Forbidden · 木马告警', {
        type: 'error',
        confirmButtonText: '已知晓',
        customClass: 'public-upload-malware-dialog',
      })
      return
    }
    if (j.ok) {
      lastResult.value = j
      ElMessage.success(`上传成功：${j.filename || ''}`)
    } else {
      ElMessage.error('上传失败')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '网络错误')
  } finally {
    loading.value = false
  }
}

function clearAll() {
  fileList.value = []
  lastResult.value = null
}
</script>

<template>
  <div class="upload-page">
    <div class="upload-bg" />
    <div class="upload-card">
      <div class="card-header">
        <h2>匿名举报 / 反馈材料上传</h2>
        <p>如发现平台违规问题，可匿名上传相关材料，我们将核实处理</p>
      </div>

      <div class="upload-form">
        <div class="file-input-wrap">
          <input
            type="file"
            id="fileInput"
            class="file-input"
            @change="(e: Event) => onFileChange((e.target as HTMLInputElement)?.files)"
          />
          <label for="fileInput" class="file-label">
            <el-icon :size="24"><Upload /></el-icon>
            <span>选择文件</span>
          </label>
        </div>
        <p v-if="fileList.length" class="selected-file">{{ fileList[0]?.name }}（{{ ((fileList[0]?.size || 0) / 1024).toFixed(1) }} KB）</p>

        <div class="actions">
          <el-button type="primary" :loading="loading" @click="handleUpload">上传</el-button>
          <el-button @click="clearAll">清空</el-button>
        </div>
      </div>

      <div v-if="lastResult?.ok && lastResult.saved_as" class="result-box" :class="{ 'result-box--warn': lastResult.security_alert }">
        <h4>{{ lastResult.security_alert ? '上传已落盘（功能正常）' : '上传结果' }}</h4>
        <p>文件名：{{ lastResult.filename }}</p>
        <p>保存为：{{ lastResult.saved_as }}</p>
        <p>大小：{{ lastResult.size }} 字节</p>
        <a v-if="lastResult.url" :href="lastResult.url" target="_blank" rel="noopener">访问文件</a>
        <p v-if="lastResult.security_alert" class="result-note">
          上方已弹出「403 + 木马告警」提示；文件实际已写入服务器，供管理员在隔离区查看。
        </p>
      </div>

      <div v-if="lastResult?.ok && lastResult.saved_as && lastResult.audit" class="audit-summary-box">
        <div class="audit-pills">
          <span class="audit-pill">{{ auditModeLabel(lastResult) }}</span>
          <span class="audit-pill" :class="{ 'audit-pill--danger': lastResult.quarantined }">
            {{ lastResult.audit.verdict || '-' }}
          </span>
        </div>
        <p>处理结果：{{ dispositionLabel(lastResult) }}</p>
        <p>风险等级：{{ lastResult.audit.risk_level || '-' }}</p>
        <p>置信度：{{ typeof lastResult.audit.confidence === 'number' ? `${lastResult.audit.confidence}%` : '-' }}</p>
        <p>审计摘要：{{ lastResult.audit.summary || '-' }}</p>
        <p v-if="lastResult.audit.linked_event_id">关联事件：#{{ lastResult.audit.linked_event_id }}</p>
        <div v-if="lastResult.audit.evidence?.length" class="evidence-list">
          <div class="evidence-title">命中依据</div>
          <ul>
            <li v-for="item in lastResult.audit.evidence" :key="item">{{ item }}</li>
          </ul>
        </div>
      </div>

      <p class="hint">
        无需登录即可上传 · 局域网请用本机 IP 访问前端（如 http://192.168.x.x:5173/upload），勿用 127.0.0.1 代替对方电脑。
      </p>
    </div>

    <router-link to="/login" class="back-link">返回登录</router-link>
  </div>
</template>

<style lang="scss">
/* MessageBox 全局挂载：加深 403/木马告警视觉 */
.el-overlay-dialog .public-upload-malware-dialog.el-message-box {
  border: 1px solid #fecaca;
  background: linear-gradient(180deg, #fff5f5 0%, #ffffff 100%);
}
.el-overlay-dialog .public-upload-malware-dialog .el-message-box__title {
  color: #b91c1c;
  font-weight: 700;
}
.el-overlay-dialog .public-upload-malware-dialog .el-message-box__message {
  color: #7f1d1d;
  white-space: pre-wrap;
  line-height: 1.55;
}
</style>

<style lang="scss" scoped>
.upload-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 24px;
  position: relative;
}

.upload-bg {
  position: fixed;
  inset: 0;
  background: linear-gradient(135deg, #fafaf9 0%, #f0f4f8 100%);
  z-index: 0;
}

.upload-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: 32px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.08);
}

.card-header {
  text-align: center;
  margin-bottom: 28px;

  h2 {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 8px;
  }

  p {
    font-size: 13px;
    color: var(--text-muted);
    margin: 0;
  }
}

.file-input-wrap {
  position: relative;
}

.file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  overflow: hidden;
}

.file-label {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px 24px;
  border: 2px dashed var(--border-color, #dcdfe6);
  border-radius: 12px;
  cursor: pointer;
  color: var(--text-secondary);
  transition: all 0.2s;

  &:hover {
    border-color: var(--primary);
    color: var(--primary);
  }
}

.selected-file {
  font-size: 13px;
  color: var(--text-muted);
  margin: 12px 0 0;
}

.actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.result-box {
  margin-top: 24px;
  padding: 16px;
  background: var(--primary-muted, #f0f4ff);
  border-radius: 10px;

  h4 {
    margin: 0 0 8px;
    font-size: 14px;
  }

  p {
    margin: 4px 0;
    font-size: 13px;
  }

  a {
    display: inline-block;
    margin-top: 8px;
    color: var(--primary);
    font-size: 13px;
  }
}

.result-box--warn {
  background: #fffbeb;
  border: 1px solid #fde68a;
}

.result-note {
  margin-top: 10px !important;
  font-size: 12px !important;
  color: #92400e !important;
  line-height: 1.45;
}

.audit-summary-box {
  margin-top: 18px;
  padding: 16px;
  border-radius: 12px;
  border: 1px solid #dbeafe;
  background: linear-gradient(180deg, #f8fbff 0%, #eef6ff 100%);

  p {
    margin: 6px 0;
    font-size: 13px;
    color: #1f2937;
    line-height: 1.55;
  }
}

.audit-pills {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}

.audit-pill {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #dbeafe;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
}

.audit-pill--danger {
  background: #fee2e2;
  color: #b91c1c;
}

.evidence-list {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(148, 163, 184, 0.22);

  ul {
    margin: 8px 0 0;
    padding-left: 18px;
  }

  li {
    margin: 6px 0;
    font-size: 12px;
    color: #475569;
    line-height: 1.5;
  }
}

.evidence-title {
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
}

.hint {
  margin-top: 20px;
  font-size: 12px;
  color: var(--text-muted);
  text-align: center;
  line-height: 1.5;
}

.back-link {
  position: relative;
  z-index: 1;
  margin-top: 20px;
  font-size: 14px;
  color: var(--primary);
}
</style>
