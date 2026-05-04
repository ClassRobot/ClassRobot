<template>
  <div class="flex flex-col gap-4 h-full">
    <div class="flex items-center justify-between shrink-0">
      <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">Agent 管理</h1>
      <!-- Segmented control -->
      <div class="inline-flex bg-surface-container-lowest dark:bg-zinc-900 border border-outline-variant dark:border-zinc-700 p-1 rounded-lg">
        <button
          v-for="seg in segments"
          :key="seg.key"
          @click="activeSegment = seg.key; page = 1; fetchData()"
          class="px-3 py-1 rounded-md font-body-sm text-body-sm transition-colors"
          :class="activeSegment === seg.key
            ? 'bg-surface-container dark:bg-zinc-800 text-primary dark:text-primary-dark font-medium shadow-sm'
            : 'text-on-surface-variant dark:text-zinc-400 hover:text-on-surface dark:hover:text-zinc-200'"
        >
          {{ seg.label }}
          <span v-if="seg.key === 'pending' && pendingCount" class="ml-1.5 px-1.5 py-0.5 rounded-full bg-warning/20 dark:bg-amber-500/20 text-warning dark:text-amber-400 text-[10px] font-bold">{{ pendingCount }}</span>
        </button>
      </div>
    </div>

    <!-- Table -->
    <div class="flex-1 rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 overflow-hidden flex flex-col">
      <div class="flex items-center px-4 py-2 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50 gap-3">
        <div class="relative flex-1 max-w-[300px]">
          <Search :size="14" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant dark:text-zinc-500" />
          <input v-model="search" @input="onSearch" class="w-full pl-7 pr-3 py-1.5 rounded-lg border border-outline-variant dark:border-zinc-700 bg-surface-container dark:bg-zinc-800 text-body-sm text-on-surface dark:text-zinc-200 focus:outline-none focus:border-primary dark:focus:border-primary-dark" placeholder="搜索..." />
        </div>
        <AppSelect
          v-if="activeSegment === 'runs'"
          v-model="kindFilter"
          :options="kindOptions"
          wrapper-class="w-[128px]"
          @change="page = 1; fetchData()"
        />
      </div>
      <div class="overflow-auto flex-1">
        <table class="w-full text-left border-collapse whitespace-nowrap">
          <thead class="bg-surface-bright dark:bg-zinc-900/50 border-b border-outline-variant dark:border-zinc-800 sticky top-0 z-10">
            <tr>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">Trace ID</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">用户</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">类型</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase w-24">状态</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">目标</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase text-right">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-variant dark:divide-zinc-800 font-body-sm text-body-sm text-on-surface dark:text-zinc-200">
            <tr v-if="items.length === 0"><td colspan="6" class="p-8 text-center text-on-surface-variant dark:text-zinc-500">暂无记录</td></tr>
            <tr v-for="item in items" :key="`${activeSegment}-${item.id}`" class="hover:bg-surface-container dark:hover:bg-zinc-800/50 cursor-pointer transition-colors" @click="selectItem(item)">
              <td class="p-[10px_12px] font-code-block text-code-block text-primary dark:text-primary-dark">{{ item.trace_id || '-' }}</td>
              <td class="p-[10px_12px]">{{ item.user_id }}</td>
              <td class="p-[10px_12px]">{{ item.kind || '-' }}</td>
              <td class="p-[10px_12px]"><StatusChip :status="item.status || ''" /></td>
              <td class="p-[10px_12px] font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500">{{ item.goal || item.summary || '-' }}</td>
              <td class="p-[10px_12px] text-right">
                <div class="flex items-center justify-end gap-1">
                  <button @click.stop="selectItem(item)" class="p-1 text-on-surface-variant dark:text-zinc-400 hover:text-primary dark:hover:text-primary-dark rounded"><Eye :size="16" /></button>
                  <button @click.stop="copyTraceId(item)" class="p-1 text-on-surface-variant dark:text-zinc-400 hover:text-on-surface dark:hover:text-zinc-200 rounded"><Copy :size="16" /></button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="flex items-center justify-between px-4 py-2 border-t border-outline-variant dark:border-zinc-800 text-[11px] text-on-surface-variant dark:text-zinc-500">
        <span>共 {{ total }} 条，第 {{ page }}/{{ totalPages }} 页</span>
        <div class="flex gap-1">
          <button :disabled="page <= 1" @click="page--; fetchData()" class="px-2 py-1 rounded-lg border border-outline-variant dark:border-zinc-700 hover:bg-surface-container dark:hover:bg-zinc-800 disabled:opacity-40 text-body-sm">上一页</button>
          <button :disabled="page >= totalPages" @click="page++; fetchData()" class="px-2 py-1 rounded-lg border border-outline-variant dark:border-zinc-700 hover:bg-surface-container dark:hover:bg-zinc-800 disabled:opacity-40 text-body-sm">下一页</button>
        </div>
      </div>
    </div>

    <Teleport to="body">
      <div v-if="selectedItem" class="fixed inset-0 z-50">
        <div class="absolute inset-0 bg-black/10 dark:bg-black/40" @click="closeDetail" />
        <aside class="fixed right-0 top-topbar bottom-0 w-drawer-max bg-surface-container-lowest dark:bg-zinc-900 border-l border-outline-variant dark:border-zinc-800 flex flex-col shadow-xl">
          <div class="flex items-center justify-between p-4 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50">
            <div>
              <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">运行详情</h2>
              <p class="font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500 mt-0.5">{{ selectedItem.trace_id }}</p>
            </div>
            <button @click="closeDetail" class="p-1.5 text-on-surface-variant dark:text-zinc-400 hover:bg-surface-container dark:hover:bg-zinc-800 rounded-lg">
              <X :size="18" />
            </button>
          </div>
          <div class="flex-1 overflow-y-auto p-4">
            <div v-if="detailLoading" class="py-8 text-center text-on-surface-variant dark:text-zinc-500">加载中...</div>
            <pre v-else class="rounded-lg border border-outline-variant dark:border-zinc-800 bg-code dark:bg-zinc-800 p-4 font-code-block text-code-block text-on-surface dark:text-zinc-300 overflow-x-auto"><code>{{ JSON.stringify(detailData || selectedItem, null, 2) }}</code></pre>
          </div>
        </aside>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchAgentRuns, fetchAgentRun, fetchAgentCheckpoints, fetchAgentCheckpoint } from '@/api/agents'
