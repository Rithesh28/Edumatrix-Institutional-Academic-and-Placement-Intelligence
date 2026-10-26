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
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">Reminders</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Total</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Unread</p>
          <p className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">{stats.pending}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Read</p>
          <p className="text-2xl font-bold text-green-600 dark:text-green-400">{stats.sent}</p>
        </div>
        <div className="bg-white dark:bg-gray-900 p-4 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800">
          <p className="text-sm text-gray-500 dark:text-gray-400">Overdue</p>
          <p className="text-2xl font-bold text-red-600 dark:text-red-400">{stats.overdue || 0}</p>
        </div>
      </div>

      {/* Unread Reminders */}
      {unreadReminders.length > 0 && (
        <>
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">Unread Reminders</h2>
          <div className="space-y-3 mb-6">
            {unreadReminders.map((reminder) => (
              <div
                key={reminder.id}
                className="p-4 bg-yellow-50 dark:bg-yellow-950/30 rounded-xl shadow-sm border border-yellow-300 dark:border-yellow-700/60"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-2xl">{getReminderEmoji(reminder.reminder_type)}</span>
                      <span className="font-medium text-gray-900 dark:text-white">
                        {getReminderLabel(reminder.reminder_type)}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-100 dark:bg-yellow-900/60 text-yellow-700 dark:text-yellow-300">
                        Unread
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                      {reminder.circular_title || 'Reminder'}
                    </p>
                    {reminder.circular_due_date && (
                      <p className="text-sm text-red-600 dark:text-red-400 mt-1">
                        Due: {new Date(reminder.circular_due_date).toLocaleDateString()}
                      </p>
                    )}
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      Scheduled: {new Date(reminder.scheduled_at).toLocaleString()}
                    </p>
                  </div>
                  <button
                    onClick={() => handleMarkAsRead(reminder.id)}
                    className="px-3 py-1 text-sm text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors cursor-pointer"
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
          <h2 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">Read Reminders</h2>
          <div className="space-y-3">
            {readReminders.map((reminder) => (
              <div
                key={reminder.id}
                className="p-4 bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-2xl">{getReminderEmoji(reminder.reminder_type)}</span>
                      <span className="font-medium text-gray-900 dark:text-white">
                        {getReminderLabel(reminder.reminder_type)}
                      </span>
                      <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 dark:bg-green-900/60 text-green-700 dark:text-green-300">
                        Read
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 dark:text-gray-300 mt-1">
                      {reminder.circular_title || 'Reminder'}
                    </p>
                    {reminder.circular_due_date && (
                      <p className="text-sm text-red-600 dark:text-red-400 mt-1">
                        Due: {new Date(reminder.circular_due_date).toLocaleDateString()}
                      </p>
                    )}
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                      Read on: {reminder.sent_at ? new Date(reminder.sent_at).toLocaleString() : 'Read date unavailable'}
                    </p>
                  </div>
                  <button
                    onClick={() => handleDelete(reminder.id)}
                    className="text-sm text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-300 cursor-pointer"
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
        <p className="text-gray-500 dark:text-gray-400 text-center py-10">No reminders yet</p>
      )}
    </div>
  )
}

export default ReminderList