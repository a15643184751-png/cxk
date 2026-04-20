<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { useUserStore, type AppLocale } from '@/stores/user'
import { useUiSettingsStore, THEME_PRESETS } from '@/stores/uiSettings'
import { themeAnimation } from '@/utils/themeAnimation'
import { Check } from '@element-plus/icons-vue'

const { locale } = useI18n()
const userStore = useUserStore()
const ui = useUiSettingsStore()

const languageOptions: { label: string; value: AppLocale }[] = [
  { label: '简体中文', value: 'zh-CN' },
  { label: 'English', value: 'en-US' },
]

function changeLanguage(lang: AppLocale) {
  if (locale.value === lang) return
  locale.value = lang
  userStore.setLanguage(lang)
}

function changeThemeColor(color: string) {
  if (ui.primaryColor === color) return
  ui.setPrimary(color)
}

function onThemeClick(e: MouseEvent) {
  themeAnimation(e)
}
</script>

<template>
  <div class="auth-top-bar">
    <div class="auth-top-bar__spacer" />
    <div class="auth-top-bar__actions">
      <div class="color-picker-expandable">
        <div class="color-dots">
          <button
            v-for="(color, index) in THEME_PRESETS"
            :key="color"
            type="button"
            class="color-dot"
            :class="{ active: color === ui.primaryColor }"
            :style="{ background: color, '--index': index }"
            @click="changeThemeColor(color)"
          >
            <el-icon v-if="color === ui.primaryColor" class="check" color="#fff"><Check /></el-icon>
          </button>
        </div>
        <div class="palette-btn" aria-hidden="true">
          <span class="palette-ico">🎨</span>
        </div>
      </div>

      <el-dropdown trigger="click" @command="changeLanguage">
        <div class="icon-btn" :title="'Language'">
          <span class="ico">A</span>
        </div>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="opt in languageOptions"
              :key="opt.value"
              :command="opt.value"
            >
              {{ opt.label }}
              <el-icon v-if="locale === opt.value" class="check-r"><Check /></el-icon>
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <div class="icon-btn" :title="ui.isDark ? 'Light' : 'Dark'" @click="onThemeClick">
        <span v-if="ui.isDark" class="ico">☀</span>
        <span v-else class="ico">☾</span>
      </div>
    </div>
  </div>
</template>

<style scoped lang="scss">
.auth-top-bar {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 14px 20px;
  pointer-events: none;
  &__spacer {
    flex: 1;
  }
  &__actions {
    display: flex;
    align-items: center;
    gap: 8px;
    pointer-events: auto;
  }
}

.icon-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.25s ease;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.06);
  .ico {
    font-size: 16px;
    line-height: 1;
    color: var(--text-primary);
  }
  &:hover {
    background: rgba(79, 70, 229, 0.1);
  }
}

html.dark .icon-btn {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.1);
  .ico {
    color: #e2e8f0;
  }
}

.color-picker-expandable {
  position: relative;
  display: flex;
  align-items: center;
}
.color-dots {
  position: absolute;
  right: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 28px 6px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.85);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
  opacity: 0;
  transform: translateX(8px);
  pointer-events: none;
  transition:
    opacity 0.3s ease,
    transform 0.3s ease;
}
.color-dot {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 2px 4px rgb(0 0 0 / 15%);
  transition:
    transform 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.3s ease;
  transition-delay: calc(var(--index) * 0.05s);
  opacity: 0;
  transform: translateX(12px) scale(0.85);
  .check {
    font-size: 12px;
  }
  &:hover {
    transform: translateX(0) scale(1.08);
  }
}
.palette-btn {
  position: relative;
  z-index: 2;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: default;
  background: rgba(255, 255, 255, 0.6);
  border: 1px solid rgba(0, 0, 0, 0.06);
  transition: background 0.25s ease;
}
.palette-ico {
  font-size: 16px;
}
.color-picker-expandable:hover .color-dots {
  opacity: 1;
  transform: translateX(0);
  pointer-events: auto;
}
.color-picker-expandable:hover .color-dot {
  opacity: 1;
  transform: translateX(0) scale(1);
}
.color-picker-expandable:hover .palette-btn {
  background: rgba(79, 70, 229, 0.12);
}

html.dark .color-dots {
  background: rgba(30, 32, 40, 0.95);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
}
html.dark .palette-btn {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.1);
}

.check-r {
  float: right;
  margin-left: 8px;
}
</style>
