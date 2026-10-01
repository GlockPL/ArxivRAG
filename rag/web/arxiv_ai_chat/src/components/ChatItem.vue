<template>
  <div class="chat-item" :class="{ active: isActive }" @click="setActiveChat(chat.id)">
    <!-- Chat Item Content -->
    <div class="chat-name">
      <template v-if="chat.isEditing">
        <input class="edit-title-input" v-model="chat.editingName" @click.stop ref="titleInput"
          @keyup.enter="saveConversationTitle(chat)" @keyup.esc="cancelEditingTitle(chat)" />
        <div class="edit-title-actions">
          <button class="cancel-btn" @click.stop="cancelEditingTitle(chat)">Cancel</button>
          <button class="save-btn" @click.stop="saveConversationTitle(chat)">Save</button>
        </div>
      </template>
      <template v-else>
        {{ chat.name }}
      </template>
    </div>
    <div v-if="!chat.isEditing" class="chat-date">{{ formatDate(chat.createdAt) }}</div>

    <!-- Menu Button and Dropdown -->
    <button v-if="!chat.isEditing" class="chat-menu-button" @click.stop="toggleMenu(chat.id)" aria-label="Conversation actions">
      <i class="fas fa-ellipsis"></i>
    </button>

    <!-- Dropdown Menu -->
    <div class="chat-menu" v-if="openMenuId === chat.id && !chat.isEditing">
      <div class="chat-menu-item" @click.stop="editConversationTitle(chat)">
        <i class="fas fa-pen fa-fw"></i> Rename
      </div>
      <div class="chat-menu-item danger" @click.stop="deleteConversation(chat.id)">
        <i class="fas fa-trash fa-fw"></i> Delete
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, nextTick } from 'vue'
import { useChatStore } from '@/stores'
import { formatDate } from '@/utils/dateFormatter'

export default {
  name: 'ChatItem',
  props: {
    chat: {
      type: Object,
      required: true
    }
  },
  setup(props) {
    const chatStore = useChatStore()
    const titleInput = ref(null)

    const isActive = computed(() => chatStore.activeChatId === props.chat.id)
    const openMenuId = computed(() => chatStore.openMenuId)

    const setActiveChat = (id) => {
      chatStore.setActiveChat(id)
    }

    const toggleMenu = (id) => {
      chatStore.toggleMenu(id)
    }

    const editConversationTitle = (chat) => {
      chatStore.editConversationTitle(chat)

      nextTick(() => {
        if (titleInput.value) {
          titleInput.value.focus()
        }
      })
    }

    const saveConversationTitle = (chat) => {
      chatStore.saveConversationTitle(chat)
    }

    const cancelEditingTitle = (chat) => {
      chatStore.cancelEditingTitle(chat)
    }

    const deleteConversation = (id) => {
      chatStore.deleteConversation(id)
    }

    // Close menu when clicking outside
    onMounted(() => {
      document.addEventListener('click', () => {
        if (openMenuId.value) {
          chatStore.toggleMenu(null)
        }
      })
    })

    return {
      isActive,
      openMenuId,
      titleInput,
      setActiveChat,
      toggleMenu,
      editConversationTitle,
      saveConversationTitle,
      cancelEditingTitle,
      deleteConversation,
      formatDate
    }
  }
}
</script>