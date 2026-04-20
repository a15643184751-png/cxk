<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useFullscreen } from '@vueuse/core'
import {
  Fold,
  Expand,
  Search,
  Refresh,
  FullScreen,
  Reading,
  ChatDotRound,
  Setting,
  Sunny,
  Moon,
} from '@element-plus/icons-vue'
import type { AppLocale } from '@/stores/user'
import { useUserStore } from '@/stores/user'
import { useUiSettingsStore } from '@/stores/uiSettings'
import { openSearchBus, openChatBus, openSettingsBus } from '@/utils/layoutBus'
import { themeAnimation } from '@/utils/themeAnimation'
import UserMenuPopover from './UserMenuPopover.vue'

defineProps<{
  title: string
  sidebarExpanded: boolean
  immersive?: boolean
  /** 展示为平台全称（略小字号、可多行） */
  platformBrand?: boolean
}>()
defineEmits<{ (e: 'toggle'): void }>()

const { t, locale } = useI18n()
const router = useRouter()
const userStore = useUserStore()
const ui = useUiSettingsStore()

const { isFullscreen, toggle: toggleFullscreen } = useFullscreen()

const isWindows = typeof navigator !== 'undefined' && navigator.userAgent.includes('Windows')

const languageOptions: { label: string; value: AppLocale }[] = [
  { label: '简体中文', value: 'zh-CN' },
  { label: 'English', value: 'en-US' },
]

function reload() {
  window.location.reload()
}

function changeLanguage(lang: AppLocale) {
  if (locale.value === lang) return
  locale.value = lang
  userStore.setLanguage(lang)
  setTimeout(() => reload(), 50)
}

function openSearch() {
  openSearchBus.emit()
}

function openChat() {
  router.push('/ai/chat')
  openChatBus.emit()
}

function openSetting() {
  openSettingsBus.emit()
}

</script>

<template>
  <header class="app-header" :class="{ 'app-header--immersive': immersive }">
    <div class="header-left">
      <div class="toggle-btn" @click="$emit('toggle')">
        <el-icon :size="22"><Fold v-if="sidebarExpanded" /><Expand v-else /></el-icon>
      </div>
      <h1 class="page-title" :class="{ 'page-title--platform': platformBrand }">{{ title }}</h1>
    </div>

    <div class="header-right">
      <div
        class="search-pill hide-mobile"
        role="button"
        tabindex="0"
        @click="openSearch"
        @keydown.enter.prevent="openSearch"
      >
        <el-icon class="sp-i"><Search /></el-icon>
        <span>{{ t('topBar.search.title') }}</span>
        <div class="kbd">
          <span>{{ isWindows ? 'Ctrl' : '⌘' }}</span>
          <span>k</span>
        </div>
      </div>

      <el-tooltip :content="isFullscreen ? '退出全屏' : '全屏'" placement="bottom">
        <div class="icon-tool hide-mobile" @click="toggleFullscreen">
          <el-icon :size="20"><FullScreen /></el-icon>
        </div>
      </el-tooltip>

      <el-dropdown trigger="click" @command="changeLanguage">
        <div class="icon-tool" aria-label="language">
          <el-icon :size="20"><Reading /></el-icon>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="opt in languageOptions"
              :key="opt.value"
              :command="opt.value"
            >
              {{ opt.label }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <el-tooltip content="AI 助手" placement="bottom">
        <div class="icon-tool hide-mobile" @click="openChat">
          <el-icon :size="20"><ChatDotRound /></el-icon>
          <span class="dot dot--green" />
        </div>
      </el-tooltip>

      <el-popover
        v-if="ui.showSettingGuide"
        placement="bottom-end"
        :width="200"
        trigger="hover"
        :content="`${t('topBar.guide.title')} ${t('topBar.guide.theme')}、${t('topBar.guide.menu')} ${t('topBar.guide.description')}`"
      >
        <template #reference>
          <div class="icon-tool" @click="openSetting">
            <el-icon :size="20"><Setting /></el-icon>
          </div>
        </template>
      </el-popover>
      <el-tooltip v-else :content="t('settings.title')" placement="bottom">
        <div class="icon-tool" @click="openSetting">
          <el-icon :size="20"><Setting /></el-icon>
        </div>
      </el-tooltip>

      <el-tooltip :content="ui.isDark ? '浅色' : '深色'" placement="bottom">
        <div class="icon-tool" @click="themeAnimation($event)">
          <el-icon :size="20"><Sunny v-if="ui.isDark" /><Moon v-else /></el-icon>
        </div>
      </el-tooltip>

      <el-tooltip content="刷新" placement="bottom">
        <div class="icon-tool hide-mobile refresh-tool" @click="reload">
          <el-icon :size="20"><Refresh /></el-icon>
        </div>
      </el-tooltip>

      <UserMenuPopover :immersive="immersive" trigger="hover" />
    </div>

  </header>
</template>

<style lang="scss" scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 50;
  height: 64px;
  padding: 0 16px 0 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: color-mix(in srgb, var(--bg-elevated) 88%, transparent);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border-subtle);
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
  flex-shrink: 0;
  transition:
    box-shadow 0.28s cubic-bezier(0.25, 0.1, 0.25, 1),
    background 0.28s ease;

  &::after {
    content: '';
    position: absolute;
    left: 0;
    right: 0;
    bottom: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(79, 70, 229, 0.08), transparent);
    opacity: 0;
    transition: opacity 0.28s ease;
    pointer-events: none;
  }

  &:hover::after {
    opacity: 1;
  }
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.toggle-btn {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  cursor: pointer;
  color: var(--text-secondary);
  transition:
    background 0.22s cubic-bezier(0.4, 0, 0.2, 1),
    color 0.22s cubic-bezier(0.4, 0, 0.2, 1),
    transform 0.22s cubic-bezier(0.4, 0, 0.2, 1);

  &:hover {
    background: var(--primary-muted);
    color: var(--primary);
    transform: scale(1.04);
  }

  &:active {
    transform: scale(0.96);
  }
}

