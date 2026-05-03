<template>
  <div class="space-y-6">
    <section class="grid gap-4 xl:grid-cols-3">
      <MetricCard
        v-for="metric in agents?.metrics ?? []"
        :key="metric.key"
        :label="metric.label"
        :value="metric.value"
        :description="metric.description"
        :tone="metricTone(metric.key)"
      />
    </section>

    <div class="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <SectionPanel title="审批状态分布" description="工作流运行历史中审批状态的分布情况。">
        <VChart class="h-[320px]" :option="approvalOption" autoresize />
      </SectionPanel>

      <SectionPanel title="最近活跃会话" description="展示当前进程内最近被访问的会话摘要。">
        <div class="overflow-hidden rounded-[28px] border border-slate-200">
          <div class="max-h-[320px] overflow-auto">
            <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead class="bg-slate-50 text-slate-500">
                <tr>
                  <th class="px-4 py-3 font-medium">用户</th>
                  <th class="px-4 py-3 font-medium">最近 Trace</th>
                  <th class="px-4 py-3 font-medium">状态</th>
                  <th class="px-4 py-3 font-medium">最近意图</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 bg-white">
                <tr v-for="session in agents?.recent_sessions ?? []" :key="`${session.user_id}-${session.last_trace_id}`">
                  <td class="px-4 py-4">
                    <p class="font-semibold text-brand-ink">#{{ session.user_id }}</p>
                    <p class="mt-1 text-xs text-slate-400">{{ session.updated_at }}</p>
                  </td>
                  <td class="px-4 py-4 font-mono text-xs text-slate-600">{{ session.last_trace_id || "-" }}</td>
                  <td class="px-4 py-4">
                    <div class="flex flex-wrap gap-2">
                      <span
                        class="rounded-full px-3 py-1 text-xs"
                        :class="session.lock ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'"
                      >
                        {{ session.lock ? "处理中" : "空闲" }}
                      </span>
                      <span
                        v-if="session.has_pending_workflow"
                        class="rounded-full bg-brand-sea/10 px-3 py-1 text-xs text-brand-sea"
                      >
                        待确认
                      </span>
                    </div>
                  </td>
                  <td class="px-4 py-4 text-slate-600">
                    <p>{{ session.last_intent || "-" }}</p>
                    <p v-if="session.pending_goal" class="mt-1 text-xs text-slate-400">{{ session.pending_goal }}</p>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
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

import MetricCard from "@/components/MetricCard.vue";
import SectionPanel from "@/components/SectionPanel.vue";
import { normalizeApiError } from "@/api/client";
import { fetchAdminAgents } from "@/api/modules/admin";
import type { AdminAgentOverviewResponse } from "@/types/admin";

const agents = ref<AdminAgentOverviewResponse | null>(null);
const errorMessage = ref("");

const approvalOption = computed(() => ({
  tooltip: { trigger: "item" },
  legend: { bottom: 0, textStyle: { color: "#475569" } },
  series: [
    {
      type: "pie",
      radius: ["36%", "70%"],
      data: agents.value?.approval_status_distribution ?? [],
      itemStyle: { borderColor: "#fff", borderWidth: 4 },
    },
  ],
}));

function metricTone(key: string) {
  if (key.includes("memory")) return "sea";
  if (key.includes("pending")) return "amber";
  if (key.includes("locked")) return "mint";
  return "ink";
}

onMounted(async () => {
  try {
    agents.value = await fetchAdminAgents();
  } catch (error) {
    errorMessage.value = normalizeApiError(error);
  }
});
</script>
