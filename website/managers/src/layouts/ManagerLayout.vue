<template>
  <div class="relative isolate flex h-screen overflow-hidden bg-[#fbfaf7] text-on-surface dark:bg-zinc-950 dark:text-zinc-100">
    <div class="pointer-events-none absolute inset-0 dark:hidden">
      <div class="absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(231,158,124,0.08),_transparent_22%),radial-gradient(circle_at_78%_14%,_rgba(40,100,90,0.08),_transparent_18%),linear-gradient(180deg,_#fcfbf8_0%,_#f5f1eb_100%)]" />
      <div class="absolute -left-12 top-10 h-56 w-56 rounded-full bg-[#f4ddd0]/55 blur-3xl" />
      <div class="absolute bottom-12 right-[12%] h-52 w-52 rounded-full bg-[#eef2ea] blur-3xl" />
      <div class="absolute right-[7%] top-[11%] h-[76%] w-[42%] opacity-75 [background-image:radial-gradient(rgba(200,195,185,0.95)_1px,transparent_1.8px)] [background-size:22px_22px] [mask-image:radial-gradient(circle_at_center,black_16%,transparent_72%)]" />
      <div class="absolute left-[32%] top-[12%] h-24 w-64 opacity-55 [background-image:radial-gradient(rgba(209,202,192,0.95)_1px,transparent_1.8px)] [background-size:20px_20px] [mask-image:linear-gradient(90deg,transparent_0%,black_22%,black_78%,transparent_100%)]" />
    </div>

    <!-- Sidebar -->
    <aside
      class="fixed inset-y-0 left-0 z-30 flex flex-col overflow-visible border-r border-outline-variant/80 bg-white/76 shadow-[0_20px_50px_rgba(132,121,106,0.08)] backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-900 transition-[width] duration-300 ease-out"
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
      <nav class="flex-1 overflow-y-auto px-2 py-3" :class="collapsed ? 'space-y-3' : 'space-y-2'">
        <div
          v-for="(group, groupIndex) in navGroups"
          :key="group.label"
          class="relative"
          :class="hasActiveGroupItem(group) ? 'z-10' : 'z-0'"
        >
          <button
            v-if="!collapsed"
            type="button"
            class="relative z-0 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left transition-colors"
            :class="groupToggleClass(group)"
            :aria-expanded="isGroupExpanded(group.label)"
            :title="`${isGroupExpanded(group.label) ? '折叠' : '展开'} ${group.label}`"
            @click="toggleGroup(group.label)"
          >
            <span class="truncate text-[11px] font-bold uppercase tracking-[0.18em]">
              {{ group.label }}
            </span>
            <span class="ml-auto flex items-center gap-2">
              <span
                v-if="hasActiveGroupItem(group)"
                class="h-1.5 w-1.5 rounded-full bg-primary/70 dark:bg-primary-dark/80"
              />
              <ChevronDown
                :size="14"
                class="shrink-0 transition-transform duration-200"
                :class="isGroupExpanded(group.label) ? 'rotate-0' : '-rotate-90'"
              />
            </span>
          </button>
          <div
            v-else-if="groupIndex > 0"
            class="mx-3 mb-1 h-px bg-outline-variant/70 dark:bg-zinc-800"
          />
          <div
            class="transition-[max-height,opacity,margin] duration-200 ease-out"
            :class="collapsed || isGroupExpanded(group.label)
              ? 'max-h-[320px] overflow-visible opacity-100'
              : 'max-h-0 overflow-hidden opacity-0'"
          >
            <div :class="collapsed ? 'space-y-1 py-1' : 'space-y-1.5 px-0 py-1 pb-4'">
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
          </div>
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
      <header class="relative z-20 flex h-topbar shrink-0 items-center gap-4 overflow-visible border-b border-outline-variant/80 bg-white/72 px-6 backdrop-blur-xl dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex min-w-0 flex-1 items-center gap-4">
          <div class="flex shrink-0 items-center gap-3">
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

          <div class="relative z-30 hidden min-w-0 max-w-[340px] flex-1 md:block xl:max-w-[360px]">
            <Search :size="15" class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant/80 dark:text-zinc-500" />
            <input
              v-model="globalSearch"
              type="search"
              class="h-10 w-full rounded-xl border border-outline-variant/80 bg-surface-container-lowest pl-9 pr-3 text-body-sm text-on-surface outline-none transition-colors focus:border-primary focus:bg-white dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-primary-dark dark:focus:bg-zinc-950"
              placeholder="搜索页面、功能、管理入口..."
              @focus="openSearchPanel"
              @blur="handleSearchBlur"
              @keydown.enter.prevent="openFirstSearchResult"
              @keydown.esc="closeSearchPanel"
            />

            <div
              v-if="searchPanelVisible"
              class="absolute left-0 right-0 top-[calc(100%+0.625rem)] z-40 overflow-hidden rounded-2xl border border-[#d8d1c6] bg-[#fcfbf7] shadow-[0_20px_44px_rgba(15,23,42,0.12)] dark:border-zinc-800 dark:bg-[#121316] dark:shadow-[0_20px_50px_rgba(0,0,0,0.45)]"
            >
              <div class="flex items-center justify-between border-b border-outline-variant/70 px-3 py-2 text-[11px] text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
                <span>搜索结果 {{ Math.min(filteredSearchItems.length, 5) }} 项</span>
                <span>回车打开首项</span>
              </div>

              <div v-if="searchResultItems.length" class="max-h-[280px] overflow-y-auto p-2">
                <button
                  v-for="item in searchResultItems"
                  :key="item.to"
                  type="button"
                  class="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-[#f1ede4] dark:hover:bg-zinc-800/80"
                  @mousedown.prevent="navigateToSearchItem(item)"
                >
                  <span class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary dark:bg-primary-dark/15 dark:text-primary-dark">
                    <component :is="item.icon" :size="16" />
                  </span>
                  <span class="min-w-0 flex-1">
                    <span class="block truncate text-body-sm font-medium text-on-surface dark:text-zinc-100">{{ item.label }}</span>
                    <span class="block truncate text-[11px] text-on-surface-variant dark:text-zinc-500">{{ item.group }} · {{ item.to }}</span>
                  </span>
                  <span
                    v-if="route.path === item.to"
                    class="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary dark:bg-primary-dark/15 dark:text-primary-dark"
                  >
                    当前页
                  </span>
                </button>
              </div>

              <div v-else class="px-3 py-4 text-body-sm text-on-surface-variant dark:text-zinc-500">
                没有匹配的页面或功能入口
              </div>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2">
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
      <main class="relative flex-1 overflow-y-auto">
        <div class="pointer-events-none absolute inset-0 dark:hidden">
          <div class="absolute inset-x-[9%] top-0 h-28 rounded-b-[32px] bg-white/28 blur-2xl" />
        </div>
        <div class="relative z-10 p-6">
          <router-view />
        </div>
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
  FileText, Cpu, Bot, Plug, Terminal, Database, FileCode2, FolderKanban,
  MessageSquare, History, RefreshCw, LogOut, PanelLeftClose, PanelLeftOpen, Search, ChevronDown,
} from 'lucide-vue-next'
import ThemeModeSwitch from '@/components/ThemeModeSwitch.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { isDark } = useTheme()
const SIDEBAR_COLLAPSE_KEY = 'classrobot-manager-sidebar-collapsed'
const NAV_GROUP_STATE_KEY = 'classrobot-manager-nav-groups'
const expandedSidebarWidth = '240px'
const collapsedSidebarWidth = '84px'
const collapsed = ref(false)
const groupOpenState = ref<Record<string, boolean>>({})
const globalSearch = ref('')
const searchPanelOpen = ref(false)

