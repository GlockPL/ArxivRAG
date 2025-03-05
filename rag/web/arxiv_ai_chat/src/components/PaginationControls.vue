<template>
    <div class="pagination-controls">
        <div class="pagination-info">
            {{ paginationOffset + 1 }}-{{ paginationOffset + chats.length }}
        </div>

        <div class="pagination-buttons">
            <button class="pagination-button" @click="previousPage" :disabled="paginationOffset === 0">
                <i class="fas fa-chevron-left"></i>
            </button>

            <button class="pagination-button" @click="nextPage" :disabled="!hasMorePages">
                <i class="fas fa-chevron-right"></i>
            </button>

        </div>
    </div>
</template>

<script>
import { computed } from 'vue'
import { useChatStore } from '@/stores'

export default {
    name: 'PaginationControls',
    setup() {
        const chatStore = useChatStore()

        const chats = computed(() => chatStore.chats)
        const paginationOffset = computed(() => chatStore.paginationOffset)
        const paginationLimit = computed({
            get: () => chatStore.paginationLimit,
            set: (value) => {
                chatStore.paginationLimit = parseInt(value)
            }
        })
        const hasMorePages = computed(() => chatStore.hasMorePages)

        const previousPage = () => {
            chatStore.previousPage()
        }

        const nextPage = () => {
            chatStore.nextPage()
        }

        const updatePagination = () => {
            chatStore.updatePagination()
        }

        return {
            chats,
            paginationOffset,
            paginationLimit,
            hasMorePages,
            previousPage,
            nextPage,
            updatePagination
        }
    }
}
</script>