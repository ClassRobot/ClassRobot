<template>
  <div class="flex flex-col gap-6">
    <div>
      <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">MCP / 集成管理</h1>
      <p class="font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500 mt-1">外部服务连接状态与集成能力面板</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <!-- MCP -->
      <div class="rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 p-5 flex flex-col gap-4">
        <div class="flex items-start justify-between">
          <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">MCP 注册表</h2>
          <StatusChip :status="integrations?.mcp?.status || 'not_configured'" />
        </div>
        <p class="font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">{{ integrations?.mcp?.message || '加载中...' }}</p>
        <div class="mt-auto pt-3 border-t border-outline-variant dark:border-zinc-800 flex justify-between items-center">
          <span class="font-body-sm text-on-surface-variant dark:text-zinc-500">当前仓库尚未接入 MCP 注册表</span>
          <a href="#" class="text-primary dark:text-primary-dark font-body-sm hover:underline">架构文档</a>
        </div>
      </div>

      <!-- RAGFlow -->
      <div class="rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 p-5 flex flex-col gap-4">
        <div class="flex items-start justify-between">
          <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">RAGFlow</h2>
          <StatusChip :status="integrations?.ragflow?.status || 'not_configured'" />
        </div>
        <div class="space-y-2 font-body-sm text-body-sm">
          <div class="flex justify-between"><span class="text-on-surface-variant dark:text-zinc-500">URL</span><span class="text-on-surface dark:text-zinc-200 font-code-inline">{{ integrations?.ragflow?.url || '-' }}</span></div>
          <div class="flex justify-between"><span class="text-on-surface-variant dark:text-zinc-500">密钥</span><span class="text-on-surface dark:text-zinc-200 font-code-inline">{{ integrations?.ragflow?.has_key ? '已配置' : '未配置' }}</span></div>
        </div>
      </div>

      <!-- COS -->
      <div class="rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 p-5 flex flex-col gap-4">
        <div class="flex items-start justify-between">
          <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">COS 对象存储</h2>
          <StatusChip :status="integrations?.cos?.status || 'not_configured'" />
        </div>
        <div class="space-y-2 font-body-sm text-body-sm">
          <div class="flex justify-between"><span class="text-on-surface-variant dark:text-zinc-500">Region</span><span class="text-on-surface dark:text-zinc-200 font-code-inline">{{ integrations?.cos?.region || '-' }}</span></div>
          <div class="flex justify-between"><span class="text-on-surface-variant dark:text-zinc-500">Bucket</span><span class="text-on-surface dark:text-zinc-200 font-code-inline">{{ integrations?.cos?.bucket || '-' }}</span></div>
          <div class="flex justify-between"><span class="text-on-surface-variant dark:text-zinc-500">Scheme</span><span class="text-on-surface dark:text-zinc-200 font-code-inline">{{ integrations?.cos?.scheme || '-' }}</span></div>
        </div>
      </div>

      <!-- Models -->
      <div class="rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 p-5 flex flex-col gap-4">
        <div class="flex items-start justify-between">
          <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">模型 Provider</h2>
          <StatusChip :status="integrations?.models?.status || 'not_configured'" />
        </div>
        <div class="space-y-2 font-body-sm text-body-sm">
          <div class="flex justify-between"><span class="text-on-surface-variant dark:text-zinc-500">已配置</span><span class="text-on-surface dark:text-zinc-200 font-code-inline">{{ integrations?.models?.configured || 0 }}</span></div>
          <div class="flex justify-between"><span class="text-on-surface-variant dark:text-zinc-500">模型列表</span><span class="text-on-surface dark:text-zinc-200 font-code-inline text-right max-w-[200px] truncate">{{ integrations?.models?.names?.join(', ') || '-' }}</span></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchIntegrations } from '@/api/integrations'
import type { IntegrationsResponse } from '@/types/api'
import StatusChip from '@/components/StatusChip.vue'

const integrations = ref<IntegrationsResponse | null>(null)

onMounted(async () => {
  try { integrations.value = await fetchIntegrations() } catch { /* */ }
})
</script>
