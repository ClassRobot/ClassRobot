<template>
  <div class="min-h-screen bg-[linear-gradient(145deg,_#0f172a,_#172133_38%,_#202020_70%,_#d4af37_140%)] px-4 py-8">
    <div class="mx-auto grid min-h-[calc(100vh-4rem)] max-w-6xl gap-8 rounded-[40px] border border-white/10 bg-white/8 p-6 backdrop-blur-xl lg:grid-cols-[1.1fr_0.9fr] lg:p-8">
      <section class="rounded-[32px] border border-white/10 bg-slate-950/35 p-8 text-white">
        <p class="text-xs uppercase tracking-[0.36em] text-white/50">ClassRobot Control Plane</p>
        <h1 class="mt-4 max-w-xl text-4xl font-semibold leading-tight">
          管理员后台登录
        </h1>
        <p class="mt-5 max-w-2xl text-base leading-8 text-white/72">
          直接复用系统内已有用户账号登录，只有 `is_admin = true` 的用户才能进入后台。
          登录后可以集中维护用户、命令插件、技能、模型配置、Bot 运行态和系统状态。
        </p>

        <div class="mt-10 grid gap-4 md:grid-cols-3">
          <div class="rounded-3xl border border-white/10 bg-white/5 p-5">
            <p class="text-sm text-white/60">账号鉴权</p>
            <p class="mt-2 text-3xl font-semibold">Admin</p>
            <p class="mt-3 text-sm leading-6 text-white/70">
              使用现有用户体系登录，后端统一校验管理员身份和会话时效。
            </p>
          </div>
          <div class="rounded-3xl border border-white/10 bg-white/5 p-5">
            <p class="text-sm text-white/60">资源目录</p>
            <p class="mt-2 text-3xl font-semibold">Plugins</p>
            <p class="mt-3 text-sm leading-6 text-white/70">
              浏览命令插件、项目技能、模型配置与运行中的 Bot。
            </p>
          </div>
          <div class="rounded-3xl border border-white/10 bg-white/5 p-5">
            <p class="text-sm text-white/60">运行治理</p>
            <p class="mt-2 text-3xl font-semibold">Ops</p>
            <p class="mt-3 text-sm leading-6 text-white/70">
              统一查看 Agent、数据库和系统运行态，为后续维护留出治理入口。
            </p>
          </div>
        </div>

        <div class="mt-10 grid gap-4 md:grid-cols-3">
          <div class="rounded-3xl border border-white/10 bg-white/5 px-5 py-4">
            <p class="text-xs uppercase tracking-[0.22em] text-white/45">管理员账号</p>
            <p class="mt-3 font-mono text-3xl font-semibold">{{ authStatus?.admin_account_count ?? "-" }}</p>
          </div>
          <div class="rounded-3xl border border-white/10 bg-white/5 px-5 py-4">
            <p class="text-xs uppercase tracking-[0.22em] text-white/45">登录态密钥</p>
            <p class="mt-3 text-lg font-semibold">
              {{ authStatus?.session_secret_configured ? "已配置" : "未配置" }}
            </p>
          </div>
          <div class="rounded-3xl border border-white/10 bg-white/5 px-5 py-4">
            <p class="text-xs uppercase tracking-[0.22em] text-white/45">前端构建</p>
            <p class="mt-3 text-lg font-semibold">
              {{ authStatus?.frontend_dist_exists ? "就绪" : "未构建" }}
            </p>
          </div>
        </div>
      </section>

      <section class="rounded-[32px] bg-white p-8 shadow-panel">
        <p class="text-xs uppercase tracking-[0.32em] text-slate-400">Administrator Access</p>
        <h2 class="mt-3 text-3xl font-semibold text-brand-ink">进入管理后台</h2>
        <p class="mt-3 text-sm leading-7 text-slate-500">
          请输入系统中已有的管理员用户名和密码。非管理员账号会被拒绝登录。
        </p>

        <div class="mt-8 grid gap-4 rounded-3xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600 md:grid-cols-2">
          <div>
            <p class="text-xs uppercase tracking-[0.18em] text-slate-400">Auth Mode</p>
            <p class="mt-2 font-medium text-brand-ink">{{ authStatus?.auth_mode ?? "加载中" }}</p>
          </div>
          <div>
            <p class="text-xs uppercase tracking-[0.18em] text-slate-400">Generated At</p>
            <p class="mt-2 font-medium text-brand-ink">{{ formatDateTime(authStatus?.generated_at) }}</p>
          </div>
        </div>

        <form class="mt-8 space-y-5" @submit.prevent="handleSubmit">
          <label class="block">
            <span class="mb-2 block text-sm font-medium text-slate-700">管理员用户名</span>
            <input
              v-model.trim="form.username"
              type="text"
              autocomplete="username"
              placeholder="请输入系统用户名"
              class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-brand-amber focus:ring-4 focus:ring-amber-100"
            />
          </label>

          <label class="block">
            <span class="mb-2 block text-sm font-medium text-slate-700">登录密码</span>
            <input
              v-model="form.password"
              type="password"
              autocomplete="current-password"
              placeholder="请输入管理员密码"
              class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-800 outline-none transition focus:border-brand-amber focus:ring-4 focus:ring-amber-100"
            />
          </label>

          <p
            v-if="errorMessage"
            class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600"
          >
            {{ errorMessage }}
          </p>

          <p
            v-if="authStatus && !authStatus.session_secret_configured"
            class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700"
          >
            后端尚未配置后台登录态签名密钥，当前无法正常签发管理员会话。
          </p>

          <button
            type="submit"
            class="w-full rounded-2xl bg-brand-ink px-4 py-3 text-sm font-medium text-white transition hover:-translate-y-0.5 hover:bg-slate-950 disabled:opacity-70"
            :disabled="submitting"
          >
            {{ submitting ? "正在登录..." : "进入管理后台" }}
          </button>
        </form>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { normalizeApiError } from "@/api/client";
import { fetchAdminAuthStatus, loginAdmin } from "@/api/modules/admin";
import { useAuthStore } from "@/stores/auth";
import type { AdminAuthStatusResponse } from "@/types/admin";
import { formatDateTime } from "@/utils/formatters";

const router = useRouter();
const authStore = useAuthStore();

const submitting = ref(false);
const errorMessage = ref("");
const authStatus = ref<AdminAuthStatusResponse | null>(null);
const form = reactive({
  username: "",
  password: "",
});

onMounted(async () => {
  try {
    authStatus.value = await fetchAdminAuthStatus();
  } catch (error) {
    errorMessage.value = normalizeApiError(error);
  }

  if (authStore.token) {
    try {
      await authStore.bootstrap();
      router.replace({ name: "dashboard" });
    } catch {
      errorMessage.value = "当前登录态已失效，请重新输入管理员账号登录。";
    }
  }
});

async function handleSubmit() {
  errorMessage.value = "";
  if (!form.username || !form.password) {
    errorMessage.value = "请完整输入管理员用户名和密码。";
    return;
  }
  submitting.value = true;
  try {
    const session = await loginAdmin({
      username: form.username,
      password: form.password,
    });
    authStore.updateSession(session.access_token, session.user);
    router.push({ name: "dashboard" });
  } catch (error) {
    errorMessage.value = normalizeApiError(error);
  } finally {
    submitting.value = false;
  }
}
</script>
