# ClassRobot Managers

机器人后台管理界面前端工程。

## 技术栈

- Vue 3
- TypeScript
- Vite
- Tailwind CSS
- Less
- Pinia
- Vue Router
- Axios
- ECharts

## 目录约定

- `src/api/`: 管理端请求封装
- `src/components/`: 可复用组件
- `src/layouts/`: 页面布局
- `src/router/`: 前端路由
- `src/stores/`: 状态管理
- `src/types/`: 接口类型定义
- `src/views/`: 页面视图
- `src/styles/`: Tailwind 与 Less 全局样式

## 启动方式

```bash
npm install
npm run dev
```

默认通过 Vite 代理访问本地后端 `http://127.0.0.1:8088`。

## 环境变量

复制 `.env.example` 为 `.env.local` 后按需修改：

- `VITE_API_BASE_URL`: 后端 API 前缀
- `VITE_ADMIN_API_TOKEN`: 默认管理令牌，可为空，运行时也可在登录页填写
