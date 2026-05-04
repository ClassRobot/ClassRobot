<template>
  <div class="flex flex-col gap-6">
    <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">运维调试</h1>
        <p class="mt-1 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">
          实时日志、自动化动作、受控终端与管理操作审计
        </p>
      </div>
      <button
        type="button"
        class="inline-flex h-9 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 font-body-sm text-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
        @click="reloadAll"
      >
        <RefreshCw :size="15" :class="{ 'animate-spin': loading }" />
        刷新全部
      </button>
    </div>

    <div class="grid grid-cols-1 gap-6 2xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
      <section class="flex min-h-[460px] flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex flex-col gap-3 border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/50 xl:flex-row xl:items-center xl:justify-between">
          <div class="flex items-center gap-2">
            <ScrollText :size="18" class="text-primary dark:text-primary-dark" />
            <div>
              <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">系统工作日志</h2>
              <p class="text-body-sm text-on-surface-variant dark:text-zinc-500">
                {{ logMeta }}
              </p>
            </div>
          </div>
          <div class="flex flex-wrap items-center gap-2">
            <AppSelect
              v-model="activeLog"
              :options="logOptions"
              wrapper-class="w-[280px]"
              @change="() => refreshLogTail()"
            />
            <button
              type="button"
              class="inline-flex h-9 items-center gap-2 rounded-lg border px-3 font-body-sm text-body-sm transition-colors"
              :class="liveLog
                ? 'border-primary/30 bg-primary/10 text-primary dark:border-primary-dark/30 dark:bg-primary-dark/10 dark:text-primary-dark'
                : 'border-outline-variant bg-surface-container-lowest text-on-surface dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200'"
              @click="liveLog = !liveLog"
            >
              <Activity :size="14" />
              {{ liveLog ? '实时跟随' : '手动刷新' }}
            </button>
            <button
              type="button"
              class="inline-flex h-9 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 font-body-sm text-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
              @click="() => refreshLogTail()"
            >
              <RefreshCw :size="14" :class="{ 'animate-spin': logLoading }" />
              刷新
            </button>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto bg-code p-4 font-code-block text-code-block text-on-surface dark:bg-zinc-950 dark:text-zinc-300">
          <pre v-if="logContent" class="whitespace-pre-wrap"><code>{{ logContent }}</code></pre>
          <div v-else class="flex h-full items-center justify-center text-center text-on-surface-variant dark:text-zinc-500">
            请选择一个日志文件，或等待系统生成日志
          </div>
        </div>
      </section>

      <section class="flex min-h-[460px] flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div class="flex items-center gap-2">
            <Terminal :size="18" class="text-primary dark:text-primary-dark" />
            <div>
              <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">受控终端</h2>
              <p class="text-body-sm text-on-surface-variant dark:text-zinc-500">仅开放预设命令，执行结果会写入审计日志</p>
            </div>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto p-3">
          <div
            v-for="command in terminalCommands"
            :key="command.command_id"
            class="mb-2 rounded-lg border border-outline-variant bg-surface-container-low p-3 dark:border-zinc-800 dark:bg-zinc-800/55"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <span class="truncate font-body-sm text-body-sm font-medium text-on-surface dark:text-zinc-200">{{ command.title }}</span>
                  <span class="shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase" :class="riskClass(command.risk)">
                    {{ command.risk === 'low' ? '低风险' : '中风险' }}
                  </span>
                </div>
                <p class="mt-1 text-body-sm text-on-surface-variant dark:text-zinc-500">{{ command.description }}</p>
                <p class="mt-2 truncate font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-400">{{ command.command }}</p>
              </div>
              <button
                type="button"
                class="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-lg border border-outline-variant bg-surface-container-lowest px-2.5 font-body-sm text-body-sm text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
                :disabled="terminalRunning === command.command_id || !command.available"
                @click="runTerminal(command.command_id)"
              >
                <Loader2 v-if="terminalRunning === command.command_id" :size="14" class="animate-spin" />
                <Play v-else :size="14" />
                执行
              </button>
            </div>
          </div>
          <div v-if="terminalCommands.length === 0" class="p-8 text-center text-body-sm text-on-surface-variant dark:text-zinc-500">
            暂无可用终端命令
          </div>
        </div>
        <div class="max-h-[220px] overflow-y-auto border-t border-outline-variant bg-code p-3 font-code-block text-code-block text-on-surface dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-300">
          <pre v-if="terminalOutput" class="whitespace-pre-wrap"><code>{{ terminalOutput }}</code></pre>
          <div v-else class="text-on-surface-variant dark:text-zinc-500">终端输出会显示在这里</div>
        </div>
      </section>
    </div>

    <div class="grid grid-cols-1 gap-6 xl:grid-cols-2">
      <section class="rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/50">
          <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">自动化动作</h2>
        </div>
        <div class="divide-y divide-outline-variant dark:divide-zinc-800">
          <div v-for="action in actions" :key="action.action_id" class="flex items-center justify-between gap-3 px-4 py-3">
            <div>
              <div class="font-body-sm text-body-sm font-medium text-on-surface dark:text-zinc-200">{{ action.title }}</div>
              <div class="mt-0.5 flex items-center gap-2">
                <span class="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-bold uppercase" :class="riskClass(action.risk)">
                  {{ action.risk === 'low' ? '低风险' : '中风险' }}
                </span>
                <span
                  v-if="lastResults[action.action_id]"
                  class="text-[11px]"
                  :class="lastResults[action.action_id]?.status === 'completed' ? 'text-primary dark:text-emerald-400' : 'text-error dark:text-red-400'"
                >
                  {{ lastResults[action.action_id]?.status === 'completed' ? '成功' : '失败' }} ({{ lastResults[action.action_id]?.duration_ms }}ms)
                </span>
              </div>
            </div>
            <button
              type="button"
              class="flex items-center gap-1.5 rounded-lg border border-outline-variant px-3 py-1.5 font-body-sm text-body-sm text-on-surface transition-colors hover:bg-surface-container disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
              :disabled="running === action.action_id"
              @click="runAutomation(action.action_id)"
            >
              <Loader2 v-if="running === action.action_id" :size="14" class="animate-spin" />
              <Play v-else :size="14" />
              执行
            </button>
          </div>
        </div>
      </section>

      <section class="rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex flex-col gap-3 border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/50 md:flex-row md:items-center md:justify-between">
          <div class="flex items-center gap-2">
            <History :size="18" class="text-primary dark:text-primary-dark" />
            <div>
              <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">管理操作日志</h2>
              <p class="text-body-sm text-on-surface-variant dark:text-zinc-500">最近 {{ auditItems.length }} 条</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <AppSelect v-model="auditFilter" :options="auditFilterOptions" wrapper-class="w-[160px]" @change="() => loadAudit()" />
            <button
              type="button"
              class="inline-flex h-9 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 font-body-sm text-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
              @click="() => loadAudit()"
            >
              <RefreshCw :size="14" :class="{ 'animate-spin': auditLoading }" />
              刷新
            </button>
          </div>
        </div>
        <div class="max-h-[420px] overflow-y-auto divide-y divide-outline-variant dark:divide-zinc-800">
          <div v-for="item in auditItems" :key="`${item.timestamp}-${item.event_type}-${item.action}`" class="px-4 py-3">
            <div class="flex items-center justify-between gap-3">
              <div class="min-w-0">
                <div class="flex items-center gap-2">
                  <span class="rounded-full bg-surface-container px-2 py-0.5 text-[11px] text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400">{{ item.event_type }}</span>
                  <span class="truncate font-body-sm text-body-sm font-medium text-on-surface dark:text-zinc-200">{{ item.action }}</span>
                </div>
                <p class="mt-1 font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500">{{ formatTime(item.timestamp) }} · {{ item.session_id || 'no-session' }}</p>
              </div>
              <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px]" :class="item.status === 'completed' ? 'bg-primary/10 text-primary dark:bg-emerald-500/10 dark:text-emerald-400' : 'bg-error/10 text-error dark:bg-red-500/10 dark:text-red-400'">
                {{ item.status }}
              </span>
            </div>
            <pre v-if="Object.keys(item.detail || {}).length" class="mt-2 overflow-x-auto rounded-md bg-code p-2 font-code-inline text-code-inline text-on-surface-variant dark:bg-zinc-950 dark:text-zinc-400"><code>{{ stringifyDetail(item.detail) }}</code></pre>
          </div>
          <div v-if="auditItems.length === 0" class="p-8 text-center text-body-sm text-on-surface-variant dark:text-zinc-500">
            暂无操作日志
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Activity, History, Loader2, Play, RefreshCw, ScrollText, Terminal } from 'lucide-vue-next'
import { fetchLogs, tailLog } from '@/api/logs'
import {
  fetchActions,
  fetchAuditLog,
  fetchTerminalCommands,
  runAction as runOpAction,
  runTerminalCommand,
} from '@/api/operations'
import type {
  ActionItem,
  ActionRunResult,
  AuditLogItem,
  LogFileItem,
  TerminalCommandItem,
  TerminalRunResult,
} from '@/types/api'
import AppSelect from '@/components/AppSelect.vue'

