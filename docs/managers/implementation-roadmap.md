# 实施路线与验收清单

## 开发顺序

建议按低风险到高风险推进。

## Phase 1: 后台骨架

目标：后台可以登录、进入总览、访问只读状态。

任务：

- 新增 `src/routers/managers/` FastAPI router。
- 实现启动 token 生成和登录接口。
- 实现 `/api/v1/manager/overview`。
- 实现 `/api/v1/manager/status` 只读接口。
- 创建 `website/managers/` 前端骨架。
- 完成登录页、应用外壳、总览页。

验收：

- 启动项目后控制台出现后台 token。
- 输入 token 可以登录。
- 未登录访问后台 API 返回 `401`。
- 总览页可以展示数据库、Skill、Prompt、Model 的基本状态。

## Phase 2: 只读管理页

目标：能查看系统核心资产。

任务：

- 用户中心只读列表和详情。
- Skill 管理只读列表和详情。
- Prompt 管理只读列表和详情。
- Model 管理只读列表。
- Agent 运行记录和检查点只读列表。
- 运维调试页展示日志文件列表。

验收：

- 用户详情能聚合绑定、教师扩展、学生扩展。
- Skill 列表能展示内置 Skill。
- Prompt 列表能展示 `resources/prompts` 下模板。
- Agent 详情能展示 `workflow_data`。
- 日志列表不会展示允许目录以外的文件。

## Phase 3: 调试动作

目标：后台可以执行受控诊断动作。

任务：

- 实现自动化动作白名单。
- 支持配置检查。
- 支持数据库检查。
- 支持 Prompt 校验。
- 支持 Skill 重载。
- 支持模型连通性测试。
- 支持动作结果展示。

验收：

- 前端不能输入任意 shell 命令。
- 每个动作都有 loading、成功、失败状态。
- 失败结果包含可读错误摘要。
- 长输出被截断并可展开或下载。

## Phase 4: 可写设置

目标：系统设置页可以安全修改配置。

任务：

- 实现设置读取和脱敏。
- 实现设置保存。
- 实现 `.env` 或 overlay 配置写入。
- 实现保存前备份。
- 实现重启提示。
- 实现 token 轮换。

验收：

- 密钥字段不会明文回显。
- 未修改密钥不会被掩码覆盖。
- 修改后明确提示是否需要重启。
- 轮换 token 后旧 session 失效。

## Phase 5: Prompt 与 Agent 写操作

目标：开放有限的 AI 资产维护能力。

任务：

- Prompt 编辑。
- Prompt 保存前备份。
- Prompt 校验。
- Prompt diff。
- Agent 检查点删除。
- 失败工作流过滤。

验收：

- Prompt 只能编辑 `resources/prompts/` 内文件。
- 保存失败不会破坏原文件。
- 删除检查点必须二次确认。
- Agent 列表默认不加载大型 JSON。

## Phase 6: 集成与增强

目标：为后续 MCP、Tool Registry、评测和成本统计留接口。

任务：

- MCP / 集成页展示状态。
- RagFlow、COS、模型 Provider 健康检查。
- Tool Registry 预留接口。
- 操作审计预留。
- 模型调用统计预留。

验收：

- 未实现能力以 `planned` 或 `not_configured` 呈现。
- 不把未接通能力展示成可用。
- 后续新增 MCP 注册表时不需要重做导航结构。

## 交付清单

### 后端

- `src/routers/managers/router.py`
- `src/routers/managers/security.py`
- `src/routers/managers/schemas.py`
- `src/routers/managers/service.py`
- `src/routers/managers/status.py`
- `src/routers/managers/settings_store.py`
- `src/routers/managers/skills.py`
- `src/routers/managers/prompts.py`
- `src/routers/managers/agents.py`
- `src/routers/managers/logs.py`
- `src/routers/managers/operations.py`

### 前端

- `website/managers/README.md`
- 登录页。
- 应用外壳。
- 总览页。
- 用户中心。
- 系统状态。
- 系统设置。
- Skill 管理。
- Agent 管理。
- Prompt 管理。
- Model 管理。
- MCP / 集成管理。
- 运维调试。

### 文档

- 本目录下所有设计文档。
- `docs/README.md` 导航更新。
- `docs/getting-started/project-structure.md` 目录说明更新。

## 验收标准

### 安全

- 所有后台 API 都需要 token。
- 密钥默认脱敏。
- Prompt 和日志读取有路径限制。
- 自动化动作必须白名单。
- 危险操作有二次确认。

### 可用性

- 进入后台后能在 3 次点击内查看日志。
- 进入后台后能在 3 次点击内测试模型。
- 进入后台后能在 3 次点击内查看失败 Agent 运行。
- 系统设置保存后能明确知道是否需要重启。

### 稳定性

- 未配置 Redis、RagFlow、COS 时后台不能崩溃。
- Agent 表为空时显示空状态。
- Prompt 解析失败时能保留原内容。
- 模型测试超时时能正常返回错误。

### 可维护性

- 后台接口和普通机器人命令分离。
- 后台服务层不直接拼接危险 shell 命令。
- 配置写入有备份。
- 大型 JSON 只在详情接口返回。

## 风险与处理

| 风险 | 处理 |
| --- | --- |
| `.env` 写入破坏格式 | 写入前备份，优先使用结构化 parser |
| 密钥泄露到日志 | 脱敏函数集中处理，错误信息过滤 |
| 自动化动作被滥用 | 白名单 + 二次确认 + 超时 |
| Prompt 编辑破坏 Agent | 保存前校验 + 备份恢复 |
| MCP 尚未实现 | 页面标记为 `planned`，只做状态占位 |
| 日志路径越权 | 固定允许目录，拒绝相对跳转 |

## 推荐第一批任务

1. 实现 token 登录和鉴权依赖。
2. 实现总览和系统状态只读接口。
3. 搭建前端应用外壳和登录页。
4. 实现 Skill、Prompt、Model 只读列表。
5. 实现 Agent 运行记录只读列表。
6. 实现日志查看和 Prompt 校验动作。
7. 再进入可写系统设置。
