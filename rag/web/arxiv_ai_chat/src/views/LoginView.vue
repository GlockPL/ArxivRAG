<template>
    <section class="bg-gray-50 dark:bg-gray-900">
        <div class="flex flex-col items-center justify-center px-6 py-8 mx-auto md:h-screen lg:py-0">
            <div
                class="w-full bg-white rounded-lg shadow dark:border md:mt-0 sm:max-w-md xl:p-0 dark:bg-gray-800 dark:border-gray-700">
                <div class="p-6 space-y-4 md:space-y-6 sm:p-8">
                    <h1
                        class="text-xl font-bold leading-tight tracking-tight text-gray-900 md:text-2xl dark:text-white">
                        Sign in to your account - Arxiv RAG
                    </h1>
                    <!-- Use a div instead of form to prevent any potential html form submission -->
                    <div class="space-y-4 md:space-y-6">
                        <div>
                            <label for="username"
                                class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Your
                                Username</label>
                            <input type="text" name="username" id="username"
                                class="bg-gray-50 border border-gray-300 text-gray-900 rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                                placeholder="Enter your username" required v-model="username">
                        </div>
                        <div>
                            <label for="password"
                                class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Password</label>
                            <input type="password" name="password" id="password" placeholder="••••••••"
                                class="bg-gray-50 border border-gray-300 text-gray-900 rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                                required v-model="password">
                        </div>
                        <button type="button"
                            class="w-full text-white bg-blue-500 hover:bg-primary-700 focus:ring-4 focus:outline-none focus:ring-primary-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-primary-600 dark:hover:bg-primary-700 dark:focus:ring-primary-800"
                            @click="handleLogin" :disabled="isLoggingIn || !username || !password">
                            {{ isLoggingIn ? 'Signing in...' : 'Sign in' }}
                        </button>
                        <div v-if="loginError" class="error-message text-red-500 text-center p-2 bg-red-100 rounded">
                            {{ loginError }}
                        </div>
                        <p class="text-sm font-light text-gray-500 dark:text-gray-400">
                            Don't have an account yet? <router-link to="/register"
                                class="font-medium text-primary-600 hover:underline dark:text-primary-500">Sign
                                up</router-link>
                        </p>
                    </div>
                </div>
            </div>
        </div>
    </section>
</template>

<script>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores'

export default {
    name: 'LoginView',
    setup() {
        const router = useRouter()
        const authStore = useAuthStore()

        const username = ref('')
        const password = ref('')

        const isLoggingIn = computed(() => authStore.isLoggingIn)
        const loginError = computed(() => authStore.loginError)

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
            handleLogin
        }
    }
}
</script>