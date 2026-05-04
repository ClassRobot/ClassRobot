<template>
  <section class="rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 overflow-hidden">
    <div class="flex items-start justify-between gap-3 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50 px-4 py-3">
      <div>
        <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ title }}</h2>
        <p v-if="sub" class="mt-0.5 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">{{ sub }}</p>
      </div>
      <slot name="action" />
    </div>
    <div class="p-3">
      <VChart
        class="w-full"
        :style="{ height }"
        :option="option"
        :loading="loading"
        :loading-options="loadingOptions"
        autoresize
      />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart, GaugeChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { useTheme } from '@/composables/useTheme'

use([CanvasRenderer, BarChart, GaugeChart, PieChart, GridComponent, LegendComponent, TooltipComponent])

const { isDark } = useTheme()

withDefaults(defineProps<{
  title: string
  sub?: string
  option: Record<string, unknown>
  height?: string
  loading?: boolean
}>(), {
  sub: '',
  height: '220px',
  loading: false,
})

const loadingOptions = computed(() => ({
  text: '加载中',
  color: isDark.value ? '#4da394' : '#28645a',
  textColor: isDark.value ? '#e4e4e7' : '#404946',
  maskColor: isDark.value ? 'rgba(24, 24, 27, 0.72)' : 'rgba(248, 250, 243, 0.82)',
  zlevel: 0,
}))
</script>
