<template>
  <div class="space-y-6">
    <SectionPanel title="命令目录" description="这里直接读取后端的统一 Helper 元数据，便于后续扩展命令治理能力。">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div class="grid flex-1 gap-4 sm:grid-cols-3">
          <div
            v-for="scope in commands?.scope_distribution ?? []"
            :key="scope.name"
            class="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4"
          >
            <p class="text-sm text-slate-500">{{ scope.name }}</p>
            <p class="mt-2 font-mono text-3xl font-semibold text-brand-ink">{{ scope.value }}</p>
          </div>
        </div>
        <label class="block lg:w-[320px]">
          <span class="mb-2 block text-sm font-medium text-slate-600">筛选命令</span>
          <input
            v-model.trim="keyword"
            type="search"
            placeholder="按命令名、别名或描述筛选"
            class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand-mint focus:ring-4 focus:ring-emerald-100"
          />
        </label>
      </div>
    </SectionPanel>

    <SectionPanel title="命令清单" description="当前先做只读视图，后续可以继续挂启停、风险等级、人工审核等治理动作。">
      <div class="overflow-hidden rounded-[28px] border border-slate-200">
        <div class="max-h-[640px] overflow-auto">
          <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
            <thead class="bg-slate-50 text-slate-500">
              <tr>
                <th class="px-4 py-3 font-medium">命令</th>
                <th class="px-4 py-3 font-medium">说明</th>
                <th class="px-4 py-3 font-medium">参数</th>
                <th class="px-4 py-3 font-medium">作用域</th>
                <th class="px-4 py-3 font-medium">角色</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-100 bg-white">
              <tr v-for="item in filteredCommands" :key="item.command" class="align-top hover:bg-slate-50">
                <td class="px-4 py-4">
                  <p class="font-semibold text-brand-ink">{{ item.command }}</p>
                  <p class="mt-2 text-xs text-slate-400">{{ item.aliases.join(" / ") || "无别名" }}</p>
                </td>
                <td class="px-4 py-4 text-slate-600">
                  <p class="leading-6">{{ item.description }}</p>
                  <p v-if="item.ai_description" class="mt-3 rounded-2xl bg-slate-100 px-3 py-2 text-xs leading-5 text-slate-500">
                    AI: {{ item.ai_description }}
                  </p>
                </td>
                <td class="px-4 py-4">
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="param in item.params"
                      :key="param"
                      class="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600"
                    >
                      {{ param }}
                    </span>
                    <span v-if="item.params.length === 0" class="text-slate-400">无</span>
                  </div>
                </td>
                <td class="px-4 py-4">
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="scope in item.scopes"
                      :key="scope"
                      class="rounded-full bg-brand-sea/10 px-3 py-1 text-xs text-brand-sea"
                    >
                      {{ scope }}
                    </span>
                  </div>
                </td>
                <td class="px-4 py-4">
                  <div class="flex flex-wrap gap-2">
                    <span
                      v-for="role in item.roles"
                      :key="role"
                      class="rounded-full bg-brand-mint/10 px-3 py-1 text-xs text-emerald-700"
                    >
                      {{ role }}
                    </span>
                    <span v-if="item.roles.length === 0" class="text-slate-400">公共命令</span>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
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

import SectionPanel from "@/components/SectionPanel.vue";
import { normalizeApiError } from "@/api/client";
import { fetchAdminCommands } from "@/api/modules/admin";
import type { AdminCommandListResponse } from "@/types/admin";

const commands = ref<AdminCommandListResponse | null>(null);
const keyword = ref("");
const errorMessage = ref("");

const filteredCommands = computed(() => {
  const source = commands.value?.items ?? [];
  if (!keyword.value) {
    return source;
  }
  const value = keyword.value.toLowerCase();
  return source.filter((item) => {
    return [item.command, item.description, item.ai_description, ...item.aliases].some((field) =>
      String(field ?? "").toLowerCase().includes(value),
    );
  });
});

onMounted(async () => {
  try {
    commands.value = await fetchAdminCommands();
  } catch (error) {
    errorMessage.value = normalizeApiError(error);
  }
});
</script>
