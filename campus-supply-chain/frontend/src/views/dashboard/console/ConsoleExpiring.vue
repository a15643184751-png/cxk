<script setup lang="ts">
import { useRouter } from 'vue-router'

defineProps<{
  items: { name: string; days: number; count: number }[]
}>()

const router = useRouter()
</script>

<template>
  <div v-if="items.length" class="dcc-card dcc-exp">
    <h4>库存临期提醒</h4>
    <div class="list">
      <div
        v-for="e in items"
        :key="e.name"
        class="item"
        @click="router.push({ path: '/goods', query: { tab: 'stock' } })"
      >
        <span class="name">{{ e.name }}</span>
        <span class="badge" :class="{ urgent: e.days <= 7 }">{{ e.days }} 天内</span>
        <span class="cnt">{{ e.count }} 件</span>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.dcc-card {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 22px;
  margin-bottom: 20px;
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
h4 {
  margin: 0 0 16px;
  font-size: 15px;
  font-weight: 600;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  font-size: 13px;
  cursor: pointer;
  transition: background 0.2s;
  &:hover {
    background: rgba(79, 70, 229, 0.06);
  }
}
.name {
  flex: 1;
  min-width: 0;
}
.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--el-fill-color-dark);
  color: var(--el-text-color-secondary);
  &.urgent {
    color: var(--el-color-danger);
    background: rgba(245, 108, 108, 0.12);
  }
}
.cnt {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
