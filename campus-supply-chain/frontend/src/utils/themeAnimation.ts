import { useUiSettingsStore } from '@/stores/uiSettings'

/** 明暗切换（可选 View Transition API 圆形扩散，对齐 art-design-pro） */
export function themeAnimation(e: MouseEvent) {
  const ui = useUiSettingsStore()
  const x = e.clientX
  const y = e.clientY
  const endRadius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y))
  // 与 art-design-pro theme-animation 一致，供 ::view-transition clip-path 使用
  document.documentElement.style.setProperty('--x', `${x}px`)
  document.documentElement.style.setProperty('--y', `${y}px`)
  document.documentElement.style.setProperty('--r', `${endRadius}px`)

  const run = () => {
    ui.setDark(!ui.isDark)
  }

  if (typeof document.startViewTransition === 'function') {
    document.startViewTransition(() => run())
  } else {
    run()
  }
}
