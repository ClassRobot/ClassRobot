<template>
  <aside class="flex h-full flex-col rounded-[30px] bg-brand-ink px-5 py-6 text-white shadow-panel">
    <div>
      <p class="text-xs uppercase tracking-[0.34em] text-white/50">ClassRobot</p>
      <h1 class="mt-2 text-2xl font-semibold">Managers</h1>
      <p class="mt-3 text-sm leading-6 text-white/70">
        面向管理员的统一控制台，覆盖账号、命令、Agent 与系统运行态。
      </p>
    </div>

    <nav class="mt-8 flex-1 space-y-2">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="block rounded-2xl px-4 py-3 text-sm transition"
        :class="
          route.path === item.to
            ? 'bg-white text-brand-ink shadow-md'
            : 'text-white/70 hover:bg-white/10 hover:text-white'
        "
      >
        <span class="block font-medium">{{ item.label }}</span>
        <span class="mt-1 block text-xs opacity-70">{{ item.description }}</span>
      </RouterLink>
    </nav>

    <div class="space-y-3">
      <div class="rounded-2xl border border-white/15 bg-white/5 p-4 text-sm text-white/70">
        <p class="font-medium text-white">当前会话</p>
        <p class="mt-2 text-base font-semibold text-white">{{ authStore.displayName }}</p>
        <p class="mt-1 text-xs uppercase tracking-[0.22em] text-white/45">
          {{ authStore.user?.is_admin ? "Administrator" : "Read Session" }}
        </p>
      </div>

      <div class="rounded-2xl border border-white/15 bg-white/5 p-4 text-sm text-white/70">
        <p class="font-medium text-white">运行建议</p>
        <p class="mt-2 leading-6">
          运行时托管资源默认保持只读，真正可写的入口优先落在服务层并保留审计约束。
        </p>
      </div>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { RouterLink, useRoute } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const authStore = useAuthStore();

const navItems = [
  { to: "/dashboard", label: "总览面板", description: "关键指标、命令分布和工作流状态" },
  { to: "/users", label: "用户管理", description: "管理员登录、用户资料与账号维护" },
  { to: "/commands", label: "命令管理", description: "查看命令目录、作用域和 AI 提示" },
  { to: "/assets", label: "资源目录", description: "插件、技能、模型与运行 Bot 清单" },
  { to: "/agents", label: "Agent 管理", description: "会话、工作流审批和执行态" },
  { to: "/database", label: "数据库总览", description: "核心业务表数量和运行概况" },
  { to: "/system", label: "系统状态", description: "插件、路径、环境和 API 状态" },
];
</script>