const logFiles = ref<LogFileItem[]>([])
const activeLog = ref('')
const logContent = ref('')
const logTotalLines = ref(0)
const liveLog = ref(true)
const logLoading = ref(false)
const actions = ref<ActionItem[]>([])
const running = ref('')
const lastResults = ref<Record<string, ActionRunResult>>({})
const terminalCommands = ref<TerminalCommandItem[]>([])
const terminalRunning = ref('')
const terminalResult = ref<TerminalRunResult | null>(null)
const auditItems = ref<AuditLogItem[]>([])
const auditFilter = ref('')
const auditLoading = ref(false)
const loading = ref(false)
let logTimer: number | undefined
let auditTimer: number | undefined

const logOptions = computed(() => [
  { label: '选择日志文件', value: '' },
  ...logFiles.value.map((log) => ({
    label: log.relative_path || log.name,
    value: log.path,
  })),
])

const auditFilterOptions = [
  { label: '全部', value: '' },
  { label: '终端', value: 'terminal' },
  { label: '动作', value: 'operation' },
  { label: '设置', value: 'settings' },
  { label: '数据库', value: 'databases' },
  { label: '用户', value: 'users' },
]

const logMeta = computed(() => activeLog.value ? `${logTotalLines.value} 行 · ${liveLog.value ? '自动跟随' : '手动'}` : '未选择日志')
const terminalOutput = computed(() => {
  if (!terminalResult.value) return ''
  const result = terminalResult.value
  return [
    `$ ${result.command}`,
    `cwd: ${result.cwd}`,
    `status: ${result.status} · exit ${result.exit_code} · ${result.duration_ms}ms`,
    result.error ? `error: ${result.error}` : '',
    result.stdout ? `\nstdout:\n${result.stdout}` : '',
    result.stderr ? `\nstderr:\n${result.stderr}` : '',
  ].filter(Boolean).join('\n')
})

