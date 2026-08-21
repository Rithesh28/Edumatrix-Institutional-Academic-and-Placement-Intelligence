import { useEffect, useRef, useState, useCallback } from 'react'
import { useAuthStore } from '../store/authStore'

export const useWebSocket = () => {
  const [isConnected, setIsConnected] = useState(false)
  const [messages, setMessages] = useState([])
  const wsRef = useRef(null)
  const reconnectTimeoutRef = useRef(null)
  const { token, user } = useAuthStore()

  const connect = useCallback(() => {
    if (!token || !user) {
      console.log('No token or user, skipping WebSocket connection')
      return
    }

    // Close existing connection if any
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.close()
    }

    const wsUrl = `ws://localhost:8000/chat/ws/${token}`
    console.log('Connecting WebSocket...', wsUrl.substring(0, 100) + '...')
    
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      console.log('WebSocket connected successfully')
      setIsConnected(true)
    }

    ws.onclose = (event) => {
      console.log('WebSocket disconnected, code:', event.code, 'reason:', event.reason)
      setIsConnected(false)
      
      // Attempt to reconnect after 5 seconds
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current)
      }
      reconnectTimeoutRef.current = setTimeout(() => {
        console.log('Attempting to reconnect...')
        connect()
      }, 5000)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log('WebSocket message received:', data)
        if (data.type === 'message') {
          setMessages((prev) => {
            // Avoid duplicate messages
            const exists = prev.some(m => m.id === data.id)
            if (exists) return prev
            return [...prev, data]
          })
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }
  }, [token, user])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setIsConnected(false)
  }, [])

  const sendMessage = useCallback((receiver_id, content) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      const message = JSON.stringify({ receiver_id, content })
      wsRef.current.send(message)
      console.log('WebSocket message sent:', { receiver_id, content })
      return true
    } else {
      console.log('WebSocket not connected, readyState:', wsRef.current?.readyState)
      return false
    }
  }, [])

  useEffect(() => {
    connect()
    return () => disconnect()
  }, [connect, disconnect])

  return { isConnected, sendMessage, messages, setMessages }
}