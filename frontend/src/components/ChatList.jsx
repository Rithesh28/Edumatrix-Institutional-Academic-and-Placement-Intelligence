import React, { useState, useEffect } from 'react'
import { chatAPI } from '../services/api'

const ChatList = ({ onSelectUser, selectedUserId }) => {
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

  // Combine conversations + all users (show everyone)
  const getAllContacts = () => {
    const existingUserIds = new Set(conversations.map(c => c.user_id))
    const newUsers = allUsers.filter(u => !existingUserIds.has(u.id))
    
    const newContacts = newUsers.map(u => ({
      user_id: u.id,
      user_name: u.name,
      user_role: u.role,
      last_message: null,
      last_message_time: null,
      unread_count: 0
    }))
    
    // Sort: active conversations first (with last_message), then new contacts
    const activeConversations = conversations.filter(c => c.last_message)
    const emptyConversations = conversations.filter(c => !c.last_message)
    
    return [...activeConversations, ...emptyConversations, ...newContacts]
  }

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500">Loading conversations...</div>
      </div>
    )
  }

  const allContacts = getAllContacts()

  if (allContacts.length === 0) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500 text-center">
          <p className="text-lg">No users available</p>
          <p className="text-sm mt-2">Contact your administrator</p>
        </div>
      </div>
    )
  }

  return (
    <div className="divide-y divide-gray-200">
      {allContacts.map((contact) => (
        <div
          key={contact.user_id}
          onClick={() => onSelectUser(contact.user_id, contact.user_name, contact.user_role)}
          className={`p-4 cursor-pointer hover:bg-gray-50 transition-colors ${
            selectedUserId === contact.user_id ? 'bg-blue-50 border-l-4 border-blue-500' : ''
          }`}
        >
          <div className="flex justify-between items-start">
            <div className="flex-1">
              <div className="flex items-center space-x-2">
                <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                  <span className="text-blue-600 font-medium">
                    {contact.user_name?.charAt(0).toUpperCase()}
                  </span>
                </div>
                <div className="flex-1">
                  <div className="flex items-center space-x-2">
                    <span className="font-medium text-gray-900">{contact.user_name}</span>
                    <span className="text-xs text-gray-500 capitalize bg-gray-100 px-2 py-0.5 rounded">
                      {contact.user_role}
                    </span>
                  </div>
                  <p className="text-sm text-gray-500 mt-0.5 truncate">
                    {contact.last_message || 'Click to start chatting'}
                  </p>
                </div>
              </div>
            </div>
            {contact.unread_count > 0 && (
              <span className="inline-flex items-center justify-center px-2 py-1 text-xs font-bold text-white bg-blue-600 rounded-full">
                {contact.unread_count}
              </span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export default ChatList