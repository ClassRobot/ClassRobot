<template>
  <div class="flex flex-col gap-6">
    <div>
      <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">运维调试</h1>
      <p class="font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500 mt-1">日志查看、自动化诊断与调试工具</p>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Log viewer -->
      <div class="lg:col-span-2 rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 flex flex-col min-h-[400px]">
        <div class="flex items-center justify-between px-4 py-3 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50 rounded-t-xl">
          <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">日志查看</h2>
          <AppSelect
            v-model="activeLog"
            :options="logOptions"
            wrapper-class="w-[260px]"
            @change="readLog"
          />
        </div>
        <div class="flex-1 overflow-y-auto p-4 bg-code dark:bg-zinc-800 font-code-block text-code-block text-on-surface dark:text-zinc-300">
          <pre v-if="logContent" class="whitespace-pre-wrap"><code>{{ logContent }}</code></pre>
          <div v-else class="text-on-surface-variant dark:text-zinc-500 flex items-center justify-center h-full">请选择一个日志文件查看</div>
        </div>
      </div>

      <!-- Actions -->
      <div class="rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 flex flex-col">
        <div class="px-4 py-3 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50 rounded-t-xl">
          <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">自动化动作</h2>
        </div>
        <div class="flex-1 overflow-y-auto divide-y divide-outline-variant dark:divide-zinc-800">
          <div v-for="action in actions" :key="action.action_id" class="px-4 py-3 flex items-center justify-between">
            <div>
              <div class="font-body-sm text-body-sm font-medium text-on-surface dark:text-zinc-200">{{ action.title }}</div>
              <div class="flex items-center gap-2 mt-0.5">
                <span
                  class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase"
                  :class="action.risk === 'low'
                    ? 'bg-primary/10 dark:bg-emerald-500/10 text-primary dark:text-emerald-400'
                    : 'bg-warning/10 dark:bg-amber-500/10 text-warning dark:text-amber-400'"
                >{{ action.risk === 'low' ? '低风险' : '中风险' }}</span>
                <span v-if="lastResults[action.action_id]" class="text-[11px]" :class="lastResults[action.action_id]?.status === 'completed' ? 'text-primary dark:text-emerald-400' : 'text-error dark:text-red-400'">
                  {{ lastResults[action.action_id]?.status === 'completed' ? '成功' : '失败' }} ({{ lastResults[action.action_id]?.duration_ms }}ms)
                </span>
              </div>
            </div>
            <button
              @click="runAction(action.action_id)"
              :disabled="running === action.action_id"
              class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 border border-outline-variant dark:border-zinc-700 text-on-surface dark:text-zinc-200 font-body-sm hover:bg-surface-container dark:hover:bg-zinc-800 disabled:opacity-50 transition-colors"
            >
              <Loader2 v-if="running === action.action_id" :size="14" class="animate-spin" />
              <Play v-else :size="14" />
              执行
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchLogs, readLog as readLogApi } from '@/api/logs'
import { fetchActions, runAction as runOpAction } from '@/api/operations'
import type { LogFileItem, ActionItem, ActionRunResult } from '@/types/api'
import { Play, Loader2 } from 'lucide-vue-next'
import AppSelect from '@/components/AppSelect.vue'

const logFiles = ref<LogFileItem[]>([])
const activeLog = ref('')
const logContent = ref('')
const actions = ref<ActionItem[]>([])
const running = ref('')
const lastResults = ref<Record<string, ActionRunResult>>({})
const logOptions = ref([{ label: '选择日志文件', value: '' }])

onMounted(async () => {
  try {
    logFiles.value = (await fetchLogs()).items
    logOptions.value = [
      { label: '选择日志文件', value: '' },
      ...logFiles.value.map((log) => ({
        label: log.relative_path || log.name,
        value: log.path,
      })),
    ]
  } catch { /* */ }
  try { actions.value = (await fetchActions()).items } catch { /* */ }
})

async function readLog() {
  if (!activeLog.value) return
  try {
    const result = await readLogApi(activeLog.value, 0, 1000)
    logContent.value = result.lines?.join('\n') || ''
  } catch { logContent.value = '读取失败' }
}

async function runAction(id: string) {
  running.value = id
  try {
    const result = await runOpAction(id)
    lastResults.value[id] = result
  } catch (e: unknown) {
    lastResults.value[id] = {
      action_id: id, status: 'failed', exit_code: 1, duration_ms: 0,
      error: (e as Error).message || '执行失败', result: {},
    }
  }
  running.value = ''
}
</script>
