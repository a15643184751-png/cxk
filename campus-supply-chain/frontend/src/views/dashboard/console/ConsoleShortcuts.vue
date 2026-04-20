<script setup lang="ts">
import type { Component } from 'vue'
import { useRouter } from 'vue-router'

defineProps<{
  items: { icon: Component; label: string; path: string }[]
}>()

const router = useRouter()

function go(path: string) {
  router.push(path.startsWith('/') ? path : `/${path}`)
}
</script>

<template>
  <div v-if="items.length" class="dcc-card dcc-shortcuts">
    <h4>快捷入口</h4>
    <div class="grid" :class="{ compact: items.length <= 3 }">
      <div v-for="s in items" :key="s.path" class="cell" @click="go(s.path)">
        <el-icon :size="22"><component :is="s.icon" /></el-icon>
        <span>{{ s.label }}</span>
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
.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  &.compact {
    grid-template-columns: repeat(2, 1fr);
  }
}
.cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 14px 8px;
  background: var(--el-fill-color-light);
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
  .el-icon {
    color: #4f46e5;
  }
  span {
    font-size: 12px;
    color: var(--el-text-color-regular);
    text-align: center;
  }
  &:hover {
    background: rgba(79, 70, 229, 0.08);
    .el-icon,
    span {
      color: #4f46e5;
    }
  }
}
</style>
