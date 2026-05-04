<template>
  <div ref="rootRef" class="relative" :class="wrapperClass">
    <button
      type="button"
      class="flex w-full items-center justify-between gap-3 rounded-lg border border-outline-variant bg-surface-container px-3 py-2 text-left text-body-sm text-on-surface transition-colors hover:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:border-primary-dark/60 dark:focus:ring-primary-dark/20"
      :class="buttonClass"
      :disabled="disabled"
      :aria-expanded="open"
      @click="toggleOpen"
    >
      <span class="truncate" :class="selectedOption ? 'text-on-surface dark:text-zinc-100' : 'text-on-surface-variant dark:text-zinc-500'">
        {{ selectedOption?.label || placeholder }}
      </span>
      <ChevronDown
        :size="16"
        class="shrink-0 text-on-surface-variant transition-transform duration-200 dark:text-zinc-500"
        :class="open ? 'rotate-180' : ''"
      />
    </button>

    <Transition
      enter-active-class="transition ease-out duration-150"
      enter-from-class="opacity-0 translate-y-1"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition ease-in duration-100"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 translate-y-1"
    >
      <div
        v-if="open"
        class="absolute left-0 right-0 top-[calc(100%+6px)] z-50 overflow-hidden rounded-lg border border-outline-variant bg-surface-container-lowest shadow-[0_14px_28px_rgba(0,0,0,0.18)] dark:border-zinc-700 dark:bg-zinc-900"
      >
        <div class="max-h-64 overflow-y-auto py-1">
          <button
            v-for="option in options"
            :key="String(option.value)"
            type="button"
            class="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-body-sm transition-colors hover:bg-surface-container hover:text-on-surface dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
            :class="isSelected(option.value) ? 'bg-primary/12 text-primary dark:bg-primary-dark/18 dark:text-primary-dark' : 'text-on-surface-variant dark:text-zinc-300'"
            @click="selectOption(option.value)"
          >
            <span class="truncate">{{ option.label }}</span>
            <Check v-if="isSelected(option.value)" :size="15" class="shrink-0" />
          </button>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Check, ChevronDown } from 'lucide-vue-next'

export interface SelectOption {
  label: string
  value: string | number
}

const props = withDefaults(defineProps<{
  modelValue: string | number | null | undefined
  options: SelectOption[]
  placeholder?: string
  disabled?: boolean
  wrapperClass?: string
  buttonClass?: string
}>(), {
  placeholder: '请选择',
  disabled: false,
  wrapperClass: '',
  buttonClass: '',
})

const emit = defineEmits<{
  'update:modelValue': [value: string | number]
  change: [value: string | number]
}>()

const open = ref(false)
const rootRef = ref<HTMLElement | null>(null)

const selectedOption = computed(() => props.options.find((option) => option.value === props.modelValue))

function toggleOpen() {
  if (props.disabled) return
  open.value = !open.value
}

function isSelected(value: string | number) {
  return value === props.modelValue
}

function selectOption(value: string | number) {
  emit('update:modelValue', value)
  emit('change', value)
  open.value = false
}

function handlePointerDown(event: MouseEvent) {
  if (!rootRef.value) return
  if (!rootRef.value.contains(event.target as Node)) {
    open.value = false
  }
}

function handleEscape(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    open.value = false
  }
}

onMounted(() => {
  document.addEventListener('mousedown', handlePointerDown)
  document.addEventListener('keydown', handleEscape)
})

onBeforeUnmount(() => {
  document.removeEventListener('mousedown', handlePointerDown)
  document.removeEventListener('keydown', handleEscape)
})
</script>
