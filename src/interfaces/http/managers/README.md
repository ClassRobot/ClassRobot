# ClassBot 管理后台 API

`src/interfaces/http/managers/` 是管理端 HTTP 的真实实现目录，统一承载
`/api/v1/manager/*` 相关路由、服务编排和返回结构。

## 目录职责

- 对外暴露管理后台使用的 HTTP API
- 串联状态检测、配置读写、日志读取、Prompt/Skill/Model 管理等后台能力
- 与 `website/managers/` 前端配套，但不直接承担前端资源本身

## 当前结构

- `router.py`：总入口，只负责聚合所有管理后台子路由
- `api/`：按接口域拆分的 HTTP 路由层
- `agent/`：Agent 编排、运行记录、检查点和设计器相关实现
- `catalog/`：Prompt、Skill、模型配置等 AI 资产管理实现
- `database/`：数据库连接、表结构、ER 关系和数据编辑实现
- `identity/`：用户中心与群组中心实现
- `runtime/`：运行时配置、系统状态、NoneBot 运行态、日志与运维动作实现
- `storage/`：文件空间与聊天记录实现
- `schemas.py`：管理后台共享请求体模型
- `security.py`：本地后台令牌登录、会话鉴权与依赖
- `service.py`：跨领域共用的时间、路径与脱敏辅助函数
- `audit.py`：管理端审计日志写入与查询
- `__init__.py`：按需暴露管理端主路由，避免包级导入放大启动副作用

路由层拆分说明见：[api/README.md](api/README.md)

## 关联目录

- 后台专题文档：[docs/managers](../../../../docs/managers/README.md)
- 前端实现：[website/managers](../../../../website/managers/README.md)
- 路由入口：`src/interfaces/http/path.py`

## 维护建议

- 路由层只做参数校验、鉴权、审计和 HTTP 异常映射
- 业务逻辑尽量下沉到 service/store 层，不要再往 `router.py` 聚合入口塞业务代码
- 新增后台接口时，优先在对应领域子包里补 service，再在 `api/` 中追加路由边界
- 新功能应按领域落位，例如用户与群组放 `identity/`，运行时和运维放 `runtime/`，不要再回退成顶层平铺文件
- 新代码应直接使用 `src.interfaces.http.managers...` 路径；旧路由兼容层已经移除
- 后台专用接口不要混入通用外部 API 文档目录，统一在 [接口设计](../../../../docs/managers/api-design.md) 中维护
