<template>
  <header class="flex flex-col gap-4 rounded-[30px] border border-white/70 bg-white/85 px-6 py-5 shadow-panel md:flex-row md:items-center md:justify-between">
    <div>
      <p class="text-xs uppercase tracking-[0.28em] text-slate-400">Control Plane</p>
      <h2 class="mt-2 text-3xl font-semibold text-brand-ink">{{ title }}</h2>
      <p class="mt-2 text-sm text-slate-500">{{ description }}</p>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <span class="rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-sm text-emerald-700">
        {{ authStore.isAuthenticated ? "管理员已登录" : "未登录" }}
      </span>
      <span
        v-if="authStore.user"
        class="rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-600"
      >
        {{ authStore.user.username }}
      </span>
      <button
        type="button"
        class="rounded-full border border-slate-200 px-4 py-2 text-sm text-slate-600 transition hover:border-brand-ink hover:text-brand-ink"
        @click="handleLogout"
      >
        退出登录
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const title = computed(() => String(route.meta.title ?? "管理后台"));
const description = computed(() => {
  const descriptions: Record<string, string> = {
    dashboard: "从命令、业务数据和工作流运行态三个方向快速把握系统整体情况。",
    users: "直接使用系统内管理员账号登录，在这里维护后台可访问的用户与账号属性。",
    commands: "统一查看命令帮助元数据，为后续命令启停、风险治理和后台编辑预留落点。",
    assets: "集中查看命令插件、项目技能、模型配置与当前运行中的 Bot 实例。",
    agents: "观察 AutoGPT 会话、审批恢复和工作流历史的当前状态。",
    database: "聚焦关键业务表的体量和增长趋势，方便后续补更细粒度查询。",
    system: "核对当前环境、插件、目录和后台前端构建状态。",
  };
  return descriptions[String(route.name ?? "dashboard")] ?? "后台统一治理入口。";
});

function handleLogout() {
  authStore.logout();
  router.push({ name: "login" });
}
</script>
