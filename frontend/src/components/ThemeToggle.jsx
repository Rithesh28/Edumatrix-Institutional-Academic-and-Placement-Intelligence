import React from 'react'
import { useThemeStore } from '../store/themeStore'
import { Sun, Moon } from 'lucide-react'

/**
 * Reusable ThemeToggle component.
 * Allows toggling between global Dark and Light themes with immediate update,
 * persistent storage, and accessible keyboard and screen-reader controls.
 */
export default function ThemeToggle({ showLabel = true, className = '', id = 'global-theme-toggle' }) {
  const { theme, isDark, toggleTheme } = useThemeStore()

  const currentLabel = isDark ? 'Dark' : 'Light'
  const targetLabel = isDark ? 'Light' : 'Dark'
  const accessibleTitle = `Current theme: ${currentLabel}. Click to switch to ${targetLabel} Mode.`

  return (
    <button
      id={id}
      type="button"
      onClick={toggleTheme}
      title={accessibleTitle}
      aria-label={`Toggle theme, currently ${currentLabel} mode`}
      aria-pressed={isDark}
      className={`group relative inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs sm:text-sm font-semibold transition-all duration-200 select-none border focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 flex-shrink-0 cursor-pointer ${
        isDark
          ? 'bg-gray-800 hover:bg-gray-700 text-amber-300 border-gray-600 shadow-sm focus:ring-offset-gray-900 ring-1 ring-amber-400/20'
          : 'bg-gray-100 hover:bg-gray-200 text-gray-800 border-gray-300 shadow-sm focus:ring-offset-white ring-1 ring-black/5'
      } ${className}`}
    >
      <span className="relative flex items-center justify-center w-5 h-5 rounded-full transition-transform duration-200 group-hover:scale-110">
        {isDark ? (
          <Moon className="w-4 h-4 text-amber-300 transition-transform duration-300" aria-hidden="true" />
        ) : (
          <Sun className="w-4 h-4 text-amber-500 transition-transform duration-300" aria-hidden="true" />
        )}
      </span>

      {showLabel && (
        <span className="font-semibold tracking-wide whitespace-nowrap">
          {isDark ? '🌙 Dark' : '☀️ Light'}
        </span>
      )}
    </button>
  )
}
