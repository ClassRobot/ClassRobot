<template>
  <div class="flex h-[calc(100vh-96px)] min-h-0 flex-col gap-4 overflow-hidden">
    <div class="flex shrink-0 items-start justify-between gap-4">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">数据库管理</h1>
        <p class="mt-1 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">
          连接、表结构、关系与数据维护
        </p>
      </div>
      <button
        type="button"
        class="flex h-9 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 font-body-sm text-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
        @click="reload"
      >
        <RefreshCw :size="15" :class="{ 'animate-spin': loading }" />
        刷新
      </button>
    </div>

    <div v-if="message" class="shrink-0 rounded-lg border px-3 py-2 text-body-sm" :class="messageClass">
      {{ message }}
    </div>

    <div class="grid shrink-0 grid-cols-2 gap-3 lg:grid-cols-4">
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">连接</span>
          <Database :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ connections.length }}</div>
        <div class="mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">
          {{ selectedDatabase?.dialect || '-' }} / {{ selectedDatabase?.driver || '-' }}
        </div>
      </div>
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">数据表</span>
          <Table2 :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ tables.length }}</div>
        <div class="mt-1 text-body-sm text-on-surface-variant dark:text-zinc-500">当前连接已识别</div>
      </div>
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">关系</span>
          <GitBranch :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ relationships.length }}</div>
        <div class="mt-1 text-body-sm text-on-surface-variant dark:text-zinc-500">外键关系</div>
      </div>
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">行数据</span>
          <Rows3 :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ rows?.total ?? '-' }}</div>
        <div class="mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">{{ selectedTableName || '未选择表' }}</div>
      </div>
    </div>

    <div class="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <aside class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="border-b border-outline-variant bg-surface-bright p-3 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div class="relative">
            <Search :size="15" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant dark:text-zinc-500" />
            <input
              v-model="tableSearch"
              class="h-9 w-full rounded-lg border border-outline-variant bg-surface-container pl-8 pr-3 text-body-sm text-on-surface outline-none transition-colors focus:border-primary dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:focus:border-primary-dark"
              placeholder="搜索表名..."
            />
          </div>
        </div>
        <div class="flex-1 overflow-y-auto p-2">
          <button
            v-for="table in filteredTables"
            :key="table.name"
            type="button"
            class="mb-1 w-full rounded-lg px-3 py-2 text-left transition-colors"
            :class="selectedTableName === table.name
              ? 'bg-primary/10 text-primary dark:bg-primary-dark/15 dark:text-primary-dark'
              : 'text-on-surface hover:bg-surface-container dark:text-zinc-200 dark:hover:bg-zinc-800'"
            @click="selectTable(table.name)"
          >
            <div class="flex items-center justify-between gap-2">
              <span class="truncate font-body-sm text-body-sm font-medium">{{ table.name }}</span>
              <span class="shrink-0 rounded-full bg-surface-container px-2 py-0.5 text-[11px] text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400">
                {{ table.row_count ?? '-' }}
              </span>
            </div>
            <div class="mt-1 flex items-center gap-2 text-[11px] text-on-surface-variant dark:text-zinc-500">
              <span>{{ table.column_count }} 列</span>
              <span v-if="table.foreign_key_count">{{ table.foreign_key_count }} 关系</span>
              <span v-if="!table.editable">只读</span>
            </div>
          </button>
          <div v-if="filteredTables.length === 0" class="p-6 text-center text-body-sm text-on-surface-variant dark:text-zinc-500">
            暂无匹配的数据表
          </div>
        </div>
      </aside>

      <section class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between gap-3 border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <h2 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ selectedTableName || '选择数据表' }}</h2>
              <span v-if="selectedTable?.editable" class="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary dark:bg-primary-dark/15 dark:text-primary-dark">可编辑</span>
              <span v-else-if="selectedTable" class="rounded-full bg-surface-container px-2 py-0.5 text-[11px] text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400">无主键</span>
            </div>
            <p class="mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">
              {{ selectedDatabase?.url || '未读取连接信息' }}
            </p>
          </div>
          <div class="flex rounded-lg border border-outline-variant bg-surface-container p-0.5 dark:border-zinc-700 dark:bg-zinc-800">
            <button
              type="button"
              class="h-8 rounded-md px-3 text-body-sm transition-colors"
              :class="activeTab === 'data' ? 'bg-surface-container-lowest text-primary shadow-sm dark:bg-zinc-900 dark:text-primary-dark' : 'text-on-surface-variant dark:text-zinc-400'"
              @click="activeTab = 'data'"
            >
              数据
            </button>
            <button
              type="button"
              class="h-8 rounded-md px-3 text-body-sm transition-colors"
              :class="activeTab === 'schema' ? 'bg-surface-container-lowest text-primary shadow-sm dark:bg-zinc-900 dark:text-primary-dark' : 'text-on-surface-variant dark:text-zinc-400'"
              @click="activeTab = 'schema'"
            >
              结构
            </button>
          </div>
        </div>

        <div v-if="activeTab === 'schema'" class="grid min-h-0 flex-1 grid-cols-1 gap-4 overflow-hidden p-4 2xl:grid-cols-[minmax(0,1fr)_360px]">
          <div class="min-h-0 overflow-y-auto pr-1">
            <div class="mb-3 flex items-center gap-2 text-body-sm font-medium text-on-surface dark:text-zinc-200">
              <GitBranch :size="16" />
              ER 关系
            </div>
            <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              <button
                v-for="table in schemaTables"
                :key="table.name"
                type="button"
                class="rounded-xl border p-3 text-left transition-colors"
                :class="selectedTableName === table.name
                  ? 'border-primary/40 bg-primary/10 dark:border-primary-dark/35 dark:bg-primary-dark/10'
                  : 'border-outline-variant bg-surface-container-lowest hover:bg-surface-container dark:border-zinc-800 dark:bg-zinc-900 dark:hover:bg-zinc-800/70'"
                @click="selectTable(table.name)"
              >
                <div class="mb-2 flex items-center justify-between gap-2">
                  <span class="truncate font-code-inline text-code-inline font-semibold text-on-surface dark:text-zinc-100">{{ table.name }}</span>
                  <span class="text-[11px] text-on-surface-variant dark:text-zinc-500">{{ table.columns.length }} 列</span>
                </div>
                <div class="space-y-1">
                  <div
                    v-for="column in table.columns.slice(0, 6)"
                    :key="column.name"
                    class="flex items-center justify-between gap-2 text-[12px]"
                  >
                    <span class="truncate text-on-surface-variant dark:text-zinc-400">{{ column.name }}</span>
                    <span v-if="column.primary_key" class="inline-flex items-center gap-1 rounded-full bg-primary/10 px-1.5 py-0.5 text-[10px] text-primary dark:bg-primary-dark/15 dark:text-primary-dark">
                      <KeyRound :size="10" />
                      PK
                    </span>
                  </div>
                  <div v-if="table.columns.length > 6" class="text-[11px] text-on-surface-variant dark:text-zinc-500">还有 {{ table.columns.length - 6 }} 列</div>
                </div>
              </button>
            </div>
          </div>

          <aside class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
            <div class="shrink-0 border-b border-outline-variant px-4 py-3 dark:border-zinc-800">
              <h3 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">关系列表</h3>
            </div>
            <div class="min-h-0 flex-1 overflow-y-auto p-3">
              <div
                v-for="relation in relationships"
                :key="relation.label"
                class="mb-2 rounded-lg border border-outline-variant bg-surface-container-low p-3 dark:border-zinc-800 dark:bg-zinc-800/55"
              >
                <div class="flex items-center gap-2 text-body-sm text-on-surface dark:text-zinc-200">
                  <Link2 :size="14" class="text-primary dark:text-primary-dark" />
                  <span class="truncate">{{ relation.source_table }}</span>
                </div>
                <div class="mt-2 font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-400">
                  {{ relation.source_columns.join(', ') }} -> {{ relation.target_table }}.{{ relation.target_columns.join(', ') }}
                </div>
              </div>
              <div v-if="relationships.length === 0" class="p-6 text-center text-body-sm text-on-surface-variant dark:text-zinc-500">
                暂无外键关系
              </div>
            </div>
          </aside>
        </div>

        <div v-else class="grid min-h-0 flex-1 grid-cols-1 overflow-hidden xl:grid-cols-[minmax(0,1fr)_360px]">
          <div class="flex min-w-0 flex-col overflow-hidden">
            <div class="min-h-0 flex-1 overflow-auto">
              <table class="w-full border-collapse text-left">
                <thead class="sticky top-0 z-10 border-b border-outline-variant bg-surface-bright dark:border-zinc-800 dark:bg-zinc-900">
                  <tr>
                    <th
                      v-for="column in rows?.columns || []"
                      :key="column.name"
                      class="whitespace-nowrap p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500"
                    >
                      <span class="inline-flex items-center gap-1.5">
                        <KeyRound v-if="column.primary_key" :size="12" class="text-primary dark:text-primary-dark" />
                        {{ column.name }}
                      </span>
                    </th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-outline-variant text-body-sm text-on-surface dark:divide-zinc-800 dark:text-zinc-200">
                  <tr v-if="!rows || rows.items.length === 0">
                    <td :colspan="rows?.columns.length || 1" class="p-8 text-center text-on-surface-variant dark:text-zinc-500">
                      暂无行数据
                    </td>
                  </tr>
                  <tr
                    v-for="(row, index) in rows?.items || []"
                    :key="rowKey(row, index)"
                    class="cursor-pointer transition-colors hover:bg-surface-container dark:hover:bg-zinc-800/60"
                    :class="{ 'bg-surface-container dark:bg-zinc-800/40': selectedRow === row }"
                    @click="openRow(row)"
                  >
                    <td
                      v-for="column in rows?.columns || []"
                      :key="column.name"
                      class="max-w-[240px] whitespace-nowrap p-[10px_12px] align-top"
                    >
                      <span class="block truncate font-code-inline text-code-inline" :title="formatCell(row[column.name])">
                        {{ formatCell(row[column.name]) }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="shrink-0 flex items-center justify-between border-t border-outline-variant px-4 py-2 text-body-sm text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
              <span>共 {{ rows?.total || 0 }} 行，第 {{ page }}/{{ totalPages }} 页</span>
              <div class="flex gap-1">
                <button class="rounded-lg border border-outline-variant px-2 py-1 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700" :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
                <button class="rounded-lg border border-outline-variant px-2 py-1 disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700" :disabled="page >= totalPages" @click="changePage(page + 1)">下一页</button>
              </div>
            </div>
          </div>

          <aside class="flex min-h-0 flex-col overflow-hidden border-t border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900 xl:border-l xl:border-t-0">
            <div class="shrink-0 flex items-center justify-between border-b border-outline-variant px-4 py-3 dark:border-zinc-800">
              <h3 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">行编辑</h3>
              <button v-if="selectedRow" type="button" class="rounded-lg p-1.5 text-on-surface-variant hover:bg-surface-container dark:text-zinc-400 dark:hover:bg-zinc-800" @click="closeRow">
                <X :size="16" />
              </button>
            </div>
            <div v-if="selectedRow && rows" class="min-h-0 flex-1 overflow-y-auto p-4">
              <div class="mb-4 rounded-lg border border-outline-variant bg-surface-container-low p-3 dark:border-zinc-800 dark:bg-zinc-800/55">
                <div class="mb-1 flex items-center gap-2 text-body-sm font-medium text-on-surface dark:text-zinc-200">
                  <KeyRound :size="14" />
                  主键
                </div>
                <div class="font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-400">{{ JSON.stringify(primaryKeyPayload(selectedRow)) }}</div>
              </div>

              <div
                v-if="editErrorDetail"
                class="mb-4 rounded-lg border border-error/25 bg-error-container/55 p-3 text-body-sm text-error dark:border-red-800/60 dark:bg-red-950/35 dark:text-red-200"
              >
                <div class="mb-1 flex items-center justify-between gap-2">
                  <span class="inline-flex items-center gap-2 font-medium">
                    <AlertTriangle :size="14" />
                    保存失败
                  </span>
                  <span class="rounded-full bg-surface-container-lowest px-2 py-0.5 font-code-inline text-[11px] text-error dark:bg-red-950/70 dark:text-red-300">
                    {{ editErrorDetail.code }}
                  </span>
                </div>
                <p>{{ editErrorDetail.message }}</p>
                <p v-if="editErrorDetail.hint" class="mt-2 text-[12px] text-on-surface-variant dark:text-red-100/80">
                  建议：{{ editErrorDetail.hint }}
                </p>
                <div
                  v-if="editErrorDetail.expected || editErrorDetail.received_type || editErrorDetail.received_value"
                  class="mt-2 grid gap-1 rounded-md bg-surface-container-lowest p-2 font-code-inline text-code-inline text-on-surface-variant dark:bg-zinc-950/70 dark:text-red-100/80"
                >
                  <span v-if="editErrorDetail.expected">expected: {{ editErrorDetail.expected }}</span>
                  <span v-if="editErrorDetail.received_type">received_type: {{ editErrorDetail.received_type }}</span>
                  <span v-if="editErrorDetail.received_value">received_value: {{ editErrorDetail.received_value }}</span>
                </div>
                <p v-if="editErrorDetail.detail" class="mt-2 rounded-md bg-surface-container-lowest p-2 font-code-inline text-code-inline text-on-surface-variant dark:bg-zinc-950/70 dark:text-red-100/80">
                  {{ editErrorDetail.detail }}
                </p>
              </div>

              <div class="space-y-3">
                <label
                  v-for="column in editableColumns"
                  :key="column.name"
                  class="block"
                >
                  <span class="mb-1 flex items-center justify-between gap-2 text-[12px] font-medium text-on-surface-variant dark:text-zinc-400">
                    <span class="truncate">{{ column.name }}</span>
                    <span class="font-code-inline text-code-inline">{{ column.type }}</span>
                  </span>
                  <textarea
                    v-if="isTextareaColumn(column)"
                    v-model="editValues[column.name]"
                    class="min-h-[92px] w-full resize-y rounded-lg border px-3 py-2 font-code-inline text-code-inline text-on-surface outline-none transition-colors dark:text-zinc-100"
                    :class="inputStateClass(column.name)"
                    :aria-invalid="Boolean(editFieldErrors[column.name])"
                    @input="clearFieldError(column.name)"
                  />
                  <input
                    v-else
                    v-model="editValues[column.name]"
                    class="h-9 w-full rounded-lg border px-3 font-code-inline text-code-inline text-on-surface outline-none transition-colors dark:text-zinc-100"
                    :class="inputStateClass(column.name)"
                    :aria-invalid="Boolean(editFieldErrors[column.name])"
                    @input="clearFieldError(column.name)"
                  />
                  <p v-if="editFieldErrors[column.name]" class="mt-1 text-[12px] text-error dark:text-red-300">
                    {{ editFieldErrors[column.name] }}
                  </p>
                </label>
              </div>

              <button
                type="button"
                class="mt-4 flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-primary text-on-primary transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-primary-dark dark:text-zinc-950"
                :disabled="saving || !selectedTable?.editable"
                @click="saveRow"
              >
                <Loader2 v-if="saving" :size="15" class="animate-spin" />
                <Save v-else :size="15" />
                保存修改
              </button>
            </div>
            <div v-else class="flex min-h-0 flex-1 items-center justify-center p-6 text-center text-body-sm text-on-surface-variant dark:text-zinc-500">
              选择一行查看和编辑
            </div>
          </aside>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  AlertTriangle,
  Database,
  GitBranch,
  KeyRound,
  Link2,
  Loader2,
  RefreshCw,
  Rows3,
  Save,
  Search,
  Table2,
  X,
} from 'lucide-vue-next'
import {
  fetchDatabaseSchema,
  fetchDatabaseTables,
  fetchDatabases,
  fetchTableRows,
  updateTableRow,
} from '@/api/databases'
import type {
  DatabaseColumn,
  DatabaseConnection,
  DatabaseMutationErrorDetail,
  DatabaseRow,
  DatabaseSchemaResponse,
  DatabaseTableRowsResponse,
  DatabaseTableSummary,
} from '@/types/api'

