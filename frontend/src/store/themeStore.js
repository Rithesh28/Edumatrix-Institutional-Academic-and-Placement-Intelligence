import { create } from 'zustand'

export const THEME_STORAGE_KEY = 'edumatrix_theme'

/**
 * Determine initial theme.
 * Default is strictly DARK unless user explicitly saved 'light'.
 * Does NOT rely on OS media queries.
 */
const getInitialTheme = () => {
  if (typeof window === 'undefined') return 'dark'
  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY)
    if (saved === 'light' || saved === 'dark') {
      return saved
    }
  } catch (e) {
    console.warn('Failed to access localStorage for theme:', e)
  }
  return 'dark'
}

/**
 * Apply the theme to the root HTML document element.
 */
export const applyThemeToDom = (theme) => {
  if (typeof document === 'undefined') return
  const root = document.documentElement
  if (theme === 'dark') {
    root.classList.add('dark')
    root.setAttribute('data-theme', 'dark')
    root.style.colorScheme = 'dark'
  } else {
    root.classList.remove('dark')
    root.setAttribute('data-theme', 'light')
    root.style.colorScheme = 'light'
  }
}

// Initial application immediately on import
const initialTheme = getInitialTheme()
applyThemeToDom(initialTheme)

export const useThemeStore = create((set, get) => ({
  theme: initialTheme,
  isDark: initialTheme === 'dark',

  /**
   * Set theme to a specific mode ('dark' | 'light')
   */
  setTheme: (newTheme) => {
    const theme = newTheme === 'light' ? 'light' : 'dark'
    try {
      localStorage.setItem(THEME_STORAGE_KEY, theme)
    } catch (e) {
      console.warn('Failed to persist theme to localStorage:', e)
    }
    applyThemeToDom(theme)
    set({ theme, isDark: theme === 'dark' })
  },

  /**
   * Toggle between dark and light mode
   */
  toggleTheme: () => {
    const currentTheme = get().theme
    const nextTheme = currentTheme === 'dark' ? 'light' : 'dark'
    get().setTheme(nextTheme)
  },
}))

// Cross-tab synchronization
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key === THEME_STORAGE_KEY && event.newValue) {
      const syncedTheme = event.newValue === 'light' ? 'light' : 'dark'
      applyThemeToDom(syncedTheme)
      useThemeStore.setState({ theme: syncedTheme, isDark: syncedTheme === 'dark' })
    }
  })
}