const pageTitle = computed(() => (route.meta.title as string) || 'ClassRobot Manager')
const sidebarStyle = computed(() => ({ width: collapsed.value ? collapsedSidebarWidth : expandedSidebarWidth }))
const mainStyle = computed(() => ({ marginLeft: collapsed.value ? collapsedSidebarWidth : expandedSidebarWidth }))
const normalizedSearchQuery = computed(() => globalSearch.value.trim().toLowerCase())

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
    active ? 'z-10' : 'z-0',
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

function hasActiveGroupItem(group: NavGroup) {
  return group.items.some((item) => isActive(item.to))
}

function isGroupExpanded(label: string) {
  return groupOpenState.value[label] !== false
}

function toggleGroup(label: string) {
  groupOpenState.value = {
    ...groupOpenState.value,
    [label]: !isGroupExpanded(label),
  }
}

function groupToggleClass(group: NavGroup) {
  return hasActiveGroupItem(group)
    ? 'bg-primary/6 text-on-surface dark:bg-primary-dark/10 dark:text-zinc-100'
    : 'text-on-surface-variant/70 hover:bg-surface-container/85 hover:text-on-surface dark:text-zinc-500 dark:hover:bg-zinc-800/70 dark:hover:text-zinc-200'
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

type NavItem = {
  to: string
  label: string
  icon: object
  keywords?: string[]
}

type NavGroup = {
  label: string
  items: NavItem[]
}

type SearchItem = NavItem & {
  group: string
  searchText: string
}

const navGroups: NavGroup[] = [
  { label: '概览', items: [{ to: '/overview', label: '总览', icon: LayoutDashboard }] },
  {
    label: '身份',
    items: [
      { to: '/users', label: '用户中心', icon: Users, keywords: ['用户', '账号', '绑定', 'teacher', 'student'] },
      { to: '/groups', label: '群组中心', icon: MessageSquare, keywords: ['群组', '班级', '群聊'] },
    ],
  },
  {
    label: '系统',
    items: [
      { to: '/status', label: '系统状态', icon: Activity, keywords: ['状态', '监控', 'cpu', '内存', '磁盘'] },
      { to: '/databases', label: '数据库管理', icon: Database, keywords: ['数据库', '表', 'schema', 'er'] },
      { to: '/files', label: '文件空间', icon: FolderKanban, keywords: ['文件', '目录', '空间', 'storage'] },
      { to: '/chat-history', label: '聊天记录', icon: History, keywords: ['聊天', '消息', '历史', '会话'] },
      { to: '/settings', label: '系统设置', icon: Settings, keywords: ['设置', '配置', 'system'] },
    ],
  },
  {
    label: 'AI 资产',
    items: [
      { to: '/skills', label: 'Skill 管理', icon: Puzzle, keywords: ['skill', '技能'] },
      { to: '/prompts', label: 'Prompt 管理', icon: FileText, keywords: ['prompt', '提示词'] },
      { to: '/models', label: 'Model 管理', icon: Cpu, keywords: ['model', 'llm', '模型'] },
    ],
  },
  { label: 'Agent', items: [{ to: '/agents', label: 'Agent 管理', icon: Bot, keywords: ['agent', '工作流', 'run'] }] },
  {
    label: '集成',
    items: [
      { to: '/integrations', label: 'MCP / 集成', icon: Plug, keywords: ['mcp', '集成', 'integration'] },
      { to: '/nonebot/plugins', label: 'Plugin 管理', icon: Puzzle, keywords: ['nonebot', 'plugin', '命令', '插件'] },
      { to: '/nonebot/bots', label: 'Bot 管理', icon: Bot, keywords: ['nonebot', 'bot', '适配器'] },
    ],
  },
  {
    label: '运维',
    items: [
      { to: '/operations', label: '运维调试', icon: Terminal, keywords: ['终端', '日志', '调试', 'ops'] },
      { to: '/automation-scripts', label: '自动化脚本', icon: FileCode2, keywords: ['脚本', '自动化', 'script'] },
    ],
  },
]

const searchItems = computed<SearchItem[]>(() =>
  navGroups.flatMap((group) =>
    group.items.map((item) => ({
      ...item,
      group: group.label,
      searchText: [group.label, item.label, item.to, ...(item.keywords || [])].join(' ').toLowerCase(),
    })),
  ),
)

const filteredSearchItems = computed(() => {
  const query = normalizedSearchQuery.value
  if (!query) return searchItems.value
  return searchItems.value.filter((item) => item.searchText.includes(query))
})

const searchResultItems = computed(() => filteredSearchItems.value.slice(0, 5))
const searchPanelVisible = computed(() => searchPanelOpen.value && normalizedSearchQuery.value.length > 0)

function openSearchPanel() {
  searchPanelOpen.value = true
}

function closeSearchPanel() {
  searchPanelOpen.value = false
}

function handleSearchBlur() {
  window.setTimeout(() => {
    searchPanelOpen.value = false
  }, 120)
}

async function navigateToSearchItem(item: SearchItem) {
  globalSearch.value = ''
  searchPanelOpen.value = false
  if (route.path !== item.to) {
    await router.push(item.to)
  }
}

async function openFirstSearchResult() {
  const firstItem = filteredSearchItems.value[0]
  if (!firstItem) return
  await navigateToSearchItem(firstItem)
}

onMounted(() => {
  collapsed.value = localStorage.getItem(SIDEBAR_COLLAPSE_KEY) === 'true'
  try {
    const storedGroups = localStorage.getItem(NAV_GROUP_STATE_KEY)
    if (!storedGroups) return
    const parsed = JSON.parse(storedGroups)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return
    groupOpenState.value = Object.fromEntries(
      Object.entries(parsed).filter((entry): entry is [string, boolean] => typeof entry[1] === 'boolean'),
    )
  }
  catch {
    groupOpenState.value = {}
  }
})

watch(collapsed, (value) => {
  localStorage.setItem(SIDEBAR_COLLAPSE_KEY, String(value))
})

watch(
  groupOpenState,
  (value) => {
    localStorage.setItem(NAV_GROUP_STATE_KEY, JSON.stringify(value))
  },
  { deep: true },
)

watch(
  () => route.fullPath,
  () => {
    globalSearch.value = ''
    searchPanelOpen.value = false
  },
)
</script>
