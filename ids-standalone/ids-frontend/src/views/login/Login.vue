<script setup lang="ts">
import { nextTick, onMounted, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import { ElMessage } from 'element-plus'
import { Lock, User } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const autoLoginTriggered = ref(false)
const form = reactive({
  username: 'ids_admin',
  password: '123456',
})

const rules: FormRules<typeof form> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  await formRef.value?.validate()
  loading.value = true
  try {
    const response: any = await login({
      username: form.username.trim(),
      password: form.password,
    })
    const payload = response?.data ?? response
    userStore.setToken(payload.access_token)
    userStore.setUserInfo(payload.user)
    ElMessage.success('登录成功')
    await router.replace((route.query.redirect as string) || '/overview')
  } catch (error: any) {
    const msg =
      error?.response?.data?.detail ||
      error?.message ||
      '登录失败，请检查安全分析服务是否已经启动'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

async function tryAutoLogin() {
  if (route.query.autologin !== '1' || autoLoginTriggered.value) return
  autoLoginTriggered.value = true
  userStore.logout()
  form.username = 'ids_admin'
  form.password = '123456'
  await nextTick()
  await handleLogin()
}

onMounted(async () => {
  if (route.query.autologin === '1') {
    await tryAutoLogin()
    return
  }

  if (userStore.isLoggedIn) {
    void router.replace('/overview')
  }
})
</script>

<template>
  <div class="login-page">
    <div class="login-backdrop" />

    <section class="login-layout">
      <aside class="hero-panel">
        <div class="hero-badge">Threat Verification Console</div>
        <h1>安全分析中心</h1>
        <p>
          安全分析中心聚焦流量检测、告警留痕、攻击研判、样本审计与复核验证，为渗透验证后的证据归集提供统一入口。
        </p>

        <div class="hero-grid">
          <article class="hero-card">
            <h3>事件中心</h3>
            <p>负责事件列表、筛选、处置、归档和证据闭环。</p>
          </article>
          <article class="hero-card">
            <h3>分析工作台</h3>
            <p>负责攻击画像、攻击链、聚类、误报学习、AI 研判和报告输出。</p>
          </article>
          <article class="hero-card">
            <h3>检测工具</h3>
            <p>提供请求重放检测、样本送检与关联事件联查能力，用于复核拦截结果和验证防护策略。</p>
          </article>
          <article class="hero-card">
            <h3>流量防护</h3>
            <p>当前已纳管应用侧 HTTP 请求与样本审计链路，可继续接入代理、WAF、Suricata、Zeek 等入口扩展覆盖范围。</p>
          </article>
        </div>
      </aside>

      <main class="form-panel">
        <div class="form-shell">
          <div class="form-head">
            <div class="form-logo">
              <el-icon><Lock /></el-icon>
            </div>
            <div>
              <h2>登录系统</h2>
              <p>默认管理员账号已预置为 ids_admin / 123456。</p>
            </div>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            class="login-form"
            label-position="top"
            @submit.prevent="handleLogin"
          >
            <el-form-item label="用户名" prop="username">
              <el-input
                v-model="form.username"
                autocomplete="username"
                :prefix-icon="User"
                placeholder="请输入账号"
              />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input
                v-model="form.password"
                type="password"
                show-password
                autocomplete="current-password"
                placeholder="请输入密码"
                @keyup.enter="handleLogin"
              />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" class="submit-btn" :loading="loading" @click="handleLogin">
                进入安全分析中心
              </el-button>
            </el-form-item>
          </el-form>

          <div class="tips">
            <p>后端默认地址：`http://127.0.0.1:8170`</p>
            <p>登录后可进入“检测工具”执行请求重放、样本送检，并联动事件中心与分析工作台复核验证结果。</p>
          </div>
        </div>
      </main>
    </section>
  </div>
</template>

<style scoped lang="scss">
.login-page {
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  background: #08111f;
}

.login-backdrop {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 12% 18%, rgba(34, 211, 238, 0.18), transparent 26%),
    radial-gradient(circle at 88% 18%, rgba(59, 130, 246, 0.2), transparent 22%),
    radial-gradient(circle at 50% 100%, rgba(239, 68, 68, 0.12), transparent 28%),
    linear-gradient(135deg, #040b16 0%, #091423 46%, #0f172a 100%);
}

.login-layout {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(360px, 420px);
}

.hero-panel {
  padding: 64px;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.hero-badge {
  width: fit-content;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(34, 211, 238, 0.14);
  border: 1px solid rgba(34, 211, 238, 0.18);
  color: #67e8f9;
  font-size: 12px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
}

.hero-panel h1 {
  margin: 18px 0 14px;
  font-size: 48px;
  line-height: 1.08;
  color: #f8fafc;
}

.hero-panel > p {
  max-width: 720px;
  margin: 0 0 28px;
  line-height: 1.8;
  color: rgba(226, 232, 240, 0.8);
}

.hero-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  max-width: 760px;
}

.hero-card {
  padding: 18px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(8, 15, 28, 0.72);
  box-shadow: 0 20px 40px rgba(2, 6, 23, 0.22);

  h3 {
    margin: 0 0 10px;
    color: #f8fafc;
    font-size: 18px;
  }

  p {
    margin: 0;
    color: rgba(203, 213, 225, 0.82);
    line-height: 1.7;
    font-size: 14px;
  }
}

.form-panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background: rgba(2, 6, 23, 0.34);
  backdrop-filter: blur(12px);
}

.form-shell {
  width: 100%;
  padding: 28px;
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(8, 15, 28, 0.88);
  box-shadow: 0 24px 80px rgba(2, 6, 23, 0.4);
}

.form-head {
  display: flex;
  gap: 14px;
  align-items: center;
  margin-bottom: 24px;

  h2 {
    margin: 0 0 6px;
    color: #f8fafc;
  }

  p {
    margin: 0;
    color: rgba(203, 213, 225, 0.78);
    line-height: 1.6;
  }
}

.form-logo {
  width: 48px;
  height: 48px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(56, 189, 248, 0.16);
  color: #67e8f9;
  flex-shrink: 0;
}

.login-form :deep(.el-form-item__label) {
  color: rgba(226, 232, 240, 0.88);
}

.login-form :deep(.el-input__wrapper) {
  background: rgba(15, 23, 42, 0.88);
  box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.16);
}

.submit-btn {
  width: 100%;
  min-height: 46px;
  border-radius: 14px;
}

.tips {
  margin-top: 12px;
  color: rgba(148, 163, 184, 0.86);
  font-size: 13px;
  line-height: 1.8;
}

@media (max-width: 1080px) {
  .login-layout {
    grid-template-columns: 1fr;
  }

  .hero-panel {
    padding: 40px 24px 16px;
  }

  .hero-grid {
    grid-template-columns: 1fr;
  }
}
</style>
