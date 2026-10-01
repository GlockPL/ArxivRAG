import { defineStore } from 'pinia'
import axios from 'axios'
import { renderMarkdown } from '@/utils/markdownProcessor'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
// Close a chat stream if the server sends nothing for this long
const STREAM_IDLE_TIMEOUT_MS = 120000

// Set up axios interceptors
// Setup axios interceptors for authentication
axios.interceptors.request.use(config => {
    const token = localStorage.getItem('chatToken')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
}, error => {
    return Promise.reject(error)
})

// Refresh tokens are single use, so all callers share one in-flight refresh request
let refreshPromise = null

const refreshTokens = () => {
    if (!refreshPromise) {
        const refreshToken = localStorage.getItem('chatRefreshToken')
        const request = refreshToken
            ? axios.post(`${API_BASE_URL}/refresh`, { refresh_token: refreshToken })
            : Promise.reject(new Error('No refresh token available'))

        refreshPromise = request.then(response => {
            const { access_token, refresh_token } = response.data
            localStorage.setItem('chatToken', access_token)
            localStorage.setItem('chatRefreshToken', refresh_token)

            const authStore = useAuthStore()
            authStore.authToken = access_token
            authStore.refreshToken = refresh_token

            return access_token
        }).finally(() => {
            refreshPromise = null
        })
    }
    return refreshPromise
}

// True if the JWT is expired or expires within the next 30 seconds
const tokenExpiresSoon = (token) => {
    try {
        const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
        return payload.exp * 1000 < Date.now() + 30000
    } catch (e) {
        return true
    }
}

// POST a chat message and call onEvent with every server-sent event of the streamed answer
const streamChat = async (body, onEvent, signal) => {
    const authStore = useAuthStore()
    const send = (token) => fetch(`${API_BASE_URL}/conversations/stream`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(body),
        signal
    })

    // fetch bypasses the axios interceptor, so refresh tokens here and retry once on 401.
    // Like the interceptor, log out when no valid token can be obtained.
    const getToken = async (forceRefresh) => {
        try {
            return forceRefresh ? await refreshTokens() : await authStore.getFreshToken()
        } catch (error) {
            authStore.logout()
            throw error
        }
    }

    let response = await send(await getToken(false))
    if (response.status === 401) {
        response = await send(await getToken(true))
    }

    if (!response.ok) {
        let detail = `Request failed with status ${response.status}`
        try {
            detail = (await response.json()).detail || detail
        } catch (e) {
            // Keep the generic message when the body is not JSON
        }
        throw new Error(detail)
    }

    const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
    let buffer = ''
    while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += value

        // Events are separated by a blank line, each carries one JSON payload in its data lines
        let boundary
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
            const rawEvent = buffer.slice(0, boundary)
            buffer = buffer.slice(boundary + 2)
            const data = rawEvent
                .split('\n')
                .filter(line => line.startsWith('data:'))
                .map(line => line.slice(5).trimStart())
                .join('\n')
            if (data) {
                onEvent(JSON.parse(data))
            }
        }
    }
}

// Auth endpoints must not trigger a refresh, or a failing /refresh would try to refresh itself
const AUTH_ENDPOINTS = ['/token', '/refresh', '/logout']

// Response interceptor for token refresh
axios.interceptors.response.use(response => {
    return response
}, async error => {
    const originalRequest = error.config
    const isAuthEndpoint = AUTH_ENDPOINTS.some(endpoint => originalRequest?.url?.endsWith(endpoint))

    // If the error is 401 and we haven't tried to refresh the token yet
    if (error.response?.status === 401 && !originalRequest._retry && !isAuthEndpoint) {
        originalRequest._retry = true

        try {
            const accessToken = await refreshTokens()
            originalRequest.headers['Authorization'] = `Bearer ${accessToken}`
            return axios(originalRequest)
        } catch (refreshError) {
            // Refresh token failed, logout
            useAuthStore().logout()
            return Promise.reject(refreshError)
        }
    }

    return Promise.reject(error)
})

