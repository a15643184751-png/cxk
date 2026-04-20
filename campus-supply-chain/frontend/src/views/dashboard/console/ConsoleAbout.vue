<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'

const router = useRouter()

const links = [
  { label: '溯源与批次查询', path: '/trace' },
  { label: 'AI 采购助手', path: '/ai/chat' },
  { label: '全景大屏', path: '/dashboard/analysis' },
  { label: '用户与权限', path: '/system/users' },
  { label: '角色与菜单', path: '/system/roles' },
  { label: '操作日志与审计', path: '/system/operation-logs' },
]

function go(path: string) {
  router.push(path)
}
</script>

<template>
  <div class="dcc-card dcc-about">
    <div class="text">
      <h2>校园供应链安全控制台</h2>
      <p class="lead">
        面向管理员的「采供 — 仓储 — 配送 — 溯源」一体化工作台，强调过程留痕、风险可见与多角色协同。
      </p>
      <p>
        技术栈与 Art Design Pro 一致方向：Vue 3、TypeScript、Vite、Element Plus，关键指标使用 ECharts
        呈现；安全能力对接 IDS、态势与审计模块。
      </p>
      <div class="links">
        <div
          v-for="l in links"
          :key="l.path"
          class="link"
          @click="go(l.path)"
        >
          <span>{{ l.label }}</span>
          <el-icon><ArrowRight /></el-icon>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.dcc-card {
  background: linear-gradient(135deg, var(--el-bg-color) 0%, var(--el-fill-color-lighter) 100%);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 28px 32px;
  margin-bottom: 20px;
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.03em;
}
.lead {
  margin: 14px 0 0;
  font-size: 14px;
  color: var(--el-text-color-primary);
  line-height: 1.65;
  max-width: 800px;
}
p {
  margin: 10px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.65;
  max-width: 800px;
}
.links {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}
.link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 200px;
  padding: 12px 16px;
  border: 1px solid var(--el-border-color);
  border-radius: 10px;
  font-size: 13px;
  cursor: pointer;
  transition: transform 0.2s, border-color 0.2s, background 0.2s, box-shadow 0.2s;
  background: var(--el-bg-color);
  &:hover {
    transform: translateY(-2px);
    border-color: rgba(79, 70, 229, 0.45);
    background: rgba(79, 70, 229, 0.05);
    color: #4f46e5;
    box-shadow: 0 8px 24px rgba(79, 70, 229, 0.08);
  }
}
</style>
