import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import './styles/index.scss'
import { getUserInfo } from '@/api/auth'
import { useUserStore } from '@/stores/user'
import { bindGlobalIdsAlertAudioPriming } from '@/utils/idsAdminAlert'

async function bootstrap() {
  bindGlobalIdsAlertAudioPriming()

  const app = createApp(App)
  const pinia = createPinia()
  app.use(pinia)

  const userStore = useUserStore(pinia)
  if (userStore.token && !userStore.userInfo) {
    try {
      const info: any = await getUserInfo()
      userStore.setUserInfo(info?.data ?? info ?? null)
    } catch {
      userStore.logout()
    }
  }

  app.use(router)
  app.use(ElementPlus)
  app.mount('#app')
}

void bootstrap()
