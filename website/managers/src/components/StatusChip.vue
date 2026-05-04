<template>
  <span
    class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full font-code-inline text-[11px] leading-tight border"
    :class="chipClass"
  >
    <CircleCheck v-if="status === 'ok' || status === 'success' || status === 'completed'" :size="12" />
    <TriangleAlert v-else-if="status === 'warning'" :size="12" />
    <CircleX v-else-if="status === 'error' || status === 'failed'" :size="12" />
    <Settings v-else-if="status === 'not_configured'" :size="12" />
    <Loader2 v-else-if="status === 'running'" :size="12" class="animate-spin" />
    <Clock v-else :size="12" />
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CircleCheck, TriangleAlert, CircleX, Settings, Loader2, Clock } from 'lucide-vue-next'

const props = defineProps<{ status: string }>()

const label = computed(() => {
  const map: Record<string, string> = {
    ok: '正常', success: '成功', completed: '已完成',
    warning: '警告', error: '异常', failed: '失败', critical: '严重',
    configured: '已配置', not_configured: '未配置', running: '运行中', pending: '待处理',
    needs_confirm: '待确认', locked: '已锁定',
  }
  return map[props.status] || props.status
})

const chipClass = computed(() => {
  switch (props.status) {
    case 'ok': case 'success': case 'completed': case 'configured':
      return 'bg-primary/10 dark:bg-emerald-500/10 text-primary dark:text-emerald-400 border-primary/20 dark:border-emerald-500/20'
    case 'warning':
      return 'bg-warning/10 dark:bg-amber-500/10 text-warning dark:text-amber-400 border-warning/20 dark:border-amber-500/20'
    case 'error': case 'failed': case 'critical':
      return 'bg-error/10 dark:bg-red-500/10 text-error dark:text-red-400 border-error/20 dark:border-red-500/20'
    case 'not_configured':
      return 'bg-surface-variant/50 dark:bg-zinc-800 text-on-surface-variant dark:text-zinc-400 border-outline-variant dark:border-zinc-700'
    case 'running':
      return 'bg-secondary/10 dark:bg-blue-500/10 text-secondary dark:text-blue-400 border-secondary/20 dark:border-blue-500/20'
    default:
      return 'bg-surface-variant/50 dark:bg-zinc-800 text-on-surface-variant dark:text-zinc-400 border-outline-variant dark:border-zinc-700'
  }
})
</script>
