# 本地管理后台文档

本目录用于沉淀 ClassRobot 本地管理后台的产品范围、接口约定、前端布局、权限模型和落地路线。

这里讨论的后台不是校园业务管理后台。班级、请假、课表、校园审批等功能会在后续独立的校园管理界面中展开；本目录聚焦机器人项目本身的本地化运维、调试、AI 资产和系统设置。

## 阅读顺序

1. [范围与需求说明](./scope-and-requirements.md)
2. [信息架构与页面清单](./information-architecture.md)
3. [接口设计](./api-design.md)
4. [前端界面布局](./frontend-layout.md)
5. [数据来源与权限策略](./data-and-permissions.md)
6. [后端实现方案](./backend-implementation.md)
7. [实施路线与验收清单](./implementation-roadmap.md)

## 后台定位

管理后台是一个随项目本地启动的系统控制台，优先解决下面几类问题：

- 查看项目是否正常运行，包括数据库、缓存、模型、Prompt、Skill、Agent、日志等状态。
- 管理系统级配置，包括模型配置、RAG 配置、COS 配置、缓存配置和后台登录 token。
- 查看和调试 Agent 工作流，包括运行记录、检查点、失败原因和待确认状态。
- 管理 AI 资产，包括 Skill、Prompt、Model、MCP 接入占位和后续工具注册状态。
- 提供本地自动化入口，包括运行检查、生成 SQL、测试模型连通性、重载 Skill、校验 Prompt 等操作。

## 不纳入本期

- 请假、课表、入班审批、班级组织架构等校园业务后台。
- 面向多租户或公网开放的管理平台。
- 独立缺陷工单系统。
- 完整 MCP 服务市场。
- 持久化用户会话系统。

## 当前代码落点

- FastAPI 入口：`src/routers/path.py`
- 管理后台后端预留目录：`src/routers/managers/`
- 管理后台前端预留目录：`website/managers/`
- 用户与绑定数据：`utils/models/models.py`
- Agent 运行数据：`src/plugins/autogpt/runs.py`、`src/plugins/autogpt/checkpoints.py`
- Skill 注册：`src/agents/skills/registry.py`
- Prompt 模板：`resources/prompts/`
- 模型配置：`utils/llm/config.py`
- 全局配置：`utils/config.py`

## 文档放置约定

管理后台相关文档统一放在 `docs/managers/`。

如果内容是后台专用接口、后台页面布局、后台配置项、后台权限和后台实施路线，都放在本目录。通用外部 API 仍放在 `docs/api/`；通用架构原则仍放在 `docs/architecture/`；通用开发方法仍放在 `docs/guides/`。
