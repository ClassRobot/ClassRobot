<template>
  <div class="relative min-h-screen overflow-hidden bg-[radial-gradient(circle_at_top_left,_rgba(231,158,124,0.12),_transparent_24%),radial-gradient(circle_at_82%_14%,_rgba(40,100,90,0.08),_transparent_20%),linear-gradient(180deg,_#fcfbf8_0%,_#f5f1eb_100%)] text-on-surface dark:bg-[radial-gradient(circle_at_top_left,_rgba(77,163,148,0.16),_transparent_32%),radial-gradient(circle_at_bottom_right,_rgba(43,96,153,0.12),_transparent_28%),linear-gradient(180deg,_#111113_0%,_#09090b_100%)] dark:text-zinc-100">
    <div class="pointer-events-none absolute inset-0">
      <div class="absolute inset-0 dark:hidden">
        <div class="absolute right-[8%] top-[10%] h-[78%] w-[42%] opacity-70 [background-image:radial-gradient(rgba(200,195,185,0.92)_1px,transparent_1.8px)] [background-size:22px_22px] [mask-image:radial-gradient(circle_at_center,black_18%,transparent_72%)]" />
        <div class="absolute left-[30%] top-[12%] h-24 w-64 opacity-50 [background-image:radial-gradient(rgba(209,202,192,0.95)_1px,transparent_1.8px)] [background-size:20px_20px] [mask-image:linear-gradient(90deg,transparent_0%,black_20%,black_80%,transparent_100%)]" />
      </div>
      <div class="absolute left-[8%] top-20 h-48 w-48 rounded-full bg-primary/10 blur-3xl dark:bg-primary-dark/12" />
      <div class="absolute bottom-16 right-[10%] h-56 w-56 rounded-full bg-secondary/10 blur-3xl dark:bg-blue-500/10" />
    </div>

    <div class="absolute right-6 top-6 z-20">
      <ThemeModeSwitch />
    </div>

    <div class="relative z-10 flex min-h-screen items-center justify-center px-4 py-10">
      <section class="w-full max-w-[440px] rounded-[28px] border border-outline-variant/80 bg-surface-container-lowest/92 shadow-[0_28px_60px_rgba(15,23,42,0.12)] backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/90 dark:shadow-[0_28px_72px_rgba(0,0,0,0.34)]">
        <div class="px-8 pb-5 pt-8 text-center">
          <div class="mx-auto mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/15 dark:bg-primary-dark/20">
            <Bot :size="30" class="text-primary dark:text-primary-dark" />
          </div>
          <h1 class="text-[30px] font-semibold tracking-[-0.02em] text-on-surface dark:text-zinc-50">ClassRobot Manager</h1>
          <p class="mt-2 text-[14px] leading-6 text-on-surface-variant dark:text-zinc-400">
            请输入访问令牌登录本地运维控制台
          </p>
        </div>

        <form class="flex flex-col gap-5 border-t border-outline-variant/80 px-8 py-7 dark:border-zinc-800" @submit.prevent="handleLogin">
            <div class="flex flex-col gap-2">
              <label class="flex items-center gap-1.5 font-label-caps text-label-caps uppercase text-on-surface dark:text-zinc-300" for="token">
                <KeyRound :size="14" />
                访问令牌
              </label>
              <input
                id="token"
                v-model="token"
                type="password"
                autocomplete="off"
                class="h-12 w-full rounded-xl border border-outline-variant dark:border-zinc-700 bg-surface-container/90 dark:bg-zinc-800 px-4 font-code-inline text-code-inline text-on-surface dark:text-zinc-100 placeholder:text-outline dark:placeholder:text-zinc-500 transition-all focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 dark:focus:border-primary-dark dark:focus:ring-primary-dark/20"
                placeholder="请输入启动令牌..."
                :disabled="loading"
              />
              <div v-if="errorMsg" class="mt-1 flex items-start gap-2 rounded-xl border border-error/20 bg-error-container/60 p-3 dark:border-red-800/50 dark:bg-red-900/30">
                <CircleX :size="16" class="mt-px shrink-0 text-error dark:text-red-400" />
                <span class="font-body-sm text-body-sm text-on-error-container dark:text-red-300">{{ errorMsg }}</span>
              </div>
            </div>

            <div class="pt-1">
              <button
                type="submit"
                :disabled="!token.trim() || loading"
                class="flex h-12 w-full items-center justify-center gap-2 rounded-xl font-label-caps text-label-caps uppercase transition-all duration-200"
                :class="token.trim() && !loading
                  ? 'cursor-pointer bg-primary text-on-primary shadow-[0_18px_36px_rgba(40,100,90,0.22)] hover:-translate-y-0.5 hover:opacity-95 dark:bg-primary-dark dark:text-zinc-950 dark:shadow-[0_18px_38px_rgba(77,163,148,0.18)]'
                  : 'cursor-not-allowed bg-primary/30 text-on-primary/50 dark:bg-primary-dark/20 dark:text-zinc-500'"
              >
                <Loader2 v-if="loading" :size="16" class="animate-spin" />
                <LogIn v-else :size="16" />
                {{ loading ? '验证中...' : '登录' }}
              </button>
            </div>
        </form>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '@/api/auth'
import { useAuthStore } from '@/composables/useAuth'
import ThemeModeSwitch from '@/components/ThemeModeSwitch.vue'
import { Bot, CircleX, KeyRound, Loader2, LogIn } from 'lucide-vue-next'

const router = useRouter()
const auth = useAuthStore()

const token = ref('')
const loading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  if (!token.value.trim() || loading.value) return
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await login({ token: token.value.trim() })
    auth.setSession(res.access_token, new Date(Date.now() + res.expires_in * 1000).toISOString())
    router.push({ name: 'Overview' })
  } catch (e: unknown) {
    const err = e as { response?: { data?: { detail?: string }; status?: number } }
    if (err.response?.status === 401) {
      errorMsg.value = '令牌无效，请检查后重试'
    } else if (err.response?.data?.detail) {
      errorMsg.value = err.response.data.detail
    } else {
      errorMsg.value = '无法连接到服务器，请确认后端已启动'
    }
  } finally {
    loading.value = false
  }
}
</script>
