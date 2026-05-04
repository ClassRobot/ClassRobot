# ClassRobot 管理后台

基于 Vue 3 + TypeScript + Tailwind CSS + Less 的本地管理平台前端。

## 快速开始

```bash
cd website/managers
npm install
npm run dev        # 启动开发服务器 (http://localhost:5173)
npm run build      # 生产构建
npm run preview    # 预览生产构建
```

开发时 Vite 会将 `/api` 请求代理到 `http://127.0.0.1:8080`（后端 FastAPI 端口）。

## 目录结构

```
website/managers/
├── index.html
├── package.json
├── vite.config.ts          # Vite 配置、路径别名、代理
├── tailwind.config.js      # 设计 token（颜色/字体/尺寸）
├── tsconfig.json
├── src/
│   ├── main.ts             # 应用入口
│   ├── App.vue             # 根组件
│   ├── router/index.ts     # 路由配置 + 鉴权守卫
│   ├── composables/
│   │   └── useAuth.ts      # 响应式 auth store
│   ├── types/
│   │   └── api.ts          # 后端 API 完整类型定义
│   ├── api/
│   │   ├── client.ts       # Axios 实例 + auth 拦截器
│   │   ├── auth.ts
│   │   ├── overview.ts
│   │   ├── users.ts
│   │   ├── status.ts
│   │   ├── settings.ts
│   │   ├── skills.ts
│   │   ├── prompts.ts
│   │   ├── models.ts
│   │   ├── agents.ts
│   │   ├── integrations.ts
│   │   ├── logs.ts
│   │   └── operations.ts
│   ├── layouts/
│   │   └── ManagerLayout.vue   # 应用外壳（sidebar + topbar）
│   ├── views/
│   │   ├── LoginView.vue
│   │   ├── OverviewView.vue
│   │   ├── UsersView.vue
│   │   ├── StatusView.vue
│   │   ├── SettingsView.vue
│   │   ├── SkillsView.vue
│   │   ├── PromptsView.vue
│   │   ├── ModelsView.vue
│   │   ├── AgentsView.vue
│   │   ├── IntegrationsView.vue
│   │   └── OperationsView.vue
│   └── styles/
│       ├── variables.less      # Less 变量（颜色/尺寸）
│       └── global.less         # Tailwind directives + 全局样式
```

## 页面清单

| 页面 | 路由 | 状态 |
|------|------|------|
| 登录 | `/login` | 骨架就绪 |
| 总览 | `/overview` | 骨架就绪 |
| 用户中心 | `/users` | 骨架就绪 |
| 系统状态 | `/status` | 骨架就绪 |
| 系统设置 | `/settings` | 骨架就绪 |
| Skill 管理 | `/skills` | 骨架就绪 |
| Prompt 管理 | `/prompts` | 骨架就绪 |
| Model 管理 | `/models` | 骨架就绪 |
| Agent 管理 | `/agents` | 骨架就绪 |
| MCP/集成 | `/integrations` | 骨架就绪 |
| 运维调试 | `/operations` | 骨架就绪 |

所有页面均挂载在 `/manager` 路径下（由 `vite.config.ts` 和 `router/index.ts` 统一管理）。
