<template>
    <div class="empty-state">
      <i class="fas fa-comments"></i>
      <h3>No chat selected</h3>
      <p>Select an existing chat from the sidebar or create a new one to get started.</p>
      <button class="start-chat-btn" @click="createNewChat">Start a new chat</button>
    </div>
  </template>
  
  <script>
  import { useChatStore } from '@/stores'
  
  export default {
    name: 'EmptyState',
    setup() {
      const chatStore = useChatStore()
      
      const createNewChat = () => {
        chatStore.createNewChat()
      }
      
      return {
        createNewChat
      }
    }
  }
  </script>