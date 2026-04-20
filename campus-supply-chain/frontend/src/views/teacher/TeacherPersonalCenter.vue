<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Setting } from '@element-plus/icons-vue'
import TeacherOrdersPanel from './TeacherOrdersPanel.vue'
import TeacherAssetsPanel from './TeacherAssetsPanel.vue'
import TeacherSettingsPanel from './TeacherSettingsPanel.vue'

const route = useRoute()
const router = useRouter()

type TabKey = 'orders' | 'assets'
const activeTab = ref<TabKey>('orders')
const settingsOpen = ref(false)

function tabFromQuery(q: unknown): TabKey {
  const t = String(q || '')
  if (t === 'assets') return 'assets'
  return 'orders'
}

watch(
  () => route.query.tab,
  (t) => {
    const next = tabFromQuery(t)
    if (activeTab.value !== next) activeTab.value = next
    if (String(t) === 'analytics') {
      router.replace({ path: route.path, query: { ...route.query, tab: 'orders' } })
    }
  },
  { immediate: true }
)

watch(activeTab, (v) => {
  const cur = tabFromQuery(route.query.tab)
  if (cur === v) return
  router.replace({ path: route.path, query: { ...route.query, tab: v } })
})
</script>

<template>
  <div class="personal-page">
    <div class="page-intro">
      <div class="intro-text">
        <h2>个人中心</h2>
        <p>我买了什么、货到哪了、手里在用啥、要不要还——首页只看结果，明细进详情。</p>
      </div>
      <el-button :icon="Setting" @click="settingsOpen = true">设置</el-button>
    </div>

    <el-tabs v-model="activeTab" class="main-tabs">
      <el-tab-pane label="我的订单" name="orders">
        <TeacherOrdersPanel />
      </el-tab-pane>
      <el-tab-pane label="我的领用 / 借还" name="assets">
        <TeacherAssetsPanel />
      </el-tab-pane>
    </el-tabs>

    <el-drawer v-model="settingsOpen" title="账号与系统设置" size="420px" destroy-on-close>
      <TeacherSettingsPanel />
    </el-drawer>
  </div>
</template>

<style scoped lang="scss">
.personal-page {
  padding: 0;
}
.page-intro {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}
.intro-text h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
}
.intro-text p {
  margin: 0;
  max-width: 520px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.55;
}
.main-tabs {
  :deep(.el-tabs__header) {
    margin-bottom: 22px;
  }
  :deep(.el-tabs__item) {
    font-size: 15px;
    font-weight: 600;
  }
}
</style>
