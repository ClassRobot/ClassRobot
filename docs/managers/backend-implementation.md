# 后端实现方案

本文档说明管理后台后端应该如何分层、如何落目录，以及哪些能力适合放在统一入口、领域服务和运行时探针中。

## 总体思路

管理后台后端建议继续保持“薄路由 + 领域服务 + 运行时探针”的结构：

- `router.py`
  - 负责统一挂载和模块聚合。
- `api/`
  - 负责按页面或资源拆分 HTTP 接口。
- `agent/`、`catalog/`、`database/`、`identity/`、`runtime/`、`storage/`
  - 负责具体领域能力。
- `security.py`
  - 负责后台鉴权和会话令牌。
- `schemas.py`
  - 负责公共响应模型和共享请求模型。

这样可以避免把后台做成一个“只有接口没有边界”的大目录，也方便后续持续扩展。

## 代码放置

后台后端统一放在：

```text
src/interfaces/http/managers/
```

推荐结构如下：

```text
src/interfaces/http/managers/
  __init__.py
  README.md
  router.py
  security.py
  schemas.py
  service.py
  audit.py
  api/
    auth.py
    overview.py
    users.py
    groups.py
    models.py
    skills.py
    prompts.py
    agents.py
    settings.py
    logs.py
    operations.py
    chat_history.py
    files.py
    databases.py
    nonebot.py
  agent/
  catalog/
  database/
  identity/
  runtime/
  storage/
```

前端管理端继续放在：

```text
website/managers/
```

## FastAPI 挂载方式

当前 `src/interfaces/http/path.py` 已经通过 `get_app()` 获取 FastAPI app，并在同一个应用实例上挂载管理端路由。

示意代码：

```python
from src.interfaces.http.managers.router import router as managers_router

app.include_router(managers_router)
```

后台 router 自身建议保持：

```python
APIRouter(prefix="/api/v1/manager", tags=["Manager"])
```

## 鉴权收口

后台鉴权建议统一收口到 `security.py`，不要把 token 校验散落到各个 API 文件中。

### MVP 策略

- 项目启动时生成随机 token。
- 在控制台输出一次。
- 进程内保存 hash 或签发依据。
- 登录时校验用户输入。
- 登录成功后返回短期 session token。

### 轮换策略

- 在系统设置页触发轮换。
- 新 token 输出到控制台。
- 旧 session token 失效。
- 前端回到登录页重新认证。

### 不建议

- 不建议把启动 token 明文写入仓库。
- 不建议在前端展示完整 token。
- 不建议把后台登录直接做成普通用户密码登录，避免和 `User.password` 概念混淆。

## 服务分层

这里建议明确区分“入口层”和“领域服务层”，避免后续把所有逻辑重新堆回 `api/*.py`。

### Router 层

职责：

- 参数解析。
- 鉴权依赖。
- 调用 service。
- 返回 Pydantic schema。
- 把能力按页面或资源拆到 `api/*.py`。

### Service 层

职责：

- 聚合 ORM、文件系统、配置和运行时信息。
- 做业务校验。
- 控制危险操作。
- 组装状态检查结果。
- 尽量按领域放到子包中，而不是继续往根目录新增无边界模块。

## 主要模块职责

下面的说明更偏“职责视角”，不要求所有文件名与早期草案完全一致。实现时应优先服从当前目录边界。

### `security.py`

职责：

- 生成启动 token。
- 登录校验。
- session token 签发与校验。
- 提供 FastAPI 鉴权依赖。

### `runtime/status.py`

职责：

- 检测数据库连接。
- 检测 Alembic 版本。
- 检测缓存状态。
- 检测关键路径存在性。
- 检测 Prompt、Skill、模型、COS、RAGFlow 等依赖状态。

### `runtime/settings.py`

职责：

- 读取当前配置。
- 对密钥字段脱敏。
- 写入设置。
- 标记是否需要重启。
- 写入前创建备份。

推荐先支持两类写入：

