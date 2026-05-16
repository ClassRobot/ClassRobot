# Manager HTTP 入口

`src.interfaces.http.manager` 是管理端 HTTP 的 canonical import。

当前阶段这里先提供稳定入口和开发文档，底层仍桥接到 `src.routers.managers` 的现有实现；后续会逐步把实现迁移到这里，旧路径保留兼容。

## 入口职责

- 暴露管理端 `router`
- 维护 schema / service 的统一导入入口
- 明确管理端属于接口层，不是业务命令层

## 边界

- 管理端路由属于接口层。
- 业务规则应下沉到 service 或 `core`。
- Agent 编排草稿、运行时热更新、配置落盘都应围绕统一 schema 与 service 完成。

