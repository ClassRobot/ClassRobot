<template>
  <div
    class="rounded-xl border p-4 flex flex-col gap-3 relative overflow-hidden transition-colors"
    :class="cardClass"
  >
    <div class="flex items-start justify-between">
      <span class="font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">{{ label }}</span>
      <span
        class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-code-inline text-code-inline text-[11px]"
        :class="statusClass"
      >
        <CircleCheck v-if="status === 'ok' || status === 'configured'" :size="12" />
        <TriangleAlert v-else-if="status === 'warning'" :size="12" />
        <CircleX v-else-if="status === 'error'" :size="12" />
        <Settings v-else :size="12" />
        {{ statusText }}
      </span>
    </div>
    <div>
      <div class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ value }}</div>
      <div class="font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500 mt-1">{{ sub }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheck, TriangleAlert, CircleX, Settings } from 'lucide-vue-next'
import type { StatusLevel } from '@/types/api'

const props = defineProps<{
  label: string
  status: StatusLevel | string
  value: string
  sub: string
  icon?: string
}>()

const statusLabel: Record<string, string> = {
  ok: '正常', configured: '已配置', warning: '警告', error: '异常', not_configured: '未配置',
}

const statusText = computed(() => statusLabel[props.status] || props.status)

const cardClass = computed(() => {
  switch (props.status) {
    case 'error':
      return 'bg-surface-container-lowest dark:bg-zinc-900 border-error/40 dark:border-red-500/40 shadow-[inset_4px_0_0_0_#ba1a1a] dark:shadow-[inset_4px_0_0_0_#ef4444]'
    case 'warning':
      return 'bg-surface-container-lowest dark:bg-zinc-900 border-warning/40 dark:border-amber-500/40'
    default:
      return 'bg-surface-container-lowest dark:bg-zinc-900 border-outline-variant dark:border-zinc-800'
  }
})

const statusClass = computed(() => {
  switch (props.status) {
    case 'ok': case 'configured': return 'bg-primary/10 dark:bg-emerald-500/10 text-primary dark:text-emerald-400'
    case 'warning': return 'bg-warning/10 dark:bg-amber-500/10 text-warning dark:text-amber-400'
    case 'error': return 'bg-error/10 dark:bg-red-500/10 text-error dark:text-red-400'
    default: return 'bg-surface-variant/50 dark:bg-zinc-800 text-on-surface-variant dark:text-zinc-500'
  }
})
</script>
