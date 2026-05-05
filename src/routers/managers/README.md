# ClassBot 管理后台 API

`src/routers/managers/` 是本地管理后台后端接口的主要落点，建议统一承载 `/api/v1/manager/*` 相关路由、服务编排和返回结构。

## 目录职责

- 对外暴露管理后台使用的 HTTP API
- 串联状态检测、配置读写、日志读取、Prompt/Skill/Model 管理等后台能力
- 与 `website/managers/` 前端配套，但不直接承担前端资源本身

## 关联目录

- 后台专题文档：[docs/managers](../../../docs/managers/README.md)
- 前端实现：[website/managers](../../../website/managers/README.md)
- 路由入口：`src/routers/path.py`

## 维护建议

- 路由层只做参数校验、鉴权和响应组织
- 业务逻辑尽量下沉到 service/store 层
- 后台专用接口不要混入通用外部 API 文档目录，统一在 [接口设计](../../../docs/managers/api-design.md) 中维护
