<template>
  <div class="flex flex-col gap-6">
    <div class="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">系统状态</h1>
        <p class="mt-1 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">
          实时资源、运行环境与健康检查
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span class="rounded-full border border-outline-variant bg-surface-container-lowest px-3 py-1 font-code-inline text-code-inline text-on-surface-variant dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
          {{ metricsUpdatedAt }}
        </span>
        <button
          type="button"
          class="inline-flex h-9 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 font-body-sm text-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
          @click="reloadAll"
        >
          <RefreshCw :size="15" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
      </div>
    </div>

    <section class="rounded-2xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div class="mb-4 flex items-center justify-between gap-3">
        <div>
          <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">实时资源</h2>
          <p class="mt-1 text-body-sm text-on-surface-variant dark:text-zinc-500">
            每 3 秒自动刷新，便于观察系统工作时的负载变化
          </p>
        </div>
        <StatusChip :status="systemMetrics?.status || 'not_configured'" />
      </div>

      <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45">
          <div class="flex items-center justify-between">
            <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">CPU</span>
            <Cpu :size="16" class="text-primary dark:text-primary-dark" />
          </div>
          <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ formatPercent(systemMetrics?.cpu.percent) }}</div>
          <div class="mt-2 h-2 overflow-hidden rounded-full bg-surface-container dark:bg-zinc-800">
            <div class="h-full rounded-full transition-all duration-300" :class="barClass(systemMetrics?.cpu.percent)" :style="{ width: barWidth(systemMetrics?.cpu.percent) }" />
          </div>
          <p class="mt-2 text-body-sm text-on-surface-variant dark:text-zinc-500">
            {{ systemMetrics?.cpu.count || '-' }} 逻辑核心
          </p>
        </div>

        <div class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45">
          <div class="flex items-center justify-between">
            <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">内存</span>
            <MemoryStick :size="16" class="text-primary dark:text-primary-dark" />
          </div>
          <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ formatPercent(systemMetrics?.memory?.percent) }}</div>
          <div class="mt-2 h-2 overflow-hidden rounded-full bg-surface-container dark:bg-zinc-800">
            <div class="h-full rounded-full transition-all duration-300" :class="barClass(systemMetrics?.memory?.percent)" :style="{ width: barWidth(systemMetrics?.memory?.percent) }" />
          </div>
          <p class="mt-2 text-body-sm text-on-surface-variant dark:text-zinc-500">
            {{ formatBytes(systemMetrics?.memory?.used) }} / {{ formatBytes(systemMetrics?.memory?.total) }}
          </p>
        </div>

        <div class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45">
          <div class="flex items-center justify-between">
            <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">磁盘峰值</span>
            <HardDrive :size="16" class="text-primary dark:text-primary-dark" />
          </div>
          <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ formatPercent(maxDisk?.percent) }}</div>
          <div class="mt-2 h-2 overflow-hidden rounded-full bg-surface-container dark:bg-zinc-800">
            <div class="h-full rounded-full transition-all duration-300" :class="barClass(maxDisk?.percent)" :style="{ width: barWidth(maxDisk?.percent) }" />
          </div>
          <p class="mt-2 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">
            {{ maxDisk?.mountpoint || '暂无磁盘信息' }}
          </p>
        </div>

        <div class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45">
          <div class="flex items-center justify-between">
            <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">进程</span>
            <Gauge :size="16" class="text-primary dark:text-primary-dark" />
          </div>
          <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ formatDuration(systemMetrics?.process?.uptime_seconds) }}</div>
          <p class="mt-2 text-body-sm text-on-surface-variant dark:text-zinc-500">
            PID {{ systemMetrics?.process?.pid || '-' }} · {{ systemMetrics?.process?.threads || '-' }} 线程
          </p>
          <p class="mt-1 text-body-sm text-on-surface-variant dark:text-zinc-500">
            RSS {{ formatBytes(systemMetrics?.process?.memory_rss) }}
          </p>
        </div>
      </div>

      <div class="mt-4 rounded-xl border border-outline-variant bg-surface-container-low p-3 dark:border-zinc-800 dark:bg-zinc-800/50">
        <div class="mb-3 flex items-center gap-2 text-body-sm font-medium text-on-surface dark:text-zinc-200">
          <HardDrive :size="15" />
          磁盘空间
        </div>
        <div class="grid gap-2 lg:grid-cols-2">
          <div
            v-for="disk in systemMetrics?.disks || []"
            :key="`${disk.device}-${disk.mountpoint}`"
            class="rounded-lg border border-outline-variant bg-surface-container-lowest p-3 dark:border-zinc-800 dark:bg-zinc-900"
          >
            <div class="mb-2 flex items-center justify-between gap-3">
              <span class="truncate font-code-inline text-code-inline text-on-surface dark:text-zinc-200">{{ disk.mountpoint }}</span>
              <span class="text-body-sm text-on-surface-variant dark:text-zinc-500">{{ formatPercent(disk.percent) }}</span>
            </div>
            <div class="h-2 overflow-hidden rounded-full bg-surface-container dark:bg-zinc-800">
              <div class="h-full rounded-full" :class="barClass(disk.percent)" :style="{ width: barWidth(disk.percent) }" />
            </div>
            <div class="mt-2 flex items-center justify-between text-[12px] text-on-surface-variant dark:text-zinc-500">
              <span>{{ disk.fstype || 'unknown' }}</span>
              <span>{{ formatBytes(disk.free) }} 可用 / {{ formatBytes(disk.total) }}</span>
            </div>
          </div>
          <div v-if="!systemMetrics?.disks?.length" class="rounded-lg border border-dashed border-outline-variant p-6 text-center text-body-sm text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
            暂无磁盘信息
          </div>
        </div>
      </div>
    </section>

    <section>
      <div class="mb-3 flex items-center justify-between">
        <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">健康检查</h2>
        <button
          type="button"
          class="inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-body-sm text-on-surface-variant transition-colors hover:bg-surface-container dark:text-zinc-400 dark:hover:bg-zinc-800"
          @click="loadStatus"
        >
          <RefreshCw :size="14" />
          重新检查
        </button>
      </div>
      <div class="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <StatusCard
          v-for="card in cards"
          :key="card.key"
          :label="card.label"
          :status="card.status"
          :value="card.value"
          :sub="card.sub"
          @click="openDetail(card.key)"
        />
      </div>
    </section>

    <Teleport to="body">
      <div v-if="drawerOpen" class="fixed inset-0 z-50">
        <div class="absolute inset-0 bg-black/10 dark:bg-black/40" @click="drawerOpen = false" />
        <aside class="fixed bottom-0 right-0 top-topbar flex w-drawer-max flex-col border-l border-outline-variant bg-surface-container-lowest shadow-xl dark:border-zinc-800 dark:bg-zinc-900">
          <div class="flex items-center justify-between border-b border-outline-variant bg-surface-bright p-4 dark:border-zinc-800 dark:bg-zinc-900/50">
            <div class="flex items-center gap-2">
              <Activity :size="20" class="text-primary dark:text-primary-dark" />
              <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ drawerTitle }}</h2>
              <StatusChip :status="drawerStatus" />
            </div>
            <button @click="drawerOpen = false" class="rounded-lg p-1.5 text-on-surface-variant hover:bg-surface-container dark:text-zinc-400 dark:hover:bg-zinc-800">
              <X :size="18" />
            </button>
          </div>
          <div class="flex-1 overflow-y-auto p-4">
            <pre class="overflow-x-auto rounded-lg border border-outline-variant bg-code p-4 font-code-block text-code-block text-on-surface dark:border-zinc-800 dark:bg-zinc-800 dark:text-zinc-300"><code>{{ JSON.stringify(detailData, null, 2) }}</code></pre>
          </div>
        </aside>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Activity, Cpu, Gauge, HardDrive, MemoryStick, RefreshCw, X } from 'lucide-vue-next'
