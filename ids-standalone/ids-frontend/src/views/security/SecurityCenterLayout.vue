<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Bell,
  Connection,
  DataAnalysis,
  Document,
  FolderOpened,
  House,
  Lock,
  Monitor,
  SwitchButton,
  Upload,
  Warning,
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const loading = ref(true)

const navItems = [
  { path: '/overview', label: '总览', icon: House },
  { path: '/events', label: '事件中心', icon: Warning },
  { path: '/workbench', label: '分析工作台', icon: DataAnalysis },
  { path: '/detection', label: '检测工具', icon: Upload },
  { path: '/config', label: '通信配置', icon: Connection },
  { path: '/notifications', label: '通知配置', icon: Bell },
  { path: '/audit', label: '审计中心', icon: Document },
  { path: '/situation', label: '安全态势', icon: Monitor },
  { path: '/sandbox', label: '文件审计', icon: FolderOpened },
]

const userLabel = computed(
  () => userStore.userInfo?.real_name || userStore.userInfo?.username || 'IDS User',
)

function goTo(path: string) {
  if (route.path === path) return
  loading.value = true
  void router.push(path)
}

function logout() {
  userStore.logout()
  void router.replace('/login')
}

const isActive = (path: string) => route.path === path || route.path.startsWith(`${path}/`)

let loadTimer: ReturnType<typeof setTimeout> | null = null

function restartLoading() {
  if (loadTimer) clearTimeout(loadTimer)
  loading.value = true
  loadTimer = setTimeout(() => {
    loading.value = false
    loadTimer = null
  }, 180)
}

watch(
  () => route.fullPath,
  () => {
    restartLoading()
  },
  { immediate: true },
)

onMounted(() => {
  document.body.classList.add('security-center-active')
})

onBeforeUnmount(() => {
  document.body.classList.remove('security-center-active')
  if (loadTimer) clearTimeout(loadTimer)
})
</script>

<template>
  <div class="security-center">
    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner" />
      <span class="loading-text">安全中心加载中...</span>
    </div>

    <aside class="security-nav">
      <div class="nav-header">
        <div class="nav-logo">
          <el-icon :size="26"><Lock /></el-icon>
        </div>
        <div class="nav-meta">
          <span class="nav-title">安全中心</span>
          <span class="nav-subtitle">通信审计、事件处置与策略封禁工作台</span>
        </div>
      </div>

      <div class="nav-user">
        <strong>{{ userLabel }}</strong>
        <span>{{ userStore.userInfo?.role || 'ids_admin' }}</span>
      </div>

      <nav class="nav-list">
        <button
          v-for="item in navItems"
          :key="item.path"
          type="button"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          @click="goTo(item.path)"
        >
          <el-icon :size="18"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </button>
      </nav>

      <button type="button" class="nav-logout" @click="logout">
        <el-icon :size="18"><SwitchButton /></el-icon>
        <span>退出登录</span>
      </button>
    </aside>

    <main class="security-main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<style scoped>
.security-center {
  position: fixed;
  inset: 0;
  display: flex;
  background: #050505;
  z-index: 2000;
}

.loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(5, 5, 5, 0.88);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  z-index: 1000;
  backdrop-filter: blur(8px);
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 3px solid rgba(59, 130, 246, 0.2);
  border-top-color: #38bdf8;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.loading-text {
  font-size: 14px;
  font-family: monospace;
  color: rgba(255, 255, 255, 0.76);
  letter-spacing: 0.14em;
}

.security-nav {
  width: 252px;
  background: linear-gradient(180deg, #07111f, #040913 62%, #02060c);
  border-right: 1px solid rgba(255, 255, 255, 0.06);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  padding: 20px 16px 16px;
  gap: 16px;
}

.nav-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.nav-logo {
  width: 48px;
  height: 48px;
  border-radius: 14px;
  background: rgba(56, 189, 248, 0.15);
  border: 1px solid rgba(56, 189, 248, 0.22);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #38bdf8;
}

.nav-meta {
  display: flex;
  flex-direction: column;
}

.nav-title {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
}

.nav-subtitle {
  margin-top: 2px;
  color: rgba(203, 213, 225, 0.88);
  font-size: 12px;
  line-height: 1.5;
}

.nav-user {
  padding: 14px;
  border-radius: 16px;
  background: rgba(15, 23, 42, 0.74);
  border: 1px solid rgba(56, 189, 248, 0.14);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-user strong {
  color: #f8fafc;
  font-size: 15px;
}

.nav-user span {
  color: rgba(226, 232, 240, 0.76);
  font-size: 12px;
}

.nav-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.nav-item,
.nav-logout {
  appearance: none;
  border: none;
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  padding: 14px 16px;
  min-height: 48px;
  border-radius: 14px;
  cursor: pointer;
  transition: 0.2s ease;
  text-align: left;
}

.nav-item {
  background: rgba(255, 255, 255, 0.02);
  color: rgba(226, 232, 240, 0.8);
}

.nav-item:hover,
.nav-logout:hover {
  background: rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.98);
}

.nav-item.active {
  background: rgba(56, 189, 248, 0.16);
  color: #67e8f9;
  box-shadow: inset 0 0 0 1px rgba(56, 189, 248, 0.16);
}

.nav-logout {
  background: rgba(239, 68, 68, 0.08);
  color: rgba(254, 202, 202, 0.94);
}

.security-main {
  flex: 1;
  min-width: 0;
  overflow: auto;
  display: flex;
  flex-direction: column;
  background: #020617;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.18s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

@media (max-width: 980px) {
  .security-center {
    flex-direction: column;
  }

  .security-nav {
    width: 100%;
    padding-bottom: 12px;
  }

  .nav-list {
    flex-direction: row;
    overflow-x: auto;
  }
}
</style>
