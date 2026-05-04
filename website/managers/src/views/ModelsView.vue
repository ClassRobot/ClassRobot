<template>
  <div class="flex flex-col gap-4 h-full">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">Model 管理</h1>
        <p class="font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500 mt-1">模型配置、路由与连通性测试</p>
      </div>
      <div class="flex items-center gap-3">
        <span class="font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-400">超时: {{ modelTimeout }}s</span>
        <button @click="refresh" class="p-2 rounded-lg border border-outline-variant dark:border-zinc-700 text-on-surface-variant dark:text-zinc-400 hover:bg-surface-container dark:hover:bg-zinc-800">
          <RefreshCw :size="16" />
        </button>
      </div>
    </div>

    <div class="flex-1 rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 overflow-hidden flex flex-col">
      <div class="overflow-auto flex-1">
        <table class="w-full text-left border-collapse whitespace-nowrap">
          <thead class="bg-surface-bright dark:bg-zinc-900/50 border-b border-outline-variant dark:border-zinc-800 sticky top-0 z-10">
            <tr>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">名称</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">模型</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">Base URL</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">优先级</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">多模态</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">工具调用</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase w-10 text-center">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-variant dark:divide-zinc-800 font-body-sm text-body-sm text-on-surface dark:text-zinc-200">
            <tr v-if="models.length === 0"><td colspan="7" class="p-8 text-center text-on-surface-variant dark:text-zinc-500">暂无模型配置</td></tr>
            <tr v-for="m in models" :key="m.name" class="hover:bg-surface-container dark:hover:bg-zinc-800/50 transition-colors">
              <td class="p-[10px_12px] font-medium">{{ m.name }}</td>
              <td class="p-[10px_12px] font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-400">{{ m.model }}</td>
              <td class="p-[10px_12px] font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-400 truncate max-w-[200px]">{{ m.url }}</td>
              <td class="p-[10px_12px]">{{ m.priority }}</td>
              <td class="p-[10px_12px]"><StatusChip :status="m.multi_modal ? 'ok' : 'not_configured'" /></td>
              <td class="p-[10px_12px]"><StatusChip :status="m.supports_functools ? 'ok' : 'not_configured'" /></td>
              <td class="p-[10px_12px] text-center">
                <button @click="testModel(m.name)" :disabled="testing === m.name" class="p-1 text-on-surface-variant dark:text-zinc-400 hover:text-primary dark:hover:text-primary-dark rounded disabled:opacity-50" title="测试连通性">
                  <Loader2 v-if="testing === m.name" :size="16" class="animate-spin" />
                  <FlaskConical v-else :size="16" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Test result toast -->
    <div v-if="testResult" class="fixed bottom-6 right-6 rounded-xl border px-4 py-3 font-body-sm shadow-lg transition-all z-50"
      :class="testResult.ok
        ? 'bg-primary/10 dark:bg-emerald-500/10 border-primary/20 dark:border-emerald-500/20 text-primary dark:text-emerald-400'
        : 'bg-error/10 dark:bg-red-500/10 border-error/20 dark:border-red-500/20 text-error dark:text-red-400'">
      <div class="flex items-center gap-2">
        <CircleCheck v-if="testResult.ok" :size="16" />
        <CircleX v-else :size="16" />
        <span>{{ testResult.ok ? `连通成功 (${testResult.latency_ms}ms)` : testResult.message || '连接失败' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchModels, testModel as testModelApi } from '@/api/models'
import type { ModelConfigItem, ModelTestResult } from '@/types/api'
import { RefreshCw, FlaskConical, Loader2, CircleCheck, CircleX } from 'lucide-vue-next'
import StatusChip from '@/components/StatusChip.vue'

const models = ref<ModelConfigItem[]>([])
const modelTimeout = ref(60)
const testing = ref('')
const testResult = ref<ModelTestResult | null>(null)
let resultTimer: ReturnType<typeof setTimeout>

onMounted(() => refresh())

async function refresh() {
  try {
    const data = await fetchModels()
    models.value = data.items || []
    if (data.llm_timeout) modelTimeout.value = data.llm_timeout
  } catch { /* */ }
}

async function testModel(name: string) {
  testing.value = name
  testResult.value = null
  try {
    testResult.value = await testModelApi(name)
  } catch (e: unknown) {
    testResult.value = { ok: false, message: (e as Error).message || '请求失败' }
  }
  testing.value = ''
  clearTimeout(resultTimer)
  resultTimer = setTimeout(() => { testResult.value = null }, 4000)
}
</script>
