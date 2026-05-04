<template>
  <div class="flex h-[calc(100vh-96px)] min-h-0 flex-col gap-4 overflow-hidden">
    <div class="flex shrink-0 flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">自动化脚本</h1>
        <p class="mt-1 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">
          本地管理员脚本的添加、编辑、执行和结果查看
        </p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <RouterLink to="/operations" class="tool-button dark:!border-zinc-800 dark:!bg-zinc-900 dark:!text-zinc-100 dark:hover:!bg-zinc-800">
          <Terminal :size="15" />
          返回终端
        </RouterLink>
        <button type="button" class="tool-button dark:!border-zinc-800 dark:!bg-zinc-900 dark:!text-zinc-100 dark:hover:!bg-zinc-800" @click="loadScripts">
          <RefreshCw :size="15" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
        <button type="button" class="primary-button" @click="openNewScript">
          <Plus :size="15" />
          新脚本
        </button>
      </div>
    </div>

    <div class="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[420px_minmax(0,1fr)]">
      <aside class="panel-frame dark:!border-zinc-800 dark:!bg-zinc-900">
        <div class="panel-header dark:!border-zinc-800 dark:!bg-zinc-900/95">
          <div class="flex min-w-0 items-center gap-2">
            <FileCode2 :size="18" class="shrink-0 text-primary dark:text-primary-dark" />
            <div class="min-w-0">
              <h2 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">脚本库</h2>
              <p class="truncate text-body-sm text-on-surface-variant dark:text-zinc-500">本地保存 {{ scripts.length }} 个脚本</p>
            </div>
          </div>
        </div>
        <div class="min-h-0 flex-1 overflow-y-auto p-3">
          <button
            v-for="script in scripts"
            :key="script.id"
            type="button"
            class="script-card dark:!border-zinc-700 dark:!bg-zinc-800/70 dark:hover:!bg-zinc-800"
            :class="selectedScript?.id === script.id ? 'script-card-active dark:!border-primary-dark/40 dark:!bg-zinc-800' : ''"
            @click="selectedScriptId = script.id"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="flex flex-wrap items-center gap-2">
                  <span class="font-body-sm text-body-sm font-semibold text-on-surface dark:text-zinc-100">{{ script.title }}</span>
                  <span class="rounded-full px-2 py-0.5 text-[10px] font-bold uppercase" :class="riskClass(script.risk)">
                    {{ script.risk === 'low' ? '低风险' : '中风险' }}
                  </span>
                  <span v-if="!script.enabled" class="rounded-full bg-surface-container px-2 py-0.5 text-[10px] text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400">停用</span>
                </div>
                <p v-if="script.description" class="mt-1 line-clamp-2 text-body-sm text-on-surface-variant dark:text-zinc-500">{{ script.description }}</p>
                <p class="mt-2 truncate font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-400">{{ script.command }}</p>
              </div>
            </div>
          </button>
          <div v-if="scripts.length === 0" class="flex h-full min-h-[220px] items-center justify-center rounded-lg border border-dashed border-outline-variant p-8 text-center text-body-sm text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
            暂无脚本，点击右上角添加本地管理员脚本
          </div>
        </div>
      </aside>

      <section class="grid min-h-0 grid-rows-[minmax(240px,0.6fr)_minmax(220px,0.4fr)] gap-4">
        <section class="panel-frame dark:!border-zinc-800 dark:!bg-zinc-900">
          <div class="panel-header dark:!border-zinc-800 dark:!bg-zinc-900/95">
            <div class="flex min-w-0 items-center gap-2">
              <Files :size="18" class="shrink-0 text-primary dark:text-primary-dark" />
              <div class="min-w-0">
                <h2 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ selectedScript?.title || '选择脚本' }}</h2>
                <p class="truncate text-body-sm text-on-surface-variant dark:text-zinc-500">{{ selectedScript?.cwd || '选择左侧脚本查看详情' }}</p>
              </div>
            </div>
            <div v-if="selectedScript" class="flex shrink-0 items-center gap-2">
              <button type="button" class="tool-button dark:!border-zinc-700 dark:!bg-zinc-900 dark:!text-zinc-100 dark:hover:!bg-zinc-800" :disabled="scriptRunning === selectedScript.id || !selectedScript.enabled" @click="runScript(selectedScript.id)">
                <Loader2 v-if="scriptRunning === selectedScript.id" :size="14" class="animate-spin" />
                <Play v-else :size="14" />
                执行
              </button>
              <button type="button" class="tool-button dark:!border-zinc-700 dark:!bg-zinc-900 dark:!text-zinc-100 dark:hover:!bg-zinc-800" @click="openEditScript(selectedScript)">
                <Pencil :size="14" />
                编辑
              </button>
              <button type="button" class="danger-button dark:!border-red-900/70 dark:!bg-red-950/40 dark:!text-red-300" @click="removeScript(selectedScript.id)">
                <Trash2 :size="14" />
                删除
              </button>
            </div>
          </div>

          <div v-if="selectedScript" class="min-h-0 flex-1 overflow-y-auto p-4">
            <div class="grid gap-3 lg:grid-cols-3">
              <div class="info-card dark:!border-zinc-700 dark:!bg-zinc-800/70 dark:!text-zinc-100">
                <span class="info-label dark:!text-zinc-400">状态</span>
                <strong>{{ selectedScript.enabled ? '启用' : '停用' }}</strong>
              </div>
              <div class="info-card dark:!border-zinc-700 dark:!bg-zinc-800/70 dark:!text-zinc-100">
                <span class="info-label dark:!text-zinc-400">风险</span>
                <strong>{{ selectedScript.risk === 'low' ? '低风险' : '中风险' }}</strong>
              </div>
              <div class="info-card dark:!border-zinc-700 dark:!bg-zinc-800/70 dark:!text-zinc-100">
                <span class="info-label dark:!text-zinc-400">超时</span>
                <strong>{{ selectedScript.timeout }}s</strong>
              </div>
            </div>

            <div class="mt-4 rounded-xl border border-outline-variant bg-code p-4 dark:border-zinc-800 dark:bg-zinc-950">
              <div class="mb-2 flex items-center gap-2 font-body-sm text-body-sm font-semibold text-on-surface dark:text-zinc-100">
                <Terminal :size="15" />
                命令
              </div>
              <pre class="whitespace-pre-wrap break-words font-code-block text-code-block text-on-surface-variant dark:text-zinc-300"><code>{{ selectedScript.command }}</code></pre>
            </div>

            <div v-if="selectedScript.description" class="mt-4 rounded-xl border border-outline-variant bg-surface-container-low p-4 text-body-sm text-on-surface-variant dark:border-zinc-800 dark:bg-zinc-800/50 dark:text-zinc-400">
              {{ selectedScript.description }}
            </div>
          </div>

          <div v-else class="flex min-h-0 flex-1 items-center justify-center p-8 text-center text-body-sm text-on-surface-variant dark:text-zinc-500">
            从左侧选择脚本查看详情
          </div>
        </section>

        <section class="output-shell dark:!border-zinc-800 dark:!bg-zinc-900">
          <div class="panel-header output-titlebar dark:!border-zinc-800 dark:!bg-zinc-900/95">
            <div class="flex min-w-0 items-center gap-2">
              <ScrollText :size="18" class="shrink-0 text-primary dark:text-primary-dark" />
              <div class="min-w-0">
                <h2 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">脚本输出</h2>
                <p class="mt-0.5 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">stdout / stderr / exit code</p>
              </div>
            </div>
          </div>
          <div class="output-body min-h-0 flex-1 overflow-y-auto p-4 font-code-block text-code-block text-on-surface dark:text-zinc-200">
            <pre v-if="scriptOutput" class="whitespace-pre-wrap"><code>{{ scriptOutput }}</code></pre>
            <div v-else class="flex h-full min-h-[160px] items-center justify-center text-center text-on-surface-variant dark:text-zinc-500">
              执行脚本后会在这里显示 stdout / stderr / exit code。
            </div>
          </div>
        </section>
      </section>
    </div>

    <Teleport to="body">
      <div v-if="scriptEditorOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/20 p-4 dark:bg-black/55" @click.self="scriptEditorOpen = false">
        <form class="w-full max-w-[680px] overflow-hidden rounded-lg border border-outline-variant bg-surface-container-lowest shadow-2xl dark:border-zinc-800 dark:bg-zinc-900" @submit.prevent="saveScript">
          <div class="flex items-center justify-between border-b border-outline-variant px-4 py-3 dark:border-zinc-800">
            <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ editingScriptId ? '编辑脚本' : '添加脚本' }}</h2>
            <button type="button" class="icon-button dark:!border-zinc-700 dark:!bg-zinc-900 dark:!text-zinc-100 dark:hover:!bg-zinc-800" @click="scriptEditorOpen = false">
              <X :size="15" />
            </button>
          </div>
          <div class="grid gap-3 p-4">
            <input v-model="scriptForm.title" class="form-input dark:!border-zinc-700 dark:!bg-zinc-950 dark:!text-zinc-100" placeholder="脚本名称" />
            <input v-model="scriptForm.description" class="form-input dark:!border-zinc-700 dark:!bg-zinc-950 dark:!text-zinc-100" placeholder="描述，可选" />
            <textarea v-model="scriptForm.command" class="form-textarea dark:!border-zinc-700 dark:!bg-zinc-950 dark:!text-zinc-100" placeholder="脚本命令..." />
            <input v-model="scriptForm.cwd" class="form-input font-code-inline text-code-inline dark:!border-zinc-700 dark:!bg-zinc-950 dark:!text-zinc-100" placeholder="工作目录，默认项目根目录" />
            <div class="grid grid-cols-[1fr_120px] gap-2">
              <AppSelect v-model="scriptForm.risk" :options="riskOptions" />
              <input v-model.number="scriptForm.timeout" type="number" min="1" max="600" class="form-input font-code-inline text-code-inline dark:!border-zinc-700 dark:!bg-zinc-950 dark:!text-zinc-100" title="超时时间" />
            </div>
            <label class="flex items-center gap-2 text-body-sm text-on-surface-variant dark:text-zinc-400">
              <input v-model="scriptForm.enabled" type="checkbox" class="h-4 w-4 accent-primary dark:accent-primary-dark" />
              启用脚本
            </label>
          </div>
          <div class="flex justify-end gap-2 border-t border-outline-variant px-4 py-3 dark:border-zinc-800">
            <button type="button" class="tool-button dark:!border-zinc-700 dark:!bg-zinc-900 dark:!text-zinc-100 dark:hover:!bg-zinc-800" @click="scriptEditorOpen = false">取消</button>
            <button
              type="submit"
              class="primary-button"
              :disabled="scriptSaving || !scriptForm.title.trim() || !scriptForm.command.trim()"
            >
              <Loader2 v-if="scriptSaving" :size="14" class="animate-spin" />
              <Save v-else :size="14" />
              保存
            </button>
          </div>
        </form>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import {
  FileCode2,
  Files,
  Loader2,
  Pencil,
  Play,
  Plus,
  RefreshCw,
  Save,
  ScrollText,
  Terminal,
  Trash2,
  X,
} from 'lucide-vue-next'
import {
  createAutomationScript,
  deleteAutomationScript,
  fetchAutomationScripts,
  runAutomationScript,
  updateAutomationScript,
} from '@/api/operations'
import type { AutomationScriptItem, TerminalRunResult } from '@/types/api'
import AppSelect from '@/components/AppSelect.vue'

