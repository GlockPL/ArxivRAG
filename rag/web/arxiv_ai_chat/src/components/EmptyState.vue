<template>
  <div class="empty-state">
    <i class="fas fa-comments"></i>
    <h3>No conversation selected</h3>
    <p>Pick a conversation from the sidebar or start a new one.</p>
    <button class="btn-primary" @click="createNewChat"><i class="fas fa-plus"></i> New chat</button>
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
