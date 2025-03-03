<template>
    <div class="login-container">
      <div class="login-form">
        <h1>ARXiV RAG Login</h1>
        <div class="form-group">
          <label for="username">Username</label>
          <input
            type="text"
            id="username"
            v-model="username"
            @keyup.enter="login"
            placeholder="Enter your username"
          >
        </div>
        <div class="form-group">
          <label for="password">Password</label>
          <input
            type="password"
            id="password"
            v-model="password"
            @keyup.enter="login"
            placeholder="Enter your password"
          >
        </div>
        <button
          class="login-btn"
          @click="login"
          :disabled="isLoggingIn || !username || !password"
        >
          <span class="loader" v-if="isLoggingIn"></span>
          {{ isLoggingIn ? 'Logging in...' : 'Login' }}
        </button>
        <div class="error-message" v-if="loginError">
          {{ loginError }}
        </div>
      </div>
    </div>
  </template>
  
  <script>
  import { ref, computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { useAuthStore } from '@/stores'
  
  export default {
    name: 'LoginView',
    setup() {
      const router = useRouter()
      const authStore = useAuthStore()
      
      const username = ref('')
      const password = ref('')
      
      const isLoggingIn = computed(() => authStore.isLoggingIn)
      const loginError = computed(() => authStore.loginError)
      
      const login = async () => {
        if (!username.value || !password.value) return
        
        const success = await authStore.login(username.value, password.value)
        
        if (success) {
          router.push('/')
        }
      }
      
      return {
        username,
        password,
        isLoggingIn,
        loginError,
        login
      }
    }
  }
  </script>