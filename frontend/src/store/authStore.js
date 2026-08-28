import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api, { API_URL } from '../services/api'

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      isLoading: false,

      login: async (email, password) => {
        set({ isLoading: true })
        try {
          const formData = new URLSearchParams()
          formData.append('username', email)
          formData.append('password', password)
          
          const response = await api.post('/auth/login', formData, {
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded'
            }
          })
          
          const { access_token, user } = response.data
          
          // Store role in localStorage for quick access
          if (user?.role) {
            localStorage.setItem('userRole', user.role)
          }
          
          set({ token: access_token, user, isLoading: false })
          
          api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
          
          return response.data
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      register: async (userData) => {
        set({ isLoading: true })
        try {
          const response = await api.post('/auth/register', userData)
          set({ isLoading: false })
          return response.data
        } catch (error) {
          set({ isLoading: false })
          throw error
        }
      },

      logout: () => {
        set({ user: null, token: null })
        localStorage.removeItem('userRole')
        delete api.defaults.headers.common['Authorization']
      },

      updateUser: (userData) => {
        set({ user: { ...get().user, ...userData } })
        if (userData?.role) {
          localStorage.setItem('userRole', userData.role)
        }
      },

      getUserRole: () => {
        return get().user?.role || localStorage.getItem('userRole')
      }
    }),
    {
      name: 'auth-storage',
      getStorage: () => localStorage
    }
  )
)