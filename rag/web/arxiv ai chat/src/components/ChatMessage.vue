<template>
    <div
      class="message"
      :class="{ sent: message.type === 'human' }"
    >
      <div class="message-avatar">
        <span v-if="message.type === 'human'">{{ userInitial }}</span>
        <span v-else v-html="'<i class=&quot;fa-solid fa-robot&quot;></i>'"></span>
      </div>
      <div 
        class="message-content markdown-content"
        v-html="message.isStreaming ? message.content : renderedContent"
      ></div>
    </div>
  </template>
  
  <script>
  import { ref, computed, watch } from 'vue'
  import { useAuthStore } from '@/stores'
  import { renderMarkdown } from '@/utils/markdownProcessor'
  
  export default {
    name: 'ChatMessage',
    props: {
      message: {
        type: Object,
        required: true
      }
    },
    setup(props) {
      const authStore = useAuthStore()
      const renderedContent = ref('')
      
      const userInitial = computed(() => authStore.userInitial)
      
      // Render markdown when message content changes
      watch(() => props.message.content, (newContent) => {
        if (!props.message.isStreaming) {
          renderedContent.value = renderMarkdown(newContent)
        }
      }, { immediate: true })
      
      return {
        userInitial,
        renderedContent
      }
    }
  }
  </script>