onMounted(async () => {
  await reloadAll()
  logTimer = window.setInterval(() => {
    if (liveLog.value && activeLog.value) refreshLogTail(true)
  }, 3000)
  auditTimer = window.setInterval(() => loadAudit(true), 5000)
})

onBeforeUnmount(() => {
  if (logTimer) window.clearInterval(logTimer)
  if (auditTimer) window.clearInterval(auditTimer)
})

async function reloadAll() {
  loading.value = true
  try {
    await Promise.all([
      loadLogs(),
      loadActions(),
      loadTerminalCommands(),
      loadAudit(true),
    ])
  } finally {
    loading.value = false
  }
}

async function loadLogs() {
  try {
    logFiles.value = (await fetchLogs()).items
    if (!activeLog.value && logFiles.value.length > 0) {
      const latest = [...logFiles.value].sort((a, b) => b.updated_at - a.updated_at)[0]
      activeLog.value = latest.path
      await refreshLogTail(true)
    }
  } catch { /* keep old logs */ }
}

async function refreshLogTail(silent = false) {
  if (!activeLog.value) return
  if (!silent) logLoading.value = true
  try {
    const result = await tailLog(activeLog.value, 500)
    logTotalLines.value = result.total_lines
    logContent.value = result.lines?.join('\n') || ''
  } catch {
    if (!silent) logContent.value = '读取失败'
  } finally {
    if (!silent) logLoading.value = false
  }
}

async function loadActions() {
  try {
    actions.value = (await fetchActions()).items
  } catch { /* keep old actions */ }
}

async function loadTerminalCommands() {
  try {
    terminalCommands.value = (await fetchTerminalCommands()).items
  } catch { /* keep old commands */ }
}

async function loadAudit(silent = false) {
  if (!silent) auditLoading.value = true
  try {
    const response = await fetchAuditLog({
      event_type: auditFilter.value || undefined,
      limit: 80,
    })
    auditItems.value = response.items
  } catch { /* keep old audit */ }
  finally {
    if (!silent) auditLoading.value = false
  }
}

async function runAutomation(id: string) {
  running.value = id
  try {
    const result = await runOpAction(id)
    lastResults.value[id] = result
    await loadAudit(true)
  } catch (error: unknown) {
    lastResults.value[id] = {
      action_id: id,
      status: 'failed',
      exit_code: 1,
      duration_ms: 0,
      error: error instanceof Error ? error.message : '执行失败',
      result: {},
    }
  } finally {
    running.value = ''
  }
}

async function runTerminal(id: string) {
  terminalRunning.value = id
  try {
    terminalResult.value = await runTerminalCommand(id)
    await loadAudit(true)
  } finally {
    terminalRunning.value = ''
  }
}

function riskClass(risk: 'low' | 'medium') {
  return risk === 'low'
    ? 'bg-primary/10 text-primary dark:bg-emerald-500/10 dark:text-emerald-400'
    : 'bg-warning/10 text-warning dark:bg-amber-500/10 dark:text-amber-400'
}

function formatTime(value: string) {
  return new Date(value).toLocaleString()
}

function stringifyDetail(detail: Record<string, unknown>) {
  return JSON.stringify(detail, null, 2)
}
</script>
