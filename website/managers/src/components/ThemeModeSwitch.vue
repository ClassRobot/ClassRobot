<template>
  <div
    class="inline-flex items-center rounded-xl border border-outline-variant dark:border-zinc-700 bg-surface-container-lowest/92 dark:bg-zinc-900/92 p-1 shadow-[0_10px_24px_rgba(15,23,42,0.08)] dark:shadow-[0_12px_28px_rgba(0,0,0,0.28)] backdrop-blur"
    aria-label="主题模式"
  >
    <button
      v-for="option in themeOptions"
      :key="option.value"
      type="button"
      class="flex h-8 w-8 cursor-pointer items-center justify-center rounded-lg text-on-surface-variant dark:text-zinc-400 transition-colors duration-200 hover:text-on-surface dark:hover:text-zinc-100"
      :class="theme === option.value ? 'bg-surface-container dark:bg-zinc-800 text-primary dark:text-primary-dark shadow-sm' : ''"
      :title="option.label"
      :aria-label="option.label"
      :aria-pressed="theme === option.value"
      @click="setTheme(option.value)"
    >
      <component :is="option.icon" :size="15" />
    </button>
  </div>
</template>

<script setup lang="ts">
import { Monitor, Moon, Sun } from 'lucide-vue-next'
import { useTheme } from '@/composables/useTheme'

const { theme, setTheme } = useTheme()

const themeOptions = [
  { value: 'light' as const, label: '浅色模式', icon: Sun },
  { value: 'dark' as const, label: '深色模式', icon: Moon },
  { value: 'system' as const, label: '跟随系统', icon: Monitor },
]
</script>
