<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { User, Box, Connection, Warning, ChatDotRound } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useUiSettingsStore } from '@/stores/uiSettings'
import { login } from '@/api/auth'
import { ROLE_LABELS } from '@/types/role'
import type { RoleType } from '@/types/role'
import DragVerify from '@/components/ui/DragVerify.vue'
import LoginAuthTopBar from '@/components/layout/LoginAuthTopBar.vue'

const LOGIN_CACHE = 'campus-login-cache-v1'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const uiSettings = useUiSettingsStore()
const { t } = useI18n()

const loading = ref(false)
const formRef = ref()
const dragVerifyRef = ref<InstanceType<typeof DragVerify> | null>(null)
const isPassing = ref(false)
const isClickPass = ref(false)
const rememberPassword = ref(false)

const form = reactive({
  username: '',
  password: '',
  role: 'logistics_admin' as RoleType,
})

const roleOptions: { value: RoleType; label: string }[] = [
  { value: 'system_admin', label: ROLE_LABELS.system_admin },
  { value: 'logistics_admin', label: ROLE_LABELS.logistics_admin },
  { value: 'warehouse_procurement', label: ROLE_LABELS.warehouse_procurement },
  { value: 'campus_supplier', label: ROLE_LABELS.campus_supplier },
  { value: 'counselor_teacher', label: ROLE_LABELS.counselor_teacher },
]

/** 与后端 init_db 预置账号一致：用户名同角色 key，密码 123456 */
const DEMO_PASSWORD = '123456'
const roleDemoUsername: Record<RoleType, string> = {
  system_admin: 'system_admin',
  logistics_admin: 'logistics_admin',
  warehouse_procurement: 'warehouse_procurement',
  campus_supplier: 'campus_supplier',
  counselor_teacher: 'counselor_teacher',
}

function applyCredentialsForRole(role: RoleType) {
  form.username = roleDemoUsername[role]
  form.password = DEMO_PASSWORD
  resetDragVerify()
  isClickPass.value = false
}

function onRoleChange(role: RoleType) {
  applyCredentialsForRole(role)
}

const rules = computed(() => ({
  username: [{ required: true, message: t('login.placeholder.username'), trigger: 'blur' }],
  password: [{ required: true, message: t('login.placeholder.password'), trigger: 'blur' }],
}))

const features = [
  { icon: Box, title: '全生命周期', desc: '采购→仓储→配送一体化' },
  { icon: Connection, title: '溯源可查', desc: '批次号追溯全链路' },
  { icon: Warning, title: '安全预警', desc: '临期短缺自动提醒' },
  { icon: ChatDotRound, title: 'AI 智能体', desc: '自然语言申请采购' },
]

function getDefaultRedirect(role: RoleType): string {
  switch (role) {
    case 'system_admin': return '/dashboard'
    case 'counselor_teacher': return '/teacher/workbench'
    case 'campus_supplier': return '/supplier/orders'
    default: return '/dashboard'
  }
}

function resetDragVerify() {
  dragVerifyRef.value?.reset?.()
  isPassing.value = false
}

async function handleLogin() {
  await formRef.value?.validate()
  if (!isPassing.value) {
    isClickPass.value = true
    ElMessage.warning('请先完成滑块验证')
    return
  }
  loading.value = true
  try {
    const res: any = await login(form)
    const token = res?.access_token || res?.token || res?.data?.access_token
    const user = res?.user || res?.data?.user
    if (rememberPassword.value) {
      localStorage.setItem(
        LOGIN_CACHE,
        JSON.stringify({
          username: form.username,
          password: form.password,
          role: form.role,
        })
      )
    } else {
      localStorage.removeItem(LOGIN_CACHE)
    }
    if (token) {
      const actualRole = (user?.role || form.role) as RoleType
      userStore.setToken(token)
      userStore.setUserInfo(
        user || { id: 1, username: form.username, real_name: '用户', role: actualRole }
      )
      ElMessage.success(t('login.success'))
      const redirect = (route.query.redirect as string) || getDefaultRedirect(actualRole)
      router.push(redirect)
    } else {
      ElMessage.warning('已使用所选角色进入系统（未获取到登录令牌）')
      userStore.setToken('demo-token')
      userStore.setUserInfo({ id: 1, username: form.username, real_name: form.username, role: form.role })
      router.push(getDefaultRedirect(form.role))
    }
  } catch {
    ElMessage.warning('无法连接认证服务，已使用本地会话进入')
    userStore.setToken('demo-token')
    userStore.setUserInfo({ id: 1, username: form.username, real_name: form.username, role: form.role })
    router.push(getDefaultRedirect(form.role))
  } finally {
    loading.value = false
    resetDragVerify()
    isClickPass.value = false
  }
}

