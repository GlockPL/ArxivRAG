<template>
    <div class="message" :class="{ sent: message.type === 'human' }">
        <div class="message-avatar">
            <span v-if="message.type === 'human'">{{ userInitial }}</span>
            <span v-else v-html="'<i class=&quot;fa-solid fa-robot&quot;></i>'"></span>
        </div>
        <div class="message-content markdown-content" v-html="message.isStreaming ? message.content : renderedContent">
        </div>
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
        watch(
            [() => props.message.content, () => props.message.isStreaming],
            ([newContent, isStreaming], [oldContent, oldIsStreaming]) => {
                // Process markdown when:
                // 1. Content changes and we're not streaming, OR
                // 2. We just finished streaming (isStreaming changed from true to false)
                if (!isStreaming) {
                    // console.log("Processing markdown for message:", newContent);
                    renderedContent.value = renderMarkdown(newContent);
                }
            },
            { immediate: true, deep: true }
        );

        return {
            userInitial,
            renderedContent
        }
    }
}
</script>