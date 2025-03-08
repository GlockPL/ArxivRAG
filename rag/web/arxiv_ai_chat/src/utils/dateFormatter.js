export function formatDate(date) {
    if (!date) return ''
  
    // Make sure we have a valid date object
    let messageDate
    try {
      messageDate = date instanceof Date ? date : new Date(date)
      // Check if the date is valid
      if (isNaN(messageDate.getTime())) {
        return 'Invalid date'
      }
    } catch (e) {
      return 'Invalid date'
    }
  
    const now = new Date()
  
    // If today, show time
    if (messageDate.toDateString() === now.toDateString()) {
      return messageDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
  
    // If this year, show month and day
    if (messageDate.getFullYear() === now.getFullYear()) {
      return messageDate.toLocaleDateString([], { month: 'short', day: 'numeric' })
    }
  
    // Otherwise show full date
    return messageDate.toLocaleDateString([], { year: 'numeric', month: 'short', day: 'numeric' })
  }
  
  export function getLastMessagePreview(chat) {
    if (!chat.messages || chat.messages.length === 0) return "No messages"
    
    const lastMessage = chat.messages[chat.messages.length - 1]
    // Strip markdown and limit to 30 chars
    const plainText = lastMessage.content.replace(/[#*_`~$]/g, '')
    return plainText.length > 30 ? plainText.substring(0, 30) + '...' : plainText
  }