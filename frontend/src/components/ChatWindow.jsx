import React, { useState, useEffect, useRef, useCallback } from 'react'
import { chatAPI } from '../services/api'
import { useWebSocket } from '../hooks/useWebSocket'

const AI_USER_ID = 0

// ─── Icons ──────────────────────────────────────────────────────────────────

const SendIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
  </svg>
)

const SpinnerIcon = () => (
  <svg className="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
  </svg>
)

const SparkleIcon = () => (
  <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
  </svg>
)

// ─── AI "Thinking" bubble ────────────────────────────────────────────────────

const ThinkingBubble = () => (
  <div className="flex justify-start">
    <div className="flex items-end gap-2">
      <div className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center bg-gradient-to-br from-indigo-500 to-purple-600">
        <SparkleIcon />
      </div>
      <div className="max-w-xs px-4 py-3 rounded-2xl rounded-bl-none bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 shadow-sm">
        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400 text-sm">
          <SpinnerIcon />
          <span>Thinking…</span>
        </div>
      </div>
    </div>
  </div>
)

// ─── AI Source attribution chip ──────────────────────────────────────────────

const SourceChip = ({ label }) => (
  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs bg-indigo-50 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-700">
    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
    {label}
  </span>
)

// ─── AI intent/sentiment badge ───────────────────────────────────────────────

const MetaBadge = ({ label, value }) => (
  <span className="text-xs text-gray-400 dark:text-gray-500">
    <span className="font-medium text-gray-500 dark:text-gray-400">{label}:</span> {value}
  </span>
)

// ─── Message content renderer (clean markdown bold rendering) ──────────────

const renderMessageContent = (content) => {
  if (!content) return ''
  const parts = content.split(/(\*\*.*?\*\*)/g)
  return parts.map((part, idx) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      return (
        <strong key={idx} className="font-semibold text-inherit">
          {part.slice(2, -2)}
        </strong>
      )
    }
    return part
  })
}

// ─── Individual message bubble ───────────────────────────────────────────────

