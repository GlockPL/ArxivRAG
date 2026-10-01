<template>
  <header class="chat-header">
    <button class="icon-btn menu-toggle" @click="toggleSidebar" aria-label="Open conversations">
      <i class="fas fa-bars"></i>
    </button>
    <h2>{{ displayedText || 'arXiv RAG' }}</h2>
  </header>
</template>

<script>
import { computed, ref, watch } from 'vue'
import { useChatStore } from '@/stores'

export default {
  name: 'ChatHeader',
  setup() {
    const chatStore = useChatStore()
    const activeChat = computed(() => chatStore.activeChat)

    // For the typing animation
    const displayedText = ref('')
    const targetText = ref('')
    let typingTimer = null

    // Animation settings
    const typingSpeed = 30 // milliseconds between characters

    // Function to animate typing
    const animateTyping = (fullText) => {
      // Clear any existing animation
      if (typingTimer) {
        clearTimeout(typingTimer)
      }

      // Store the target text
      targetText.value = fullText || ''

      // Start with an empty string
      displayedText.value = ''

      // Function to add one character at a time
      const typeNextChar = () => {
        if (displayedText.value.length < targetText.value.length) {
          // Add the next character
          displayedText.value = targetText.value.substring(0, displayedText.value.length + 1)

          // Schedule the next character
          typingTimer = setTimeout(typeNextChar, typingSpeed)
        }
      }

      // Start typing if there's text to type
      if (targetText.value) {
        typingTimer = setTimeout(typeNextChar, typingSpeed)
      }
    }

    // Type out a freshly generated title once; any other title (switching or loading chats) shows instantly
    watch(
      () => activeChat.value?.name,
      (newName) => {
        if (typingTimer) {
          clearTimeout(typingTimer)
        }
        if (newName && activeChat.value.animateTitle) {
          activeChat.value.animateTitle = false
          animateTyping(newName)
        } else {
          displayedText.value = newName || ''
        }
      },
      { immediate: true }
    )

    const toggleSidebar = () => {
      chatStore.toggleSidebar()
    }

    return {
      displayedText,
      toggleSidebar
    }
  }
}
</script>
