<template>
    <div id="outer">
        <div class="sidebar-overlay" :class="{ open: sidebarOpen }" @click="closeSidebar"></div>
        <aside class="sidebar" :class="{ open: sidebarOpen }">
            <div class="sidebar-brand">
                <span class="brand-mark"><i class="fas fa-book-open"></i></span>
                arXiv RAG
            </div>
            <div class="sidebar-header">
                <button class="btn-primary new-chat-btn" @click="createNewChat">
                    <i class="fas fa-plus"></i> New chat
                </button>
            </div>
            <div class="sidebar-section-label">Recent</div>
            <ChatList />
            <UserInfo />
        </aside>
        <main class="main">
            <ChatHeader />
            <template v-if="activeChat">
                <div v-if="isLoadingMessages" class="messages-loading">
                    <div class="loading-spinner"></div>
                    <span>Loading messages...</span>
                </div>
                <ChatMessages v-else />
                <ChatInput />
            </template>
            <EmptyState v-else />
        </main>
    </div>
</template>

<script>
import { onMounted, computed } from 'vue'
import { useChatStore } from '@/stores'
import UserInfo from '@/components/UserInfo.vue'
import ChatList from '@/components/ChatList.vue'
import ChatHeader from '@/components/ChatHeader.vue'
import ChatMessages from '@/components/ChatMessages.vue'
import ChatInput from '@/components/ChatInput.vue'
import EmptyState from '@/components/EmptyState.vue'

export default {
    name: 'ChatView',
    components: {
        UserInfo,
        ChatList,
        ChatHeader,
        ChatMessages,
        ChatInput,
        EmptyState
    },
    setup() {
        const chatStore = useChatStore()

        const activeChat = computed(() => chatStore.activeChat)
        const isLoadingMessages = computed(() => chatStore.isLoadingMessages)
        const sidebarOpen = computed(() => chatStore.sidebarOpen)

        const createNewChat = () => {
            chatStore.createNewChat()
            chatStore.toggleSidebar(false)
        }

        const closeSidebar = () => {
            chatStore.toggleSidebar(false)
        }

        onMounted(() => {
            chatStore.fetchConversations()
        })

        return {
            activeChat,
            isLoadingMessages,
            sidebarOpen,
            createNewChat,
            closeSidebar
        }
    }
}
</script>
