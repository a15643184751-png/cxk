<script setup lang="ts">
import { computed } from 'vue'
import { useUserStore } from '@/stores/user'
import { ROLE_LABELS } from '@/types/role'
import type { RoleType } from '@/types/role'

const userStore = useUserStore()
const roleLabel = computed(() => {
  const r = userStore.userInfo?.role as RoleType | undefined
  return r ? ROLE_LABELS[r] || r : '—'
})
</script>

<template>
  <div class="page-card">
    <h2>个人中心</h2>
    <el-descriptions :column="1" border class="desc">
      <el-descriptions-item label="用户名">{{ userStore.userInfo?.username || '—' }}</el-descriptions-item>
      <el-descriptions-item label="姓名">{{ userStore.userInfo?.real_name || '—' }}</el-descriptions-item>
      <el-descriptions-item label="角色">{{ roleLabel }}</el-descriptions-item>
      <el-descriptions-item label="部门">{{ userStore.userInfo?.department || '—' }}</el-descriptions-item>
    </el-descriptions>
  </div>
</template>

<style scoped lang="scss">
.page-card {
  max-width: 560px;
}
h2 {
  margin: 0 0 20px;
  font-size: 18px;
}
.desc {
  margin-top: 8px;
}
</style>