.page-title {
  font-size: 18px;
  font-weight: 600;
  margin: 0;
  color: var(--text-primary);
  letter-spacing: -0.02em;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.page-title--platform {
  font-size: 15px;
  font-weight: 650;
  white-space: normal;
  line-height: 1.35;
  max-width: min(520px, 46vw);
  letter-spacing: -0.01em;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.search-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  height: 34px;
  padding: 0 10px;
  margin-right: 6px;
  border-radius: 8px;
  border: 1px solid var(--border-default);
  cursor: pointer;
  font-size: 12px;
  color: var(--text-muted);
  transition:
    border-color 0.2s ease,
    background 0.2s ease;
  .sp-i {
    font-size: 14px;
  }
  .kbd {
    display: flex;
    align-items: center;
    gap: 2px;
    margin-left: 4px;
    padding: 0 6px;
    height: 20px;
    border: 1px solid var(--border-default);
    border-radius: 4px;
    font-size: 11px;
    color: var(--text-muted);
  }
  &:hover {
    border-color: rgba(79, 70, 229, 0.35);
    background: var(--primary-muted);
  }
}

.icon-tool {
  position: relative;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  cursor: pointer;
  color: var(--text-secondary);
  transition:
    background 0.2s ease,
    color 0.2s ease,
    transform 0.2s ease;
  &:hover {
    background: var(--primary-muted);
    color: var(--primary);
    transform: scale(1.05);
  }
}

.refresh-tool:hover :deep(.el-icon) {
  animation: spin-180 0.5s ease;
}

@keyframes spin-180 {
  to {
    transform: rotate(180deg);
  }
}

.dot {
  position: absolute;
  top: 7px;
  right: 7px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--danger);
  &--green {
    background: var(--success);
    animation: breathe 1.5s ease-in-out infinite;
  }
}

@keyframes breathe {
  0%,
  100% {
    opacity: 0.5;
    transform: scale(0.9);
  }
  50% {
    opacity: 1;
    transform: scale(1.05);
  }
}

.hide-mobile {
  @media (max-width: 768px) {
    display: none !important;
  }
}

.app-header--immersive {
  background: color-mix(in srgb, #141a2e 82%, transparent);
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--screen-chrome-border);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);

  .page-title {
    color: var(--screen-text);
  }

  .toggle-btn {
    color: rgba(226, 232, 240, 0.75);

    &:hover {
      background: rgba(99, 102, 241, 0.2);
      color: var(--screen-accent-strong);
    }
  }

  .search-pill {
    border-color: rgba(148, 163, 184, 0.25);
    color: var(--screen-muted);
    .kbd {
      border-color: rgba(148, 163, 184, 0.25);
    }
    &:hover {
      background: rgba(99, 102, 241, 0.15);
      color: var(--screen-accent-strong);
    }
  }

  .icon-tool {
    color: rgba(226, 232, 240, 0.75);
    &:hover {
      background: rgba(99, 102, 241, 0.2);
      color: var(--screen-accent-strong);
    }
  }
}
</style>
