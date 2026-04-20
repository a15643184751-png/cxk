import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'

import App from './App.vue'
import router from './router'
import { i18n } from './i18n'
import { useUserStore } from './stores/user'
import { useUiSettingsStore } from './stores/uiSettings'
import './styles/index.scss'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(i18n)

const userStore = useUserStore()
i18n.global.locale.value = userStore.language

useUiSettingsStore()

app.use(router)
app.use(ElementPlus)
app.mount('#app')
