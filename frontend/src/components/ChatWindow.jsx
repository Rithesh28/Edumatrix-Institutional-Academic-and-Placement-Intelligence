import React, { useState, useEffect, useRef } from 'react'
import { chatAPI } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'

const ChatWindow = ({ userId, userName, userRole }) => {
  const [messages, setMessages] = useState([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const messagesEndRef = useRef(null)
  const { isConnected, sendMessage, messages: wsMessages } = useWebSocket()

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const fetchMessages = async () => {
    if (!userId) return
    try {
      const response = await chatAPI.getMessages(userId)
      setMessages(response.data)
    } catch (error) {
      console.error('Failed to fetch messages:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (userId) {
      fetchMessages()
    }
  }, [userId])

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Poll for new messages every 3 seconds
  useEffect(() => {
    if (!userId) return
    const interval = setInterval(fetchMessages, 3000)
    return () => clearInterval(interval)
  }, [userId])

  // Handle WebSocket messages
  useEffect(() => {
    if (wsMessages.length > 0) {
      const lastMessage = wsMessages[wsMessages.length - 1]
      if (lastMessage && (lastMessage.sender_id === userId || lastMessage.receiver_id === userId)) {
        setMessages(prev => {
          const exists = prev.some(m => m.id === lastMessage.id)
          if (exists) return prev
          return [...prev, lastMessage]
        })
      }
    }
  }, [wsMessages, userId])

  const handleSendMessage = async () => {
    if (!newMessage.trim()) return

    setSending(true)
    const messageContent = newMessage.trim()
    setNewMessage('')

    // Try WebSocket first
    const sent = sendMessage(userId, messageContent)
    
    if (!sent) {
      // Fallback to REST API
      try {
        await chatAPI.sendMessage(userId, messageContent)
        setTimeout(() => fetchMessages(), 500)
      } catch (error) {
        console.error('Failed to send message:', error)
        setNewMessage(messageContent)
        alert('Failed to send message. Please try again.')
      }
    }
    
    setSending(false)
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  if (!userId) {
    return (
      <div className="flex justify-center items-center h-full">
        <div className="text-gray-500 text-center">
          <svg className="w-16 h-16 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <p className="text-lg font-medium">Select a conversation</p>
          <p className="text-sm mt-1">Choose a user from the sidebar to start chatting</p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-full">
        <div className="text-gray-500">Loading messages...</div>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* Chat Header */}
      <div className="p-4 border-b border-gray-200 bg-white">
        <div className="flex items-center space-x-2">
          <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
            <span className="text-blue-600 font-semibold text-lg">
              {userName?.charAt(0).toUpperCase()}
            </span>
          </div>
          <div className="flex-1">
            <div className="flex items-center space-x-2">
              <span className="font-semibold text-gray-900">{userName}</span>
              <span className="text-xs text-gray-500 capitalize bg-gray-100 px-2 py-0.5 rounded">
                {userRole}
              </span>
            </div>
            <div className="flex items-center mt-0.5">
              {isConnected ? (
                <>
                  <span className="w-2 h-2 bg-green-500 rounded-full mr-1"></span>
                  <span className="text-xs text-green-600">Online</span>
                </>
              ) : (
                <>
                  <span className="w-2 h-2 bg-gray-400 rounded-full mr-1"></span>
                  <span className="text-xs text-gray-500">Offline</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Messages Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
        {messages.length === 0 ? (
          <div className="flex justify-center items-center h-32">
            <p className="text-gray-400 text-center">
              No messages yet.<br />
              Send a message to start the conversation!
            </p>
          </div>
        ) : (
          messages.map((msg) => {
            const isSentByMe = msg.sender_id !== userId
            return (
              <div
                key={msg.id}
                className={`flex ${isSentByMe ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                    isSentByMe
                      ? 'bg-blue-600 text-white'
                      : 'bg-white text-gray-900 border border-gray-200'
                  }`}
                >
                  <p className="text-sm break-words">{msg.content}</p>
                  <p className={`text-xs mt-1 ${isSentByMe ? 'text-blue-200' : 'text-gray-400'}`}>
                    {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    {msg.is_read && isSentByMe && (
                      <span className="ml-2">✓ Read</span>
                    )}
                  </p>
                </div>
              </div>
            )
          })
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Message Input */}
      <div className="p-4 border-t border-gray-200 bg-white">
        <div className="flex space-x-2">
          <textarea
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Type your message..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            rows="2"
            disabled={sending}
          />
          <button
            onClick={handleSendMessage}
            disabled={sending || !newMessage.trim()}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2"
          >
            {sending ? (
              <>
                <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span>Sending</span>
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
                <span>Send</span>
              </>
            )}
          </button>
        </div>
        {!isConnected && (
          <p className="text-xs text-gray-400 mt-2 text-center">
            ⚡ Connecting to real-time... Messages will still be sent via REST API.
          </p>
        )}
      </div>
    </div>
  )
}

export default ChatWindow