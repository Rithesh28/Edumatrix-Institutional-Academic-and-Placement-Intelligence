import React, { useState } from 'react'
import ChatList from '../../components/ChatList'
import ChatWindow from '../../components/ChatWindow'

const LecturerChat = () => {
  const [selectedUser, setSelectedUser] = useState(null)

  const handleSelectUser = (userId, userName, userRole) => {
    setSelectedUser({ userId, userName, userRole })
  }

  return (
    <div className="h-[calc(100vh-120px)]">
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Messages</h1>
      <div className="flex h-full bg-white rounded-lg shadow-sm overflow-hidden border border-gray-200">
        <div className="w-80 border-r border-gray-200 overflow-y-auto">
          <ChatList onSelectUser={handleSelectUser} selectedUserId={selectedUser?.userId} />
        </div>
        <div className="flex-1 flex flex-col">
          {selectedUser ? (
            <ChatWindow
              userId={selectedUser.userId}
              userName={selectedUser.userName}
              userRole={selectedUser.userRole}
            />
          ) : (
            <div className="flex justify-center items-center h-full">
              <div className="text-gray-500 text-center">
                <p className="text-lg">Select a conversation to start chatting</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default LecturerChat