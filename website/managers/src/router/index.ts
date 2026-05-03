import { createRouter, createWebHashHistory } from "vue-router";

import { getStoredAdminToken } from "@/utils/admin-token";

const AdminLayout = () => import("@/layouts/AdminLayout.vue");
const LoginView = () => import("@/views/LoginView.vue");
const DashboardView = () => import("@/views/DashboardView.vue");
const UsersView = () => import("@/views/UsersView.vue");
const CommandsView = () => import("@/views/CommandsView.vue");
const AssetsView = () => import("@/views/AssetsView.vue");
const AgentsView = () => import("@/views/AgentsView.vue");
const DatabaseView = () => import("@/views/DatabaseView.vue");
const SystemView = () => import("@/views/SystemView.vue");


const router = createRouter({
  history: createWebHashHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: "/login",
      name: "login",
      component: LoginView,
      meta: { title: "后台登录" },
    },
    {
      path: "/",
      component: AdminLayout,
      redirect: { name: "dashboard" },
      children: [
        {
          path: "dashboard",
          name: "dashboard",
          component: DashboardView,
          meta: { title: "总览面板", requiresAuth: true },
        },
        {
          path: "users",
          name: "users",
          component: UsersView,
          meta: { title: "用户管理", requiresAuth: true },
        },
        {
          path: "commands",
          name: "commands",
          component: CommandsView,
          meta: { title: "命令管理", requiresAuth: true },
        },
        {
          path: "assets",
          name: "assets",
          component: AssetsView,
          meta: { title: "资源目录", requiresAuth: true },
        },
        {
          path: "agents",
          name: "agents",
          component: AgentsView,
          meta: { title: "Agent 管理", requiresAuth: true },
        },
        {
          path: "database",
          name: "database",
          component: DatabaseView,
          meta: { title: "数据库总览", requiresAuth: true },
        },
        {
          path: "system",
          name: "system",
          component: SystemView,
          meta: { title: "系统状态", requiresAuth: true },
        },
      ],
    },
  ],
});


router.beforeEach((to) => {
  document.title = `ClassRobot Managers | ${String(to.meta.title ?? "管理后台")}`;
  if (to.meta.requiresAuth && !getStoredAdminToken()) {
    return { name: "login" };
  }
  if (to.name === "login" && getStoredAdminToken()) {
    return { name: "dashboard" };
  }
  return true;
});


export default router;
