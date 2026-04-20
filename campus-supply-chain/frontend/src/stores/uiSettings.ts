import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

const STORAGE_KEY = 'campus-ui-settings-v1'

export const THEME_PRESETS = ['#5d5fe3', '#409eff', '#13c2c2', '#f5222d', '#fa8c16', '#722ed1'] as const

function load(): { isDark: boolean; primary: string; guideDismissed: boolean } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      return { isDark: false, primary: THEME_PRESETS[0], guideDismissed: false }
    }
    const j = JSON.parse(raw)
    return {
      isDark: !!j.isDark,
      primary: typeof j.primary === 'string' ? j.primary : THEME_PRESETS[0],
      guideDismissed: !!j.guideDismissed,
    }
  } catch {
    return { isDark: false, primary: THEME_PRESETS[0], guideDismissed: false }
  }
}

function save(state: { isDark: boolean; primary: string; guideDismissed: boolean }) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
}

function applyDom(isDark: boolean, primary: string) {
  const root = document.documentElement
  root.classList.toggle('dark', isDark)
  root.style.setProperty('--el-color-primary', primary)
  root.style.setProperty('--primary', primary)
  const hover = adjustBrightness(primary, isDark ? 12 : -8)
  root.style.setProperty('--primary-hover', hover)
  root.style.setProperty(
    '--gradient-primary',
    `linear-gradient(180deg, ${primary} 0%, ${adjustBrightness(primary, -15)} 100%)`
  )
}

function adjustBrightness(hex: string, percent: number) {
  const h = hex.replace('#', '')
  if (h.length !== 6) return hex
  const num = parseInt(h, 16)
  let r = (num >> 16) + percent
  let g = ((num >> 8) & 0x00ff) + percent
  let b = (num & 0x0000ff) + percent
  r = Math.max(0, Math.min(255, r))
  g = Math.max(0, Math.min(255, g))
  b = Math.max(0, Math.min(255, b))
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`
}

export const useUiSettingsStore = defineStore('uiSettings', () => {
  const initial = load()
  const isDark = ref(initial.isDark)
  const primaryColor = ref(initial.primary)
  const showSettingGuide = ref(!initial.guideDismissed)

  function persist() {
    save({
      isDark: isDark.value,
      primary: primaryColor.value,
      guideDismissed: !showSettingGuide.value,
    })
  }

  function setDark(v: boolean) {
    isDark.value = v
  }

  function toggleDark() {
    isDark.value = !isDark.value
  }

  function setPrimary(color: string) {
    primaryColor.value = color
  }

  function dismissSettingGuide() {
    showSettingGuide.value = false
    persist()
  }

  function hydrate() {
    applyDom(isDark.value, primaryColor.value)
  }

  watch(
    [isDark, primaryColor],
    () => {
      applyDom(isDark.value, primaryColor.value)
      persist()
    },
    { immediate: true }
  )

  return {
    isDark,
    primaryColor,
    showSettingGuide,
    setDark,
    toggleDark,
    setPrimary,
    dismissSettingGuide,
    hydrate,
    persist,
  }
})