const scripts = ref<AutomationScriptItem[]>([])
const selectedScriptId = ref('')
const scriptRunning = ref('')
const scriptSaving = ref(false)
const scriptEditorOpen = ref(false)
const editingScriptId = ref('')
const loading = ref(false)
const lastRun = ref<TerminalRunResult | null>(null)
const scriptForm = ref({
  title: '',
  description: '',
  command: '',
  cwd: '',
  risk: 'medium' as 'low' | 'medium',
  timeout: 300,
  enabled: true,
})

const riskOptions = [
  { label: '中风险', value: 'medium' },
  { label: '低风险', value: 'low' },
]

const selectedScript = computed(() => scripts.value.find((item) => item.id === selectedScriptId.value) || scripts.value[0] || null)
const scriptOutput = computed(() => {
  if (!lastRun.value) return ''
  return [
    `$ ${lastRun.value.command}`,
    `cwd: ${lastRun.value.cwd}`,
    `status: ${lastRun.value.status} · exit ${lastRun.value.exit_code} · ${lastRun.value.duration_ms}ms`,
    lastRun.value.error ? `error: ${lastRun.value.error}` : '',
    lastRun.value.stdout ? `\nstdout:\n${lastRun.value.stdout}` : '',
    lastRun.value.stderr ? `\nstderr:\n${lastRun.value.stderr}` : '',
  ].filter(Boolean).join('\n')
})

