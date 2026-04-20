/// <reference types="vite/client" />

declare module 'element-plus/dist/locale/zh-cn.mjs' {
  const locale: object
  export default locale
}

/** package exports 与 typings 路径不一致时，避免 vue-tsc 7016 */
declare module '@wangeditor/editor-for-vue' {
  import type { DefineComponent } from 'vue'
  export const Editor: DefineComponent<object, object, unknown>
  export const Toolbar: DefineComponent<object, object, unknown>
}
