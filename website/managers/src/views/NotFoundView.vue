<template>
  <div class="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top,_rgba(77,163,148,0.14),_transparent_30%),linear-gradient(180deg,_#f8faf3_0%,_#eef2ea_100%)] text-on-surface dark:bg-[radial-gradient(circle_at_top,_rgba(77,163,148,0.16),_transparent_28%),radial-gradient(circle_at_bottom_right,_rgba(43,96,153,0.12),_transparent_26%),linear-gradient(180deg,_#111113_0%,_#09090b_100%)] dark:text-zinc-100">
    <div class="absolute right-6 top-6 z-20">
      <ThemeModeSwitch />
    </div>

    <div class="pointer-events-none absolute inset-0">
      <div class="absolute left-[12%] top-24 h-44 w-44 rounded-full bg-primary/12 blur-3xl dark:bg-primary-dark/16" />
      <div class="absolute bottom-20 right-[14%] h-56 w-56 rounded-full bg-secondary/10 blur-3xl dark:bg-blue-500/12" />
    </div>

    <div class="relative z-10 flex min-h-screen items-center justify-center px-4 py-10">
      <section class="w-full max-w-[720px] rounded-[30px] border border-outline-variant/80 bg-surface-container-lowest/92 p-8 text-center shadow-[0_28px_60px_rgba(15,23,42,0.12)] backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/90 dark:shadow-[0_28px_72px_rgba(0,0,0,0.34)] sm:p-10">
        <div class="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-primary/15 dark:bg-primary-dark/20">
          <Compass :size="28" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="text-[12px] font-semibold uppercase tracking-[0.2em] text-primary dark:text-primary-dark">404 · PAGE NOT FOUND</div>
        <h1 class="mt-4 text-[38px] font-semibold tracking-[-0.03em] text-on-surface dark:text-zinc-50 sm:text-[46px]">
          这个管理页面不存在
        </h1>
        <p class="mx-auto mt-4 max-w-[44ch] text-[15px] leading-7 text-on-surface-variant dark:text-zinc-400">
          链接可能已经失效，或者你访问了一个尚未配置的后台路由。可以返回登录页重新进入，或者直接回到控制台首页。
        </p>

        <div class="mt-8 grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            class="flex h-12 items-center justify-center gap-2 rounded-xl border border-outline-variant bg-surface-container-low px-4 text-sm font-medium text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:hover:bg-zinc-700"
            @click="router.back()"
          >
            <ArrowLeft :size="16" />
            返回上一页
          </button>
          <router-link
            :to="primaryRoute"
            class="flex h-12 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-on-primary shadow-[0_18px_36px_rgba(40,100,90,0.22)] transition-all hover:-translate-y-0.5 hover:opacity-95 dark:bg-primary-dark dark:text-zinc-950 dark:shadow-[0_18px_38px_rgba(77,163,148,0.18)]"
          >
            <Home :size="16" />
            {{ auth.isAuthenticated ? '返回控制台' : '前往登录页' }}
          </router-link>
        </div>

        <div class="mt-6 rounded-2xl border border-outline-variant/80 bg-surface-container-low/82 px-5 py-4 text-left dark:border-zinc-800 dark:bg-zinc-900/56">
          <div class="mb-2 text-[11px] font-semibold uppercase tracking-[0.14em] text-on-surface-variant dark:text-zinc-500">
            建议操作
          </div>
          <ul class="space-y-2 text-sm leading-6 text-on-surface-variant dark:text-zinc-400">
            <li>确认当前地址是否为正确的后台路由。</li>
            <li>如果是书签地址，可能需要更新到新的路径结构。</li>
            <li>如果问题持续存在，可以回到运维调试页进一步排查。</li>
          </ul>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Compass, Home } from 'lucide-vue-next'
import ThemeModeSwitch from '@/components/ThemeModeSwitch.vue'
import { useAuthStore } from '@/composables/useAuth'

const router = useRouter()
const auth = useAuthStore()

const primaryRoute = computed(() => (auth.isAuthenticated ? { name: 'Overview' } : { name: 'Login' }))
</script>