import { fetchStatus, fetchSystemMetrics } from '@/api/status'
import type { StatusResponse, SystemDiskMetrics, SystemMetrics } from '@/types/api'
import StatusCard from '@/components/StatusCard.vue'
import StatusChip from '@/components/StatusChip.vue'

const statusData = ref<StatusResponse | null>(null)
const systemMetrics = ref<SystemMetrics | null>(null)
const drawerOpen = ref(false)
const detailKey = ref('')
const loading = ref(false)
let metricsTimer: number | undefined
let statusTimer: number | undefined

onMounted(async () => {
  await reloadAll()
  metricsTimer = window.setInterval(loadMetrics, 3000)
  statusTimer = window.setInterval(loadStatus, 15000)
})

onBeforeUnmount(() => {
  if (metricsTimer) window.clearInterval(metricsTimer)
  if (statusTimer) window.clearInterval(statusTimer)
})

const maxDisk = computed<SystemDiskMetrics | null>(() => {
  const disks = systemMetrics.value?.disks || []
  if (!disks.length) return null
  return [...disks].sort((a, b) => b.percent - a.percent)[0]
})

const metricsUpdatedAt = computed(() => {
  if (!systemMetrics.value?.timestamp) return '等待采样'
  return `更新于 ${new Date(systemMetrics.value.timestamp).toLocaleTimeString()}`
})

