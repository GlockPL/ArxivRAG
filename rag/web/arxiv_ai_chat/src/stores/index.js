import { defineStore } from 'pinia'
import { EventSource } from 'eventsource'
import axios from 'axios'
import { renderMarkdown } from '@/utils/markdownProcessor'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

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

// Create a flag to prevent multiple refresh attempts at once
let isRefreshing = false
// Store for the requests that failed due to token expiration
let failedQueue = []

// Process the failed queue
const processQueue = (error, token = null) => {
    failedQueue.forEach(prom => {
        if (error) {
            prom.reject(error)
        } else {
            prom.resolve(token)
        }
    })
    failedQueue = []
}

// Enhanced response interceptor for token refresh
axios.interceptors.response.use(response => {
    return response
}, async error => {
    const originalRequest = error.config

    // If the error is 401 and we haven't tried to refresh the token yet
    if (error.response && error.response.status === 401 && !originalRequest._retry) {
        if (isRefreshing) {
            // If we're already refreshing, queue this request
            return new Promise((resolve, reject) => {
                failedQueue.push({ resolve, reject })
            }).then(token => {
                originalRequest.headers['Authorization'] = `Bearer ${token}`
                return axios(originalRequest)
            }).catch(err => {
                return Promise.reject(err)
            })
        }

        // Mark that we're trying to refresh
        originalRequest._retry = true
        isRefreshing = true

        // Try to refresh the token
        const refreshToken = localStorage.getItem('chatRefreshToken')

        if (!refreshToken) {
            // No refresh token available, logout
            const authStore = useAuthStore()
            authStore.logout()
            processQueue(new Error('No refresh token available'))
            isRefreshing = false
            return Promise.reject(error)
        }

        try {
            // Call the refresh token endpoint
            const response = await axios.post(`${API_BASE_URL}/refresh`, { refresh_token: refreshToken })

            // Update tokens in localStorage
            const { access_token, refresh_token } = response.data
            localStorage.setItem('chatToken', access_token)
            localStorage.setItem('chatRefreshToken', refresh_token)

            // Update auth headers for the original request
            originalRequest.headers['Authorization'] = `Bearer ${access_token}`

            // Process any queued requests
            processQueue(null, access_token)

            // Reset refreshing flag
            isRefreshing = false

            // Retry the original request
            return axios(originalRequest)
        } catch (refreshError) {
            // Refresh token failed, logout
            const authStore = useAuthStore()
            authStore.logout()

            // Process queued requests with the error
            processQueue(refreshError)

            // Reset refreshing flag
            isRefreshing = false

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
            if (!this.refreshToken) {
                throw new Error('No refresh token available')
            }

            try {
                const response = await axios.post(`${API_BASE_URL}/refresh`, {
                    refresh_token: this.refreshToken
                })

                this.authToken = response.data.access_token
                this.refreshToken = response.data.refresh_token

                localStorage.setItem('chatToken', this.authToken)
                localStorage.setItem('chatRefreshToken', this.refreshToken)

                return true
            } catch (error) {
                console.error('Token refresh error:', error)
                this.logout()
                return false
            }
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
        newMessage: ''
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
            this.activeChatId = id

            if (id && !id.startsWith('temp-')) {
                this.fetchMessages(id)
            }
        },

        async createNewChat() {
            try {
                const newChatId = 'temp-id'
                const newChat = {
                    id: newChatId,
                    name: `New Chat`,
                    createdAt: new Date(),
                    messages: [],
                    isEditing: false,
                    editingName: `New Chat`
                }

                if (this.paginationOffset === 0) {
                    this.chats.unshift(newChat)
                    if (this.chats.length > this.paginationLimit) {
                        this.chats.pop()
                    }
                } else {
                    this.paginationOffset = 0
                    await this.fetchConversations()
                }

                this.setActiveChat(newChatId)
            } catch (error) {
                console.error('Error creating new chat:', error)
            }
        },

        async sendMessage(messageText) {
            if (!messageText.trim() || !this.activeChat) return

            this.newMessage = ""

            const userMessage = {
                content: messageText,
                type: 'human',
                thread_id: this.activeChat.id
            }

            this.activeChat.messages.push(userMessage)

            // Create a new reactive message object
            const aiMessage = {
                content: "<div class='thinking'><div class='dot-spinner'></div><span>Thinking...</span></div>",
                type: 'ai',
                thread_id: this.activeChat.id,
                isStreaming: true,
                rawContent: ""
            }

            this.activeChat.messages.push(aiMessage)


            this.isSending = true

            try {
                const encodedQuery = encodeURIComponent(messageText)
                const streamUrl = `${API_BASE_URL}/conversations/stream?query=${encodedQuery}&thread_id=${this.activeChat.id}`

                // Create EventSource with custom headers using the fetch option
                const es = new EventSource(streamUrl, {
                    fetch: (input, init) =>
                        fetch(input, {
                            ...init,
                            headers: {
                                ...init.headers,
                                'Authorization': `Bearer ${useAuthStore().authToken}`,
                                'Accept': 'text/event-stream',
                                'Cache-Control': 'no-cache'
                            }
                        })
                })

                let isFirstChunk = true
                let currentActiveChatId = this.activeChat.id

                // Store a reference to the message index for faster lookups
                const messageIndex = this.activeChat.messages.length - 1

                // Monitor for chat ID changes
                const checkForChatChange = () => {
                    if (this.activeChatId !== currentActiveChatId) {
                        console.log('Chat changed - cleaning up stream')
                        cleanup()
                        return true
                    }
                    return false
                }

                // Process content to ensure it's a string and handle potential JSON objects
                const processContent = (content) => {
                    if (typeof content === 'object') {
                        try {
                            return JSON.stringify(content); // Convert object to string
                        } catch (e) {
                            return String(content); // Fallback to string conversion
                        }
                    }
                    return content; // Already a string
                };

                // Process markdown on each update if needed
                const processMarkdown = (text) => {
                    // If your app has a markdown processor, call it here
                    // For example: return markdownProcessor.render(text);
                    return renderMarkdown(text);
                };

                // Handle incoming messages
                es.addEventListener('message', (event) => {
                    // Check if chat has changed
                    if (checkForChatChange()) return;
                
                    const data = event.data;
                    let parsedData;
                
                    try {
                        parsedData = JSON.parse(data);
                    } catch (e) {
                        console.error("Error parsing JSON:", e);
                        return;
                    }
                    const messageIndex = this.activeChat.messages.length - 1;
                    
                    // Handle different message types
                    switch (parsedData.type) {
                        case "connection_established":
                            console.log("Connection established");
                            break;
                            
                        case "message":
                            // Update the AI message with new content
                            if (messageIndex >= 0 && messageIndex < this.activeChat.messages.length) {
                                const currentMsg = this.activeChat.messages[messageIndex];
                                
                                if (isFirstChunk) {
                                    // For first chunk, replace the entire content
                                    currentMsg.rawContent = parsedData.content;
                                    currentMsg.content = renderMarkdown(parsedData.content);
                                    isFirstChunk = false;
                                } else {
                                    // For subsequent chunks, append
                                    currentMsg.rawContent += parsedData.content;
                                    currentMsg.content = renderMarkdown(currentMsg.rawContent);
                                }
                            }
                            break;
                            
                        case "streaming_finished":
                            console.log("Streaming finished");                            
                            if (messageIndex >= 0 && messageIndex < this.activeChat.messages.length) {
                                this.activeChat.messages[messageIndex].isStreaming = false;
                            }
                            es.close();
                            this.isSending = false;

                            // Update thread_id if different from current
                            if (parsedData.thread_id && parsedData.thread_id !== this.activeChat.id) {
                                console.log(`Server assigned new thread_id: ${parsedData.thread_id}`);
                                
                                // Update thread_id in messages and chat
                                this.activeChat.messages.forEach(msg => {
                                    msg.thread_id = parsedData.thread_id;
                                });
                                
                                if (this.activeChat.id.startsWith('temp-')) {
                                    this.activeChat.id = parsedData.thread_id;                                    
                                    this.activeChatId = parsedData.thread_id;
                                    this.activeChat.name = parsedData.content;
                                }
                            }

                            break;
                            
                        case "error":
                            console.error("Server error:", parsedData.error);
                            // Update message with error
                            if (messageIndex >= 0 && messageIndex < this.activeChat.messages.length) {
                                const currentMsg = this.activeChat.messages[messageIndex];
                                currentMsg.content = `Error: ${parsedData.error || 'Unknown error'}. Please try again.`;
                                currentMsg.isStreaming = false;
                            }
                            es.close();
                            this.isSending = false;
                            break;
                            
                        default:
                            console.log("Unknown message type:", parsedData.type);
                    }
                });

                // Handle errors
                es.addEventListener('error', (error) => {
                    console.error('EventSource error:', error)

                    // Check for HTTP error codes (if available)
                    if (error.code) {
                        console.error(`HTTP error code: ${error.code}`)
                    }

                    // Update the message with error content
                    if (messageIndex >= 0 && messageIndex < this.activeChat.messages.length) {
                        const currentMsg = this.activeChat.messages[messageIndex]

                        if (currentMsg.isStreaming) {
                            currentMsg.content = `Error: Connection failed. Please try again.`
                        } else {
                            currentMsg.content += `\n\nError: Connection lost. Please try again.`
                        }

                        currentMsg.isStreaming = false
                    }

                    es.close()
                    this.isSending = false
                })

                // Set up a safety timeout in case the [DONE] event never arrives
                const timeoutId = setTimeout(() => {
                    if (messageIndex >= 0 &&
                        messageIndex < this.activeChat.messages.length &&
                        this.activeChat.messages[messageIndex].isStreaming) {

                        console.log('Stream timeout - closing connection')
                        this.activeChat.messages[messageIndex].isStreaming = false
                        es.close()
                        this.isSending = false
                    }
                }, 30000) // 30-second timeout

                // Clean up when component unmounts or stream completes
                const cleanup = () => {
                    clearTimeout(timeoutId)
                    es.close()
                    this.isSending = false
                }

            } catch (error) {
                console.error('Error setting up message stream:', error)

                // Update the message with error content
                const messageIndex = this.activeChat.messages.length - 1;
                if (messageIndex >= 0 && messageIndex < this.activeChat.messages.length) {
                    const currentMsg = this.activeChat.messages[messageIndex]

                    if (currentMsg.isStreaming) {
                        currentMsg.content = `Error: ${error.message || 'Failed to load response'}. Please try again.`
                    } else {
                        currentMsg.content += `\n\nError: ${error.message || 'Connection failed'}. Please try again.`
                    }

                    currentMsg.isStreaming = false
                }

                this.isSending = false
            }

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