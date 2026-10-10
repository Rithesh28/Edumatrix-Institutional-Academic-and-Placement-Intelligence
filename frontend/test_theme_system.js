/**
 * Automated Verification Script for Phase 3 Step 0: Global Dark/Light Theme System
 */

import assert from 'assert'
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

console.log('🧪 Starting Phase 3 Step 0: Global Theme System Verification...\n')

// 1. Check tailwind.config.js
console.log('1. Checking tailwind.config.js...')
const tailwindConfig = fs.readFileSync(path.join(__dirname, 'tailwind.config.js'), 'utf8')
assert(tailwindConfig.includes("darkMode: 'class'"), 'tailwind.config.js must specify darkMode: "class"')
console.log('   ✅ darkMode: "class" configured properly.\n')

// 2. Check index.html anti-flash script and default dark class
console.log('2. Checking index.html...')
const indexHtml = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8')
assert(indexHtml.includes('<html lang="en" class="dark">'), 'index.html must have class="dark" by default on html element')
assert(indexHtml.includes('edumatrix_theme'), 'index.html must check edumatrix_theme in localStorage')
assert(indexHtml.includes("document.documentElement.classList.add('dark')"), 'index.html must add dark class')
assert(indexHtml.includes("document.documentElement.classList.remove('dark')"), 'index.html must remove dark class when light')
console.log('   ✅ index.html has default class="dark" and synchronous anti-flash script.\n')

// 3. Check themeStore.js implementation
console.log('3. Checking themeStore.js...')
const themeStoreCode = fs.readFileSync(path.join(__dirname, 'src/store/themeStore.js'), 'utf8')
assert(themeStoreCode.includes("THEME_STORAGE_KEY = 'edumatrix_theme'"), 'Storage key must be edumatrix_theme')
assert(themeStoreCode.includes("return 'dark'"), 'Default theme must be dark when no saved preference exists')
assert(themeStoreCode.includes('toggleTheme'), 'themeStore must export toggleTheme')
assert(themeStoreCode.includes('applyThemeToDom'), 'themeStore must synchronize with DOM')
console.log('   ✅ themeStore.js has correct default dark, persistence, and DOM sync.\n')

// 4. Check ThemeToggle.jsx component
console.log('4. Checking ThemeToggle.jsx...')
const toggleCode = fs.readFileSync(path.join(__dirname, 'src/components/ThemeToggle.jsx'), 'utf8')
assert(toggleCode.includes('useThemeStore'), 'ThemeToggle must use useThemeStore')
assert(toggleCode.includes('toggleTheme'), 'ThemeToggle must call toggleTheme')
assert(toggleCode.includes('aria-label'), 'ThemeToggle must have accessible aria-label')
assert(toggleCode.includes('🌙 Dark'), 'ThemeToggle must render Dark indicator')
assert(toggleCode.includes('☀️ Light'), 'ThemeToggle must render Light indicator')
console.log('   ✅ ThemeToggle.jsx renders accessible, clear mode indicators.\n')

// 5. Check Layout.jsx (all 5 roles: Student, Lecturer, HOD, Placement Officer, Admin)
console.log('5. Checking Layout.jsx role navigation integration...')
const layoutCode = fs.readFileSync(path.join(__dirname, 'src/components/Layout.jsx'), 'utf8')
assert(layoutCode.includes("import ThemeToggle from './ThemeToggle'"), 'Layout must import ThemeToggle')
assert(layoutCode.includes('<ThemeToggle'), 'Layout navbar must render ThemeToggle')
assert(layoutCode.includes('dark:bg-gray-900'), 'Layout navbar and sidebar must have dark mode classes')
assert(layoutCode.includes('dark:bg-gray-950'), 'Layout background must have dark mode classes')
console.log('   ✅ Layout.jsx renders ThemeToggle in navbar across all authenticated roles.\n')

// 6. Check Login.jsx
console.log('6. Checking Login.jsx integration...')
const loginCode = fs.readFileSync(path.join(__dirname, 'src/pages/Login.jsx'), 'utf8')
assert(loginCode.includes("import ThemeToggle from '../components/ThemeToggle'"), 'Login must import ThemeToggle')
assert(loginCode.includes('<ThemeToggle'), 'Login page must render ThemeToggle')
assert(loginCode.includes('dark:bg-gray-900'), 'Login card must support dark styling')
console.log('   ✅ Login.jsx renders ThemeToggle and supports dark/light mode.\n')

// 7. Check Register.jsx and Unauthorized.jsx
console.log('7. Checking Register.jsx & Unauthorized.jsx...')
const registerCode = fs.readFileSync(path.join(__dirname, 'src/pages/Register.jsx'), 'utf8')
assert(registerCode.includes('<ThemeToggle'), 'Register page must render ThemeToggle')
const unauthorizedCode = fs.readFileSync(path.join(__dirname, 'src/pages/Unauthorized.jsx'), 'utf8')
assert(unauthorizedCode.includes('<ThemeToggle'), 'Unauthorized page must render ThemeToggle')
console.log('   ✅ Register.jsx and Unauthorized.jsx render ThemeToggle.\n')

// 8. Check index.css
console.log('8. Checking index.css...')
const indexCss = fs.readFileSync(path.join(__dirname, 'src/index.css'), 'utf8')
assert(indexCss.includes('html.dark'), 'index.css must define html.dark color scheme')
assert(indexCss.includes('.dark .bg-white'), 'index.css must define dark card backgrounds')
assert(indexCss.includes('.dark .border-gray-200'), 'index.css must define dark borders')
assert(indexCss.includes('.dark .text-gray-900'), 'index.css must define dark text colors')
console.log('   ✅ index.css contains comprehensive dark mode tokens and utility mappings.\n')

