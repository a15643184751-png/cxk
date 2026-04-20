<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { openSettingsBus } from '@/utils/layoutBus'
import { useUiSettingsStore, THEME_PRESETS } from '@/stores/uiSettings'

const { t } = useI18n()
const ui = useUiSettingsStore()

const open = ref(false)
const radius = ref(0.5)

watch(radius, (v) => {
  document.documentElement.style.setProperty('--app-radius-rem', `${v}rem`)
})

let unsub: (() => void) | undefined

onMounted(() => {
  unsub = openSettingsBus.on(() => {
    open.value = true
    ui.dismissSettingGuide()
  })
})
onUnmounted(() => unsub?.())

function reset() {
  ui.setDark(false)
  ui.setPrimary(THEME_PRESETS[0])
  radius.value = 0.5
  document.documentElement.style.setProperty('--app-radius-rem', `${radius.value}rem`)
}
</script>

<template>
  <el-drawer v-model="open" :title="t('settings.title')" size="320px" append-to-body>
    <div class="sd-block">
      <div class="sd-label">{{ t('settings.themeColor') }}</div>
      <div class="sd-colors">
        <button
          v-for="c in THEME_PRESETS"
          :key="c"
          type="button"
          class="sd-dot"
          :class="{ active: ui.primaryColor === c }"
          :style="{ background: c }"
          @click="ui.setPrimary(c)"
        />
      </div>
    </div>
    <div class="sd-block">
      <div class="sd-label">{{ ui.isDark ? t('settings.darkMode') : t('settings.lightMode') }}</div>
      <el-switch :model-value="ui.isDark" @update:model-value="ui.setDark(!!$event)" />
    </div>
    <div class="sd-block">
      <div class="sd-label">{{ t('settings.radius') }}</div>
      <el-slider v-model="radius" :min="0.25" :max="1" :step="0.05" />
    </div>
    <el-button class="sd-reset" @click="reset">{{ t('settings.reset') }}</el-button>
  </el-drawer>
</template>

<style scoped lang="scss">
.sd-block {
  margin-bottom: 24px;
}
.sd-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}
.sd-colors {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.sd-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  transition: transform 0.2s ease;
  &.active {
    border-color: var(--text-primary);
    transform: scale(1.08);
  }
}
.sd-reset {
  width: 100%;
}
</style>
