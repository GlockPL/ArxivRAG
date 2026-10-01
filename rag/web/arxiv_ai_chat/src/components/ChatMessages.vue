<template>
  <div class="chat-messages" ref="messagesContainer">
    <div v-if="activeChat.messages.length === 0" class="welcome">
      <span class="brand-mark welcome-mark"><i class="fas fa-book-open"></i></span>
      <h3>What would you like to know?</h3>
      <p>Ask about research in arXiv's cs.AI category. Answers are grounded in the papers and cite their arXiv ids.</p>
      <div class="suggestions">
        <button v-for="suggestion in suggestions" :key="suggestion.query" class="suggestion"
          :disabled="isSending" @click="send(suggestion.query)">
          {{ suggestion.title }}
          <small>{{ suggestion.subtitle }}</small>
        </button>
      </div>
    </div>
    <div v-else class="thread">
      <ChatMessage v-for="(message, index) in activeChat.messages" :key="index" :message="message" />
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, nextTick } from 'vue'
import { useChatStore } from '@/stores'
import ChatMessage from '@/components/ChatMessage.vue'

const suggestions = [
  {
    title: 'Retrieval-augmented generation',
    subtitle: 'What are recent improvements to RAG?',
    query: 'What are recent improvements to retrieval-augmented generation?'
  },
  {
    title: 'LLM agents',
    subtitle: 'How do agents plan and use tools?',
    query: 'How do recent LLM agents plan and use tools?'
  },
  {
    title: 'Efficient fine-tuning',
    subtitle: 'Compare LoRA with full fine-tuning',
    query: 'Compare LoRA and other parameter-efficient methods with full fine-tuning.'
  },
  {
    title: 'Hallucinations',
    subtitle: 'How can they be detected and reduced?',
    query: 'How can hallucinations in large language models be detected and reduced?'
  }
]

export default {
  name: 'ChatMessages',
  components: {
    ChatMessage
  },
  setup() {
    const chatStore = useChatStore()
    const messagesContainer = ref(null)

    const activeChat = computed(() => chatStore.activeChat)
    const isSending = computed(() => chatStore.isSending)

    const send = (query) => {
      chatStore.sendMessage(query)
    }

    const scrollToBottom = () => {
      nextTick(() => {
        if (messagesContainer.value) {
          messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
        }
      })
    }

    // Scroll to bottom when messages change
    watch(() => activeChat.value?.messages, () => {
      scrollToBottom()
    }, { deep: true })

    // Initial scroll to bottom when component mounts
    nextTick(() => {
      scrollToBottom()
    })

    return {
      activeChat,
      isSending,
      messagesContainer,
      suggestions,
      send
    }
  }
}
</script>