const cards = computed(() => [
  { key: 'runtime', label: '运行状态', status: statusData.value?.runtime?.status || 'not_configured', value: statusData.value?.runtime?.python_version || '-', sub: statusData.value?.runtime?.driver || '' },
  { key: 'database', label: '数据库', status: statusData.value?.database?.status || 'not_configured', value: statusData.value?.database?.alembic_version?.slice(0, 8) || '-', sub: `${Object.values(statusData.value?.database?.tables || {}).reduce((a, b) => a + b, 0)} 条记录` },
  {
    key: 'cache',
    label: '缓存',
    status: statusData.value?.cache?.status || 'not_configured',
    value: statusData.value?.cache?.backend || statusData.value?.cache?.configured_backend || `${statusData.value?.cache?.host || '-'}:${statusData.value?.cache?.port || ''}`,
    sub: statusData.value?.cache?.backend === 'local'
      ? statusData.value?.cache?.local_path || statusData.value?.cache?.path || '本地缓存兜底'
      : statusData.value?.cache?.message || `${statusData.value?.cache?.host || '-'}:${statusData.value?.cache?.port || ''}`,
  },
  { key: 'models', label: '模型', status: statusData.value?.models?.status || 'not_configured', value: `${statusData.value?.models?.configured || 0}`, sub: statusData.value?.models?.names?.join(', ') || '未配置' },
  { key: 'cos', label: 'COS 存储', status: statusData.value?.cos?.status || 'not_configured', value: statusData.value?.cos?.region || '-', sub: statusData.value?.cos?.bucket || '' },
  { key: 'ragflow', label: 'RAGFlow', status: statusData.value?.ragflow?.status || 'not_configured', value: statusData.value?.ragflow?.has_key ? '已配置' : '未配置', sub: statusData.value?.ragflow?.url || '' },
])

const drawerTitle = computed(() => cards.value.find((card) => card.key === detailKey.value)?.label || '详情')
const drawerStatus = computed(() => cards.value.find((card) => card.key === detailKey.value)?.status || 'not_configured')
const detailData = computed(() => {
  if (!statusData.value || !detailKey.value) return {}
  const key = detailKey.value as keyof StatusResponse
  return statusData.value[key] || {}
})

async function reloadAll() {
  loading.value = true
  try {
    await Promise.all([loadStatus(), loadMetrics()])
  } finally {
    loading.value = false
  }
}

async function loadStatus() {
  try {
    const data = await fetchStatus()
    statusData.value = data
    if (data.system) systemMetrics.value = data.system
  } catch { /* keep last good snapshot */ }
}

async function loadMetrics() {
  try {
    systemMetrics.value = await fetchSystemMetrics()
  } catch { /* keep last good snapshot */ }
}

function openDetail(key: string) {
  detailKey.value = key
  drawerOpen.value = true
}

function formatPercent(value: number | null | undefined) {
  return typeof value === 'number' ? `${value.toFixed(value % 1 === 0 ? 0 : 1)}%` : '-'
}

function barWidth(value: number | null | undefined) {
  if (typeof value !== 'number') return '0%'
  return `${Math.min(Math.max(value, 0), 100)}%`
}

function barClass(value: number | null | undefined) {
  if (typeof value !== 'number') return 'bg-surface-variant dark:bg-zinc-700'
  if (value >= 90) return 'bg-error dark:bg-red-500'
  if (value >= 75) return 'bg-warning dark:bg-amber-400'
  return 'bg-primary dark:bg-primary-dark'
}

function formatBytes(value: number | null | undefined) {
  if (typeof value !== 'number') return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function formatDuration(seconds: number | null | undefined) {
  if (typeof seconds !== 'number') return '-'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}
</script>