const MessageBubble = ({ msg, isSentByMe, isAIConversation }) => {
  const isAIReply = isAIConversation && !isSentByMe
  const metadata = msg.ai_metadata || null
  const sources = msg.retrieval_sources || metadata?.retrieval_sources || []

  return (
    <div className={`flex ${isSentByMe ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex items-end gap-2 ${isSentByMe ? 'flex-row-reverse' : ''}`}>
        {/* AI avatar for AI replies */}
        {isAIReply && (
          <div className="w-7 h-7 rounded-full flex-shrink-0 flex items-center justify-center bg-gradient-to-br from-indigo-500 to-purple-600 self-end">
            <SparkleIcon />
          </div>
        )}

        <div className="max-w-sm lg:max-w-lg">
          {/* Main bubble */}
          <div
            className={`px-4 py-2.5 rounded-2xl text-sm break-words shadow-sm
              ${isSentByMe
                ? 'bg-blue-600 text-white rounded-br-none'
                : isAIReply
                  ? 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700 rounded-bl-none'
                  : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 border border-gray-200 dark:border-gray-700 rounded-bl-none'
              }
            `}
          >
            <p className="whitespace-pre-wrap leading-relaxed">{renderMessageContent(msg.content)}</p>
          </div>

          {/* AI metadata footer: Relevant verified source(s) only (Intent/Mood kept in backend metadata) */}
          {isAIReply && sources.length > 0 && (
            <div className="mt-1.5 px-1 space-y-1">
              <div className="flex flex-wrap gap-1">
                {sources.slice(0, 4).map((src, i) => (
                  <SourceChip key={i} label={src.title || src.type || `Source ${i + 1}`} />
                ))}
              </div>
            </div>
          )}

          {/* Timestamp */}
          <p className={`text-xs mt-1 px-1 ${isSentByMe ? 'text-right text-blue-200' : 'text-gray-400 dark:text-gray-500'}`}>
            {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            {msg.is_read && isSentByMe && !isAIConversation && (
              <span className="ml-1">✓ Read</span>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}

// ─── AI Welcome state ────────────────────────────────────────────────────────

const AIWelcome = () => (
  <div className="flex flex-col items-center justify-center h-full gap-4 px-6 text-center">
    <div className="w-16 h-16 rounded-full flex items-center justify-center bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg">
      <svg className="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 24 24">
        <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
      </svg>
    </div>
    <div>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-gray-100 mb-1">EduMatrix AI Assistant</h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 max-w-xs leading-relaxed">
        Ask me about assignments, deadlines, circulars, results, placement drives, or any institutional information.
      </p>
    </div>
    <div className="mt-2 text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1">
      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      Answers are grounded in institutional data only
    </div>
  </div>
)

// ─── Main ChatWindow ──────────────────────────────────────────────────────────

const ChatWindow = ({ userId, userName, userRole, isAI = false }) => {
  const [messages, setMessages] = useState([])
  const [newMessage, setNewMessage] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [aiThinking, setAiThinking] = useState(false)
  const [error, setError] = useState(null)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)
  const { isConnected, sendMessage, messages: wsMessages, error: wsError } = useWebSocket()

  const isAIConversation = isAI || userId === AI_USER_ID || Number(userId) === AI_USER_ID || userRole === 'assistant'

  useEffect(() => {
    if (wsError) {
      setError(wsError)
    }
  }, [wsError])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const fetchMessages = useCallback(async () => {
    if (userId === null || userId === undefined || userId === '') return
    try {
      const response = await chatAPI.getMessages(userId)
      setMessages(response.data)
    } catch (err) {
      console.error('Failed to fetch messages:', err)
    } finally {
      setLoading(false)
    }
  }, [userId])

  useEffect(() => {
    if (userId !== null && userId !== undefined && userId !== '') {
      setLoading(true)
      setMessages([])
      setError(null)
      fetchMessages()
    }
  }, [userId, fetchMessages])

  useEffect(() => {
    scrollToBottom()
  }, [messages, aiThinking])

  // Poll for new messages — human conversations only (AI uses REST directly)
  useEffect(() => {
    if (isAIConversation || userId === null || userId === undefined || userId === '') return
    const interval = setInterval(fetchMessages, 3000)
    return () => clearInterval(interval)
  }, [userId, isAIConversation, fetchMessages])

  // Handle WebSocket messages (human-to-human only)
  useEffect(() => {
    if (isAIConversation || wsMessages.length === 0) return
    const lastMessage = wsMessages[wsMessages.length - 1]
    if (lastMessage && (lastMessage.sender_id === userId || lastMessage.receiver_id === userId)) {
      setMessages(prev => {
        const exists = prev.some(m => m.id === lastMessage.id)
        if (exists) return prev
        return [...prev, lastMessage]
      })
    }
  }, [wsMessages, userId, isAIConversation])

  // ─── Send handlers ──────────────────────────────────────────────────────

  const handleSendAI = async (content) => {
    // Optimistically append user message
    const optimisticUserMsg = {
      id: `opt-${Date.now()}`,
      sender_id: -1, // current user placeholder (not AI_USER_ID)
      receiver_id: AI_USER_ID,
      content,
      is_ai: true,
      created_at: new Date().toISOString(),
    }
    setMessages(prev => [...prev, optimisticUserMsg])
    setAiThinking(true)
    setError(null)

    try {
      const response = await chatAPI.chatAI(content)
      const { user_message, ai_response, intent, sentiment, retrieval_sources } = response.data

      // Replace optimistic message + append real AI reply (with metadata)
      setMessages(prev => {
        const withoutOptimistic = prev.filter(m => m.id !== optimisticUserMsg.id)
        const enrichedAI = {
          ...ai_response,
          intent,
          sentiment,
          retrieval_sources,
        }
        return [...withoutOptimistic, user_message, enrichedAI]
      })
    } catch (err) {
      console.error('AI chat error:', err)
      setMessages(prev => prev.filter(m => m.id !== optimisticUserMsg.id))
      setError(err.response?.data?.detail || 'The AI assistant is temporarily unavailable. Please try again.')
    } finally {
      setAiThinking(false)
    }
  }

  const handleSendHuman = async (content) => {
    setSending(true)
    setError(null)
    const sent = sendMessage(userId, content)
    if (!sent) {
      try {
        await chatAPI.sendMessage(userId, content)
        setTimeout(() => fetchMessages(), 500)
      } catch (err) {
        console.error('Failed to send message:', err)
        setNewMessage(content)
        setError(err.response?.data?.detail || 'Failed to send message. Please try again.')
      }
    }
    setSending(false)
  }

  const handleSendMessage = async () => {
    const content = newMessage.trim()
    if (!content) return
    setNewMessage('')
    setError(null)

    if (isAIConversation) {
      await handleSendAI(content)
    } else {
      await handleSendHuman(content)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  // ─── Determine if a message was sent by the current user ───────────────
  // AI conversation:  student msg → sender_id=user.id, receiver_id=null
  //                   AI reply    → sender_id=null,    receiver_id=user.id
  // Human conversation: sender_id !== userId means the other person sent it
  const isSentByCurrentUser = (msg) => {
    if (isAIConversation) {
      return msg.sender_id !== null && msg.sender_id !== undefined
    }
    return msg.sender_id !== userId
  }

  // ─── Empty / loading states ──────────────────────────────────────────────

  const isNoConversationSelected = !isAIConversation && (userId === null || userId === undefined || userId === '')

  if (isNoConversationSelected) {
    return (
      <div className="flex justify-center items-center h-full">
        <div className="text-gray-500 dark:text-gray-400 text-center">
          <svg className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
          </svg>
          <p className="text-lg font-medium">Select a conversation</p>
          <p className="text-sm mt-1">Choose a contact from the sidebar</p>
        </div>
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-full">
        <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
          <SpinnerIcon />
          <span>Loading messages…</span>
        </div>
      </div>
    )
  }

  const isBusy = sending || aiThinking

  return (
    <div className="flex flex-col h-full">
      {/* ── Chat Header ── */}
      <div className={`p-4 border-b flex-shrink-0 ${
        isAIConversation
          ? 'bg-gradient-to-r from-indigo-600 to-purple-600 border-indigo-700'
          : 'bg-white dark:bg-gray-900 border-gray-200 dark:border-gray-800'
      }`}>
        <div className="flex items-center gap-3">
          {isAIConversation ? (
            <div className="w-10 h-10 rounded-full flex items-center justify-center bg-white/20">
              <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24">
                <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
              </svg>
            </div>
          ) : (
            <div className="w-10 h-10 rounded-full flex items-center justify-center bg-blue-100 dark:bg-blue-900/40">
              <span className="text-blue-600 dark:text-blue-400 font-semibold text-lg">
                {userName?.charAt(0).toUpperCase()}
              </span>
            </div>
          )}

          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className={`font-semibold ${isAIConversation ? 'text-white' : 'text-gray-900 dark:text-gray-100'}`}>
                {userName}
              </span>
              <span className={`text-xs capitalize px-2 py-0.5 rounded ${
                isAIConversation
                  ? 'bg-white/20 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400'
              }`}>
                {userRole}
              </span>
            </div>
            <div className="flex items-center mt-0.5">
              {isAIConversation ? (
                <span className="text-xs text-indigo-200">Institutional knowledge assistant</span>
              ) : isConnected ? (
                <>
                  <span className="w-2 h-2 bg-green-500 rounded-full mr-1" />
                  <span className="text-xs text-green-600 dark:text-green-400">Online</span>
                </>
              ) : (
                <>
                  <span className="w-2 h-2 bg-gray-400 rounded-full mr-1" />
                  <span className="text-xs text-gray-500 dark:text-gray-400">Offline</span>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Messages Area ── */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50 dark:bg-gray-950">
        {messages.length === 0 && !aiThinking ? (
          isAIConversation ? (
            <AIWelcome />
          ) : (
            <div className="flex justify-center items-center h-32">
              <p className="text-gray-400 dark:text-gray-500 text-center text-sm">
                No messages yet.<br />Send a message to start the conversation!
              </p>
            </div>
          )
        ) : (
          messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              msg={msg}
              isSentByMe={isSentByCurrentUser(msg)}
              isAIConversation={isAIConversation}
            />
          ))
        )}

        {/* AI "Thinking" indicator */}
        {aiThinking && <ThinkingBubble />}

        {/* Error toast */}
        {error && (
          <div className="flex justify-center">
            <div className="px-4 py-2 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-700 text-red-600 dark:text-red-400 text-sm rounded-lg">
              {error}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── Message Input ── */}
      <div className="p-4 border-t border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 flex-shrink-0">
        <div className="flex gap-2">
          <textarea
            ref={textareaRef}
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder={isAIConversation ? 'Ask EduMatrix AI…' : 'Type your message…'}
            className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-700 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 dark:focus:ring-indigo-500 focus:border-transparent resize-none text-sm bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 placeholder-gray-400 dark:placeholder-gray-500 transition-colors"
            rows="2"
            disabled={isBusy}
          />
          <button
            onClick={handleSendMessage}
            disabled={isBusy || !newMessage.trim()}
            className={`px-5 py-2 rounded-xl font-medium text-white transition-all flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed ${
              isAIConversation
                ? 'bg-gradient-to-br from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700'
                : 'bg-blue-600 hover:bg-blue-700'
            }`}
          >
            {isBusy ? <SpinnerIcon /> : <SendIcon />}
            <span className="hidden sm:inline">{aiThinking ? 'Thinking' : 'Send'}</span>
          </button>
        </div>

        {!isConnected && !isAIConversation && (
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-2 text-center">
            ⚡ Connecting to real-time… Messages will still be sent via REST API.
          </p>
        )}
      </div>
    </div>
  )
}

export default ChatWindow