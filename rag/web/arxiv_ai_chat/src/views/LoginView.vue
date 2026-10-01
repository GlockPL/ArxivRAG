<template>
    <section class="auth-page">
        <div class="auth-card">
            <div class="auth-brand">
                <span class="brand-mark"><i class="fas fa-book-open"></i></span>
                arXiv RAG
            </div>
            <h1>Welcome back</h1>
            <p class="auth-subtitle">Sign in to chat with arXiv cs.AI papers.</p>
            <!-- Use a div instead of form to prevent any potential html form submission -->
            <div class="auth-form">
                <div v-if="justRegistered && !loginError" class="auth-alert success">
                    Account created, you can sign in now.
                </div>
                <div v-if="loginError" class="auth-alert error">
                    {{ loginError }}
                </div>
                <div class="field">
                    <label for="username">Username</label>
                    <input type="text" name="username" id="username" autocomplete="username"
                        placeholder="Your username" required v-model="username">
                </div>
                <div class="field">
                    <label for="password">Password</label>
                    <input type="password" name="password" id="password" autocomplete="current-password"
                        placeholder="••••••••" required v-model="password">
                </div>
                <button type="button" class="btn-primary" @click="handleLogin"
                    :disabled="isLoggingIn || !username || !password">
                    {{ isLoggingIn ? 'Signing in...' : 'Sign in' }}
                </button>
            </div>
            <p class="auth-footer">
                Don't have an account yet? <router-link to="/register">Sign up</router-link>
            </p>
        </div>
    </section>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores'

export default {
    name: 'LoginView',
    setup() {
        const router = useRouter()
        const route = useRoute()
        const authStore = useAuthStore()

        const username = ref('')
        const password = ref('')

        const isLoggingIn = computed(() => authStore.isLoggingIn)
        const loginError = computed(() => authStore.loginError)
        const justRegistered = computed(() => route.query.registered === 'success')

        const handleLogin = async () => {
            // Return early if validation fails
            if (!username.value || !password.value || isLoggingIn.value) {
                return
            }

            try {
                const success = await authStore.login(username.value, password.value)
                if (success) {
                    router.push('/')
                }
                // If login was unsuccessful, we do nothing and let the store 
                // display the error message through the loginError computed property
            } catch (error) {
                console.error('Login error:', error)                
            }
        }

        // Add keyboard event listener for Enter key
        const handleKeyDown = (event) => {
            if (event.key === 'Enter' && username.value && password.value && !isLoggingIn.value) {
                // Explicitly prevent default behavior
                event.preventDefault()
                handleLogin()
            }
        }

        // Add event listener for Enter key on component mount
        // and remove it on component unmount
        onMounted(() => {
            document.addEventListener('keydown', handleKeyDown)
        })

        onUnmounted(() => {
            document.removeEventListener('keydown', handleKeyDown)
        })

        return {
            username,
            password,
            isLoggingIn,
            loginError,
            justRegistered,
            handleLogin
        }
    }
}
</script>