onMounted(() => loadScripts())

async function loadScripts() {
  loading.value = true
  try {
    scripts.value = (await fetchAutomationScripts()).items
    if (!selectedScriptId.value && scripts.value.length > 0) {
      selectedScriptId.value = scripts.value[0].id
    }
    if (selectedScriptId.value && !scripts.value.some((item) => item.id === selectedScriptId.value)) {
      selectedScriptId.value = scripts.value[0]?.id || ''
    }
  } finally {
    loading.value = false
  }
}

async function saveScript() {
  scriptSaving.value = true
  try {
    const payload = {
      title: scriptForm.value.title,
      description: scriptForm.value.description,
      command: scriptForm.value.command,
      cwd: scriptForm.value.cwd.trim() || undefined,
      risk: scriptForm.value.risk,
      timeout: Number(scriptForm.value.timeout) || 300,
      enabled: scriptForm.value.enabled,
    }
    const saved = editingScriptId.value
      ? await updateAutomationScript(editingScriptId.value, payload)
      : await createAutomationScript(payload)
    selectedScriptId.value = saved.id
    scriptEditorOpen.value = false
    resetScriptForm()
    await loadScripts()
  } finally {
    scriptSaving.value = false
  }
}

function openNewScript() {
  resetScriptForm()
  scriptEditorOpen.value = true
}

