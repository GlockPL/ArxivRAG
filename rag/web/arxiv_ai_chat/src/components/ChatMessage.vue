<template>
    <div class="message" :class="{ sent: message.type === 'human' }">
        <div class="message-avatar">
            <span v-if="message.type === 'human'">{{ userInitial }}</span>
            <span v-else><i class="fa-solid fa-robot"></i></span>
        </div>
        <div v-if="message.isStreaming && !message.content" class="message-content">
            <div class="thinking"><div class="dot-spinner"></div><span>Thinking...</span></div>
        </div>
        <div v-else class="message-content markdown-content" v-html="renderedContent">
        </div>
    </div>
</template>

<script>
import { computed } from 'vue'
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

        const userInitial = computed(() => authStore.userInitial)

        // message.content always holds raw markdown, both while streaming and for loaded history
        const renderedContent = computed(() => renderMarkdown(props.message.content))

        return {
            userInitial,
            renderedContent
        }
    }
}
</script>