const connections = ref<DatabaseConnection[]>([])
const selectedDatabaseId = ref('primary')
const schemaPayload = ref<DatabaseSchemaResponse | null>(null)
const tables = ref<DatabaseTableSummary[]>([])
const rows = ref<DatabaseTableRowsResponse | null>(null)
const selectedTableName = ref('')
const selectedRow = ref<DatabaseRow | null>(null)
const editValues = ref<Record<string, string>>({})
const editFieldErrors = ref<Record<string, string>>({})
const editErrorDetail = ref<DatabaseMutationErrorDetail | null>(null)
const tableSearch = ref('')
const activeTab = ref<'data' | 'schema'>('data')
const loading = ref(false)
const saving = ref(false)
const page = ref(1)
const pageSize = 20
const message = ref('')
const messageTone = ref<'success' | 'error'>('success')

const selectedDatabase = computed(() => connections.value.find((item) => item.id === selectedDatabaseId.value))
const schemaTables = computed(() => schemaPayload.value?.tables || [])
const relationships = computed(() => schemaPayload.value?.relationships || [])
const selectedTable = computed(() => tables.value.find((item) => item.name === selectedTableName.value))
const filteredTables = computed(() => {
  const keyword = tableSearch.value.trim().toLowerCase()
  if (!keyword) return tables.value
  return tables.value.filter((table) => table.name.toLowerCase().includes(keyword))
})
const editableColumns = computed(() => (rows.value?.columns || []).filter((column) => !column.primary_key))
const totalPages = computed(() => Math.max(1, Math.ceil((rows.value?.total || 0) / pageSize)))
const messageClass = computed(() => messageTone.value === 'success'
  ? 'border-primary/20 bg-primary/10 text-primary dark:border-primary-dark/20 dark:bg-primary-dark/10 dark:text-primary-dark'
  : 'border-error/20 bg-error-container/60 text-error dark:border-red-800/50 dark:bg-red-900/30 dark:text-red-300')

