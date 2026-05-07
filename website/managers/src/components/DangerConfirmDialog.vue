<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-[2px] dark:bg-black/60"
      @click.self="emit('close')"
    >
      <div
        class="mx-auto flex max-h-[calc(100vh-32px)] flex-col overflow-hidden rounded-[22px] border border-outline-variant bg-surface-container-lowest shadow-[0_28px_72px_rgba(15,23,42,0.22)] dark:border-zinc-800 dark:bg-zinc-900 dark:shadow-[0_30px_90px_rgba(0,0,0,0.55)]"
        :style="{ width }"
        @click.stop
      >
        <div class="flex items-start gap-4 border-b border-outline-variant px-5 py-4 dark:border-zinc-800">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-error/15 bg-error-container/20 text-error dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300">
            <AlertTriangle :size="18" />
          </div>
          <div class="min-w-0 flex-1">
            <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ title }}</h2>
            <p class="mt-1 text-body-sm leading-6 text-on-surface-variant dark:text-zinc-400">{{ message }}</p>
          </div>
          <button
            type="button"
            class="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container dark:text-zinc-400 dark:hover:bg-zinc-800"
            :disabled="busy"
            @click="emit('close')"
          >
            <X :size="16" />
          </button>
        </div>

        <div class="min-h-0 space-y-4 overflow-y-auto px-5 py-4">
          <div
            v-if="targetLabel || targetHint"
            class="rounded-xl border border-outline-variant bg-surface-container-low px-4 py-3 dark:border-zinc-800 dark:bg-zinc-800/55"
          >
            <div class="text-[11px] uppercase tracking-[0.14em] text-on-surface-variant dark:text-zinc-500">操作对象</div>
            <div v-if="targetLabel" class="mt-2 text-body-md font-semibold text-on-surface dark:text-zinc-100">{{ targetLabel }}</div>
            <div
              v-if="targetHint"
              class="mt-1 break-all font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-400"
            >
              {{ targetHint }}
            </div>
          </div>

          <div
            v-if="errorMessage"
            class="rounded-xl border border-error/20 bg-error-container/14 px-4 py-3 text-body-sm leading-6 text-error dark:border-red-800/50 dark:bg-red-950/25 dark:text-red-200"
          >
            {{ errorMessage }}
          </div>

          <div v-if="$slots.details" class="space-y-4">
            <slot name="details" />
          </div>
        </div>

        <div class="flex items-center justify-end gap-2 border-t border-outline-variant px-5 py-4 dark:border-zinc-800">
          <button
            type="button"
            class="rounded-lg border border-outline-variant px-4 py-2 text-body-sm text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
            :disabled="busy"
            @click="emit('close')"
          >
            取消
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-lg border border-error/20 bg-error px-4 py-2 text-body-sm font-medium text-on-error transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-900/50 dark:bg-red-900 dark:text-white"
            :disabled="busy"
            @click="emit('confirm')"
          >
            <Loader2 v-if="busy" :size="14" class="animate-spin" />
            <Trash2 v-else :size="14" />
            {{ confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { AlertTriangle, Loader2, Trash2, X } from 'lucide-vue-next'

withDefaults(defineProps<{
  open: boolean
  busy?: boolean
  title: string
  message: string
  targetLabel?: string
  targetHint?: string
  confirmLabel?: string
  width?: string
  errorMessage?: string
}>(), {
  busy: false,
  targetLabel: '',
  targetHint: '',
  confirmLabel: '确认删除',
  width: 'min(460px, calc(100vw - 32px))',
  errorMessage: '',
})

const emit = defineEmits<{
  (event: 'close'): void
  (event: 'confirm'): void
}>()
</script>
