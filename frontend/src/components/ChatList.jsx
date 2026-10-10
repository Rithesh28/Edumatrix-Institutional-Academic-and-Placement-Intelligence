import React, { useState, useEffect } from 'react'
import { chatAPI } from '../services/api'
import { useAuthStore } from '../store/authStore'

const AI_USER_ID = 0
const AI_ASSISTANT_NAME = 'EduMatrix AI Assistant'

// Sparkle icon for the AI avatar
const SparkleIcon = () => (
  <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z" />
  </svg>
)

const ChatList = ({ onSelectUser, selectedUserId }) => {
  const { user } = useAuthStore()
  const isStudent = user?.role?.toLowerCase() === 'student'
  const [conversations, setConversations] = useState([])
  const [allUsers, setAllUsers] = useState([])
  const [loading, setLoading] = useState(true)

  const fetchConversations = async () => {
    try {
      const response = await chatAPI.getConversations()
      setConversations(response.data)
    } catch (error) {
      console.error('Failed to fetch conversations:', error)
    }
  }

  const fetchAllUsers = async () => {
    try {
      const response = await chatAPI.getAllUsers()
      setAllUsers(response.data)
    } catch (error) {
      console.error('Failed to fetch users:', error)
    }
  }

  const fetchData = async () => {
    setLoading(true)
    await Promise.all([fetchConversations(), fetchAllUsers()])
    setLoading(false)
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchConversations, 5000)
    return () => clearInterval(interval)
  }, [])

  // Build a pinned AI entry at the top, then human contacts
  const getContactList = () => {
    // Look for an existing AI conversation (has last_message from backend)
    const aiConversation = conversations.find(c => c.user_id === AI_USER_ID || c.is_ai)

    const aiEntry = {
      user_id: AI_USER_ID,
      user_name: AI_ASSISTANT_NAME,
      user_role: 'assistant',
      last_message: aiConversation?.last_message || 'Ask me anything about EduMatrix',
      last_message_time: aiConversation?.last_message_time || null,
      unread_count: 0,
      is_ai: true,
    }

    // Human contacts: existing conversations first, then new users
    const humanConversations = conversations.filter(c => !c.is_ai && c.user_id !== AI_USER_ID)
    const existingUserIds = new Set(humanConversations.map(c => c.user_id))

    const newUsers = allUsers
      .filter(u => u.id !== AI_USER_ID && !existingUserIds.has(u.id))
      .map(u => ({
        user_id: u.id,
        user_name: u.name,
        user_role: u.role,
        last_message: null,
        last_message_time: null,
        unread_count: 0,
        is_ai: false,
      }))

    const activeConversations = humanConversations.filter(c => c.last_message)
    const emptyConversations = humanConversations.filter(c => !c.last_message)

    if (isStudent) {
      return [aiEntry, ...activeConversations, ...emptyConversations, ...newUsers]
    }
    return [...activeConversations, ...emptyConversations, ...newUsers]
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500 dark:text-gray-400 text-sm">Loading conversations…</div>
      </div>
    )
  }

  const contacts = getContactList()

  return (
    <div className="divide-y divide-gray-100 dark:divide-gray-800">
      {contacts.map((contact) => {
        const isAI = contact.is_ai || contact.user_id === AI_USER_ID || Number(contact.user_id) === AI_USER_ID
        const isSelected = selectedUserId !== null && selectedUserId !== undefined && (selectedUserId === contact.user_id || Number(selectedUserId) === Number(contact.user_id))

        return (
          <div
            key={contact.user_id}
            onClick={() => onSelectUser(contact.user_id, contact.user_name, contact.user_role, isAI)}
            className={`p-4 cursor-pointer transition-all duration-150
              ${isSelected
                ? isAI
                  ? 'bg-indigo-50 dark:bg-indigo-900/30 border-l-4 border-indigo-500'
                  : 'bg-blue-50 dark:bg-blue-900/30 border-l-4 border-blue-500'
                : 'hover:bg-gray-50 dark:hover:bg-gray-800/60'
              }
            `}
          >
            <div className="flex justify-between items-start gap-2">
              <div className="flex items-center gap-3 flex-1 min-w-0">
                {/* Avatar */}
                {isAI ? (
                  <div className="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center bg-gradient-to-br from-indigo-500 to-purple-600 shadow-sm">
                    <SparkleIcon />
                  </div>
                ) : (
                  <div className="w-10 h-10 rounded-full flex-shrink-0 flex items-center justify-center bg-blue-100 dark:bg-blue-900/40">
                    <span className="text-blue-600 dark:text-blue-400 font-medium text-sm">
                      {contact.user_name?.charAt(0).toUpperCase()}
                    </span>
                  </div>
                )}

                {/* Name + last message */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`font-medium text-sm truncate ${isAI ? 'text-indigo-700 dark:text-indigo-300' : 'text-gray-900 dark:text-gray-100'}`}>
                      {contact.user_name}
                    </span>
                    <span className={`text-xs capitalize px-1.5 py-0.5 rounded flex-shrink-0 ${
                      isAI
                        ? 'bg-indigo-100 dark:bg-indigo-800/50 text-indigo-600 dark:text-indigo-300'
                        : 'bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
                    }`}>
                      {contact.user_role}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">
                    {contact.last_message || 'Click to start chatting'}
                  </p>
                </div>
              </div>

              {/* Unread badge */}
              {contact.unread_count > 0 && (
                <span className="inline-flex items-center justify-center w-5 h-5 text-xs font-bold text-white bg-blue-600 rounded-full flex-shrink-0">
                  {contact.unread_count}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default ChatList