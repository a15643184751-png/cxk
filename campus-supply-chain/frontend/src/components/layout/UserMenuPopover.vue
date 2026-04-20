<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { ElMessageBox } from 'element-plus'
import { User, Document, Link, Lock } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { openLockBus } from '@/utils/layoutBus'

const props = withDefaults(
  defineProps<{
    immersive?: boolean
    /** hover 与 art 顶栏一致；click 用于侧栏底部 */
    trigger?: 'hover' | 'click'
    /** 仅头像，用于侧栏底部 */
    compact?: boolean
  }>(),
  { trigger: 'hover', compact: false }
)

const { t } = useI18n()
const router = useRouter()
const userStore = useUserStore()
const popoverRef = ref()

function hide() {
  popoverRef.value?.hide?.()
}

function goProfile() {
  hide()
  router.push('/profile')
}

function openDocs() {
  window.open('https://github.com', '_blank')
}

function openGithub() {
  window.open('https://github.com', '_blank')
}

function lock() {
  hide()
  openLockBus.emit()
}

function loginOut() {
  hide()
  setTimeout(() => {
    ElMessageBox.confirm(t('common.logOutTips'), t('common.tips'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
    }).then(() => {
      userStore.logout()
      router.push('/login')
    }).catch(() => {})
  }, 160)
}
</script>

<template>
  <el-popover
    ref="popoverRef"
    :placement="immersive ? 'bottom-end' : 'bottom-end'"
    :width="240"
    :trigger="trigger"
    :offset="10"
    :show-arrow="false"
    popper-class="user-menu-popover-campus"
  >
    <template #reference>
      <slot>
        <div v-if="props.compact" class="ref-compact" :class="{ immersive }" title="账户">
          <el-avatar :size="32">
            <el-icon><User /></el-icon>
          </el-avatar>
        </div>
        <div v-else class="ref-avatar" :class="{ immersive }">
          <el-avatar :size="36">
            <el-icon><User /></el-icon>
          </el-avatar>
          <span class="name">{{ userStore.userInfo?.real_name || userStore.userInfo?.username }}</span>
        </div>
      </slot>
    </template>
    <div class="um-body">
      <div class="um-head">
        <el-avatar :size="40">
          <el-icon><User /></el-icon>
        </el-avatar>
        <div class="um-meta">
          <span class="um-name">{{ userStore.userInfo?.real_name || userStore.userInfo?.username }}</span>
          <span class="um-sub">{{ userStore.userInfo?.email || userStore.userInfo?.role }}</span>
        </div>
      </div>
      <ul class="um-list">
        <li @click="goProfile"><el-icon><User /></el-icon>{{ t('topBar.user.userCenter') }}</li>
        <li @click="openDocs"><el-icon><Document /></el-icon>{{ t('topBar.user.docs') }}</li>
        <li @click="openGithub"><el-icon><Link /></el-icon>{{ t('topBar.user.github') }}</li>
        <li @click="lock"><el-icon><Lock /></el-icon>{{ t('topBar.user.lockScreen') }}</li>
      </ul>
      <div class="um-out" @click="loginOut">{{ t('topBar.user.logout') }}</div>
    </div>
  </el-popover>
</template>

<style scoped lang="scss">
.ref-compact {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s ease;
  &:hover {
    background: var(--bg-hover);
  }
  &.immersive:hover {
    background: rgba(99, 102, 241, 0.15);
  }
}
.ref-avatar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s ease;
  .name {
    font-size: 14px;
    color: var(--text-primary);
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  &:hover {
    background: var(--bg-hover);
  }
  &.immersive {
    .name {
      color: var(--screen-text);
    }
    &:hover {
      background: rgba(99, 102, 241, 0.12);
    }
  }
}
.um-body {
  padding: 4px 0;
}
.um-head {
  display: flex;
  gap: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border-subtle);
}
.um-meta {
  min-width: 0;
  flex: 1;
}
.um-name {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.um-sub {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.um-list {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
  li {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 10px;
    border-radius: 8px;
    font-size: 13px;
    cursor: pointer;
    margin-bottom: 4px;
    color: var(--text-primary);
    &:hover {
      background: var(--bg-hover);
    }
  }
}
.um-out {
  margin-top: 16px;
  padding: 8px;
  text-align: center;
  font-size: 12px;
  border: 1px solid var(--border-default);
  border-radius: 8px;
  cursor: pointer;
  transition: box-shadow 0.2s ease;
  &:hover {
    box-shadow: var(--shadow-sm);
  }
}
</style>