onMounted(() => reload())

async function reload() {
  loading.value = true
  message.value = ''
  try {
    const databasePayload = await fetchDatabases()
    connections.value = databasePayload.items
    selectedDatabaseId.value = connections.value[0]?.id || 'primary'
    await loadDatabase()
  } catch (error) {
    showMessage(errorMessage(error, '数据库信息加载失败'), 'error')
  } finally {
    loading.value = false
  }
}

async function loadDatabase() {
  const [schemaResult, tableResult] = await Promise.all([
    fetchDatabaseSchema(selectedDatabaseId.value),
    fetchDatabaseTables(selectedDatabaseId.value),
  ])
  schemaPayload.value = schemaResult
  tables.value = tableResult.items
  if (!selectedTableName.value || !tables.value.some((table) => table.name === selectedTableName.value)) {
    selectedTableName.value = tables.value[0]?.name || ''
  }
  if (selectedTableName.value) {
    await loadRows()
  }
}

async function selectTable(tableName: string) {
  if (selectedTableName.value === tableName) return
  selectedTableName.value = tableName
  selectedRow.value = null
  resetEditErrors()
  page.value = 1
  activeTab.value = 'data'
  await loadRows()
}

async function loadRows() {
  if (!selectedTableName.value) return
  try {
    rows.value = await fetchTableRows(selectedDatabaseId.value, selectedTableName.value, {
      page: page.value,
      page_size: pageSize,
    })
  } catch (error) {
    showMessage(errorMessage(error, '行数据读取失败'), 'error')
  }
}

