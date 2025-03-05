<template>
    <section class="bg-gray-50 dark:bg-gray-900">
        <div class="flex flex-col items-center justify-center px-6 py-8 mx-auto md:h-screen lg:py-0">
            <div class="w-full bg-white rounded-lg shadow dark:border md:mt-0 sm:max-w-md xl:p-0 dark:bg-gray-800 dark:border-gray-700">
                <div class="p-6 space-y-4 md:space-y-6 sm:p-8">
                    <h1 class="text-xl font-bold leading-tight tracking-tight text-gray-900 md:text-2xl dark:text-white">
                        Sign in to your account - Arxiv RAG
                    </h1>
                    <form class="space-y-4 md:space-y-6" @submit.prevent="login">
                        <div>
                            <label for="username" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Your Username</label>
                            <input type="text" name="username" id="username" class="bg-gray-50 border border-gray-300 text-gray-900 rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" placeholder="Enter your username" required="" v-model="username" @keyup.enter="login">
                        </div>
                        <div>
                            <label for="password" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Password</label>
                            <input type="password" name="password" id="password" placeholder="••••••••" class="bg-gray-50 border border-gray-300 text-gray-900 rounded-lg focus:ring-primary-600 focus:border-primary-600 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" required="" v-model="password" @keyup.enter="login">
                        </div>                        
                        <button class="w-full text-white bg-blue-500 hover:bg-primary-700 focus:ring-4 focus:outline-none focus:ring-primary-300 font-medium rounded-lg text-sm px-5 py-2.5 text-center dark:bg-primary-600 dark:hover:bg-primary-700 dark:focus:ring-primary-800" @click="login" :disabled="isLoggingIn || !username || !password">Sign in</button>
                        <div class="error-message" v-if="loginError">
                            {{ loginError }}
                        </div>
                        <p class="text-sm font-light text-gray-500 dark:text-gray-400">
                            Don’t have an account yet? <a href="/register" class="font-medium text-primary-600 hover:underline dark:text-primary-500">Sign up</a>
                        </p>
                    </form>
                </div>
            </div>
        </div>
    </section>
</template>


<!-- <template>
    <div class="login-container">
        <div class="login-form">
            <h1>ARXiV RAG Login</h1>
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" v-model="username" @keyup.enter="login"
                    placeholder="Enter your username">
            </div>
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" v-model="password" @keyup.enter="login"
                    placeholder="Enter your password">
            </div>
            <button class="login-btn" @click="login" :disabled="isLoggingIn || !username || !password">
                <span class="loader" v-if="isLoggingIn"></span>
                {{ isLoggingIn ? 'Logging in...' : 'Login' }}
            </button>
            <div class="error-message" v-if="loginError">
                {{ loginError }}
            </div>
            <div class="text-sm text-center mt-4">
                <a href="/register" class="font-medium text-indigo-600 hover:text-indigo-500">Register new account</a>
            </div>
        </div>
    </div>
</template> -->

<script>
import { ref, computed } from 'vue'
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

        const login = async () => {
            if (!username.value || !password.value) return

            const success = await authStore.login(username.value, password.value)

            if (success) {
                router.push('/')
            }
        }

        return {
            username,
            password,
            isLoggingIn,
            loginError,
            login
        }
    }
}
</script>