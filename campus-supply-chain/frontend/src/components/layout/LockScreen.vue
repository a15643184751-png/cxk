<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { openLockBus } from '@/utils/layoutBus'
import { Lock } from '@element-plus/icons-vue'

const userStore = useUserStore()
const locked = ref(false)
const pwd = ref('')

let unsub: (() => void) | undefined

onMounted(() => {
  unsub = openLockBus.on(() => {
    locked.value = true
    pwd.value = ''
  })
})
onUnmounted(() => unsub?.())

function unlock() {
  const expect = userStore.userInfo?.username || '123456'
  if (pwd.value === expect || pwd.value === '123456') {
    locked.value = false
    pwd.value = ''
  }
}
</script>

<template>
  <Teleport to="body">
    <Transition name="fade">
      <div v-if="locked" class="lock-screen">
        <div class="lock-card">
          <el-icon :size="40" class="ic"><Lock /></el-icon>
          <p class="name">{{ userStore.userInfo?.real_name || userStore.userInfo?.username }}</p>
          <p class="hint">输入登录用户名或 <code>123456</code> 解锁</p>
          <el-input
            v-model="pwd"
            type="password"
            show-password
            placeholder="密码"
            @keyup.enter="unlock"
          />
          <el-button type="primary" class="btn" @click="unlock">解锁</el-button>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped lang="scss">
.lock-screen {
  position: fixed;
  inset: 0;
  z-index: 10000;
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(12px);
  display: flex;
  align-items: center;
  justify-content: center;
}
.lock-card {
  width: 320px;
  padding: 32px;
  background: var(--bg-elevated);
  border-radius: 16px;
  text-align: center;
  box-shadow: var(--shadow-lg);
}
.ic {
  color: var(--primary);
  margin-bottom: 12px;
}
.name {
  font-weight: 600;
  margin: 0 0 8px;
}
.hint {
  font-size: 12px;
  color: var(--text-muted);
  margin: 0 0 16px;
}
.btn {
  width: 100%;
  margin-top: 12px;
}
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.25s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
