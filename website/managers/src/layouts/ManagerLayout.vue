<template>
  <div class="flex h-screen overflow-hidden bg-surface dark:bg-zinc-950 text-on-surface dark:text-zinc-100">
    <!-- Sidebar -->
    <aside
      class="fixed inset-y-0 left-0 z-30 flex flex-col overflow-visible border-r border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 transition-[width] duration-300 ease-out"
      :style="sidebarStyle"
    >
      <!-- Brand -->
      <div class="px-4 py-3 mb-1 border-b border-outline-variant dark:border-zinc-800">
        <div class="flex items-center" :class="collapsed ? 'justify-center' : 'gap-2.5'">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15 dark:bg-primary-dark/20">
            <Bot :size="20" class="text-primary dark:text-primary-dark" />
          </div>
          <div
            class="overflow-hidden transition-[width,opacity,transform] duration-200 ease-out"
            :class="collapsed ? 'w-0 opacity-0 -translate-x-1' : 'w-[122px] opacity-100 translate-x-0'"
          >
            <div class="text-sm font-bold text-on-surface dark:text-zinc-100">ClassRobot</div>
            <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">运维控制台</div>
          </div>
        </div>
      </div>

      <!-- Nav groups -->
      <nav class="flex-1 overflow-y-auto px-2 py-3" :class="collapsed ? 'space-y-3' : 'space-y-1.5'">
        <div v-for="(group, groupIndex) in navGroups" :key="group.label">
          <p
            v-if="!collapsed"
            class="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-on-surface-variant/60 dark:text-zinc-500"
          >
            {{ group.label }}
          </p>
          <div
            v-else-if="groupIndex > 0"
            class="mx-3 mb-1 h-px bg-outline-variant/70 dark:bg-zinc-800"
          />
          <router-link
            v-for="item in group.items"
            :key="item.to"
            :to="item.to"
            class="group relative flex items-center overflow-hidden rounded-xl text-[13px] transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 dark:focus-visible:ring-primary-dark/25"
            :class="navItemClass(item.to)"
            :aria-label="collapsed ? item.label : undefined"
            :title="collapsed ? item.label : undefined"
          >
            <span
              class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg transition-colors"
              :class="navIconClass(item.to)"
            >
              <component :is="item.icon" :size="18" />
            </span>
            <span
              class="overflow-hidden whitespace-nowrap transition-[max-width,opacity,transform,margin] duration-200 ease-out"
              :class="collapsed ? 'max-w-0 opacity-0 -translate-x-1' : 'ml-3 max-w-[144px] opacity-100 translate-x-0'"
            >
              {{ item.label }}
            </span>
            <span
              v-if="isActive(item.to) && !collapsed"
              class="ml-auto mr-1 h-2 w-2 rounded-full bg-primary/70 dark:bg-primary-dark/80"
            />
          </router-link>
        </div>
      </nav>

      <div class="border-t border-outline-variant dark:border-zinc-800 px-4 py-3">
        <div class="flex items-center" :class="collapsed ? 'justify-center' : 'gap-2'">
          <span class="h-2 w-2 rounded-full bg-primary/70 dark:bg-primary-dark/80" />
          <p
            class="overflow-hidden text-[11px] leading-4 text-on-surface-variant transition-[width,opacity] duration-200 ease-out dark:text-zinc-500"
            :class="collapsed ? 'w-0 opacity-0' : 'w-[140px] opacity-100'"
          >
            本地后台 · Token 会话
          </p>
        </div>
      </div>
    </aside>

    <!-- Main area -->
    <div
      class="flex flex-1 flex-col min-w-0 transition-[margin-left] duration-300 ease-out"
      :style="mainStyle"
    >
      <!-- Top bar -->
      <header class="flex h-topbar shrink-0 items-center gap-4 border-b border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 px-6">
        <div class="flex items-center gap-3">
          <button
            @click="toggleSidebar"
            class="flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant dark:text-zinc-400 hover:bg-surface-container dark:hover:bg-zinc-800 transition-colors"
            :title="collapsed ? '展开导航' : '收起导航'"
          >
            <PanelLeftOpen v-if="collapsed" :size="18" />
            <PanelLeftClose v-else :size="18" />
          </button>
          <h1 class="text-sm font-semibold text-on-surface dark:text-zinc-100">{{ pageTitle }}</h1>
          <span class="flex items-center gap-1.5 rounded-full bg-primary/10 dark:bg-primary-dark/15 px-2.5 py-0.5 text-[11px] font-medium text-primary dark:text-primary-dark">
            <span class="w-1.5 h-1.5 rounded-full bg-primary dark:bg-primary-dark"></span>
            运行中
          </span>
        </div>
        <div class="ml-auto flex items-center gap-2">
          <ThemeModeSwitch />
          <button
            @click="handleRefresh"
            class="flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant dark:text-zinc-400 hover:bg-surface-container dark:hover:bg-zinc-800 transition-colors"
            title="刷新"
          >
            <RefreshCw :size="18" />
          </button>
          <button
            @click="handleLogout"
            class="flex h-8 w-8 items-center justify-center rounded-lg text-on-surface-variant dark:text-zinc-400 hover:bg-surface-container dark:hover:bg-zinc-800 transition-colors"
            title="退出"
          >
            <LogOut :size="18" />
          </button>
        </div>
      </header>

      <!-- Page content -->
      <main class="flex-1 overflow-y-auto p-6">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/composables/useAuth'
