<template>
  <div class="space-y-6">
    <SectionPanel title="数据库体量概览" description="先聚焦核心业务表数量，后续再扩展只读查询和受控维护操作。">
      <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <div
          v-for="table in database?.tables ?? []"
          :key="table.key"
          class="rounded-[28px] border border-slate-200 bg-white px-5 py-4 shadow-sm"
        >
          <p class="text-sm text-slate-500">{{ table.label }}</p>
          <p class="mt-3 font-mono text-4xl font-semibold text-brand-ink">{{ table.count }}</p>
          <p class="mt-2 text-xs uppercase tracking-[0.2em] text-slate-400">{{ table.key }}</p>
        </div>
      </div>
    </SectionPanel>

    <div class="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
      <SectionPanel title="表数量分布" description="使用环形图快速识别目前占比较高的业务表。">
        <VChart class="h-[360px]" :option="tableChartOption" autoresize />
      </SectionPanel>
      <SectionPanel title="表清单" description="这部分先保持只读，避免后台直接变成通用 SQL 编辑器。">
        <div class="overflow-hidden rounded-[28px] border border-slate-200">
          <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead class="bg-slate-50 text-slate-500">
              <tr>
                <th class="px-4 py-3 font-medium">表标识</th>
                <th class="px-4 py-3 font-medium">名称</th>
                <th class="px-4 py-3 font-medium">记录数</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 bg-white">
              <tr v-for="table in database?.tables ?? []" :key="table.key">
                <td class="px-4 py-4 font-mono text-xs text-slate-500">{{ table.key }}</td>
                <td class="px-4 py-4 font-medium text-brand-ink">{{ table.label }}</td>
                <td class="px-4 py-4 font-mono text-sm text-slate-700">{{ table.count }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </SectionPanel>
    </div>

    <p v-if="errorMessage" class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
      {{ errorMessage }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import VChart from "vue-echarts";

import SectionPanel from "@/components/SectionPanel.vue";
import { normalizeApiError } from "@/api/client";
import { fetchAdminDatabase } from "@/api/modules/admin";
import type { AdminDatabaseOverviewResponse } from "@/types/admin";

const database = ref<AdminDatabaseOverviewResponse | null>(null);
const errorMessage = ref("");

const tableChartOption = computed(() => ({
  tooltip: { trigger: "item" },
  legend: { bottom: 0, textStyle: { color: "#475569" } },
  series: [
    {
      type: "pie",
      radius: ["38%", "72%"],
      data: database.value?.tables.map((item) => ({ name: item.label, value: item.count })) ?? [],
      itemStyle: { borderColor: "#fff", borderWidth: 4 },
    },
  ],
}));

onMounted(async () => {
  try {
    database.value = await fetchAdminDatabase();
  } catch (error) {
    errorMessage.value = normalizeApiError(error);
  }
});
</script>
