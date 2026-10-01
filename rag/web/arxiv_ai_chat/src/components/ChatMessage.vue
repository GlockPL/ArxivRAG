<template>
    <div class="message" :class="{ sent: message.type === 'human' }">
        <div class="message-avatar">
            <span v-if="message.type === 'human'">{{ userInitial }}</span>
            <i v-else class="fas fa-book-open"></i>
        </div>
        <div v-if="message.isStreaming && !message.content" class="message-content">
            <div class="thinking"><span class="dot-spinner"><span></span><span></span><span></span></span>Thinking</div>
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
