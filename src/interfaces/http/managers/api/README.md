# Manager API 路由分层

`src/interfaces/http/managers/api/` 只负责管理后台 HTTP 路由层的拆分与聚合，不承载具体业务实现。

## 设计目标

- 避免把所有 `/api/v1/manager/*` 路由继续堆进单个超长 `router.py`
- 让每个接口域都能在独立模块中维护鉴权、参数边界和错误映射
- 保持现有服务层文件、接口路径和测试行为不变，优先做低风险整理

## 当前结构

- `auth.py`：后台登录、鉴权会话
- `overview.py`：总览、状态、集成与系统指标
- `settings.py`：系统设置与运行时配置
- `users.py`：用户中心相关接口
- `groups.py`：群组中心相关接口
- `skills.py`：Skill 管理接口
- `prompts.py`：Prompt 管理接口
- `models.py`：模型配置接口
- `agents.py`：Agent 管理接口
- `nonebot.py`：NoneBot、Plugin、Bot 运行态接口
- `files.py`：文件空间接口
- `chat_history.py`：聊天记录接口
- `databases.py`：数据库管理接口
- `logs.py`：日志读取接口
- `operations.py`：运维动作、终端、脚本与审计接口

对应实现已按领域迁移到上一级子包中：

- `agent/`：`agents.py`
- `catalog/`：`skills.py`、`prompts.py`、`models.py`
- `database/`：`databases.py`
- `identity/`：`users.py`、`groups.py`
- `runtime/`：`auth.py` 之外的大多数运行时与运维接口
- `storage/`：`files.py`、`chat_history.py`

## 扩展建议

- 新增后台页面能力时，优先先找对应接口域模块，而不是回退到总入口文件追加
- 路由层只做参数边界、鉴权、审计和 HTTP 异常映射
- 复杂业务逻辑继续下沉到 `src/interfaces/http/managers/` 下对应领域子包的实现模块
- 当某个接口域继续膨胀时，再进一步拆为 `router.py`、`schemas.py`、`service.py` 子包
