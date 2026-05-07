<template>
  <div ref="rootRef" class="relative min-w-0" :class="wrapperClass">
    <button
      type="button"
      class="flex min-w-0 w-full items-center justify-between gap-3 rounded-lg border border-outline-variant bg-surface-container px-3 py-2 text-left text-body-sm text-on-surface transition-colors hover:border-primary/50 focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:border-primary-dark/60 dark:focus:ring-primary-dark/20"
      :class="buttonClass"
      :disabled="disabled"
      :aria-expanded="open"
      :title="buttonTitle"
      @click="toggleOpen"
    >
      <span class="flex min-w-0 items-center gap-2">
        <CalendarDays :size="15" class="shrink-0 text-on-surface-variant dark:text-zinc-500" />
        <span
          class="min-w-0 truncate"
          :class="selectedDate ? 'text-on-surface dark:text-zinc-100' : 'text-on-surface-variant dark:text-zinc-500'"
        >
          {{ displayLabel }}
        </span>
      </span>
      <span class="flex shrink-0 items-center gap-2">
        <span class="rounded-full bg-surface-container-low px-2 py-1 text-[11px] text-on-surface-variant dark:bg-zinc-900 dark:text-zinc-400">
          {{ availableDates.length }} 天
        </span>
        <ChevronDown
          :size="16"
          class="text-on-surface-variant transition-transform duration-200 dark:text-zinc-500"
          :class="open ? 'rotate-180' : ''"
        />
      </span>
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
        class="absolute left-0 top-[calc(100%+6px)] z-50 w-[320px] max-w-[min(320px,calc(100vw-32px))] overflow-hidden rounded-2xl border border-outline-variant bg-surface-container-lowest shadow-[0_20px_42px_rgba(15,23,42,0.18)] dark:border-zinc-700 dark:bg-zinc-900"
      >
        <div class="border-b border-outline-variant px-4 py-3 dark:border-zinc-800">
          <div class="flex items-center justify-between gap-3">
            <div>
              <div class="text-[11px] uppercase tracking-[0.14em] text-on-surface-variant dark:text-zinc-500">消息日期</div>
              <div class="mt-1 text-body-sm font-semibold text-on-surface dark:text-zinc-100">{{ monthLabel }}</div>
            </div>
            <div class="flex items-center gap-1">
              <button
                type="button"
                class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-35 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                :disabled="!canMovePreviousMonth"
                title="上个月"
                @click="showPreviousMonth"
              >
                <ChevronLeft :size="16" />
              </button>
              <button
                type="button"
                class="inline-flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-35 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                :disabled="!canMoveNextMonth"
                title="下个月"
                @click="showNextMonth"
              >
                <ChevronRight :size="16" />
              </button>
            </div>
          </div>
          <div class="mt-2 flex items-center justify-between gap-3 text-[11px] text-on-surface-variant dark:text-zinc-500">
            <span>仅可点击存在聊天记录的日期</span>
            <span>{{ availableDates.length }} 个可用日期</span>
          </div>
        </div>

        <div class="px-4 pb-4 pt-3">
          <div class="grid grid-cols-7 gap-1 text-center text-[11px] text-on-surface-variant dark:text-zinc-500">
            <span v-for="weekLabel in weekLabels" :key="weekLabel" class="py-1">{{ weekLabel }}</span>
          </div>

          <div class="mt-2 grid grid-cols-7 gap-1">
            <button
              v-for="cell in calendarCells"
              :key="cell.dateKey"
              type="button"
              class="flex h-10 flex-col items-center justify-center rounded-xl border text-[13px] transition-colors focus:outline-none focus:ring-2 focus:ring-primary/20 disabled:cursor-not-allowed dark:focus:ring-primary-dark/20"
              :class="cellClass(cell)"
              :disabled="!cell.enabled"
              @click="selectDate(cell.dateKey)"
            >
              <span>{{ cell.day }}</span>
              <span
                class="mt-1 h-1.5 w-1.5 rounded-full"
                :class="cell.selected
                  ? 'bg-slate-950 dark:bg-zinc-950'
                  : (cell.enabled ? 'bg-primary dark:bg-primary-dark' : 'bg-transparent')"
              ></span>
            </button>
          </div>

          <div class="mt-3 flex items-center justify-between gap-3 border-t border-outline-variant pt-3 text-[11px] dark:border-zinc-800">
            <button
              type="button"
              class="rounded-full bg-surface-container px-3 py-1.5 text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-45 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700 dark:hover:text-zinc-100"
              :disabled="!latestAvailableDate"
              @click="selectLatestDate"
            >
              跳到最新日期
            </button>
            <span class="text-on-surface-variant dark:text-zinc-500">
              {{ selectedDate ? `当前 ${selectedDate}` : '尚未选择日期' }}
            </span>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { CalendarDays, ChevronDown, ChevronLeft, ChevronRight } from 'lucide-vue-next'

interface CalendarCell {
  dateKey: string
  day: number
  inCurrentMonth: boolean
  enabled: boolean
  selected: boolean
  today: boolean
}

