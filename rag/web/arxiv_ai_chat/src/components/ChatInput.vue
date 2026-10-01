<template>
  <div class="chat-input">
    <div class="input-area">
      <textarea class="message-input" v-model="message" rows="1" placeholder="Ask about arXiv cs.AI papers..."
        @keydown.enter.exact.prevent="sendMessage" @input="resize" ref="messageInput"></textarea>
      <button class="send-btn" @click="sendMessage" :disabled="isSending || !message.trim()" aria-label="Send message">
        <i v-if="!isSending" class="fas fa-arrow-up"></i>
        <div v-else class="loading-spinner"></div>
      </button>
    </div>
    <div class="latex-help">
      <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line · <code>$...$</code> for math
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

    // Grow the textarea with its content, up to the max-height set in CSS
    const resize = () => {
      const textarea = messageInput.value
      if (!textarea) return
      textarea.style.height = 'auto'
      textarea.style.height = `${textarea.scrollHeight}px`
    }

    const sendMessage = async () => {
      if (!message.value.trim() || isSending.value) return

      const messageText = message.value
      message.value = ''
      nextTick(resize)

      await chatStore.sendMessage(messageText)

      // Focus back on input
      nextTick(() => {
        messageInput.value?.focus()
      })
    }

    return {
      message,
      messageInput,
      isSending,
      resize,
      sendMessage
    }
  }
}
</script>
