# 文档中心

`docs/` 现在按“上手、指南、参考、架构、API、管理后台”分层组织，根目录只保留总入口，避免专题文档继续堆在同一层。

## 文档分层

- `getting-started/`
  - 面向首次接手项目的开发者，重点回答“项目怎么配、目录怎么看、先读什么”
- `guides/`
  - 面向开发与扩展实践，重点回答“流程怎么跑、能力怎么接、规范怎么落”
- `reference/`
  - 面向查阅型资料，重点回答“系统现在有什么、命令怎么用、角色怎么理解”
- `architecture/`
  - 面向系统设计与演进，重点回答“当前架构是什么、目标架构是什么、如何迁移”
- `api/`
  - 面向接口使用者，集中放版本化接口文档
- `managers/`
  - 面向本地管理后台开发者，集中放后台范围、接口、界面、权限、实现路线和验收文档

## 快速导航

### 上手指南

- [上手指南总览](./getting-started/README.md)
- [配置说明](./getting-started/configuration.md)
- [项目结构说明](./getting-started/project-structure.md)

### 开发指南

- [开发指南总览](./guides/README.md)
- [Skill 系统说明](./guides/skill-system.md)
- [消息处理流程](./guides/message-processing-flow.md)
- [消息历史存储与归属说明](./guides/message-history-storage.md)
- [AutoGPT 智能能力改进方案](./guides/agent-module.md)
- [Agent Playbook 与确认执行](./guides/agent-playbooks.md)
- [Agent 工程化研发手册](./guides/agent-engineering-playbook.md)
- [Harness Engineering 架构蓝图](./architecture/harness-engineering-architecture.md)

### 参考资料

- [参考资料总览](./reference/README.md)
- [项目能力总览](./reference/capability-overview.md)
- [命令使用文档](./reference/command-reference.md)
- [角色与组织关系说明](./reference/role-reference.md)

### 架构专题

- [AI 架构专题](./architecture/README.md)
- [架构视图总览](./architecture/architecture-views.md)
- [Agent 工作流编排架构](./architecture/agent-workflow-orchestration.md)
- [命令与 Agent 一体化架构设计](./architecture/command-agent-unified-architecture.md)
- [统一 AI 平台架构总纲](./architecture/unified-ai-platform-handbook.md)
- [迁移路线图](./architecture/migration-roadmap.md)
- [软件工程流程方案](./architecture/software-engineering-process.md)

### API

- [API 文档总览](./api/README.md)
- [API V1](./api/v1.md)

### 管理后台

- [本地管理后台文档](./managers/README.md)
- [范围与需求说明](./managers/scope-and-requirements.md)
- [信息架构与页面清单](./managers/information-architecture.md)
- [接口设计](./managers/api-design.md)
- [前端界面布局](./managers/frontend-layout.md)
- [数据来源与权限策略](./managers/data-and-permissions.md)
- [后端实现方案](./managers/backend-implementation.md)
- [实施路线与验收清单](./managers/implementation-roadmap.md)

## 建议阅读路线

- 想先把项目跑起来：
  - 从 [上手指南](./getting-started/README.md) 开始，再看 [配置说明](./getting-started/configuration.md)
- 想知道消息是怎么流转的：
  - 先看 [消息处理流程](./guides/message-processing-flow.md)，再看 [架构视图总览](./architecture/architecture-views.md)
- 想接入消息采集、群历史检索或用户聊天落盘：
  - 先看 [消息历史存储与归属说明](./guides/message-history-storage.md)
- 想做命令、权限或 Agent 相关开发：
  - 先看 [命令鉴权与 Help/AutoGPT 统一机制](./guides/command-auth-and-help.md)
  - 再看 [命令与 Agent 一体化架构设计](./architecture/command-agent-unified-architecture.md)
- 想推进 Agent、Tool、Skill、MCP、RAG 或 Prompt 工程化：
  - 先看 [Agent 工程化研发手册](./guides/agent-engineering-playbook.md)，再按需回到 [AutoGPT 智能能力改进方案](./guides/agent-module.md)
  - 如果要先统一“仓库契约 + 运行时分层 + 观测恢复边界”，再看 [Harness Engineering 架构蓝图](./architecture/harness-engineering-architecture.md)
- 想做 Skill、文件处理或图片处理能力：
  - 先看 [Skill 系统说明](./guides/skill-system.md)
- 想推进本地管理后台：
  - 从 [本地管理后台文档](./managers/README.md) 进入专题

兼容说明：

- `docs/architecture/current-system-architecture-design.md`
- `docs/architecture/current-system-integration.md`
- `docs/architecture/target-ai-architecture.md`
- `docs/architecture/technology-decisions.md`

以上四篇为了兼容历史链接仍然保留，但不再作为主阅读入口。

## 新增文档放置规则

- 启动方式、环境配置、目录理解、阅读顺序，放到 `getting-started/`
- 开发步骤、接入流程、技能规范、实操指南，放到 `guides/`
- 能力清单、命令说明、角色定义、稳定约束，放到 `reference/`
- 架构设计、技术选型、演进路线、多服务拆分，放到 `architecture/`
- 对外接口与版本说明，放到 `api/`
- 本地管理后台的范围、页面、接口、权限、前端布局和落地路线，放到 `managers/`
- `docs/` 根目录尽量只保留总入口，不再直接新增专题型 Markdown

## 命名与维护规范

- 文件名统一使用英文 `kebab-case`
- 文档标题保持中文，优先让阅读者一眼看懂主题
- 一篇文档尽量只讲一个主题，避免把“上手、架构、参考”混写在一起
- 新增文档时，记得同步更新对应目录下的 `README.md` 与本页导航
