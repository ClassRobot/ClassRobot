<template>
  <div class="flex h-[calc(100vh-96px)] min-h-0 flex-col gap-4 overflow-hidden">
    <div class="flex shrink-0 flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">运维调试</h1>
        <p class="mt-1 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">
          左侧观察日志，右侧直接操作服务器终端；自动化脚本已拆分到独立页面
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <RouterLink
          to="/automation-scripts"
          class="tool-button dark:!border-zinc-800 dark:!bg-zinc-900 dark:!text-zinc-100 dark:hover:!bg-zinc-800"
        >
          <FileCode2 :size="15" />
          脚本管理
        </RouterLink>
        <button type="button" class="tool-button dark:!border-zinc-800 dark:!bg-zinc-900 dark:!text-zinc-100 dark:hover:!bg-zinc-800" @click="reloadAll">
          <RefreshCw :size="15" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
      </div>
    </div>

    <div class="grid min-h-0 flex-1 grid-rows-[260px_minmax(0,1fr)] gap-4 lg:grid-cols-[380px_minmax(0,1fr)] lg:grid-rows-1 2xl:grid-cols-[420px_minmax(0,1fr)]">
      <section class="panel-frame dark:!border-zinc-800 dark:!bg-zinc-900">
        <div class="panel-header dark:!border-zinc-800 dark:!bg-zinc-900/95">
          <div class="flex min-w-0 items-center gap-2">
            <ScrollText v-if="leftPanel === 'logs'" :size="18" class="shrink-0 text-primary dark:text-primary-dark" />
            <History v-else :size="18" class="shrink-0 text-primary dark:text-primary-dark" />
            <div class="min-w-0">
              <h2 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">
                {{ leftPanel === 'logs' ? '系统工作日志' : '管理操作日志' }}
              </h2>
              <p class="truncate text-body-sm text-on-surface-variant dark:text-zinc-500">
                {{ leftPanel === 'logs' ? logMeta : `最近 ${auditItems.length} 条` }}
              </p>
            </div>
          </div>
          <div class="flex shrink-0 rounded-lg border border-outline-variant bg-surface-container p-0.5 dark:border-zinc-700 dark:bg-zinc-800">
            <button
              type="button"
              class="h-8 rounded-md px-3 text-body-sm transition-colors"
              :class="leftPanel === 'logs' ? activeSegmentClass : inactiveSegmentClass"
              @click="leftPanel = 'logs'"
            >
              日志
            </button>
            <button
              type="button"
              class="h-8 rounded-md px-3 text-body-sm transition-colors"
              :class="leftPanel === 'audit' ? activeSegmentClass : inactiveSegmentClass"
              @click="leftPanel = 'audit'"
            >
              审计
            </button>
          </div>
        </div>

        <template v-if="leftPanel === 'logs'">
          <div class="grid shrink-0 gap-2 border-b border-outline-variant p-3 dark:border-zinc-800">
            <AppSelect
              v-model="activeLog"
              :options="logOptions"
              wrapper-class="w-full min-w-0"
              button-class="font-code-inline text-code-inline"
              @change="() => refreshLogTail()"
            />
            <div class="flex items-center gap-2">
              <button
                type="button"
                class="inline-flex h-9 flex-1 items-center justify-center gap-2 rounded-lg border px-3 font-body-sm text-body-sm transition-colors"
                :class="liveLog
                  ? 'border-primary/30 bg-primary/10 text-primary dark:border-primary-dark/30 dark:bg-primary-dark/10 dark:text-primary-dark'
                  : 'border-outline-variant bg-surface-container-lowest text-on-surface dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200'"
                @click="liveLog = !liveLog"
              >
                <Activity :size="14" />
                {{ liveLog ? '实时跟随' : '手动刷新' }}
              </button>
              <button type="button" class="tool-button dark:!border-zinc-800 dark:!bg-zinc-900 dark:!text-zinc-100 dark:hover:!bg-zinc-800" @click="() => refreshLogTail()">
                <RefreshCw :size="14" :class="{ 'animate-spin': logLoading }" />
                刷新
              </button>
            </div>
          </div>
          <div class="min-h-0 flex-1 overflow-y-auto bg-code p-4 font-code-block text-code-block text-on-surface dark:bg-zinc-950 dark:text-zinc-300">
            <pre v-if="logContent" class="whitespace-pre-wrap"><code>{{ logContent }}</code></pre>
            <div v-else class="flex h-full items-center justify-center text-center text-on-surface-variant dark:text-zinc-500">
              请选择一个日志文件，或等待系统生成日志
            </div>
          </div>
        </template>

        <template v-else>
          <div class="flex shrink-0 items-center gap-2 border-b border-outline-variant p-3 dark:border-zinc-800">
            <AppSelect v-model="auditFilter" :options="auditFilterOptions" wrapper-class="w-[180px]" @change="() => loadAudit()" />
            <button type="button" class="tool-button ml-auto dark:!border-zinc-800 dark:!bg-zinc-900 dark:!text-zinc-100 dark:hover:!bg-zinc-800" @click="() => loadAudit()">
              <RefreshCw :size="14" :class="{ 'animate-spin': auditLoading }" />
              刷新
            </button>
          </div>
          <div class="min-h-0 flex-1 overflow-y-auto divide-y divide-outline-variant dark:divide-zinc-800">
            <div v-for="item in auditItems" :key="`${item.timestamp}-${item.event_type}-${item.action}`" class="px-4 py-3">
              <div class="flex items-start justify-between gap-3">
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
              <pre v-if="Object.keys(item.detail || {}).length" class="mt-2 max-h-28 overflow-auto rounded-md bg-code p-2 font-code-inline text-code-inline text-on-surface-variant dark:bg-zinc-950 dark:text-zinc-400"><code>{{ stringifyDetail(item.detail) }}</code></pre>
            </div>
            <div v-if="auditItems.length === 0" class="p-8 text-center text-body-sm text-on-surface-variant dark:text-zinc-500">
              暂无操作日志
            </div>
          </div>
        </template>
      </section>

      <section class="terminal-shell">
        <div class="terminal-titlebar">
          <div class="min-w-0">
            <div class="font-body-sm text-body-sm font-semibold text-zinc-50">服务器终端</div>
            <div class="truncate font-code-inline text-[11px] text-slate-400">{{ linuxCwd(terminalCwd) }}</div>
          </div>
          <div class="flex items-center gap-2">
            <span class="hidden rounded-md border border-slate-700/70 bg-slate-900/65 px-2 py-1 font-code-inline text-[11px] text-slate-400 sm:inline-flex">timeout {{ terminalTimeout }}s</span>
            <button type="button" class="terminal-action" @click="clearTerminal">clear</button>
          </div>
        </div>

        <div
          ref="terminalScrollRef"
          class="terminal-body"
          @click="handleTerminalBodyClick"
        >
          <div v-if="terminalHistory.length === 0" class="mb-4 text-zinc-500">
            服务器终端已连接。输入命令后按 Enter 执行。
          </div>
          <div v-for="entry in terminalHistory" :key="entry.id" class="mb-4">
            <div class="flex items-start gap-2 text-[#33ff77]">
              <span class="shrink-0">{{ linuxPrompt(entry.cwd) }}</span>
              <span class="break-all text-zinc-100">{{ entry.command }}</span>
            </div>
            <pre v-if="entry.stdout" class="mt-1 whitespace-pre-wrap text-zinc-200"><code>{{ entry.stdout }}</code></pre>
            <pre v-if="entry.stderr" class="mt-1 whitespace-pre-wrap text-red-300"><code>{{ entry.stderr }}</code></pre>
            <div v-if="entry.error" class="mt-1 text-red-300">{{ entry.error }}</div>
            <div v-if="entry.running" class="mt-1 text-zinc-500">running...</div>
            <div v-else-if="entry.exit_code !== undefined" class="mt-1 text-[11px]" :class="entry.exit_code === 0 ? 'text-zinc-600' : 'text-red-400'">
              exit {{ entry.exit_code }} · {{ entry.duration_ms }}ms
            </div>
          </div>

          <form class="terminal-line" @submit.prevent="runDirectTerminal">
            <span class="shrink-0 text-[#33ff77]">{{ terminalPrompt }}</span>
            <input
              ref="terminalInputRef"
              v-model="terminalInput"
              class="terminal-input"
              autocomplete="off"
              spellcheck="false"
              :disabled="directRunning"
              @keydown="handleTerminalKeydown"
            />
            <Loader2 v-if="directRunning" :size="14" class="shrink-0 animate-spin text-[#33ff77]" />
          </form>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import {
  Activity,
  FileCode2,
  History,
  Loader2,
  RefreshCw,
  ScrollText,
} from 'lucide-vue-next'
import { fetchLogs, tailLog } from '@/api/logs'
import {
  executeTerminalCommand,
  fetchAuditLog,
} from '@/api/operations'
import type {
  AuditLogItem,
  LogFileItem,
} from '@/types/api'
import AppSelect from '@/components/AppSelect.vue'

