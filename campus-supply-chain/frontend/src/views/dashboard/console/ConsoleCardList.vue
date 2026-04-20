<script setup lang="ts">
import {
  Box,
  ShoppingCart,
  Warning,
  Upload,
  Document,
  List,
  User,
  OfficeBuilding,
  Connection,
  ChatDotRound,
  Edit,
} from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

defineProps<{
  cards: { title: string; value: number; trend: string; trendValue: string; icon: string; path: string }[]
}>()

const router = useRouter()

const iconMap: Record<string, object> = {
  Box,
  ShoppingCart,
  Warning,
  Upload,
  Document,
  List,
  User,
  OfficeBuilding,
  Connection,
  ChatDotRound,
  Edit,
}

function go(path: string) {
  if (!path) return
  router.push(path.startsWith('/') ? path : `/${path}`)
}
</script>

<template>
  <el-row :gutter="20" class="dcc-row">
    <el-col v-for="(item, index) in cards" :key="item.title" :xs="12" :sm="12" :md="6" :lg="6">
      <div class="dcc-card dcc-stat" :style="`--delay: ${index * 0.04}s`" @click="go(item.path)">
        <span class="dcc-stat-label">{{ item.title }}</span>
        <span class="dcc-stat-value">{{ item.value }}</span>
        <div class="dcc-stat-foot">
          <span class="muted">环比上周</span>
          <span class="chg" :class="item.trend">{{ item.trendValue }}</span>
        </div>
        <div class="dcc-stat-icon">
          <el-icon :size="22">
            <component :is="iconMap[item.icon] || Box" />
          </el-icon>
        </div>
      </div>
    </el-col>
  </el-row>
</template>

<style scoped lang="scss">
.dcc-row {
  margin-bottom: 4px;
}
.dcc-card {
  position: relative;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 22px 20px 18px;
  margin-bottom: 20px;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s;
  animation: dcc-in 0.45s ease backwards;
  animation-delay: var(--delay, 0s);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
  &:hover {
    border-color: rgba(79, 70, 229, 0.35);
    box-shadow: 0 8px 28px rgba(15, 23, 42, 0.08);
  }
}
@keyframes dcc-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
}
.dcc-stat-label {
  display: block;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.dcc-stat-value {
  display: block;
  font-size: 26px;
  font-weight: 600;
  margin-top: 8px;
  color: var(--el-text-color-primary);
}
.dcc-stat-foot {
  margin-top: 8px;
  font-size: 12px;
  .muted {
    color: var(--el-text-color-secondary);
  }
  .chg {
    margin-left: 6px;
    font-weight: 600;
    &.up {
      color: var(--el-color-success);
    }
    &.down {
      color: var(--el-color-danger);
    }
  }
}
.dcc-stat-icon {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(79, 70, 229, 0.1);
  color: #4f46e5;
}
</style>