- 后台自身状态写入 `config_dir/manager-settings.json`。
- 项目运行配置更新 `.env`，并返回 `restart_required`。

### `catalog/skills.py`

职责：

- 读取 `skill_registry.manifests`。
- 检查 skill 目录。
- 检查 runtime 是否存在。
- 提供重载入口。

### `catalog/prompts.py`

职责：

- 列出 `resources/prompts/*.jinja`。
- 读取 Prompt。
- 校验 Jinja 模板。
- 写入 Prompt 前备份。
- 提供 diff 所需版本内容。

### `catalog/llm_models.py`

职责：

- 读取 `llm_configs`。
- 脱敏模型 key。
- 测试指定模型。
- 保存模型配置。

使用 `llm_models.py` 这类显式命名，可以避免和 ORM `utils.models` 混淆。

### `agent/service.py`

职责：

- 查询 `AgentWorkflowRun`。
- 查询 `AgentWorkflowCheckpoint`。
- 按 trace_id 读取详情。
- 删除检查点。
- 提取工作流事件、步骤、审批信息。

### `runtime/logs.py`

职责：

- 枚举允许读取的日志文件。
- 分页读取日志。
- tail 日志。
- 截断过大输出。

日志读取必须做路径限制。

### `runtime/operations.py`

职责：

- 定义自动化动作白名单。
- 执行动作。
- 收集 stdout、stderr、退出码和耗时。
- 返回执行结果。

## 自动化动作白名单

第一版建议支持：

| action_id | 命令或函数 | 风险 |
| --- | --- | --- |
| `check_config` | Python 函数检查配置完整性 | 低 |
| `check_database` | ORM 查询和表统计 | 低 |
| `validate_prompts` | Jinja 模板解析 | 低 |
| `reload_skills` | `skill_registry.load_skills()` | 中 |
| `test_models` | 发送极短测试请求 | 中 |
| `generate_sql` | `scripts/generate_sql.py` | 中 |
| `run_unit_tests` | `pytest` | 中 |

禁止：

- 任意 shell 输入。
- 删除目录。
- Git reset / checkout。
- 未经限制的文件写入。

## 前端静态资源

如果前端先做静态构建，可以由 FastAPI 挂载：

```text
/manager
```

对应静态目录：

```text
website/managers/dist
```

开发阶段可以单独启动前端 dev server，再代理 `/api/v1/manager`。

## 数据库访问

后台接口读取 ORM 时优先使用当前项目模型：

```text
utils.models.models
```

涉及列表接口时要注意：

- 分页。
- 避免一次性加载大 JSON。
- `workflow_data` 只在详情接口返回。
- 用户列表不要默认展开所有关系。

## Prompt 编辑流程

```mermaid
sequenceDiagram
    participant UI as 前端
    participant API as Manager API
    participant Store as Prompt Store
    UI->>API: PUT /prompts/{name}
    API->>Store: 校验路径
    Store->>Store: 创建备份
    Store->>Store: Jinja 校验
    Store->>Store: 写入文件
    API-->>UI: saved + validation result
```

## 设置保存流程

```mermaid
sequenceDiagram
    participant UI as 前端
    participant API as Manager API
    participant Store as Settings Store
    UI->>API: PATCH /settings
    API->>Store: 字段校验
    Store->>Store: 密钥字段处理
    Store->>Store: 写入备份
    Store->>Store: 保存配置
    API-->>UI: restart_required + changed_keys
```

## 测试建议

### 单元测试

- token 校验。
- 密钥脱敏。
- Prompt 路径限制。
- Prompt 校验。
- 设置写入合并。
- 自动化动作白名单。

### 集成测试

- 未登录访问返回 `401`。
- 登录成功后可访问总览。
- 用户列表分页正常。
- Agent 详情不会在列表中展开大 JSON。
- 删除检查点需要合法 token。

### 手动验收

- 启动项目能看到后台 token。
- 登录后进入总览页。
- 所有页面刷新不丢状态。
- 修改设置能看到重启提示。
- 日志读取不会越权到任意路径。
- 模型测试失败时错误可读。