interface TerminalEntry {
  id: string
  command: string
  cwd: string
  stdout?: string
  stderr?: string
  error?: string
  exit_code?: number
  duration_ms?: number
  running?: boolean
}

const leftPanel = ref<'logs' | 'audit'>('logs')
const logFiles = ref<LogFileItem[]>([])
const activeLog = ref('')
const logContent = ref('')
const logTotalLines = ref(0)
const liveLog = ref(true)
const logLoading = ref(false)
const directRunning = ref(false)
const terminalInput = ref('')
const terminalCwd = ref('')
const terminalTimeout = ref(300)
const terminalHistory = ref<TerminalEntry[]>([])
const commandHistory = ref<string[]>([])
const commandHistoryIndex = ref(-1)
const terminalScrollRef = ref<HTMLElement | null>(null)
const terminalInputRef = ref<HTMLInputElement | null>(null)
const auditItems = ref<AuditLogItem[]>([])
const auditFilter = ref('')
const auditLoading = ref(false)
const loading = ref(false)
let logTimer: number | undefined
let auditTimer: number | undefined

const activeSegmentClass = 'bg-surface-container-lowest text-primary shadow-sm dark:bg-zinc-900 dark:text-primary-dark'
const inactiveSegmentClass = 'text-on-surface-variant dark:text-zinc-400 hover:text-on-surface dark:hover:text-zinc-100'

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
  { label: '脚本', value: 'script' },
  { label: '设置', value: 'settings' },
  { label: '数据库', value: 'databases' },
  { label: '用户', value: 'users' },
]

