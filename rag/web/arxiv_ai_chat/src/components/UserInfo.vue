<template>
    <div class="user-info">
      <div class="user-avatar">
        {{ userInitial }}
      </div>
      <div class="user-details">
        <div class="user-name">{{ username }}</div>
      </div>
      <button class="logout-btn" @click="logout">
        <i class="fas fa-sign-out-alt"></i>
      </button>
    </div>
  </template>
  
  <script>
  import { computed } from 'vue'
  import { useRouter } from 'vue-router'
  import { useAuthStore } from '@/stores'
  
  export default {
    name: 'UserInfo',
    setup() {
      const router = useRouter()
      const authStore = useAuthStore()
      
      const username = computed(() => authStore.username)
      const userInitial = computed(() => authStore.userInitial)
      
      const logout = () => {
        authStore.logout()
        router.push('/login')
      }
      
      return {
        username,
        userInitial,
        logout
      }
    }
  }
  </script>