async function changePage(nextPage: number) {
  page.value = nextPage
  selectedRow.value = null
  resetEditErrors()
  await loadRows()
}

function openRow(row: DatabaseRow) {
  selectedRow.value = row
  resetEditErrors()
  const nextValues: Record<string, string> = {}
  for (const column of editableColumns.value) {
    nextValues[column.name] = editText(row[column.name])
  }
  editValues.value = nextValues
}

function closeRow() {
  selectedRow.value = null
  editValues.value = {}
  resetEditErrors()
}

async function saveRow() {
  if (!selectedRow.value || !rows.value || !selectedTableName.value) return
  saving.value = true
  resetEditErrors()
  try {
    const values: Record<string, unknown> = {}
    const localErrors: Record<string, string> = {}
    for (const column of editableColumns.value) {
      try {
        values[column.name] = parseEditValue(column, editValues.value[column.name] ?? '')
      } catch (error) {
        localErrors[column.name] = error instanceof Error ? error.message : `字段 ${column.name} 格式不正确`
      }
    }
    if (Object.keys(localErrors).length > 0) {
      editFieldErrors.value = localErrors
      editErrorDetail.value = {
        code: 'client_validation_error',
        message: '字段格式校验未通过，修改未提交。',
        columns: Object.keys(localErrors),
        hint: '请先修正标红字段，再点击保存修改。',
      }
      showMessage('保存失败：请先修正标红字段', 'error')
      return
    }
    const result = await updateTableRow(selectedDatabaseId.value, selectedTableName.value, {
      pk: primaryKeyPayload(selectedRow.value),
      values,
    })
    if (result.row) {
      selectedRow.value = result.row
    }
    showMessage('行数据已更新', 'success')
    await loadRows()
  } catch (error) {
    const detail = normalizeDatabaseError(error, '保存失败')
    applyEditError(detail)
    showMessage(detail.message, 'error')
  } finally {
    saving.value = false
  }
}