const logMeta = computed(() => activeLog.value ? `${logTotalLines.value} 行 · ${liveLog.value ? '自动跟随' : '手动'}` : '未选择日志')
const terminalPrompt = computed(() => linuxPrompt(terminalCwd.value))

onMounted(async () => {
  await reloadAll()
  await focusTerminalInput()
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
    const result = await tailLog(activeLog.value, 240)
    logTotalLines.value = result.total_lines
    logContent.value = result.lines?.join('\n') || ''
  } catch {
    if (!silent) logContent.value = '读取失败'
  } finally {
    if (!silent) logLoading.value = false
  }
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

async function runDirectTerminal() {
  const command = terminalInput.value.trim()
  if (!command) return
  if (['clear', 'cls'].includes(command.toLowerCase())) {
    clearTerminal()
    terminalInput.value = ''
    rememberCommand(command)
    return
  }

  rememberCommand(command)
  const entry: TerminalEntry = {
    id: `${Date.now()}-${Math.random()}`,
    command,
    cwd: terminalCwd.value || 'project',
    running: true,
  }
  terminalHistory.value.push(entry)
  terminalInput.value = ''
  directRunning.value = true
  await scrollTerminalToBottom()
  try {
    const result = await executeTerminalCommand({
      command,
      cwd: terminalCwd.value || undefined,
      timeout: Number(terminalTimeout.value) || 300,
    })
    terminalCwd.value = result.cwd
    Object.assign(entry, {
      stdout: result.stdout,
      stderr: result.stderr,
      error: result.error,
      exit_code: result.exit_code,
      duration_ms: result.duration_ms,
      running: false,
    })
    await loadAudit(true)
  } catch (error) {
    Object.assign(entry, {
      error: error instanceof Error ? error.message : '命令执行失败',
      exit_code: 1,
      duration_ms: 0,
      running: false,
    })
  } finally {
    directRunning.value = false
    await scrollTerminalToBottom()
    await focusTerminalInput()
  }
}

function clearTerminal() {
  terminalHistory.value = []
}

function handleTerminalKeydown(event: KeyboardEvent) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'l') {
    event.preventDefault()
    clearTerminal()
    return
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault()
    if (commandHistory.value.length === 0) return
    commandHistoryIndex.value = commandHistoryIndex.value < 0
      ? commandHistory.value.length - 1
      : Math.max(0, commandHistoryIndex.value - 1)
    terminalInput.value = commandHistory.value[commandHistoryIndex.value]
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (commandHistory.value.length === 0 || commandHistoryIndex.value < 0) return
    commandHistoryIndex.value += 1
    if (commandHistoryIndex.value >= commandHistory.value.length) {
      commandHistoryIndex.value = -1
      terminalInput.value = ''
      return
    }
    terminalInput.value = commandHistory.value[commandHistoryIndex.value]
  }
}

function rememberCommand(command: string) {
  const last = commandHistory.value[commandHistory.value.length - 1]
  if (last !== command) {
    commandHistory.value.push(command)
  }
  if (commandHistory.value.length > 80) {
    commandHistory.value = commandHistory.value.slice(-80)
  }
  commandHistoryIndex.value = -1
}

async function focusTerminalInput() {
  await nextTick()
  terminalInputRef.value?.focus()
}

function handleTerminalBodyClick(event: MouseEvent) {
  const target = event.target as HTMLElement | null
  if (target?.closest('input, textarea, button, a, select')) return

  const selection = window.getSelection()
  if (selection && !selection.isCollapsed && selection.toString().trim()) {
    return
  }

  void focusTerminalInput()
}