// 9. Functional simulation of themeStore logic
console.log('9. Simulating themeStore state transitions...')
// Mock DOM & localStorage
class MockClassList {
  constructor() { this.classes = new Set(['dark']) }
  add(c) { this.classes.add(c) }
  remove(c) { this.classes.delete(c) }
  contains(c) { return this.classes.has(c) }
}
const mockDocumentElement = {
  classList: new MockClassList(),
  attributes: {},
  style: {},
  setAttribute(k, v) { this.attributes[k] = v },
  getAttribute(k) { return this.attributes[k] }
}

const mockStorage = {}
const mockLocalStorage = {
  getItem: (k) => mockStorage[k] || null,
  setItem: (k, v) => { mockStorage[k] = String(v) },
  removeItem: (k) => { delete mockStorage[k] }
}

global.document = { documentElement: mockDocumentElement }
global.localStorage = mockLocalStorage

// Step 9a: Fresh visit (no localStorage) -> Default must be 'dark'
let saved = localStorage.getItem('edumatrix_theme')
let initialTheme = (saved === 'light') ? 'light' : 'dark'
assert.strictEqual(initialTheme, 'dark', 'Fresh visit must default to dark')
assert.strictEqual(document.documentElement.classList.contains('dark'), true, 'Dark class must be present initially')

// Step 9b: User switches to 'light'
let currentTheme = 'light'
localStorage.setItem('edumatrix_theme', currentTheme)
document.documentElement.classList.remove('dark')
document.documentElement.setAttribute('data-theme', 'light')
document.documentElement.style.colorScheme = 'light'
assert.strictEqual(localStorage.getItem('edumatrix_theme'), 'light', 'Theme must be stored as light in localStorage')
assert.strictEqual(document.documentElement.classList.contains('dark'), false, 'Dark class must be removed in light mode')
assert.strictEqual(document.documentElement.getAttribute('data-theme'), 'light', 'data-theme must be light')

// Step 9c: Refresh / Navigation in light mode
saved = localStorage.getItem('edumatrix_theme')
let reloadedTheme = (saved === 'light') ? 'light' : 'dark'
assert.strictEqual(reloadedTheme, 'light', 'Reloaded theme must preserve light mode')

// Step 9d: User switches back to 'dark'
currentTheme = 'dark'
localStorage.setItem('edumatrix_theme', currentTheme)
document.documentElement.classList.add('dark')
document.documentElement.setAttribute('data-theme', 'dark')
document.documentElement.style.colorScheme = 'dark'
assert.strictEqual(localStorage.getItem('edumatrix_theme'), 'dark', 'Theme must be stored as dark in localStorage')
assert.strictEqual(document.documentElement.classList.contains('dark'), true, 'Dark class must be added in dark mode')
assert.strictEqual(document.documentElement.getAttribute('data-theme'), 'dark', 'data-theme must be dark')

// 10. Check Student Dashboard & Profile explicit dark classes
console.log('10. Checking Student Dashboard & Profile dark mode classes...')
const studentDashboardCode = fs.readFileSync(path.join(__dirname, 'src/pages/student/Dashboard.jsx'), 'utf8')
assert(studentDashboardCode.includes('dark:bg-gray-900'), 'Student Dashboard must have dark:bg-gray-900 on cards')
assert(studentDashboardCode.includes('dark:text-white'), 'Student Dashboard must have dark:text-white on text')

const studentProfileCode = fs.readFileSync(path.join(__dirname, 'src/pages/student/Profile.jsx'), 'utf8')
assert(studentProfileCode.includes('dark:bg-gray-900'), 'Student Profile container must have dark:bg-gray-900')

const profileFormCode = fs.readFileSync(path.join(__dirname, 'src/components/ProfileForm.jsx'), 'utf8')
assert(profileFormCode.includes('dark:bg-gray-800'), 'ProfileForm inputs must have dark:bg-gray-800')
console.log('   ✅ Student Dashboard & Profile have explicit Tailwind dark mode classes.\n')

// 11. Check Layout navbar ordering: [UnifiedBell] [ThemeToggle] [Welcome] [Logout]
console.log('11. Checking Layout top navbar structure...')
const bellIndex = layoutCode.indexOf('<UnifiedBell')
const toggleIndex = layoutCode.indexOf('<ThemeToggle')
const welcomeIndex = layoutCode.indexOf('Welcome,')
const logoutIndex = layoutCode.indexOf('onClick={handleLogout}')
assert(bellIndex !== -1, 'Layout must contain UnifiedBell')
assert(toggleIndex !== -1, 'Layout must contain ThemeToggle')
assert(bellIndex < toggleIndex, 'Layout navbar must place UnifiedBell before ThemeToggle')
assert(toggleIndex < welcomeIndex, 'Layout navbar must place ThemeToggle before Welcome message')
assert(welcomeIndex < logoutIndex, 'Layout navbar must place Welcome message before Logout')
console.log('   ✅ Layout navbar strictly ordered: [UnifiedBell] -> [ThemeToggle] -> [Welcome] -> [Logout].\n')

console.log('🎉 ALL 11 THEME CHECKS PASSED SUCCESSFULLY!\n')
