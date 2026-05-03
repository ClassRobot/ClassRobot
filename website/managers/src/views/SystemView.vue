<template>
  <div class="space-y-6">
    <SectionPanel title="运行环境" description="这里汇总的是后端管理 API 自己暴露的运行态信息。">
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-[28px] border border-slate-200 bg-white px-5 py-4 shadow-sm">
          <p class="text-sm text-slate-500">应用名</p>
          <p class="mt-2 text-2xl font-semibold text-brand-ink">{{ system?.app_name }}</p>
        </div>
        <div class="rounded-[28px] border border-slate-200 bg-white px-5 py-4 shadow-sm">
          <p class="text-sm text-slate-500">环境</p>
          <p class="mt-2 text-2xl font-semibold text-brand-ink">{{ system?.environment }}</p>
        </div>
        <div class="rounded-[28px] border border-slate-200 bg-white px-5 py-4 shadow-sm">
          <p class="text-sm text-slate-500">路由数量</p>
          <p class="mt-2 font-mono text-2xl font-semibold text-brand-ink">{{ system?.route_count ?? 0 }}</p>
        </div>
        <div class="rounded-[28px] border border-slate-200 bg-white px-5 py-4 shadow-sm">
          <p class="text-sm text-slate-500">插件数量</p>
          <p class="mt-2 font-mono text-2xl font-semibold text-brand-ink">{{ system?.plugin_count ?? 0 }}</p>
        </div>
      </div>
    </SectionPanel>

    <div class="grid gap-6 xl:grid-cols-[1fr_1fr]">
      <SectionPanel title="目录状态" description="后续可以继续在这里接静态资源、数据目录和备份目录检查。">
        <div class="space-y-3">
          <div
            v-for="directory in system?.directories ?? []"
            :key="directory.key"
            class="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4"
          >
            <div class="flex items-center justify-between gap-4">
              <div>
                <p class="font-medium text-brand-ink">{{ directory.label }}</p>
                <p class="mt-1 font-mono text-xs text-slate-500">{{ directory.path }}</p>
              </div>
              <span
                class="rounded-full px-3 py-1 text-xs"
                :class="directory.exists ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-600'"
              >
                {{ directory.exists ? "存在" : "缺失" }}
              </span>
            </div>
          </div>
        </div>
      </SectionPanel>

      <SectionPanel title="已加载插件" description="便于核对命令系统、routers 和业务插件是否都正常挂载。">
        <div class="grid max-h-[520px] gap-3 overflow-auto pr-1">
          <div
            v-for="plugin in system?.loaded_plugins ?? []"
            :key="plugin"
            class="rounded-2xl border border-slate-200 bg-white px-4 py-3 font-mono text-xs text-slate-600"
          >
            {{ plugin }}
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
import { onMounted, ref } from "vue";

import SectionPanel from "@/components/SectionPanel.vue";
import { normalizeApiError } from "@/api/client";
import { fetchAdminSystem } from "@/api/modules/admin";
import type { AdminSystemStatusResponse } from "@/types/admin";

const system = ref<AdminSystemStatusResponse | null>(null);
const errorMessage = ref("");

onMounted(async () => {
  try {
    system.value = await fetchAdminSystem();
  } catch (error) {
    errorMessage.value = normalizeApiError(error);
  }
});
</script>
