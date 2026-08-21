import React, { useState, useEffect, useRef } from 'react'
import { reminderAPI } from '../services/api'
import { useNavigate } from 'react-router-dom'

const ReminderBell = () => {
  const [unreadCount, setUnreadCount] = useState(0)
  const [showDropdown, setShowDropdown] = useState(false)
  const [reminders, setReminders] = useState([])
  const dropdownRef = useRef(null)
  const navigate = useNavigate()

  const fetchUnreadCount = async () => {
    try {
      const response = await reminderAPI.getUnreadCount()
      setUnreadCount(response.data.count)
    } catch (error) {
      console.error('Failed to fetch unread count:', error)
    }
  }

  const fetchReminders = async () => {
    try {
      const response = await reminderAPI.getAll()
      setReminders(response.data.slice(0, 5)) // Only show latest 5
    } catch (error) {
      console.error('Failed to fetch reminders:', error)
    }
  }

  useEffect(() => {
    fetchUnreadCount()
    fetchReminders()

    // Poll every 30 seconds
    const interval = setInterval(fetchUnreadCount, 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleMarkAsRead = async (id) => {
    try {
      await reminderAPI.markAsRead(id)
      fetchUnreadCount()
      fetchReminders()
    } catch (error) {
      console.error('Failed to mark as read:', error)
    }
  }

  const handleMarkAllAsRead = async () => {
    try {
      await reminderAPI.markAllAsRead()
      fetchUnreadCount()
      fetchReminders()
    } catch (error) {
      console.error('Failed to mark all as read:', error)
    }
  }

  const handleViewAll = () => {
    setShowDropdown(false)
    navigate('/student/reminders')
  }

  const getReminderIcon = (type) => {
    const icons = {
      '7_day': '📅',
      '3_day': '⏰',
      '1_day': '🚨',
      'deadline_day': '⚠️',
      'missed_deadline': '❌'
    }
    return icons[type] || '🔔'
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setShowDropdown(!showDropdown)}
        className="relative p-2 text-gray-600 hover:text-gray-900 focus:outline-none"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 inline-flex items-center justify-center px-2 py-1 text-xs font-bold leading-none text-white transform translate-x-1/2 -translate-y-1/2 bg-red-600 rounded-full">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {showDropdown && (
        <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg z-50 border border-gray-200">
          <div className="p-3 border-b border-gray-200 flex justify-between items-center">
            <h3 className="font-semibold text-gray-900">Reminders</h3>
            <div className="flex gap-2">
              {unreadCount > 0 && (
                <button
                  onClick={handleMarkAllAsRead}
                  className="text-xs text-blue-600 hover:text-blue-800"
                >
                  Mark all read
                </button>
              )}
              <button
                onClick={handleViewAll}
                className="text-xs text-blue-600 hover:text-blue-800"
              >
                View all
              </button>
            </div>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {reminders.length === 0 ? (
              <p className="p-4 text-center text-gray-500">No reminders</p>
            ) : (
              reminders.map((reminder) => (
                <div
                  key={reminder.id}
                  className={`p-3 border-b border-gray-100 hover:bg-gray-50 cursor-pointer ${
                    reminder.status === 'pending' ? 'bg-blue-50' : ''
                  }`}
                  onClick={() => handleMarkAsRead(reminder.id)}
                >
                  <div className="flex items-start gap-2">
                    <span>{getReminderIcon(reminder.reminder_type)}</span>
                    <div className="flex-1">
                      <p className="font-medium text-gray-900 text-sm">
                        {reminder.circular_title || 'Reminder'}
                      </p>
                      <p className="text-gray-600 text-xs mt-1 line-clamp-2">
                        {reminder.circular_content?.slice(0, 80)}...
                      </p>
                      <p className="text-gray-400 text-xs mt-1">
                        {new Date(reminder.scheduled_at).toLocaleString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default ReminderBell