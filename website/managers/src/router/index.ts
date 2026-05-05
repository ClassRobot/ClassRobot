import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/composables/useAuth'

const router = createRouter({
  history: createWebHistory('/manager'),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('@/views/LoginView.vue'),
      meta: { requiresAuth: false },
    },
    {
      path: '/',
      component: () => import('@/layouts/ManagerLayout.vue'),
      meta: { requiresAuth: true },
      redirect: '/overview',
      children: [
        {
          path: 'overview',
          name: 'Overview',
          component: () => import('@/views/OverviewView.vue'),
          meta: { title: '系统总览', group: '概览' },
        },
        {
          path: 'users',
          name: 'Users',
          component: () => import('@/views/UsersView.vue'),
          meta: { title: '用户中心', group: '身份' },
        },
        {
          path: 'groups',
          name: 'Groups',
          component: () => import('@/views/GroupsView.vue'),
          meta: { title: '群组中心', group: '身份' },
        },
        {
          path: 'status',
          name: 'Status',
          component: () => import('@/views/StatusView.vue'),
          meta: { title: '系统状态', group: '系统' },
        },
        {
          path: 'databases',
          name: 'Databases',
          component: () => import('@/views/DatabasesView.vue'),
          meta: { title: '数据库管理', group: '系统' },
        },
        {
          path: 'files',
          name: 'Files',
          component: () => import('@/views/FilesView.vue'),
          meta: { title: '文件空间', group: '系统' },
        },
        {
          path: 'chat-history',
          name: 'ChatHistory',
          component: () => import('@/views/ChatHistoryView.vue'),
          meta: { title: '聊天记录', group: '系统' },
        },
        {
          path: 'settings',
          name: 'Settings',
          component: () => import('@/views/SettingsView.vue'),
          meta: { title: '系统设置', group: '系统' },
        },
        {
          path: 'skills',
          name: 'Skills',
          component: () => import('@/views/SkillsView.vue'),
          meta: { title: 'Skill 管理', group: 'AI 资产' },
        },
        {
          path: 'prompts',
          name: 'Prompts',
          component: () => import('@/views/PromptsView.vue'),
          meta: { title: 'Prompt 管理', group: 'AI 资产' },
        },
        {
          path: 'models',
          name: 'Models',
          component: () => import('@/views/ModelsView.vue'),
          meta: { title: 'Model 管理', group: 'AI 资产' },
        },
        {
          path: 'agents',
          name: 'Agents',
          component: () => import('@/views/AgentsView.vue'),
          meta: { title: 'Agent 管理', group: 'Agent' },
        },
        {
          path: 'integrations',
          name: 'Integrations',
          component: () => import('@/views/IntegrationsView.vue'),
          meta: { title: 'MCP / 集成', group: '集成' },
        },
        {
          path: 'nonebot',
          name: 'NoneBot',
          redirect: '/nonebot/plugins',
        },
        {
          path: 'nonebot/plugins',
          name: 'NoneBotPlugins',
          component: () => import('@/views/NoneBotView.vue'),
          props: { mode: 'plugin' },
          meta: { title: 'Plugin 管理', group: '集成' },
        },
        {
          path: 'nonebot/bots',
          name: 'NoneBotBots',
          component: () => import('@/views/NoneBotView.vue'),
          props: { mode: 'bot' },
          meta: { title: 'Bot 管理', group: '集成' },
        },
        {
          path: 'operations',
          name: 'Operations',
          component: () => import('@/views/OperationsView.vue'),
          meta: { title: '运维调试', group: '运维' },
        },
        {
          path: 'automation-scripts',
          name: 'AutomationScripts',
          component: () => import('@/views/AutomationScriptsView.vue'),
          meta: { title: '自动化脚本', group: '运维' },
        },
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'NotFound',
      component: () => import('@/views/NotFoundView.vue'),
      meta: { requiresAuth: false },
    },
  ],
})

router.beforeEach((to, _from) => {
  const requiresAuth = to.matched.some((r) => r.meta.requiresAuth !== false)
  const isAuthenticated = useAuthStore().isAuthenticated

  if (requiresAuth && !isAuthenticated) {
    return { name: 'Login' }
  }

  if (to.name === 'Login' && isAuthenticated) {
    return { name: 'Overview' }
  }
})

export default router