function openEditScript(script: AutomationScriptItem) {
  editingScriptId.value = script.id
  scriptForm.value = {
    title: script.title,
    description: script.description || '',
    command: script.command,
    cwd: script.cwd || '',
    risk: script.risk,
    timeout: script.timeout,
    enabled: script.enabled,
  }
  scriptEditorOpen.value = true
}

function resetScriptForm() {
  editingScriptId.value = ''
  scriptForm.value = {
    title: '',
    description: '',
    command: '',
    cwd: '',
    risk: 'medium',
    timeout: 300,
    enabled: true,
  }
}

async function runScript(id: string) {
  scriptRunning.value = id
  try {
    lastRun.value = await runAutomationScript(id)
  } finally {
    scriptRunning.value = ''
  }
}

async function removeScript(id: string) {
  if (!window.confirm('确定删除这个脚本吗？')) return
  await deleteAutomationScript(id)
  if (editingScriptId.value === id) resetScriptForm()
  if (selectedScriptId.value === id) selectedScriptId.value = ''
  await loadScripts()
}

function riskClass(risk: 'low' | 'medium') {
  return risk === 'low'
    ? 'bg-primary/10 text-primary dark:bg-emerald-500/10 dark:text-emerald-400'
    : 'bg-warning/10 text-warning dark:bg-amber-500/10 dark:text-amber-400'
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

.tool-button,
.primary-button,
.danger-button,
.icon-button {
  display: inline-flex;
  height: 2.25rem;
  align-items: center;
  justify-content: center;
  gap: 0.375rem;
  border-radius: 0.5rem;
  border: 1px solid theme('colors.outline.variant');
  padding: 0 0.75rem;
  font-size: 13px;
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease, opacity 160ms ease;
}

.tool-button,
.icon-button {
  background: theme('colors.surface.container.lowest');
  color: theme('colors.on-surface');
}

.primary-button {
  border-color: theme('colors.primary.DEFAULT');
  background: theme('colors.primary.DEFAULT');
  color: theme('colors.on-primary');
}

.danger-button {
  border-color: rgba(186, 26, 26, 0.25);
  background: rgba(186, 26, 26, 0.08);
  color: theme('colors.error.DEFAULT');
}

.icon-button {
  width: 2.25rem;
  padding: 0;
}

.tool-button:hover,
.icon-button:hover {
  background: theme('colors.surface.container.DEFAULT');
  border-color: rgba(40, 100, 90, 0.35);
}

.primary-button:hover,
.danger-button:hover {
  opacity: 0.9;
}

.script-card {
  margin-bottom: 0.75rem;
  display: block;
  width: 100%;
  border-radius: 0.75rem;
  border: 1px solid theme('colors.outline.variant');
  background: theme('colors.surface.container.low');
  padding: 0.75rem;
  text-align: left;
  transition: background-color 160ms ease, border-color 160ms ease;
}

.script-card:hover,
.script-card-active {
  border-color: rgba(40, 100, 90, 0.35);
  background: theme('colors.surface.container.DEFAULT');
}

.info-card {
  border-radius: 0.75rem;
  border: 1px solid theme('colors.outline.variant');
  background: theme('colors.surface.container.low');
  padding: 0.75rem;
}

.info-label {
  display: block;
  margin-bottom: 0.25rem;
  font-size: 11px;
  color: theme('colors.on-surface-variant');
}

.output-shell {
  display: flex;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
  border-radius: 0.875rem;
  border: 1px solid theme('colors.outline.variant');
  background: theme('colors.surface.container.lowest');
  box-shadow: 0 16px 40px rgba(55, 65, 81, 0.08);
}

.output-titlebar {
  display: flex;
  flex-shrink: 0;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

.output-body {
  background: transparent;
}

.form-input,
.form-textarea {
  width: 100%;
  border-radius: 0.5rem;
  border: 1px solid theme('colors.outline.variant');
  background: theme('colors.surface.container.lowest');
  padding: 0 0.75rem;
  color: theme('colors.on-surface');
  outline: none;
  transition: border-color 160ms ease;
}

.form-input {
  height: 2.25rem;
  font-size: 13px;
}

.form-textarea {
  min-height: 8rem;
  resize: vertical;
  padding-top: 0.625rem;
  padding-bottom: 0.625rem;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
}

.form-input:focus,
.form-textarea:focus {
  border-color: theme('colors.primary.DEFAULT');
}

:global(html.dark) .panel-frame,
:global(html.dark) .panel-header,
:global(html.dark) .tool-button,
:global(html.dark) .icon-button,
:global(html.dark) .form-input,
:global(html.dark) .form-textarea {
  border-color: rgb(39 39 42) !important;
  background: rgb(24 24 27) !important;
  color: rgb(244 244 245) !important;
}

:global(html.dark) .script-card,
:global(html.dark) .info-card {
  border-color: rgb(39 39 42) !important;
  background: rgba(39, 39, 42, 0.52) !important;
  color: rgb(244 244 245) !important;
}

:global(html.dark) .script-card:hover,
:global(html.dark) .script-card-active {
  border-color: rgba(77, 163, 148, 0.36) !important;
  background: rgba(39, 39, 42, 0.82) !important;
}

:global(html.dark) .info-label {
  color: rgb(161 161 170) !important;
}

:global(html.dark) .output-shell {
  border-color: rgb(39 39 42) !important;
  background: rgb(24 24 27) !important;
  color: rgb(244 244 245) !important;
}

:global(html.dark) .output-titlebar {
  border-color: rgb(39 39 42) !important;
  background: rgb(24 24 27) !important;
}

:global(html.dark) .output-body {
  background: transparent !important;
}
</style>
