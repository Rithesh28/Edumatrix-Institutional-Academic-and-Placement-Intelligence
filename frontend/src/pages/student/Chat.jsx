import React, { useState } from 'react'
import ChatList from '../../components/ChatList'
import ChatWindow from '../../components/ChatWindow'

const StudentChat = () => {
  // null = nothing selected; 0 = AI Assistant; >0 = human user
  const [selectedUser, setSelectedUser] = useState(null)

  const handleSelectUser = (userId, userName, userRole, isAI = false) => {
    setSelectedUser({ userId, userName, userRole, isAI: isAI || userId === 0 || userRole === 'assistant' })
  }

  return (
    <div className="h-[calc(100vh-120px)]">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Messages</h1>
      <div className="flex h-full bg-white dark:bg-gray-900 rounded-xl shadow-sm overflow-hidden border border-gray-200 dark:border-gray-800">
        {/* Chat List Sidebar */}
        <div className="w-80 border-r border-gray-200 dark:border-gray-800 overflow-y-auto bg-gray-50/50 dark:bg-gray-900/50 flex-shrink-0">
          <ChatList onSelectUser={handleSelectUser} selectedUserId={selectedUser?.userId} />
        </div>

        {/* Chat Window — show when any user is selected, including AI (id 0) */}
        <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 min-w-0">
          {selectedUser !== null ? (
            <ChatWindow
              userId={selectedUser.userId}
              userName={selectedUser.userName}
              userRole={selectedUser.userRole}
              isAI={selectedUser.isAI}
            />
          ) : (
            <div className="flex justify-center items-center h-full">
              <div className="text-gray-500 dark:text-gray-400 text-center">
                <svg className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
                <p className="text-lg font-medium">Select a conversation to start chatting</p>
                <p className="text-sm mt-1 text-gray-400 dark:text-gray-500">
                  Or try the <span className="text-indigo-500 font-medium">EduMatrix AI Assistant</span> at the top
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StudentChat