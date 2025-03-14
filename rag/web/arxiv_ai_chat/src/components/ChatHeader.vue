<template>
  <div class="chat-header">
    <h2>{{ displayedText }}</h2>
  </div>
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
    const typingSpeed = 50 // milliseconds between characters

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

    // Watch for changes to the chat name
    watch(
      () => activeChat.value?.name,
      (newName) => {
        if (newName) {
          animateTyping(newName)
        } else {
          displayedText.value = ''
        }
      },
      { immediate: true }
    )

    return {
      activeChat,
      displayedText
    }
  }
}
</script>

<style scoped>
.chat-header h2 {
  min-height: 1.5em;
  /* Maintain consistent height during animation */
  position: relative;
}

.chat-header h2:after {
  content: '|';
  position: absolute;
  right: -8px;
  animation: blink 1s step-end infinite;
}

@keyframes blink {

  from,
  to {
    opacity: 1;
  }

  50% {
    opacity: 0;
  }
}
</style>