function primaryKeyPayload(row: DatabaseRow) {
  const payload: Record<string, unknown> = {}
  for (const key of rows.value?.primary_key || []) {
    payload[key] = row[key]
  }
  return payload
}

function rowKey(row: DatabaseRow, index: number) {
  const keys = rows.value?.primary_key || []
  if (keys.length === 0) return index
  return keys.map((key) => String(row[key])).join(':')
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'object') {
    const text = JSON.stringify(value)
    return text.length > 80 ? `${text.slice(0, 77)}...` : text
  }
  return String(value)
}

function editText(value: unknown): string {
  if (value === null || value === undefined) return 'null'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

function parseEditValue(column: DatabaseColumn, raw: string): unknown {
  const value = raw.trim()
  const type = column.type.toLowerCase()
  if (value === 'null') return null
  if (type.includes('json') || value.startsWith('{') || value.startsWith('[')) {
    try {
      return JSON.parse(value)
    } catch (error) {
      throw new Error(`字段 ${column.name} 的 JSON 格式不正确`)
    }
  }
  if (type.includes('bool')) {
    const lowered = value.toLowerCase()
    if (['true', '1', 'yes', 'on'].includes(lowered)) return true
    if (['false', '0', 'no', 'off'].includes(lowered)) return false
    throw new Error(`字段 ${column.name} 需要布尔值 true/false、1/0、yes/no`)
  }
  if (type.includes('int')) {
    if (!/^[+-]?\d+$/.test(value)) {
      throw new Error(`字段 ${column.name} 需要整数`)
    }
    const parsed = Number(value)
    if (!Number.isSafeInteger(parsed)) {
      throw new Error(`字段 ${column.name} 超出安全整数范围`)
    }
    return parsed
  }
  if (
    type.includes('float')
    || type.includes('numeric')
    || type.includes('decimal')
    || type.includes('double')
    || type.includes('real')
  ) {
    const parsed = Number(value)
    if (!Number.isFinite(parsed)) {
      throw new Error(`字段 ${column.name} 需要有效数字`)
    }
    return parsed
  }
  return raw
}

function isTextareaColumn(column: DatabaseColumn) {
  const type = column.type.toLowerCase()
  return type.includes('text') || type.includes('json') || (editValues.value[column.name]?.length || 0) > 80
}

function inputStateClass(columnName: string) {
  return editFieldErrors.value[columnName]
    ? 'border-error bg-error-container/35 focus:border-error dark:border-red-500/70 dark:bg-red-950/30 dark:focus:border-red-400'
    : 'border-outline-variant bg-surface-container focus:border-primary dark:border-zinc-700 dark:bg-zinc-800 dark:focus:border-primary-dark'
}

function resetEditErrors() {
  editFieldErrors.value = {}
  editErrorDetail.value = null
}

function clearFieldError(columnName: string) {
  if (!editFieldErrors.value[columnName]) return
  const nextErrors = { ...editFieldErrors.value }
  delete nextErrors[columnName]
  editFieldErrors.value = nextErrors
  if (editErrorDetail.value?.code === 'client_validation_error' && Object.keys(nextErrors).length === 0) {
    editErrorDetail.value = null
  }
}

function applyEditError(detail: DatabaseMutationErrorDetail) {
  editErrorDetail.value = detail
  const knownColumns = new Set(editableColumns.value.map((column) => column.name))
  const nextErrors: Record<string, string> = {}
  const columns = [
    ...(detail.column ? [detail.column] : []),
    ...(detail.columns || []),
  ]
  for (const columnName of columns) {
    if (knownColumns.has(columnName)) {
      nextErrors[columnName] = detail.message
    }
  }
  editFieldErrors.value = nextErrors
}

function showMessage(text: string, tone: 'success' | 'error') {
  message.value = text
  messageTone.value = tone
}

function errorMessage(error: unknown, fallback: string) {
  return normalizeDatabaseError(error, fallback).message
}

function normalizeDatabaseError(error: unknown, fallback: string): DatabaseMutationErrorDetail {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return {
      code: 'request_error',
      message: detail,
    }
  }
  if (isRecord(detail)) {
    return {
      code: readString(detail.code, 'database_update_failed'),
      message: readString(detail.message, fallback),
      column: readOptionalString(detail.column),
      columns: readStringArray(detail.columns),
      hint: readOptionalString(detail.hint),
      detail: readOptionalString(detail.detail),
      expected: readOptionalString(detail.expected),
      received_type: readOptionalString(detail.received_type),
      received_value: readOptionalString(detail.received_value),
      database_error_type: readOptionalString(detail.database_error_type),
    }
  }
  return {
    code: 'request_error',
    message: fallback,
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function readString(value: unknown, fallback: string) {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function readOptionalString(value: unknown) {
  return typeof value === 'string' && value.trim() ? value : undefined
}

function readStringArray(value: unknown) {
  if (!Array.isArray(value)) return undefined
  const items = value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
  return items.length > 0 ? items : undefined
}
</script>
