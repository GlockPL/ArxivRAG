<template>
    <section class="auth-page">
        <div class="auth-card">
            <div class="auth-brand">
                <span class="brand-mark"><i class="fas fa-book-open"></i></span>
                arXiv RAG
            </div>
            <h1>Create your account</h1>
            <p class="auth-subtitle">Start asking questions about arXiv cs.AI papers.</p>
            <form class="auth-form" @submit.prevent="register">
                <div v-if="errorMessage" class="auth-alert error" role="alert">{{ errorMessage }}</div>
                <div class="field">
                    <label for="username">Username</label>
                    <input type="text" name="username" id="username" autocomplete="username"
                        placeholder="Username" required v-model="form.username">
                </div>
                <div class="field">
                    <label for="email">Email</label>
                    <input type="email" name="email" id="email" autocomplete="email"
                        placeholder="you@example.com" required v-model="form.email">
                </div>
                <div class="field">
                    <label for="name">Name</label>
                    <input type="text" name="name" id="name" autocomplete="name"
                        placeholder="Full name" required v-model="form.name">
                </div>
                <div class="field">
                    <label for="password">Password</label>
                    <input type="password" name="password" id="password" autocomplete="new-password"
                        placeholder="At least 8 characters" required v-model="form.password">
                </div>
                <div class="field">
                    <label for="confirmPassword">Confirm password</label>
                    <input type="password" name="confirmPassword" id="confirmPassword" autocomplete="new-password"
                        placeholder="••••••••" required v-model="form.confirmPassword">
                </div>
                <button type="submit" class="btn-primary" :disabled="isSubmitting">
                    {{ isSubmitting ? 'Creating account...' : 'Create account' }}
                </button>
            </form>
            <p class="auth-footer">
                Already have an account? <router-link to="/login">Sign in</router-link>
            </p>
        </div>
    </section>
</template>

<script>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores'

export default {
    name: 'RegisterView',
    setup() {
        const router = useRouter()
        const authStore = useAuthStore()
        const form = ref({
            username: '',
            email: '',
            name: '',
            password: '',
            confirmPassword: ''
        })
        const isSubmitting = ref(false)
        const errorMessage = ref('')

        const register = async () => {
            // Reset error message
            errorMessage.value = ''

            // Validate passwords match
            if (form.value.password !== form.value.confirmPassword) {
                errorMessage.value = 'Passwords do not match'
                return
            }

            // Validate password strength (optional)
            if (form.value.password.length < 8) {
                errorMessage.value = 'Password must be at least 8 characters long'
                return
            }

            isSubmitting.value = true

            try {
                // Use the register function from the auth store
                await authStore.register({
                    username: form.value.username,
                    email: form.value.email,
                    name: form.value.name,
                    password: form.value.password
                })

                // Show success message and redirect to login
                router.push({
                    path: '/login',
                    query: { registered: 'success' }
                })
            } catch (error) {
                // The error is already handled in the auth store, but we can display it here
                errorMessage.value = authStore.registerError || 'Registration failed. Please try again.'
            } finally {
                isSubmitting.value = false
            }
        }

        return {
            form,
            isSubmitting,
            errorMessage,
            register
        }
    }
}
</script>