async function scrollTerminalToBottom() {
  await nextTick()
  if (terminalScrollRef.value) {
    terminalScrollRef.value.scrollTop = terminalScrollRef.value.scrollHeight
  }
}

function linuxPrompt(cwd: string) {
  return `manager@classrobot:${linuxCwd(cwd)}$`
}

function linuxCwd(value: string) {
  if (!value || value === 'project') return '~/ClassRobot'
  const normalized = value.replaceAll('\\', '/')
  const marker = '/ClassRobot'
  const markerIndex = normalized.lastIndexOf(marker)
  if (markerIndex >= 0) {
    const suffix = normalized.slice(markerIndex + marker.length)
    return `~/ClassRobot${suffix}`
  }
  const driveMatch = normalized.match(/^([A-Za-z]):\/(.*)$/)
  if (driveMatch) {
    return `/mnt/${driveMatch[1].toLowerCase()}/${driveMatch[2]}`
  }
  return normalized
}

function formatTime(value: string) {
  return new Date(value).toLocaleString()
}

function stringifyDetail(detail: Record<string, unknown>) {
  return JSON.stringify(detail, null, 2)
}
</script>

<style scoped>
.panel-frame {
  display: flex;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border-radius: 0.75rem;
  border: 1px solid theme('colors.outline.variant');
  background: theme('colors.surface.container.lowest');
  box-shadow: 0 16px 40px rgba(55, 65, 81, 0.08);
}

.panel-header {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  border-bottom: 1px solid theme('colors.outline.variant');
  background: theme('colors.surface.bright');
  padding: 0.75rem 1rem;
}

.tool-button {
  display: inline-flex;
  height: 2.25rem;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  border-radius: 0.5rem;
  border: 1px solid theme('colors.outline.variant');
  background: theme('colors.surface.container.lowest');
  padding: 0 0.75rem;
  font-size: 13px;
  color: theme('colors.on-surface');
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease, opacity 160ms ease;
}

.tool-button:hover {
  background: theme('colors.surface.container.DEFAULT');
  border-color: rgba(40, 100, 90, 0.35);
}

.terminal-shell {
  display: flex;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border-radius: 0.875rem;
  border: 1px solid #2b3342;
  background: linear-gradient(180deg, #0f1724 0%, #0b1018 100%);
  box-shadow:
    0 26px 60px rgba(0, 0, 0, 0.28),
    0 0 0 1px rgba(148, 163, 184, 0.05);
}

.terminal-titlebar {
  display: flex;
  min-height: 42px;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  border-bottom: 1px solid rgba(71, 85, 105, 0.42);
  background: linear-gradient(180deg, #162131 0%, #121926 100%);
  padding: 0 0.875rem;
}

.terminal-body {
  min-height: 0;
  flex: 1;
  cursor: text;
  overflow-y: auto;
  background:
    radial-gradient(circle at 18% 0%, rgba(34, 197, 94, 0.1), transparent 26%),
    linear-gradient(180deg, #0a1118 0%, #06080c 100%);
  padding: 1rem;
  font-family: 'Fira Code', Consolas, monospace;
  font-size: 13px;
  line-height: 1.58;
  color: #d7dde7;
  user-select: text;
  -webkit-user-select: text;
}

.terminal-line {
  display: flex;
  min-height: 1.5rem;
  align-items: center;
  gap: 0.5rem;
}

.terminal-input {
  min-width: 0;
  flex: 1;
  border: 0;
  background: transparent;
  padding: 0;
  font-family: 'Fira Code', Consolas, monospace;
  font-size: 13px;
  line-height: 1.58;
  color: #f4f4f5;
  caret-color: #33ff77;
  outline: none;
}

.terminal-action {
  height: 1.75rem;
  border-radius: 0.375rem;
  border: 1px solid rgba(71, 85, 105, 0.68);
  background: rgba(15, 23, 42, 0.82);
  padding: 0 0.625rem;
  font-family: 'Fira Code', Consolas, monospace;
  font-size: 12px;
  color: #e2e8f0;
  transition: background-color 160ms ease, color 160ms ease;
}

.terminal-action:hover {
  background: rgba(30, 41, 59, 0.94);
  color: #fff;
}

:global(html.dark) .panel-frame,
:global(html.dark) .panel-header,
:global(html.dark) .tool-button {
  border-color: rgb(39 39 42) !important;
  background: rgb(24 24 27) !important;
  color: rgb(244 244 245) !important;
}

:global(html.dark) .panel-header {
  background: rgb(24 24 27) !important;
}

:global(html.dark) .tool-button:hover {
  border-color: rgba(77, 163, 148, 0.36) !important;
  background: rgb(39 39 42) !important;
}
</style>