export const useAuthStore = defineStore('auth', {
    state: () => ({
        isAuthenticated: localStorage.getItem('chatToken') !== null,
        username: localStorage.getItem('chatUsername') || '',
        authToken: localStorage.getItem('chatToken') || '',
        refreshToken: localStorage.getItem('chatRefreshToken') || '',
        isLoggingIn: false,
        isRegistering: false,
        loginError: '',
        registerError: ''
    }),

    actions: {
        async register(userData) {
            this.isRegistering = true
            this.registerError = ''

            try {
                const response = await axios.post(`${API_BASE_URL}/register`, {
                    username: userData.username,
                    email: userData.email,
                    name: userData.name,
                    password: userData.password
                })

                // Optional: Auto-login after registration
                // Uncomment the next line if you want to automatically log in users after registration
                // await this.login(userData.username, userData.password)

                return response.data
            } catch (error) {
                console.error('Registration error:', error)

                if (error.response && error.response.data && error.response.data.detail) {
                    this.registerError = error.response.data.detail
                } else {
                    this.registerError = "Registration failed. Please try again."
                }

                throw new Error(this.registerError)
            } finally {
                this.isRegistering = false
            }
        },

        async login(username, password) {
            this.isLoggingIn = true
            this.loginError = ''
        
            try {
                // Use URLSearchParams instead of FormData for x-www-form-urlencoded
                const params = new URLSearchParams()
                params.append('username', username)
                params.append('password', password)
        
                // Create an axios instance with custom settings for this specific request
                const axiosInstance = axios.create({
                    // Set validateStatus to return true for all status codes
                    // This prevents axios from throwing errors for non-2xx responses
                    validateStatus: status => true,
                    // Set withCredentials to false to avoid CORS issues with redirects
                    withCredentials: false
                })
        
                const response = await axiosInstance.post(`${API_BASE_URL}/token`, params, {
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
                })
        
                // Manually handle response status codes
                if (response.status >= 200 && response.status < 300) {
                    // Success response
                    this.authToken = response.data.access_token
                    this.refreshToken = response.data.refresh_token
                    this.username = username
                    this.isAuthenticated = true
        
                    try {
                        localStorage.setItem('chatToken', this.authToken)
                        localStorage.setItem('chatRefreshToken', this.refreshToken)
                        localStorage.setItem('chatUsername', this.username)
                    } catch (storageError) {
                        console.warn('Unable to save to localStorage:', storageError)
                    }
        
                    return true
                } else {
                    // Error response - manually set error message based on status code
                    if (response.status === 401) {
                        this.loginError = "Incorrect username or password"
                    } else {
                        this.loginError = `Login failed. Error: ${response.status}`
                        console.error('Login error details:', response.data)
                    }
                    return false
                }
            } catch (error) {
                // This will only catch network errors, not HTTP status errors
                console.error('Network error during login:', error)
                this.loginError = "Network error. Please check your connection and try again."
                return false
            } finally {
                this.isLoggingIn = false
            }
        },

        async logout() {
            try {
                // Call the logout endpoint if the user is authenticated
                if (this.isAuthenticated && this.refreshToken) {
                    await axios.post(`${API_BASE_URL}/logout`, {
                        refresh_token: this.refreshToken
                    })
                }
            } catch (error) {
                console.error('Logout error:', error)
            } finally {
                // Always clear local state regardless of API call success
                this.isAuthenticated = false
                this.username = ''
                this.authToken = ''
                this.refreshToken = ''

                localStorage.removeItem('chatToken')
                localStorage.removeItem('chatRefreshToken')
                localStorage.removeItem('chatUsername')

                // Redirect to login page
                window.location.href = '/login'
            }
        },

        // Method to manually refresh the token
        async refreshAccessToken() {
            try {
                await refreshTokens()
                return true
            } catch (error) {
                console.error('Token refresh error:', error)
                this.logout()
                return false
            }
        },

        // Return a valid access token, refreshing it first if it is about to expire.
        // Needed for requests that bypass the axios interceptor, like the SSE stream.
        async getFreshToken() {
            const token = localStorage.getItem('chatToken')
            if (token && !tokenExpiresSoon(token)) {
                return token
            }
            await refreshTokens()
            return localStorage.getItem('chatToken')
        }
    },

    getters: {
        userInitial: (state) => {
            return state.username ? state.username.charAt(0).toUpperCase() : ''
        },

        isTokenValid: () => {
            const token = localStorage.getItem('chatToken')
            if (!token) return false

            // Optional: Add JWT decode and expiration check here
            // This would require a jwt-decode library

            return true
        }
    }
})

