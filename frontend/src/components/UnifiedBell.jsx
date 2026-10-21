import React, { useState, useEffect, useRef } from 'react'
import { notificationAPI, reminderAPI } from '../services/api'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'

const UnifiedBell = () => {
  const [unreadCount, setUnreadCount] = useState(0)
  const [showDropdown, setShowDropdown] = useState(false)
  const [notifications, setNotifications] = useState([])
  const [reminders, setReminders] = useState([])
  const dropdownRef = useRef(null)
  const navigate = useNavigate()
  const { user } = useAuthStore()

  const fetchUnreadCount = async () => {
    try {
      const results = await Promise.allSettled([
        notificationAPI.getUnreadCount(),
        reminderAPI.getUnreadCount()
      ])
      
      const notifCount = results[0].status === 'fulfilled' ? (results[0].value.data?.unread_count || 0) : 0
      const remindCount = results[1].status === 'fulfilled' ? (results[1].value.data?.count || 0) : 0
      setUnreadCount(notifCount + remindCount)
    } catch (error) {
      console.error('Failed to fetch unread count:', error)
    }
  }

  const fetchData = async () => {
    try {
      const results = await Promise.allSettled([
        notificationAPI.getAll(),
        reminderAPI.getAll()
      ])
      
      if (results[0].status === 'fulfilled') {
        const notifs = results[0].value.data || []
        // Sort unread notifications first, then by date descending
        notifs.sort((a, b) => {
          if (a.is_read === b.is_read) {
            return new Date(b.created_at || 0) - new Date(a.created_at || 0)
          }
          return a.is_read ? 1 : -1
        })
        setNotifications(notifs)
      }
      
      if (results[1].status === 'fulfilled') {
        setReminders(results[1].value.data || [])
      }
    } catch (error) {
      console.error('Failed to fetch notifications data:', error)
    }
  }

  useEffect(() => {
    fetchUnreadCount()
    fetchData()
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

  const handleToggleDropdown = () => {
    const nextState = !showDropdown
    setShowDropdown(nextState)
    if (nextState) {
      fetchData()
      fetchUnreadCount()
    }
  }

  const handleNotificationClick = async (notif) => {
    if (!notif.is_read) {
      try {
        await notificationAPI.markAsRead(notif.id)
        setNotifications(prev => prev.map(n => n.id === notif.id ? { ...n, is_read: true } : n))
        setUnreadCount(prev => Math.max(0, prev - 1))
      } catch (error) {
        console.error('Failed to mark as read:', error)
      }
    }

    setShowDropdown(false)
    const role = user?.role?.toLowerCase() || 'student'
    
    if (notif.type?.includes('exam_duty')) {
      if (role === 'hod') {
        navigate('/hod/exam-duties')
      } else {
        navigate('/lecturer/exam-duties')
      }
    } else if (notif.type === 'placement_circular' || notif.type === 'placement_shortlist') {
      if (role === 'student') {
        if (notif.reference_id) {
          navigate(`/student/jobs/circulars/${notif.reference_id}`)
        } else {
          navigate('/student/jobs?tab=circulars')
        }
      } else if (role === 'placement_officer' || role === 'admin') {
        if (notif.reference_id) {
          navigate(`/placement/circulars/${notif.reference_id}`)
        } else {
          navigate('/placement/circulars')
        }
      }
    } else if (notif.type === 'placement_offer') {
      if (role === 'student') {
        navigate('/student/applications')
      } else if (role === 'placement_officer' || role === 'admin') {
        navigate('/placement/offers')
      } else {
        navigate(`/${role}/dashboard`)
      }
    } else if (notif.type === 'placement_result') {
      if (role === 'student') {
        // If event_key or context indicates a circular round, route to circular details
        if (notif.event_key?.includes('circular') || notif.event_key?.includes('recruitment_circular')) {
          if (notif.reference_id) {
            navigate(`/student/jobs/circulars/${notif.reference_id}`)
          } else {
            navigate('/student/jobs?tab=circulars')
          }
        } else if (notif.reference_id) {
          navigate(`/student/jobs/${notif.reference_id}`)
        } else {
          navigate('/student/applications')
        }
      } else if (role === 'placement_officer' || role === 'admin') {
        if (notif.reference_id) {
          navigate(`/placement/results/${notif.reference_id}`)
        } else {
          navigate('/placement/results')
        }
      } else {
        navigate(`/${role}/dashboard`)
      }
    } else if (notif.type === 'placement_job' || notif.type === 'placement_confirm' || notif.type?.startsWith('placement')) {
      if (role === 'student') {
        if (notif.reference_id) {
          navigate(`/student/jobs/${notif.reference_id}`)
        } else {
          navigate('/student/jobs')
        }
      } else if (role === 'placement_officer' || role === 'admin') {
        if (notif.reference_id) {
          navigate(`/placement/jobs/${notif.reference_id}`)
        } else {
          navigate('/placement/jobs')
        }
      } else {
        navigate(`/${role}/dashboard`)
      }
    } else if (notif.type?.includes('circular') || notif.reference_id) {
      navigate(`/${role}/circulars`)
    }
  }

  const handleMarkReminderAsRead = async (id) => {
    try {
      await reminderAPI.markAsRead(id)
      setReminders(prev => prev.filter(r => r.id !== id))
      setUnreadCount(prev => Math.max(0, prev - 1))
    } catch (error) {
      console.error('Failed to mark as read:', error)
    }
  }

  const handleMarkAllAsRead = async () => {
    try {
      await Promise.allSettled([
        notificationAPI.markAllAsRead(),
        reminderAPI.markAllAsRead()
      ])
      setNotifications(prev => prev.map(n => ({ ...n, is_read: true })))
      setUnreadCount(0)
    } catch (error) {
      console.error('Failed to mark all as read:', error)
    }
  }

  const totalItems = notifications.length + reminders.length
  const role = user?.role?.toLowerCase() || 'student'

  return (
    <div className="relative flex-shrink-0" ref={dropdownRef}>
      <button
        onClick={handleToggleDropdown}
        className="relative p-2 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white focus:outline-none hover:bg-gray-100 dark:hover:bg-gray-800 rounded-full transition-colors cursor-pointer"
        title="Notifications"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-bold leading-none text-white transform translate-x-1/3 -translate-y-1/3 bg-rose-600 rounded-full min-w-[18px] h-[18px]">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {showDropdown && (
        <div className="absolute right-0 mt-2 w-96 bg-white dark:bg-gray-900 rounded-xl shadow-2xl z-50 border border-gray-200 dark:border-gray-800 max-h-[520px] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
          <div className="p-3.5 border-b border-gray-200 dark:border-gray-800 flex justify-between items-center bg-gray-50/80 dark:bg-gray-800/80 backdrop-blur-sm">
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">Notifications</h3>
              {unreadCount > 0 && (
                <span className="bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 text-xs px-2 py-0.5 rounded-full font-medium">
                  {unreadCount} unread
                </span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllAsRead}
                className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 font-medium hover:underline"
              >
                Mark all read
              </button>
            )}
          </div>

          <div className="overflow-y-auto flex-1 divide-y divide-gray-100 dark:divide-gray-800">
            {totalItems === 0 ? (
              <div className="p-8 text-center text-gray-400 dark:text-gray-500 text-sm">
                <p className="text-2xl mb-1">📭</p>
                No notifications yet
              </div>
            ) : (
              <>
                {/* Notifications List */}
                {notifications.length > 0 && (
                  <div>
                    {notifications.slice(0, 8).map((notif) => (
                      <div
                        key={`notif-${notif.id}`}
                        className={`p-3.5 hover:bg-gray-50 dark:hover:bg-gray-800/70 cursor-pointer transition-colors border-l-4 ${
                          !notif.is_read 
                            ? 'bg-blue-50/70 dark:bg-blue-950/40 border-blue-500 font-normal' 
                            : 'border-transparent opacity-85'
                        }`}
                        onClick={() => handleNotificationClick(notif)}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className={`text-sm ${!notif.is_read ? 'font-semibold text-gray-900 dark:text-gray-100' : 'font-medium text-gray-700 dark:text-gray-300'}`}>
                            {notif.title}
                          </p>
                          {!notif.is_read && (
                            <span className="w-2 h-2 rounded-full bg-blue-600 dark:bg-blue-400 shrink-0 mt-1.5" />
                          )}
                        </div>
                        <p className="text-gray-600 dark:text-gray-400 text-xs mt-1 line-clamp-2 whitespace-pre-line leading-relaxed">
                          {notif.message}
                        </p>
                        <p className="text-gray-400 dark:text-gray-500 text-[11px] mt-1.5 flex items-center gap-1">
                          <span>🕒</span>
                          {notif.created_at ? new Date(notif.created_at).toLocaleString() : 'Recent'}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Reminders List */}
                {reminders.length > 0 && (
                  <div>
                    <div className="px-3 py-1.5 bg-gray-100/70 dark:bg-gray-800/70 text-[11px] text-gray-500 dark:text-gray-400 font-semibold uppercase tracking-wider">
                      Upcoming Reminders ({reminders.length})
                    </div>
                    {reminders.slice(0, 4).map((reminder) => (
                      <div
                        key={`rem-${reminder.id}`}
                        className={`p-3 hover:bg-gray-50 dark:hover:bg-gray-800/70 cursor-pointer transition-colors ${
                          reminder.status === 'pending' ? 'bg-amber-50/50 dark:bg-amber-950/30' : ''
                        }`}
                        onClick={() => handleMarkReminderAsRead(reminder.id)}
                      >
                        <p className="font-medium text-gray-900 dark:text-gray-100 text-xs">
                          {reminder.circular_title || 'Exam Duty Reminder'}
                        </p>
                        <p className="text-amber-700 dark:text-amber-400 text-[11px] font-semibold mt-0.5">
                          ⏰ {reminder.reminder_type?.replace('_', ' ').toUpperCase()}
                        </p>
                        <p className="text-gray-400 dark:text-gray-500 text-[11px] mt-1">
                          Due: {reminder.scheduled_at ? new Date(reminder.scheduled_at).toLocaleString() : 'Soon'}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Footer view all link */}
          {notifications.length > 0 && (
            <div className="p-2 bg-gray-50 dark:bg-gray-800/90 border-t border-gray-200 dark:border-gray-800 text-center">
              <button
                onClick={() => {
                  setShowDropdown(false)
                  if (role === 'lecturer') navigate('/lecturer/exam-duties')
                  else if (role === 'hod') navigate('/hod/exam-duties')
                  else if (role === 'placement_officer') navigate('/placement/jobs')
                  else navigate(`/${role}/circulars`)
                }}
                className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 font-medium py-1"
              >
                Go to {role === 'lecturer' ? 'Exam Duties' : (role === 'placement_officer' ? 'Campus Jobs' : 'Dashboard')} →
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default UnifiedBell