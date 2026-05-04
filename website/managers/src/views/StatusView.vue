<template>
  <div class="flex flex-col gap-6">
    <div>
      <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">系统状态</h1>
      <p class="font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500 mt-1">实时运行环境健康检查</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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

    <!-- Detail drawer -->
    <Teleport to="body">
      <div v-if="drawerOpen" class="fixed inset-0 z-50">
        <div class="absolute inset-0 bg-black/10 dark:bg-black/40" @click="drawerOpen = false" />
        <aside class="fixed right-0 top-topbar bottom-0 w-drawer-max bg-surface-container-lowest dark:bg-zinc-900 border-l border-outline-variant dark:border-zinc-800 flex flex-col shadow-xl">
          <div class="flex items-center justify-between p-4 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50">
            <div class="flex items-center gap-2">
              <Activity :size="20" class="text-primary dark:text-primary-dark" />
              <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ drawerTitle }}</h2>
              <StatusChip :status="drawerStatus" />
            </div>
            <button @click="drawerOpen = false" class="p-1.5 text-on-surface-variant dark:text-zinc-400 hover:bg-surface-container dark:hover:bg-zinc-800 rounded-lg">
              <X :size="18" />
            </button>
          </div>
          <div class="flex-1 overflow-y-auto p-4 space-y-5">
            <div v-if="detailLoading" class="text-on-surface-variant dark:text-zinc-500 text-center py-8">加载中...</div>
            <div v-else>
              <pre class="rounded-lg border border-outline-variant dark:border-zinc-800 bg-code dark:bg-zinc-800 p-4 font-code-block text-code-block text-on-surface dark:text-zinc-300 overflow-x-auto"><code>{{ JSON.stringify(detailData, null, 2) }}</code></pre>
            </div>
          </div>
        </aside>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchStatus } from '@/api/status'
import type { StatusResponse } from '@/types/api'
import { Activity, X } from 'lucide-vue-next'
import StatusCard from '@/components/StatusCard.vue'
import StatusChip from '@/components/StatusChip.vue'

const statusData = ref<StatusResponse | null>(null)
const drawerOpen = ref(false)
const detailKey = ref('')
const detailLoading = ref(false)

onMounted(async () => {
  try { statusData.value = await fetchStatus() } catch { /* */ }
})

const cards = computed(() => [
  { key: 'runtime', label: '运行状态', status: statusData.value?.runtime?.status || 'not_configured', value: statusData.value?.runtime?.python_version || '-', sub: statusData.value?.runtime?.driver || '' },
  { key: 'database', label: '数据库', status: statusData.value?.database?.status || 'not_configured', value: statusData.value?.database?.alembic_version?.slice(0, 8) || '-', sub: `${Object.values(statusData.value?.database?.tables || {}).reduce((a, b) => a + b, 0)} 条记录` },
  { key: 'cache', label: '缓存', status: statusData.value?.cache?.status || 'not_configured', value: `${statusData.value?.cache?.host || '-'}:${statusData.value?.cache?.port || ''}`, sub: statusData.value?.cache?.message || '' },
  { key: 'models', label: '模型', status: statusData.value?.models?.status || 'not_configured', value: `${statusData.value?.models?.configured || 0}`, sub: statusData.value?.models?.names?.join(', ') || '未配置' },
  { key: 'cos', label: 'COS 存储', status: statusData.value?.cos?.status || 'not_configured', value: statusData.value?.cos?.region || '-', sub: statusData.value?.cos?.bucket || '' },
  { key: 'ragflow', label: 'RAGFlow', status: statusData.value?.ragflow?.status || 'not_configured', value: statusData.value?.ragflow?.has_key ? '已配置' : '未配置', sub: statusData.value?.ragflow?.url || '' },
])

const drawerTitle = computed(() => cards.value.find(c => c.key === detailKey.value)?.label || '详情')
const drawerStatus = computed(() => cards.value.find(c => c.key === detailKey.value)?.status || 'not_configured')
const detailData = computed(() => {
  if (!statusData.value || !detailKey.value) return {}
  const key = detailKey.value as keyof StatusResponse
  return statusData.value[key] || {}
})

function openDetail(key: string) {
  detailKey.value = key
  drawerOpen.value = true
}
</script>
