<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const eventId = computed(() => {
  const raw = Number(route.query.event || route.query.incident || 0)
  return Number.isFinite(raw) && raw > 0 ? raw : null
})

const attackType = computed(() => String(route.query.attack || '').trim() || 'suspicious_route')
const riskScore = computed(() => {
  const raw = Number(route.query.risk || 0)
  return Number.isFinite(raw) && raw > 0 ? raw : null
})

const routePath = computed(() => String(route.query.path || '').trim() || '/')
</script>

<template>
  <div class="security-blocked">
    <div class="security-blocked__panel">
      <div class="security-blocked__eyebrow">IDS FRONTEND ROUTE GUARD</div>
      <h1>403</h1>
      <p class="security-blocked__title">当前访问已被 IDS 前端路由守卫拦截</p>
      <p class="security-blocked__desc">
        当前 URL 中包含明显的攻击特征，页面未继续渲染，事件已写入 IDS。
      </p>

      <div class="security-blocked__meta">
        <span>攻击类型：{{ attackType }}</span>
        <span>目标路径：{{ routePath }}</span>
        <span v-if="riskScore">风险分：{{ riskScore }}</span>
        <span v-if="eventId">事件号：#{{ eventId }}</span>
      </div>

      <div class="security-blocked__actions">
        <el-button type="primary" @click="router.replace('/login')">返回登录页</el-button>
        <el-button @click="router.replace('/overview')">返回首页</el-button>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.security-blocked {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background:
    radial-gradient(circle at top, rgba(239, 68, 68, 0.18), transparent 38%),
    linear-gradient(180deg, #08111f 0%, #050b15 100%);
}

.security-blocked__panel {
  width: min(680px, 100%);
  padding: 36px;
  border-radius: 24px;
  border: 1px solid rgba(248, 113, 113, 0.28);
  background: rgba(7, 13, 24, 0.9);
  box-shadow: 0 30px 80px rgba(2, 6, 23, 0.5);
  color: #e5eefc;

  h1 {
    margin: 0 0 12px;
    font-size: 72px;
    line-height: 1;
    color: #f87171;
  }
}

.security-blocked__eyebrow {
  margin-bottom: 12px;
  color: rgba(248, 113, 113, 0.78);
  font-size: 12px;
  letter-spacing: 0.24em;
}

.security-blocked__title {
  margin: 0 0 10px;
  font-size: 24px;
  font-weight: 700;
}

.security-blocked__desc {
  margin: 0;
  color: rgba(226, 232, 240, 0.8);
  line-height: 1.7;
}

.security-blocked__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 22px;

  span {
    padding: 8px 12px;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.9);
    border: 1px solid rgba(148, 163, 184, 0.2);
    color: rgba(226, 232, 240, 0.92);
    font-size: 13px;
  }
}

.security-blocked__actions {
  display: flex;
  gap: 12px;
  margin-top: 26px;
  flex-wrap: wrap;
}
</style>
