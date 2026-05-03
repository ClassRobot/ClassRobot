<template>
  <div class="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(76,178,134,0.18),_transparent_34%),linear-gradient(180deg,_#f8fafc,_#eef4f6)] px-4 py-4 md:px-6">
    <div class="mx-auto grid min-h-[calc(100vh-2rem)] max-w-[1600px] gap-4 lg:grid-cols-[300px_minmax(0,1fr)]">
      <AppSidebar />
      <div class="flex min-h-0 flex-col gap-4">
        <AppHeader />
        <div
          v-if="authStore.isAuthenticated && !authStore.bootstrapped"
          class="rounded-3xl border border-brand-amber/20 bg-brand-amber/10 px-4 py-3 text-sm text-brand-ink"
        >
          正在校验管理员登录态并同步当前账号信息...
        </div>
        <main class="min-h-0 flex-1 overflow-auto rounded-[34px] border border-white/60 bg-white/35 p-4 backdrop-blur md:p-6">
          <RouterView />
        </main>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from "vue";
import { RouterView } from "vue-router";
import { useRouter } from "vue-router";

import AppHeader from "@/components/AppHeader.vue";
import AppSidebar from "@/components/AppSidebar.vue";
import { useAuthStore } from "@/stores/auth";

const authStore = useAuthStore();
const router = useRouter();

onMounted(async () => {
  if (!authStore.token || authStore.user || authStore.bootstrapped) {
    return;
  }
  try {
    await authStore.bootstrap();
  } catch {
    router.push({ name: "login" });
  }
});
</script>
