import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import axios from 'axios'
import VueMathjax from 'vue-mathjax-next';
import '@/assets/style.css'


// Create pinia store
const pinia = createPinia()

// Create Vue app
const app = createApp(App)


// Global properties
app.config.globalProperties.$axios = axios

// Use plugins
app.use(router)
app.use(pinia)
app.use(VueMathjax)

// Mount app
app.mount('#app')
