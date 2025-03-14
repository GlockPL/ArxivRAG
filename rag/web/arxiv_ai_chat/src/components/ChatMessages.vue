<template>
    <div class="chat-messages" ref="messagesContainer">
      <ChatMessage
        v-for="(message, index) in activeChat.messages"
        :key="index"
        :message="message"
      />
    </div>
  </template>
  
  <script>
  import { ref, computed, watch, nextTick } from 'vue'
  import { useChatStore } from '@/stores'
  import ChatMessage from '@/components/ChatMessage.vue'
  
  export default {
    name: 'ChatMessages',
    components: {
      ChatMessage
    },
    setup() {
      const chatStore = useChatStore()
      const messagesContainer = ref(null)
      
      const activeChat = computed(() => chatStore.activeChat)
      
      const scrollToBottom = () => {
        nextTick(() => {
          if (messagesContainer.value) {
            messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
          }
        })
      }
      
      // Process LaTeX and scroll to bottom when messages change
      watch(() => activeChat.value?.messages, () => {
        scrollToBottom()       
      }, { deep: true })
      
      // Initial scroll to bottom when component mounts
      nextTick(() => {
        scrollToBottom()
      })
      
      return {
        activeChat,
        messagesContainer
      }
    }
  }
  </script>