<template>
  <div class="space-y-6">
    <section class="grid gap-4 xl:grid-cols-3">
      <MetricCard
        v-for="metric in overview?.metrics ?? []"
        :key="metric.key"
        :label="metric.label"
        :value="metric.value"
        :description="metric.description"
        :tone="metricTone(metric.key)"
      />
    </section>

    <div class="grid gap-6 xl:grid-cols-[1.25fr_0.75fr]">
      <SectionPanel title="命令作用域分布" description="帮助系统里各目录下命令数量的当前分布。">
        <VChart class="h-[320px]" :option="commandScopeOption" autoresize />
      </SectionPanel>
      <SectionPanel title="工作流状态" description="数据库历史中记录到的工作流状态分布。">
        <VChart class="h-[320px]" :option="workflowStatusOption" autoresize />
      </SectionPanel>
    </div>

    <SectionPanel title="数据库快照" description="挑选后台首页最常用的核心业务表数量。">
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div
          v-for="table in database?.tables ?? []"
          :key="table.key"
          class="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4"
        >
          <p class="text-sm text-slate-500">{{ table.label }}</p>
          <p class="mt-3 font-mono text-3xl font-semibold text-brand-ink">{{ table.count }}</p>
        </div>
      </div>
    </SectionPanel>

    <p v-if="errorMessage" class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
      {{ errorMessage }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import VChart from "vue-echarts";

import MetricCard from "@/components/MetricCard.vue";
import SectionPanel from "@/components/SectionPanel.vue";
import { normalizeApiError } from "@/api/client";
import { fetchAdminDatabase, fetchAdminOverview } from "@/api/modules/admin";
import type { AdminDatabaseOverviewResponse, AdminOverviewResponse } from "@/types/admin";

const overview = ref<AdminOverviewResponse | null>(null);
const database = ref<AdminDatabaseOverviewResponse | null>(null);
const errorMessage = ref("");

const commandScopeOption = computed(() => ({
  tooltip: { trigger: "axis" },
  grid: { left: 20, right: 20, top: 30, bottom: 10, containLabel: true },
  xAxis: {
    type: "category",
    data: (overview.value?.command_scope_distribution ?? []).map((item) => item.name),
    axisLabel: { color: "#475569" },
    axisLine: { lineStyle: { color: "#cbd5e1" } },
  },
  yAxis: {
    type: "value",
    axisLabel: { color: "#64748b" },
    splitLine: { lineStyle: { color: "#e2e8f0" } },
  },
  series: [
    {
      type: "bar",
      data: (overview.value?.command_scope_distribution ?? []).map((item) => item.value),
      itemStyle: { color: "#1e3a5f", borderRadius: [12, 12, 0, 0] },
    },
  ],
}));

const workflowStatusOption = computed(() => ({
  tooltip: { trigger: "item" },
  legend: { bottom: 0, textStyle: { color: "#475569" } },
  series: [
    {
      type: "pie",
      radius: ["40%", "72%"],
      avoidLabelOverlap: true,
      data: overview.value?.workflow_status_distribution ?? [],
      itemStyle: {
        borderColor: "#ffffff",
        borderWidth: 4,
      },
    },
  ],
}));

function metricTone(key: string) {
  if (key.includes("commands")) return "sea";
  if (key.includes("users")) return "mint";
  if (key.includes("tasks")) return "amber";
  return "ink";
}

onMounted(async () => {
  try {
    const [overviewData, databaseData] = await Promise.all([fetchAdminOverview(), fetchAdminDatabase()]);
    overview.value = overviewData;
    database.value = databaseData;
  } catch (error) {
    errorMessage.value = normalizeApiError(error);
  }
});
</script>
