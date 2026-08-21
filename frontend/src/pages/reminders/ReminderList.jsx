import React, { useState, useEffect } from 'react'
import { reminderAPI } from '../../services/api'
import toast from 'react-hot-toast'

const ReminderList = () => {
  const [reminders, setReminders] = useState([])
  const [loading, setLoading] = useState(true)
  const [stats, setStats] = useState({ total: 0, pending: 0, sent: 0, failed: 0, overdue: 0 })

  const fetchData = async () => {
    try {
      const [remindersRes, statsRes] = await Promise.all([
        reminderAPI.getAll(),
        reminderAPI.getStats()
      ])
      setReminders(remindersRes.data)
      setStats(statsRes.data)
    } catch (error) {
      console.error('Failed to fetch reminders:', error)
      toast.error('Failed to load reminders')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleMarkAsRead = async (id) => {
    try {
      await reminderAPI.markAsRead(id)
      setReminders(prev => prev.filter(r => r.id !== id))
      toast.success('Reminder marked as read')
      const statsRes = await reminderAPI.getStats()
      setStats(statsRes.data)
    } catch (error) {
      toast.error('Failed to mark as read')
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this reminder?')) return
    try {
      await reminderAPI.delete(id)
      setReminders(prev => prev.filter(r => r.id !== id))
      toast.success('Reminder deleted')
      const statsRes = await reminderAPI.getStats()
      setStats(statsRes.data)
    } catch (error) {
      toast.error('Failed to delete reminder')
    }
  }

  const getReminderEmoji = (type) => {
    const emojis = {
      '7_day': '📅',
      '3_day': '⏰',
      '1_day': '🚨',
      'deadline_day': '⚠️',
      'missed_deadline': '❌'
    }
    return emojis[type] || '🔔'
  }

  const getReminderLabel = (type) => {
    const labels = {
      '7_day': '7 Days Left',
      '3_day': '3 Days Left',
      '1_day': '1 Day Left',
      'deadline_day': 'Due Today',
      'missed_deadline': 'Missed Deadline'
    }
    return labels[type] || type
  }

  if (loading) {
    return <div className="text-center py-10">Loading reminders...</div>
  }

  // Separate pending and sent reminders
  const unreadReminders = reminders.filter(r => r.status === 'pending')
  const readReminders = reminders.filter(r => r.status === 'sent')

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Reminders</h1>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
          <p className="text-sm text-gray-500">Total</p>
          <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
          <p className="text-sm text-gray-500">Unread</p>
          <p className="text-2xl font-bold text-yellow-600">{stats.pending}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
          <p className="text-sm text-gray-500">Read</p>
          <p className="text-2xl font-bold text-green-600">{stats.sent}</p>
        </div>
        <div className="bg-white p-4 rounded-lg shadow-sm border border-gray-200">
          <p className="text-sm text-gray-500">Overdue</p>
          <p className="text-2xl font-bold text-red-600">{stats.overdue || 0}</p>
        </div>
      </div>

      {/* Unread Reminders */}
      {unreadReminders.length > 0 && (
        <>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Unread Reminders</h2>
          <div className="space-y-3 mb-6">
            {unreadReminders.map((reminder) => (
              <div
                key={reminder.id}
                className="p-4 bg-white rounded-lg shadow-sm border border-yellow-300 bg-yellow-50"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-2xl">{getReminderEmoji(reminder.reminder_type)}</span>
                      <span className="font-medium text-gray-900">
                        {getReminderLabel(reminder.reminder_type)}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700">
                        Unread
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">
                      {reminder.circular_title || 'Reminder'}
                    </p>
                    {reminder.circular_due_date && (
                      <p className="text-sm text-red-600 mt-1">
                        Due: {new Date(reminder.circular_due_date).toLocaleDateString()}
                      </p>
                    )}
                    <p className="text-xs text-gray-400 mt-1">
                      Scheduled: {new Date(reminder.scheduled_at).toLocaleString()}
                    </p>
                  </div>
                  <button
                    onClick={() => handleMarkAsRead(reminder.id)}
                    className="px-3 py-1 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Mark as Read
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Read Reminders */}
      {readReminders.length > 0 && (
        <>
          <h2 className="text-lg font-semibold text-gray-800 mb-3">Read Reminders</h2>
          <div className="space-y-3">
            {readReminders.map((reminder) => (
              <div
                key={reminder.id}
                className="p-4 bg-white rounded-lg shadow-sm border border-gray-200"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-2xl">{getReminderEmoji(reminder.reminder_type)}</span>
                      <span className="font-medium text-gray-900">
                        {getReminderLabel(reminder.reminder_type)}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700">
                        Read
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mt-1">
                      {reminder.circular_title || 'Reminder'}
                    </p>
                    {reminder.circular_due_date && (
                      <p className="text-sm text-red-600 mt-1">
                        Due: {new Date(reminder.circular_due_date).toLocaleDateString()}
                      </p>
                    )}
                    <p className="text-xs text-gray-400 mt-1">
                      Read on: {new Date(reminder.sent_at || reminder.updated_at).toLocaleString()}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDelete(reminder.id)}
                    className="text-sm text-red-600 hover:text-red-800"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {reminders.length === 0 && (
        <p className="text-gray-500 text-center py-10">No reminders yet</p>
      )}
    </div>
  )
}

export default ReminderList