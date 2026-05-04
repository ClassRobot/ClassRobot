import { computed, onMounted, ref } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

const THEME_KEY = 'classrobot-manager-theme'
const getStoredTheme = () => {
  if (typeof window === 'undefined') return 'system' as ThemeMode
  return (localStorage.getItem(THEME_KEY) as ThemeMode) || 'system'
}

const theme = ref<ThemeMode>(getStoredTheme())
const systemPrefersDark = ref(false)
let mediaQuery: MediaQueryList | null = null
let runtimeInitialized = false

function resolveIsDark(mode: ThemeMode) {
  return mode === 'dark' || (mode === 'system' && systemPrefersDark.value)
}

function applyTheme(mode: ThemeMode) {
  if (typeof document === 'undefined') return
  document.documentElement.classList.toggle('dark', resolveIsDark(mode))
}

function initThemeRuntime() {
  if (runtimeInitialized || typeof window === 'undefined') return
  mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
  systemPrefersDark.value = mediaQuery.matches
  mediaQuery.addEventListener('change', (event) => {
    systemPrefersDark.value = event.matches
    if (theme.value === 'system') {
      applyTheme('system')
    }
  })
  runtimeInitialized = true
  applyTheme(theme.value)
}

export function initializeTheme() {
  initThemeRuntime()
  applyTheme(theme.value)
}

export function useTheme() {
  const resolvedTheme = computed<'light' | 'dark'>(() => (resolveIsDark(theme.value) ? 'dark' : 'light'))
  const isDark = computed(() => resolvedTheme.value === 'dark')

  onMounted(() => {
    initThemeRuntime()
  })

  function setTheme(mode: ThemeMode) {
    theme.value = mode
    applyTheme(mode)
    localStorage.setItem(THEME_KEY, mode)
  }

  function toggleTheme() {
    const cycle: ThemeMode[] = ['light', 'dark', 'system']
    const idx = cycle.indexOf(theme.value)
    setTheme(cycle[(idx + 1) % cycle.length])
  }

  return {
    theme,
    setTheme,
    toggleTheme,
    resolvedTheme,
    isDark,
  }
}