const props = withDefaults(defineProps<{
  modelValue: string | null | undefined
  availableDates: string[]
  placeholder?: string
  disabled?: boolean
  wrapperClass?: string
  buttonClass?: string
}>(), {
  placeholder: '选择日期',
  disabled: false,
  wrapperClass: '',
  buttonClass: '',
})

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: [value: string]
}>()

const rootRef = ref<HTMLElement | null>(null)
const open = ref(false)
const visibleMonth = ref('')

const weekLabels = ['一', '二', '三', '四', '五', '六', '日']
const availableDateSet = computed(() => new Set(props.availableDates))
const availableDates = computed(() => [...props.availableDates].sort())
const earliestAvailableDate = computed(() => availableDates.value[0] || '')
const latestAvailableDate = computed(() => availableDates.value[availableDates.value.length - 1] || '')
const selectedDate = computed(() => props.modelValue?.trim() || '')
const buttonTitle = computed(() => selectedDate.value || props.placeholder)
const displayLabel = computed(() => {
  if (selectedDate.value) {
    return formatDateLabel(selectedDate.value)
  }
  if (availableDates.value.length === 0) {
    return '暂无记录日期'
  }
  return props.placeholder
})
const monthLabel = computed(() => {
  if (!visibleMonth.value) return '暂无日期'
  const [year, month] = visibleMonth.value.split('-')
  return `${year} 年 ${month} 月`
})
const minimumMonth = computed(() => normalizeMonth(earliestAvailableDate.value))
const maximumMonth = computed(() => normalizeMonth(latestAvailableDate.value))
const canMovePreviousMonth = computed(() => Boolean(minimumMonth.value && visibleMonth.value > minimumMonth.value))
const canMoveNextMonth = computed(() => Boolean(maximumMonth.value && visibleMonth.value < maximumMonth.value))
const calendarCells = computed<CalendarCell[]>(() => {
  if (!visibleMonth.value) return []

  const [yearText, monthText] = visibleMonth.value.split('-')
  const year = Number(yearText)
  const month = Number(monthText)
  if (!year || !month) return []

  const monthStart = new Date(year, month - 1, 1)
  const offset = (monthStart.getDay() + 6) % 7
  const gridStart = new Date(year, month - 1, 1 - offset)
  const todayKey = formatDateKey(new Date())
  const cells: CalendarCell[] = []

  for (let index = 0; index < 42; index += 1) {
    const current = new Date(gridStart)
    current.setDate(gridStart.getDate() + index)
    const dateKey = formatDateKey(current)
    cells.push({
      dateKey,
      day: current.getDate(),
      inCurrentMonth: current.getMonth() === month - 1,
      enabled: availableDateSet.value.has(dateKey),
      selected: dateKey === selectedDate.value,
      today: dateKey === todayKey,
    })
  }
  return cells
})

watch(
  () => [props.modelValue, props.availableDates.join('|')],
  () => {
    const anchorDate = selectedDate.value || latestAvailableDate.value || formatDateKey(new Date())
    visibleMonth.value = normalizeMonth(anchorDate)
  },
  { immediate: true },
)

function toggleOpen() {
  if (props.disabled) return
  open.value = !open.value
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

function normalizeMonth(dateKey: string) {
  return dateKey ? dateKey.slice(0, 7) : ''
}

function formatDateKey(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function formatDateLabel(dateKey: string) {
  return dateKey.split('-').join(' / ')
}

function shiftMonth(monthKey: string, offset: number) {
  const [yearText, monthText] = monthKey.split('-')
  const year = Number(yearText)
  const month = Number(monthText)
  const next = new Date(year, month - 1 + offset, 1)
  return `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`
}

function showPreviousMonth() {
  if (!canMovePreviousMonth.value) return
  visibleMonth.value = shiftMonth(visibleMonth.value, -1)
}

function showNextMonth() {
  if (!canMoveNextMonth.value) return
  visibleMonth.value = shiftMonth(visibleMonth.value, 1)
}

function selectDate(dateKey: string) {
  if (!availableDateSet.value.has(dateKey)) return
  emit('update:modelValue', dateKey)
  emit('change', dateKey)
  open.value = false
}

function selectLatestDate() {
  if (!latestAvailableDate.value) return
  selectDate(latestAvailableDate.value)
}

function cellClass(cell: CalendarCell) {
  if (cell.selected) {
    return 'border-primary bg-primary text-white shadow-[0_12px_24px_rgba(37,99,235,0.24)] dark:border-primary-dark dark:bg-primary-dark dark:text-slate-950'
  }
  if (cell.enabled) {
    return [
      'border-primary/16 bg-primary/8 text-on-surface hover:border-primary/35 hover:bg-primary/12 dark:border-primary-dark/18 dark:bg-primary-dark/10 dark:text-zinc-100 dark:hover:border-primary-dark/35 dark:hover:bg-primary-dark/16',
      cell.today ? 'ring-1 ring-primary/25 dark:ring-primary-dark/28' : '',
    ].join(' ')
  }
  return cell.inCurrentMonth
    ? 'border-transparent bg-surface-container-low text-on-surface-variant/55 dark:bg-zinc-800/45 dark:text-zinc-600'
    : 'border-transparent bg-transparent text-on-surface-variant/35 dark:text-zinc-700'
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
