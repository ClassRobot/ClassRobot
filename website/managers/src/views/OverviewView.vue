<template>
  <div class="flex flex-col gap-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">系统总览</h1>
        <p class="font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500 mt-1">
          运行状态与关键资产概览
        </p>
      </div>
      <div class="flex items-center gap-2 text-body-sm text-body-sm text-on-surface-variant dark:text-zinc-400">
        <span class="w-2 h-2 rounded-full" :class="overallStatus === 'ok' ? 'bg-primary dark:bg-primary-dark' : 'bg-warning'"></span>
        <span v-if="overview">最近更新：{{ lastUpdatedText }}</span>
        <span v-else class="text-on-surface-variant/50">加载中...</span>
      </div>
    </div>

    <!-- Status cards grid -->
    <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
      <StatusCard label="运行状态" :status="runtimeStatus" :value="runtimeValue" :sub="runtimeSub" icon="Activity" />
      <StatusCard label="数据库" :status="dbStatus" :value="dbValue" :sub="dbSub" icon="Database" />
      <StatusCard label="缓存" :status="cacheStatus" :value="cacheValue" :sub="cacheSub" icon="Zap" />
      <StatusCard label="模型" :status="modelStatus" :value="modelValue" :sub="modelSub" icon="Cpu" />
      <StatusCard label="Skill" :status="skillStatus" :value="skillValue" :sub="skillSub" icon="Puzzle" />
      <StatusCard label="Agent" :status="agentStatus" :value="agentValue" :sub="agentSub" icon="Bot" />
    </div>

    <!-- Dashboard charts -->
    <div class="grid grid-cols-1 xl:grid-cols-3 gap-6">
      <ChartPanel
        title="资产分布"
        sub="系统资产数量占比"
        :option="assetChartOption"
        :loading="loading"
      />
      <ChartPanel
        title="健康状态"
        sub="运行依赖按状态聚合"
        :option="healthChartOption"
        :loading="loading"
      />
      <ChartPanel
        title="Agent 压力"
        sub="待确认工作流占运行量比例"
        :option="agentGaugeOption"
        :loading="loading"
      />
    </div>

    <!-- Row 2: Alerts + Quick Actions -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Alerts -->
      <div class="lg:col-span-2 rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 flex flex-col min-h-[200px]">
        <div class="flex items-center justify-between px-4 py-3 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50 rounded-t-xl">
          <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">异常提醒</h2>
        </div>
        <div v-if="alerts.length === 0" class="flex-1 flex items-center justify-center text-on-surface-variant dark:text-zinc-500 font-body-sm">
          暂无异常，系统运行正常
        </div>
        <div v-else class="p-2">
          <div
            v-for="alert in alerts"
            :key="alert.source"
            class="flex items-center gap-3 rounded-lg p-3 hover:bg-surface-container dark:hover:bg-zinc-800/50 transition-colors"
          >
            <TriangleAlert v-if="alert.level === 'warning'" :size="18" class="text-warning shrink-0" />
            <CircleX v-else-if="alert.level === 'error'" :size="18" class="text-error shrink-0" />
            <Settings v-else :size="18" class="text-on-surface-variant dark:text-zinc-500 shrink-0" />
            <div>
              <div class="font-body-sm text-body-sm text-on-surface dark:text-zinc-200">{{ alert.message }}</div>
              <div class="font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500 mt-0.5">{{ alert.source }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div class="rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 flex flex-col">
        <div class="px-4 py-3 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50 rounded-t-xl">
          <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">快捷操作</h2>
        </div>
        <div class="p-4 flex flex-col gap-2.5">
          <QuickBtn icon="FlaskConical" label="测试模型" @click="runAction('test_models')" />
          <QuickBtn icon="CheckCheck" label="校验 Prompt" @click="runAction('validate_prompts')" />
          <QuickBtn icon="RefreshCw" label="重载 Skill" @click="runAction('reload_skills')" />
          <div class="grid grid-cols-2 gap-2">
            <QuickBtn icon="Database" label="检查数据库" @click="runAction('check_database')" />
            <QuickBtn icon="FileText" label="打开日志" to="/operations" />
          </div>
        </div>
      </div>
    </div>

    <!-- Recent Agent Runs -->
    <div class="rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 flex flex-col flex-1 min-h-0">
      <div class="flex items-center justify-between px-4 py-3 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50 rounded-t-xl">
        <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">最近 Agent 运行</h2>
        <router-link to="/agents" class="font-body-sm text-body-sm text-primary dark:text-primary-dark hover:underline">查看全部</router-link>
      </div>
      <div class="overflow-auto">
        <table class="w-full text-left border-collapse whitespace-nowrap">
          <thead class="bg-surface-bright dark:bg-zinc-900/50 border-b border-outline-variant dark:border-zinc-800 sticky top-0 z-10">
            <tr>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">Trace ID</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">用户</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">类型</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase w-24">状态</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">目标</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase text-right">开始时间</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-variant dark:divide-zinc-800 font-body-sm text-body-sm text-on-surface dark:text-zinc-200">
            <tr v-if="!recentRuns || recentRuns.length === 0">
              <td colspan="6" class="p-8 text-center text-on-surface-variant dark:text-zinc-500">暂无运行记录</td>
            </tr>
            <tr
              v-for="run in recentRuns"
              :key="run.trace_id"
              class="hover:bg-surface-container dark:hover:bg-zinc-800/50 transition-colors h-[36px]"
            >
              <td class="p-[10px_12px] font-code-block text-code-block text-primary dark:text-primary-dark">{{ run.trace_id }}</td>
              <td class="p-[10px_12px]">{{ run.user_id }}</td>
              <td class="p-[10px_12px]">{{ run.kind }}</td>
              <td class="p-[10px_12px]">
                <StatusChip :status="run.status" />
              </td>
              <td class="p-[10px_12px] font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500">{{ run.goal || '-' }}</td>
              <td class="p-[10px_12px] font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500 text-right">{{ formatTime(run.started_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchOverview } from '@/api/overview'
import { fetchStatus } from '@/api/status'
import { runAction as runOpAction } from '@/api/operations'
import type { OverviewResponse, OverviewAlert, StatusLevel, StatusResponse } from '@/types/api'
import { TriangleAlert, CircleX, Settings } from 'lucide-vue-next'
import StatusCard from '@/components/StatusCard.vue'
import StatusChip from '@/components/StatusChip.vue'
import QuickBtn from '@/components/QuickBtn.vue'
import ChartPanel from '@/components/ChartPanel.vue'
import { useTheme } from '@/composables/useTheme'

const overview = ref<OverviewResponse | null>(null)
const statusData = ref<StatusResponse | null>(null)
const alerts = ref<OverviewAlert[]>([])
const loading = ref(true)
const lastUpdated = ref<Date | null>(null)
const { isDark } = useTheme()

onMounted(() => loadDashboard())

async function loadDashboard() {
  loading.value = true
  try {
    const [overviewPayload, statusPayload] = await Promise.all([fetchOverview(), fetchStatus()])
    overview.value = overviewPayload
    statusData.value = statusPayload
    alerts.value = overview.value.alerts || []
    lastUpdated.value = new Date()
  } catch { /* silent */ }
  loading.value = false
}

const recentRuns = computed(() => overview.value?.recent_runs || [])
const lastUpdatedText = computed(() => {
  if (!lastUpdated.value) return '-'
  return lastUpdated.value.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
})

// Derived status values from overview
const runtimeStatus = computed(() => overview.value?.runtime?.status || 'not_configured')
const runtimeValue = computed(() => overview.value?.runtime?.python_version || '-')
const runtimeSub = computed(() => overview.value?.runtime?.driver || '')

const dbStatus = computed(() => statusData.value?.database?.status || 'not_configured')
const dbValue = computed(() => statusData.value?.database?.alembic_version?.slice(0, 8) || '-')
const dbSub = computed(() => `${Object.values(statusData.value?.database?.tables || {}).reduce((a, b) => a + b, 0)} 条记录`)

const cacheStatus = computed(() => statusData.value?.cache?.status || 'not_configured')
const cacheValue = computed(() => {
  const cache = statusData.value?.cache
  if (!cache) return '-'
  return cache.backend || cache.configured_backend || `${cache.host}:${cache.port}`
})
const cacheSub = computed(() => {
  const cache = statusData.value?.cache
  if (!cache) return '连接检查'
  if (cache.backend === 'local') return cache.local_path || cache.path || '本地缓存兜底'
  return cache.message || `${cache.host}:${cache.port}`
})

const modelStatus = computed(() => overview.value?.assets.models ? 'ok' : 'not_configured')
const modelValue = computed(() => `${overview.value?.assets.models || 0}`)
const modelSub = computed(() => '已配置')

const skillStatus = computed(() => overview.value?.assets.skills ? 'ok' : 'not_configured')
const skillValue = computed(() => `${overview.value?.assets.skills || 0}`)
const skillSub = computed(() => '已加载')

const agentStatus = computed(() => (overview.value?.assets.pending_workflows || 0) > 0 ? 'warning' : 'ok')
const agentValue = computed(() => `${overview.value?.assets.agent_runs || 0}`)
const agentSub = computed(() => `${overview.value?.assets.pending_workflows || 0} 待确认`)
const overallStatus = computed<StatusLevel>(() => {
  if (alerts.value.some((item) => item.level === 'error')) return 'error'
  if (alerts.value.some((item) => item.level === 'warning' || item.level === 'not_configured')) return 'warning'
  return 'ok'
})

const chartPalette = computed(() => ({
  series: isDark.value ? ['#4da394', '#67a7ff', '#f2bf74', '#7dd4c5', '#737373'] : ['#28645a', '#2b6099', '#b7791f', '#4da394', '#707976'],
  text: isDark.value ? '#f4f4f5' : '#191c19',
  muted: isDark.value ? '#a1a1aa' : '#707976',
  axis: isDark.value ? '#52525b' : '#bfc9c5',
  split: isDark.value ? 'rgba(255,255,255,0.08)' : '#e1e3dd',
  tooltipBg: isDark.value ? 'rgba(24,24,27,0.96)' : 'rgba(255,255,255,0.96)',
  tooltipBorder: isDark.value ? 'rgba(113,113,122,0.5)' : 'rgba(191,201,197,0.9)',
  gaugeTrack: isDark.value ? 'rgba(255,255,255,0.12)' : '#e1e3dd',
}))

const assetChartOption = computed<Record<string, unknown>>(() => ({
  backgroundColor: 'transparent',
  color: chartPalette.value.series,
  tooltip: {
    trigger: 'item',
    backgroundColor: chartPalette.value.tooltipBg,
    borderColor: chartPalette.value.tooltipBorder,
    textStyle: { color: chartPalette.value.text },
  },
  legend: {
    bottom: 0,
    left: 'center',
    itemWidth: 10,
    itemHeight: 10,
    textStyle: { color: chartPalette.value.muted },
  },
  series: [
    {
      name: '资产',
      type: 'pie',
      radius: ['52%', '72%'],
      center: ['50%', '43%'],
      avoidLabelOverlap: true,
      label: { formatter: '{b}\n{c}', color: chartPalette.value.text },
      data: [
        { name: 'Skill', value: overview.value?.assets.skills || 0 },
        { name: 'Prompt', value: overview.value?.assets.prompts || 0 },
        { name: 'Model', value: overview.value?.assets.models || 0 },
        { name: 'Agent', value: overview.value?.assets.agent_runs || 0 },
        { name: '待确认', value: overview.value?.assets.pending_workflows || 0 },
      ],
    },
  ],
}))

const healthCounts = computed(() => {
  const counts: Record<string, number> = { ok: 0, warning: 0, error: 0, not_configured: 0 }
  const statusItems = [
    statusData.value?.runtime?.status,
    statusData.value?.database?.status,
    statusData.value?.cache?.status,
    statusData.value?.models?.status,
    statusData.value?.cos?.status,
    statusData.value?.ragflow?.status,
  ]
  for (const item of statusItems) {
    const normalized = item === 'configured' ? 'ok' : item || 'not_configured'
    counts[normalized] = (counts[normalized] || 0) + 1
  }
  return counts
})

const healthChartOption = computed<Record<string, unknown>>(() => ({
  backgroundColor: 'transparent',
  color: isDark.value ? ['#4da394', '#f2bf74', '#f87171', '#71717a'] : ['#28645a', '#b7791f', '#ba1a1a', '#707976'],
  tooltip: {
    trigger: 'axis',
    backgroundColor: chartPalette.value.tooltipBg,
    borderColor: chartPalette.value.tooltipBorder,
    textStyle: { color: chartPalette.value.text },
  },
  grid: { left: 28, right: 12, top: 18, bottom: 28 },
  xAxis: {
    type: 'category',
    data: ['正常', '警告', '异常', '未配置'],
    axisLabel: { color: chartPalette.value.muted },
    axisTick: { show: false },
    axisLine: { lineStyle: { color: chartPalette.value.axis } },
  },
  yAxis: {
    type: 'value',
    minInterval: 1,
    axisLabel: { color: chartPalette.value.muted },
    splitLine: { lineStyle: { color: chartPalette.value.split } },
  },
  series: [
    {
      type: 'bar',
      barWidth: 28,
      borderRadius: [6, 6, 0, 0],
      data: [
        healthCounts.value.ok,
        healthCounts.value.warning,
        healthCounts.value.error,
        healthCounts.value.not_configured,
      ],
    },
  ],
}))

const agentGaugeOption = computed<Record<string, unknown>>(() => {
  const runs = overview.value?.assets.agent_runs || 0
  const pending = overview.value?.assets.pending_workflows || 0
  const value = runs > 0 ? Math.min(100, Math.round((pending / runs) * 100)) : 0
  return {
    backgroundColor: 'transparent',
    color: [isDark.value ? '#f2bf74' : '#b7791f'],
    tooltip: {
      backgroundColor: chartPalette.value.tooltipBg,
      borderColor: chartPalette.value.tooltipBorder,
      textStyle: { color: chartPalette.value.text },
    },
    series: [
      {
        type: 'gauge',
        min: 0,
        max: 100,
        progress: { show: true, roundCap: true, width: 12 },
        axisLine: { lineStyle: { width: 12, color: [[1, chartPalette.value.gaugeTrack]] } },
        axisTick: { show: false },
        splitLine: { show: false },
        axisLabel: { show: false },
        pointer: { show: false },
        detail: {
          valueAnimation: true,
          formatter: `${pending} / ${runs || 0}`,
          color: chartPalette.value.text,
          fontSize: 24,
          fontWeight: 600,
          offsetCenter: [0, '4%'],
        },
        title: { offsetCenter: [0, '42%'], color: chartPalette.value.muted, fontSize: 12 },
        data: [{ value, name: '待确认 / 总运行' }],
      },
    ],
  }
})

function formatTime(iso: string | null) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch { return iso }
}

async function runAction(id: string) {
  try {
    await runOpAction(id)
    await loadDashboard()
  } catch { /* toast later */ }
}
</script>
