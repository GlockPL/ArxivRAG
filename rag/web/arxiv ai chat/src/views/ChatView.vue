<template>
    <div class="sidebar">
      <UserInfo />
      <div class="sidebar-header">
        <h2>Chats</h2>
        <button class="new-chat-btn" @click="createNewChat">
          <i class="fas fa-plus"></i> New
        </button>
      </div>
      <ChatList />
    </div>
    <div class="main">
      <template v-if="activeChat">
        <ChatHeader />
        <div v-if="isLoadingMessages" class="messages-loading">
          <div class="loading-spinner"></div>
          <span>Loading messages...</span>
        </div>
        <ChatMessages v-else />
        <ChatInput />
      </template>
      <EmptyState v-else />
    </div>
  </template>
  
  <script>
  import { onMounted, computed } from 'vue'
  import { useChatStore } from '@/stores'
  import UserInfo from '@/components/UserInfo.vue'
  import ChatList from '@/components/ChatList.vue'
  import ChatHeader from '@/components/ChatHeader.vue'
  import ChatMessages from '@/components/ChatMessages.vue'
  import ChatInput from '@/components/ChatInput.vue'
  import EmptyState from '@/components/EmptyState.vue'
  
  export default {
    name: 'ChatView',
    components: {
      UserInfo,
      ChatList,
      ChatHeader,
      ChatMessages,
      ChatInput,
      EmptyState
    },
    setup() {
      const chatStore = useChatStore()
      
      const activeChat = computed(() => chatStore.activeChat)
      const isLoadingMessages = computed(() => chatStore.isLoadingMessages)
      
      const createNewChat = () => {
        chatStore.createNewChat()
      }
      
      onMounted(() => {
        chatStore.fetchConversations()
      })
      
      return {
        activeChat,
        isLoadingMessages,
        createNewChat
      }
    }
  }
  </script>