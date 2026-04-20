<script setup lang="ts">
import { onMounted } from 'vue'
import { openIdsSecurityCenter } from '@/utils/openIdsSecurityCenter'

onMounted(() => {
  void openIdsSecurityCenter({ replace: true })
})
</script>

<template>
  <div class="security-center-redirect">
    <span class="security-center-redirect__text">正在进入安全中心...</span>
  </div>
</template>

<style scoped>
.security-center-redirect {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    radial-gradient(circle at top left, rgba(59, 130, 246, 0.14), transparent 28%),
    linear-gradient(135deg, #f8faff 0%, #eef3ff 100%);
}

.security-center-redirect__text {
  font-size: 14px;
  letter-spacing: 0.08em;
  color: #5b6b94;
}
</style>