import type { AgentRunDetail, AgentRunSummary, AgentCheckpointDetail, AgentCheckpointSummary } from '@/types/api'
import { Search, Eye, Copy, X } from 'lucide-vue-next'
import AppSelect from '@/components/AppSelect.vue'
import StatusChip from '@/components/StatusChip.vue'

const segments = [
  { key: 'runs', label: '运行记录' },
  { key: 'checkpoints', label: '检查点' },
  { key: 'pending', label: '待确认' },
  { key: 'failed', label: '失败记录' },
]
const activeSegment = ref('runs')
const items = ref<(AgentRunSummary | AgentCheckpointSummary)[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const search = ref('')
const kindFilter = ref('')
const pendingCount = ref(0)
const selectedItem = ref<AgentRunSummary | AgentCheckpointSummary | null>(null)
const detailData = ref<AgentRunDetail | AgentCheckpointDetail | null>(null)
const detailLoading = ref(false)
const kindOptions = [
  { label: '全部类型', value: '' },
  { label: 'Chat', value: 'chat' },
  { label: 'Task', value: 'task' },
]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

let searchTimer: ReturnType<typeof setTimeout>
function onSearch() { clearTimeout(searchTimer); searchTimer = setTimeout(() => { page.value = 1; fetchData() }, 300) }

onMounted(() => fetchData())

async function fetchData() {
  try {
    const pending = await fetchAgentCheckpoints({ status: 'needs_confirm', page: 1, page_size: 1 })
    pendingCount.value = pending.total

    if (activeSegment.value === 'checkpoints' || activeSegment.value === 'pending') {
      const res = await fetchAgentCheckpoints({
        status: activeSegment.value === 'pending' ? 'needs_confirm' : undefined,
        page: page.value,
        page_size: pageSize,
      })
      items.value = res.items
      total.value = res.total
    } else {
      const statusMap: Record<string, string | undefined> = {
        pending: 'needs_confirm',
        failed: 'failed',
      }
      const res = await fetchAgentRuns({
        status: statusMap[activeSegment.value],
        kind: kindFilter.value || undefined,
        q: search.value || undefined,
        page: page.value, page_size: pageSize,
      })
      items.value = res.items
      total.value = res.total
    }
  } catch { /* */ }
}

async function selectItem(item: AgentRunSummary | AgentCheckpointSummary) {
  selectedItem.value = item
  detailData.value = null
  detailLoading.value = true
  try {
    if (activeSegment.value === 'checkpoints' || activeSegment.value === 'pending') {
      detailData.value = await fetchAgentCheckpoint(item.user_id)
    } else {
      detailData.value = await fetchAgentRun(item.trace_id)
    }
  } catch { /* keep summary visible */ }
  detailLoading.value = false
}

function closeDetail() {
  selectedItem.value = null
  detailData.value = null
}

function copyTraceId(item: AgentRunSummary | AgentCheckpointSummary) {
  if (item.trace_id) navigator.clipboard?.writeText(item.trace_id)
}
</script>
