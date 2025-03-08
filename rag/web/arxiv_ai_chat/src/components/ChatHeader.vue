<template>
    <div class="chat-header">
      <h2>{{ activeChat.name }}</h2>
    </div>
  </template>
  
  <script>
  import { computed } from 'vue'
  import { useChatStore } from '@/stores'
  
  export default {
    name: 'ChatHeader',
    setup() {
      const chatStore = useChatStore()
      
      const activeChat = computed(() => chatStore.activeChat)
      
      return {
        activeChat
      }
    }
  }
  </script>