import React, { useState } from 'react'
import ChatList from '../../components/ChatList'
import ChatWindow from '../../components/ChatWindow'

const HODChat = () => {
  const [selectedUser, setSelectedUser] = useState(null)

  const handleSelectUser = (userId, userName, userRole, isAI = false) => {
    setSelectedUser({ userId, userName, userRole, isAI: false })
  }

  return (
    <div className="h-[calc(100vh-120px)]">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-4">Department Messages</h1>
      <div className="flex h-full bg-white dark:bg-gray-900 rounded-xl shadow-sm overflow-hidden border border-gray-200 dark:border-gray-800">
        <div className="w-80 border-r border-gray-200 dark:border-gray-800 overflow-y-auto bg-gray-50/50 dark:bg-gray-900/50">
          <ChatList onSelectUser={handleSelectUser} selectedUserId={selectedUser?.userId} />
        </div>
        <div className="flex-1 flex flex-col bg-white dark:bg-gray-900 min-w-0">
          {selectedUser !== null ? (
            <ChatWindow
              userId={selectedUser.userId}
              userName={selectedUser.userName}
              userRole={selectedUser.userRole}
              isAI={false}
            />
          ) : (
            <div className="flex justify-center items-center h-full">
              <div className="text-gray-500 dark:text-gray-400 text-center">
                <p className="text-lg font-medium">Select a department conversation to start chatting</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default HODChat
