<template>
    <div class="chat-input">
      <div class="input-area">
        <textarea
          class="message-input"
          v-model="message"
          placeholder="Type a message (supports markdown and LaTeX using $...$)..."
          @keydown.enter.prevent="sendMessage"
          ref="messageInput"
        ></textarea>
        <button class="send-btn" @click="sendMessage" :disabled="isSending">
          <i v-if="!isSending" class="fas fa-paper-plane"></i>
          <div v-else class="loading-spinner" style="width: 16px; height: 16px;"></div>
        </button>
      </div>
      <!-- LaTeX Help Tooltip -->
      <div class="latex-help">
        <i class="fas fa-question-circle"></i>
        <span>Use $...$ for inline math and $$...$$ for display equations</span>
      </div>
    </div>
  </template>
  
  <script>
  import { ref, computed, nextTick } from 'vue'
  import { useChatStore } from '@/stores'
  
  export default {
    name: 'ChatInput',
    setup() {
      const chatStore = useChatStore()
      const messageInput = ref(null)
      const message = ref('')
      
      const isSending = computed(() => chatStore.isSending)
      
      const sendMessage = async () => {
        if (!message.value.trim()) return
        
        const messageText = message.value
        message.value = ''
        
        await chatStore.sendMessage(messageText)
        
        // Focus back on input
        nextTick(() => {
          messageInput.value.focus()
        })
      }
      
      return {
        message,
        messageInput,
        isSending,
        sendMessage
      }
    }
  }
  </script>