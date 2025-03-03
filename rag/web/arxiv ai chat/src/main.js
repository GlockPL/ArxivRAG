import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import axios from 'axios'
import hljs from 'highlight.js'
import 'highlight.js/styles/github.min.css'

// Configure MathJax
window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\(', '\\)']],
    displayMath: [['$$', '$$'], ['\\[', '\\]']],
    processEscapes: true,
    processEnvironments: true
  },
  options: {
    skipHtmlTags: ['script', 'noscript', 'style', 'textarea', 'pre', 'code'],
    ignoreHtmlClass: 'tex2jax_ignore',
    processHtmlClass: 'tex2jax_process'
  },
  startup: {
    pageReady: function () {
      return new Promise(function (resolve) {
        resolve();
        console.log("MathJax page ready");
        window.isMathJaxReady = true;
      });
    }
  }
};

// Create pinia store
const pinia = createPinia()

// Create Vue app
const app = createApp(App)

// Global properties
app.config.globalProperties.$axios = axios

// Use plugins
app.use(router)
app.use(pinia)

// Mount app
app.mount('#app')

// Load MathJax dynamically
const script = document.createElement('script')
script.src = 'https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.js'
script.async = true
document.head.appendChild(script)