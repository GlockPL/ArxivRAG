<template>
  <div class="chat-list">
    <div v-if="isLoadingConversations" class="chat-loading">
      <div class="loading-spinner"></div>
      <span>Loading conversations...</span>
    </div>
    <div v-else-if="chats.length === 0" class="no-chats">
      <p>No conversations yet</p>
      <button class="start-first-chat" @click="createNewChat">Start your first chat</button>
    </div>
    <template v-else>
      <ChatItem v-for="chat in chats" :key="chat.id" :chat="chat" />

      <PaginationControls v-if="chats.length > 0" />
    </template>
  </div>
</template>

<script>
import { computed } from 'vue'
import { useChatStore } from '@/stores'
import ChatItem from '@/components/ChatItem.vue'
import PaginationControls from '@/components/PaginationControls.vue'

export default {
  name: 'ChatList',
  components: {
    ChatItem,
    PaginationControls
  },
  setup() {
    const chatStore = useChatStore()

    const chats = computed(() => chatStore.chats)
    const isLoadingConversations = computed(() => chatStore.isLoadingConversations)

    const createNewChat = () => {
      chatStore.createNewChat()
    }

    return {
      chats,
      isLoadingConversations,
      createNewChat
    }
  }
}
</script>