import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { setupRouterGuard } from './router/guard'
import pinia from './store'

// Element Plus & Icons
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

// Global Styles
import './styles/index.scss'

const app = createApp(App)

// Register all Element Plus Icons
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.use(pinia)
app.use(router)
app.use(ElementPlus)

// Setup Router Security Guard
setupRouterGuard(router)

app.mount('#app')