import { useTheme } from '@/composables/useTheme'
import {
  LayoutDashboard, Users, Activity, Settings, Puzzle,
  FileText, Cpu, Bot, Plug, Terminal,
  RefreshCw, LogOut, PanelLeftClose, PanelLeftOpen,
} from 'lucide-vue-next'
import ThemeModeSwitch from '@/components/ThemeModeSwitch.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isDark } = useTheme()
const SIDEBAR_COLLAPSE_KEY = 'classrobot-manager-sidebar-collapsed'
const expandedSidebarWidth = '240px'
const collapsedSidebarWidth = '84px'
const collapsed = ref(false)

const pageTitle = computed(() => (route.meta.title as string) || 'ClassRobot Manager')
const sidebarStyle = computed(() => ({ width: collapsed.value ? collapsedSidebarWidth : expandedSidebarWidth }))
const mainStyle = computed(() => ({ marginLeft: collapsed.value ? collapsedSidebarWidth : expandedSidebarWidth }))

function isActive(to: string) {
  return route.path === to || route.path.startsWith(to + '/')
}

function navItemClass(to: string) {
  const active = isActive(to)
  const collapsedLayout = collapsed.value
  const themeClass = active
    ? (isDark.value
      ? 'bg-zinc-800/92 text-zinc-100 shadow-[inset_0_0_0_1px_rgba(77,163,148,0.2),0_14px_28px_rgba(0,0,0,0.26)]'
      : 'bg-white/96 text-on-surface shadow-[inset_0_0_0_1px_rgba(40,100,90,0.12),0_14px_28px_rgba(15,23,42,0.08)]')
    : (isDark.value
      ? 'text-zinc-400 hover:bg-zinc-800/82 hover:text-zinc-100'
      : 'text-on-surface-variant hover:bg-surface-container/90 hover:text-on-surface')
  return [
    collapsedLayout ? 'mx-auto h-11 w-11 justify-center px-0' : 'px-2.5 py-1.5',
    themeClass,
  ]
}

function navIconClass(to: string) {
  if (isActive(to)) {
    return isDark.value
      ? 'bg-[radial-gradient(circle_at_top,rgba(77,163,148,0.24),rgba(77,163,148,0.08))] text-primary-dark shadow-[inset_0_0_0_1px_rgba(77,163,148,0.12)]'
      : 'bg-[radial-gradient(circle_at_top,rgba(40,100,90,0.2),rgba(40,100,90,0.08))] text-primary shadow-[inset_0_0_0_1px_rgba(40,100,90,0.1)]'
  }
  return isDark.value ? 'text-zinc-400 group-hover:text-zinc-100' : 'text-current'
}

function toggleSidebar() {
  collapsed.value = !collapsed.value
}

function handleRefresh() {
  window.location.reload()
}

function handleLogout() {
  auth.clearSession()
  router.push({ name: 'Login' })
}

const navGroups = [
  { label: '概览', items: [{ to: '/overview', label: '总览', icon: LayoutDashboard }] },
  { label: '身份', items: [{ to: '/users', label: '用户中心', icon: Users }] },
  {
    label: '系统',
    items: [
      { to: '/status', label: '系统状态', icon: Activity },
      { to: '/settings', label: '系统设置', icon: Settings },
    ],
  },
  {
    label: 'AI 资产',
    items: [
      { to: '/skills', label: 'Skill 管理', icon: Puzzle },
      { to: '/prompts', label: 'Prompt 管理', icon: FileText },
      { to: '/models', label: 'Model 管理', icon: Cpu },
    ],
  },
  { label: 'Agent', items: [{ to: '/agents', label: 'Agent 管理', icon: Bot }] },
  { label: '集成', items: [{ to: '/integrations', label: 'MCP / 集成', icon: Plug }] },
  { label: '运维', items: [{ to: '/operations', label: '运维调试', icon: Terminal }] },
]

onMounted(() => {
  collapsed.value = localStorage.getItem(SIDEBAR_COLLAPSE_KEY) === 'true'
})

watch(collapsed, (value) => {
  localStorage.setItem(SIDEBAR_COLLAPSE_KEY, String(value))
})
</script>