onMounted(() => {
  if (userStore.isLoggedIn) {
    const role = userStore.userInfo?.role as RoleType
    if (!role) {
      userStore.logout()
      return
    }
    router.replace(getDefaultRedirect(role))
    return
  }
  let restored = false
  try {
    const raw = localStorage.getItem(LOGIN_CACHE)
    if (raw) {
      const j = JSON.parse(raw)
      if (j.username) form.username = j.username
      if (j.password) form.password = j.password
      if (j.role) form.role = j.role as RoleType
      rememberPassword.value = true
      restored = true
    }
  } catch {
    /* ignore */
  }
  if (!restored) {
    applyCredentialsForRole(form.role)
  }
})
</script>

<template>
  <div class="login-page" :class="{ 'login-page--dark': uiSettings.isDark }">
    <div class="login-layout">
      <!-- 左侧品牌区（宽屏）；与 art-design-pro 类似的排版节奏 -->
      <div class="brand-panel login-left-view">
        <div class="brand-content">
          <header class="brand-header">
            <div class="brand-logo">
              <span class="logo-icon">链</span>
              <span class="logo-text">供应链平台</span>
            </div>
          </header>
          <h2 class="brand-title">
            <span class="brand-title-line">校园物资供应链</span>
            <span class="brand-title-line">安全健康监测平台</span>
          </h2>
          <p class="brand-desc"><span class="brand-desc-inner">— 采购 · 仓储 · 配送 · 溯源 · AI 智能体 —</span></p>

          <div class="features feature-grid">
            <div
              v-for="(f, i) in features"
              :key="f.title"
              class="feature-item feature-card"
              :style="`--delay: ${i * 0.08}s`"
            >
              <div class="feature-icon feature-card__icon-wrap">
                <el-icon :size="20"><component :is="f.icon" /></el-icon>
              </div>
              <div class="feature-text feature-card__body">
                <span class="feature-title feature-card__title">{{ f.title }}</span>
                <span class="feature-desc feature-card__desc">{{ f.desc }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧：顶栏占位 + 表单卡片（入场滑动） -->
      <div class="form-column">
        <LoginAuthTopBar />

        <header class="login-top-bar">
          <div class="login-top-bar__brand">
            <span class="logo-icon logo-icon--sm">链</span>
            <span class="login-top-bar__title">供应链平台</span>
          </div>
        </header>

        <div class="form-panel">
          <div class="form-wrap auth-right-wrap">
            <div class="form-card">
              <div class="card-header">
                <h3>{{ t('login.title') }}</h3>
                <p>{{ t('login.subTitle') }}</p>
              </div>

              <el-form
                ref="formRef"
                :model="form"
                :rules="rules"
                class="login-form"
                size="large"
                @submit.prevent="handleLogin"
              >
                <el-form-item prop="username">
                  <el-input
                    v-model="form.username"
                    :placeholder="t('login.placeholder.username')"
                    :prefix-icon="User"
                    autocomplete="username"
                  />
                </el-form-item>
                <el-form-item prop="password">
                  <el-input
                    v-model="form.password"
                    type="password"
                    :placeholder="t('login.placeholder.password')"
                    show-password
                    autocomplete="current-password"
                    @keyup.enter="handleLogin"
                  />
                </el-form-item>
                <el-form-item prop="role">
                  <el-select
                    v-model="form.role"
                    :placeholder="t('login.placeholder.role')"
                    style="width: 100%"
                    @change="onRoleChange"
                  >
                    <el-option
                      v-for="opt in roleOptions"
                      :key="opt.value"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                </el-form-item>

                <div class="slider-wrap">
                  <DragVerify
                    ref="dragVerifyRef"
                    v-model:value="isPassing"
                    :text="t('login.sliderText')"
                    :success-text="t('login.sliderSuccessText')"
                    :height="40"
                    :background="uiSettings.isDark ? '#26272f' : '#f1f1f4'"
                    :text-color="uiSettings.isDark ? '#cbd5e1' : '#333'"
                    progress-bar-bg="var(--el-color-primary)"
                    completed-bg="#57d187"
                    handler-bg="var(--el-bg-color)"
                  />
                  <p
                    v-show="!isPassing && isClickPass"
                    class="slider-err"
                  >
                    {{ t('login.placeholder.slider') }}
                  </p>
                </div>

                <div class="login-row">
                  <el-checkbox v-model="rememberPassword">{{ t('login.rememberPwd') }}</el-checkbox>
                  <router-link class="link" to="/forgot-password">{{ t('login.forgetPwd') }}</router-link>
                </div>

                <el-form-item>
                  <el-button
                    type="primary"
                    class="submit-btn"
                    :loading="loading"
                    native-type="submit"
                  >
                    {{ t('login.btnText') }}
                  </el-button>
                </el-form-item>
              </el-form>

              <p class="register-row">
                <span>{{ t('login.noAccount') }}</span>
                <router-link class="link" to="/register">{{ t('login.register') }}</router-link>
              </p>

              <p class="footer-links">
                <router-link to="/upload">{{ t('login.footerLinks.report') }}</router-link>
                <span class="sep">/</span>
                <router-link to="/upload">{{ t('login.footerLinks.feedback') }}</router-link>
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
$auth-accent: #5d5fe3;
$auth-accent-soft: rgb(93 95 227 / 12%);

/* 底：浅灰 + 细网格 + 柔色光斑（对齐 art-design-pro 授权页气质） */
.login-page {
  position: relative;
  isolation: isolate;
  min-height: 100vh;
  overflow-x: hidden;
  background-color: #f4f5f7;
  background-image:
    linear-gradient(rgb(0 0 0 / 4%) 1px, transparent 1px),
    linear-gradient(90deg, rgb(0 0 0 / 4%) 1px, transparent 1px);
  background-size: 22px 22px;

  &::before,
  &::after {
    position: fixed;
    z-index: 0;
    width: min(55vw, 520px);
    height: min(55vw, 520px);
    pointer-events: none;
    content: '';
    border-radius: 50%;
    filter: blur(80px);
    opacity: 0.45;
  }

  &::before {
    bottom: -8%;
    left: -6%;
    background: radial-gradient(circle, #7ec8c3 0%, transparent 70%);
  }

  &::after {
    top: -6%;
    right: -4%;
    background: radial-gradient(circle, #e8b4d4 0%, transparent 70%);
  }
}

.login-layout {
  position: relative;
  z-index: 1;
  display: flex;
  width: 100%;
  min-height: 100vh;
}

.login-left-view {
  box-sizing: border-box;
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  width: min(52vw, 720px);
  max-width: 55%;
  padding: clamp(24px, 4vw, 56px) clamp(28px, 4vw, 64px);
}

.brand-content {
  width: 100%;
  max-width: 520px;
}

.brand-header {
  margin-bottom: clamp(28px, 4vh, 40px);
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 12px;
}

.logo-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: var(--gradient-primary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  box-shadow: 0 8px 24px rgba(79, 70, 229, 0.32);
  transition:
    transform 0.35s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.35s ease;

  &:hover {
    transform: translateY(-2px) scale(1.02);
    box-shadow: 0 12px 28px rgba(79, 70, 229, 0.38);
  }

  &--sm {
    width: 40px;
    height: 40px;
    font-size: 18px;
    border-radius: 10px;
  }
}

.brand-logo .logo-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.brand-title {
  margin: 0 0 16px;
  font-size: clamp(22px, 2.1vw, 32px);
  font-weight: 700;
  line-height: 1.35;
  letter-spacing: -0.03em;
  color: var(--text-primary);
}

.brand-title-line {
  display: block;
}

.brand-desc {
  margin: 0 0 clamp(28px, 5vh, 48px);
  font-size: 13px;
  color: var(--text-muted);
}

.brand-desc-inner {
  letter-spacing: 0.06em;
}

.feature-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px 16px;
  max-width: 520px;
}

.feature-card {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px 16px;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 4px 14px rgb(0 0 0 / 5%);
  transition:
    transform 0.32s cubic-bezier(0.25, 0.1, 0.25, 1),
    box-shadow 0.32s ease;
  animation: feature-rise 0.55s cubic-bezier(0.25, 0.46, 0.45, 0.94) backwards;
  animation-delay: var(--delay);

  &:hover {
    transform: translateY(-3px);
    box-shadow: 0 10px 28px rgb(79 70 229 / 10%);
  }
}

@keyframes feature-rise {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.feature-card__icon-wrap {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 8px;
  background: $auth-accent-soft;
  color: $auth-accent;
}

.feature-card__body {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.feature-card__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.feature-card__desc {
  font-size: 12px;
  line-height: 1.45;
  color: var(--text-secondary);
}

/* 右侧列：顶栏 + 表单 */
.form-column {
  position: relative;
  z-index: 1;
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
}

.login-top-bar {
  display: none;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  padding: 16px 24px 8px;

  &__brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }

  &__title {
    font-size: 1.125rem;
    font-weight: 600;
    color: var(--text-primary);
    letter-spacing: -0.02em;
  }
}

.form-panel {
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  padding: clamp(24px, 4vw, 48px);
  position: relative;

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 18%;
    bottom: 18%;
    width: 1px;
    background: linear-gradient(to bottom, transparent, rgba(79, 70, 229, 0.14), transparent);
  }
}

.auth-right-wrap {
  width: 100%;
  max-width: 440px;
  margin: 0 auto;
  overflow: hidden;
  animation: slideInRight 0.6s cubic-bezier(0.25, 0.46, 0.45, 0.94) forwards;
}

@keyframes slideInRight {
  from {
    opacity: 0;
    transform: translate3d(28px, 0, 0);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
}

.form-card {
  padding: 40px 36px 36px;
  border-radius: 12px;
  background: var(--bg-elevated);
  box-shadow: 0 4px 24px rgb(0 0 0 / 6%);
  transition: box-shadow 0.35s ease;

  &:hover {
    box-shadow: 0 8px 32px rgb(0 0 0 / 7%);
  }
}

.card-header {
  margin-bottom: 28px;

  h3 {
    font-size: 26px;
    font-weight: 600;
    color: var(--text-primary);
    margin: 0 0 8px;
    letter-spacing: -0.03em;
  }

  p {
    font-size: 14px;
    color: var(--text-muted);
    margin: 0;
    line-height: 1.55;
  }
}

.login-form {
  :deep(.el-input__wrapper) {
    min-height: 44px;
    padding: 10px 14px;
    border-radius: 10px;
    transition:
      border-color 0.22s ease,
      box-shadow 0.22s ease;
  }

  :deep(.el-select__wrapper) {
    min-height: 44px !important;
    border-radius: 10px;
  }
}

.submit-btn {
  width: 100%;
  height: 48px;
  font-size: 15px;
  font-weight: 600;
  border-radius: 10px !important;
  transition:
    transform 0.2s cubic-bezier(0.4, 0, 0.2, 1),
    box-shadow 0.2s ease;

  &:active {
    transform: scale(0.99);
  }
}

.slider-wrap {
  position: relative;
  margin-bottom: 8px;
}
.slider-err {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-color-danger);
}

.login-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
  .link {
    color: var(--el-color-primary);
    text-decoration: none;
    &:hover {
      text-decoration: underline;
    }
  }
}

.register-row {
  text-align: center;
  font-size: 14px;
  color: var(--text-muted);
  margin: 16px 0 0;
  .link {
    margin-left: 6px;
    color: var(--el-color-primary);
    text-decoration: none;
    &:hover {
      text-decoration: underline;
    }
  }
}

.footer-links {
  text-align: center;
  margin-top: 12px;
  font-size: 13px;
  .sep {
    margin: 0 6px;
    color: var(--text-muted);
  }
  a {
    color: var(--el-color-primary);
    text-decoration: underline;
    text-underline-offset: 2px;
  }
}

.login-page--dark {
  background-color: #000;
  background-image:
    linear-gradient(rgb(255 255 255 / 6%) 1px, transparent 1px),
    linear-gradient(90deg, rgb(255 255 255 / 6%) 1px, transparent 1px);

  &::before,
  &::after {
    opacity: 0.22;
  }

  .form-card {
    background: rgba(255, 255, 255, 0.06);
    box-shadow: 0 4px 28px rgb(0 0 0 / 35%);
  }

  .feature-card {
    background: rgb(255 255 255 / 6%);
    box-shadow: none;
  }

  .brand-title,
  .brand-logo .logo-text,
  .login-top-bar__title {
    color: #f1f5f9;
  }

  .brand-desc,
  .feature-card__desc {
    color: #94a3b8;
  }

  .feature-card__title {
    color: #e2e8f0;
  }
}

@media only screen and (width <= 1180px) {
  .login-left-view {
    display: none;
  }

  .login-top-bar {
    display: flex;
  }

  .form-panel {
    padding-top: 8px;

    &::before {
      display: none;
    }
  }

  .auth-right-wrap {
    animation: none;
  }
}

@media (max-width: 640px) {
  .form-card {
    padding: 28px 22px 26px;
  }

  .card-header h3 {
    font-size: 22px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .auth-right-wrap,
  .feature-card {
    animation: none !important;
  }

  .feature-card:hover,
  .logo-icon:hover {
    transform: none;
  }
}
</style>