export const useChatStore = defineStore('chat', {
    state: () => ({
        chats: [],
        activeChatId: null,
        activeChatTitle: '',
        isLoadingConversations: false,
        isLoadingMessages: false,
        isSending: false,
        openMenuId: null,
        paginationLimit: parseInt(localStorage.getItem('paginationLimit')) || 12,
        paginationOffset: 0,
        newMessage: '',
        // Sidebar drawer on small screens
        sidebarOpen: false
    }),

    actions: {
        async fetchConversations() {
            if (!useAuthStore().isAuthenticated) return

            this.isLoadingConversations = true

            try {
                const response = await axios.get(`${API_BASE_URL}/conversations`, {
                    params: {
                        limit: this.paginationLimit,
                        offset: this.paginationOffset
                    }
                })

                const conversationsData = response.data || []

                this.chats = conversationsData.map(conversation => ({
                    id: conversation.thread_id || `temp-${Date.now()}`,
                    name: conversation.title || `Untitled Chat`,
                    createdAt: conversation.created_at ? new Date(conversation.created_at) : new Date(),
                    messages: [],
                    isEditing: false,
                    editingName: conversation.title || `Untitled Chat`
                }))

                this.chats.sort((a, b) => b.createdAt - a.createdAt)

                if (this.chats.length > 0 && !this.activeChatId) {
                    this.setActiveChat(this.chats[0].id)
                } else if (this.chats.length === 0) {
                    this.activeChatId = null
                }
            } catch (error) {
                console.error('Error fetching conversations:', error)
            } finally {
                this.isLoadingConversations = false
            }
        },

        async fetchMessages(chatId) {
            if (!chatId || chatId.startsWith('temp-')) return

            this.isLoadingMessages = true

            try {
                const response = await axios.get(`${API_BASE_URL}/conversations/${chatId}/messages`)

                const chat = this.chats.find(c => c.id === chatId)
                if (chat) {
                    chat.messages = response.data.map(msg => ({
                        content: msg.content,
                        type: msg.type,
                        thread_id: msg.thread_id
                    }))
                }
            } catch (error) {
                console.error(`Error fetching messages for chat ${chatId}:`, error)
            } finally {
                this.isLoadingMessages = false
            }
        },

        setActiveChat(id) {
            this.openMenuId = null
            this.sidebarOpen = false
            this.activeChatId = id

            // Only load history once; refetching would replace a message that is still streaming in
            const chat = this.chats.find(c => c.id === id)
            if (chat && !id.startsWith('temp-') && chat.messages.length === 0) {
                this.fetchMessages(id)
            }
        },

        async createNewChat() {
            try {
                // Reuse an existing empty new chat instead of stacking several of them
                const emptyChat = this.chats.find(c => c.id.startsWith('temp-') && c.messages.length === 0)
                if (emptyChat) {
                    this.setActiveChat(emptyChat.id)
                    return
                }

                const newChatId = `temp-${Date.now()}`
                const newChat = {
                    id: newChatId,
                    name: `New Chat`,
                    createdAt: new Date(),
                    messages: [],
                    isEditing: false,
                    editingName: `New Chat`
                }

                // New chats always appear on the first page
                if (this.paginationOffset !== 0) {
                    this.paginationOffset = 0
                    await this.fetchConversations()
                }

                this.chats.unshift(newChat)
                if (this.chats.length > this.paginationLimit) {
                    this.chats.pop()
                }

                this.setActiveChat(newChatId)
            } catch (error) {
                console.error('Error creating new chat:', error)
            }
        },

        async sendMessage(messageText) {
            if (!messageText.trim() || !this.activeChat || this.isSending) return

            this.newMessage = ""

            // Keep a reference to the chat the stream belongs to, even if the user switches chats meanwhile
            const chat = this.activeChat

            chat.messages.push({
                content: messageText,
                type: 'human',
                thread_id: chat.id
            })
            chat.messages.push({
                content: '',
                type: 'ai',
                thread_id: chat.id,
                isStreaming: true
            })
            // Take the reactive proxy from the array, mutating the plain object would not re-render
            const aiMessage = chat.messages[chat.messages.length - 1]

            this.isSending = true

            const controller = new AbortController()
            let timeoutId = null
            let finished = false

            const finish = (errorText = null) => {
                if (finished) return
                finished = true
                clearTimeout(timeoutId)
                controller.abort()
                if (errorText) {
                    aiMessage.content += `${aiMessage.content ? '\n\n' : ''}**Error:** ${errorText}`
                }
                aiMessage.isStreaming = false
                this.isSending = false
            }

            // Give up if the server sends nothing for this long; restarted on every received event
            const armIdleTimeout = () => {
                clearTimeout(timeoutId)
                timeoutId = setTimeout(() => finish('Response timed out. Please try again.'), STREAM_IDLE_TIMEOUT_MS)
            }

            const handleEvent = (parsedData) => {
                armIdleTimeout()

                switch (parsedData.type) {
                    case "connection_established":
                        // A new chat gets its real thread_id as soon as the server has created the conversation
                        if (chat.id.startsWith('temp-') && parsedData.thread_id) {
                            const wasActive = this.activeChatId === chat.id
                            chat.messages.forEach(msg => {
                                msg.thread_id = parsedData.thread_id
                            })
                            chat.id = parsedData.thread_id
                            if (wasActive) {
                                this.activeChatId = parsedData.thread_id
                            }
                        }
                        break

                    case "message":
                        aiMessage.content += parsedData.content
                        break

                    case "streaming_finished":
                        finish()
                        // The generated title of a new conversation, the header types it out once
                        if (parsedData.content) {
                            chat.animateTitle = true
                            chat.name = parsedData.content
                            chat.editingName = chat.name
                        }
                        break

                    case "error":
                        console.error("Server error:", parsedData.content)
                        finish(parsedData.content || 'Unknown error')
                        break

                    default:
                        console.log("Unknown message type:", parsedData.type)
                }
            }

            try {
                armIdleTimeout()
                await streamChat(
                    { query: messageText, thread_id: chat.id.startsWith('temp-') ? null : chat.id },
                    handleEvent,
                    controller.signal
                )
                if (!finished) {
                    finish('Connection closed before the answer finished. Please try again.')
                }
            } catch (error) {
                // finish() aborts the request, so an abort after it is expected
                if (finished) return
                console.error('Error streaming message:', error)
                finish(error.message || 'Connection failed. Please try again.')
            }
        },

        toggleSidebar(open = !this.sidebarOpen) {
            this.sidebarOpen = open
        },

        toggleMenu(chatId) {
            this.openMenuId = this.openMenuId === chatId ? null : chatId
        },

        editConversationTitle(chat) {
            this.openMenuId = null
            chat.isEditing = true
            chat.editingName = chat.name
        },

        async saveConversationTitle(chat) {
            if (!chat.editingName.trim()) {
                chat.editingName = 'Untitled Chat'
            }

            try {
                await axios.put(`${API_BASE_URL}/conversations/${chat.id}?title=${encodeURIComponent(chat.editingName)}`)

                chat.name = chat.editingName
                chat.isEditing = false
            } catch (error) {
                console.error('Error updating conversation title:', error)
                chat.editingName = chat.name
                chat.isEditing = false
            }
        },

        cancelEditingTitle(chat) {
            chat.editingName = chat.name
            chat.isEditing = false
        },

        async deleteConversation(chatId) {
            if (!confirm('Are you sure you want to delete this conversation?')) return

            try {
                await axios.delete(`${API_BASE_URL}/conversations/${chatId}`)

                if (this.activeChatId === chatId) {
                    this.activeChatId = null
                }

                await this.fetchConversations()

                if (this.chats.length === 0 && this.paginationOffset > 0) {
                    this.paginationOffset = Math.max(0, this.paginationOffset - this.paginationLimit)
                    await this.fetchConversations()
                }

                if (this.activeChatId === null && this.chats.length > 0) {
                    this.setActiveChat(this.chats[0].id)
                }
            } catch (error) {
                console.error('Error deleting conversation:', error)
                alert('Failed to delete conversation. Please try again.')
            }
        },

        async nextPage() {
            if (this.chats.length < this.paginationLimit) return

            this.paginationOffset += this.paginationLimit
            await this.fetchConversations()

            // Set the first chat on the new page as active if there are chats
            if (this.chats.length > 0) {
                this.setActiveChat(this.chats[0].id)
            }
        },

        async previousPage() {
            if (this.paginationOffset === 0) return

            this.paginationOffset = Math.max(0, this.paginationOffset - this.paginationLimit)
            await this.fetchConversations()

            // Set the first chat on the new page as active if there are chats
            if (this.chats.length > 0) {
                this.setActiveChat(this.chats[0].id)
            }
        },

        async updatePagination() {
            this.paginationOffset = 0
            localStorage.setItem('paginationLimit', this.paginationLimit)
            await this.fetchConversations()
        }
    },

    getters: {
        activeChat: (state) => {
            return state.chats.find(chat => chat.id === state.activeChatId) || null
        },

        hasMorePages: (state) => {
            return state.chats.length >= state.paginationLimit
        }
    }
})