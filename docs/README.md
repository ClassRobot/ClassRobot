# 文档中心

`docs/` 现在按“上手、指南、参考、架构、API”分层组织，根目录只保留总入口，避免专题文档继续堆在同一层。

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

## 快速导航

### 上手指南

- [上手指南总览](./getting-started/README.md)
- [配置说明](./getting-started/configuration.md)
- [项目结构说明](./getting-started/project-structure.md)

### 开发指南

- [开发指南总览](./guides/README.md)
- [Skill 系统说明](./guides/skill-system.md)
- [消息处理流程](./guides/message-processing-flow.md)
- [AutoGPT 智能能力改进方案](./guides/agent-module.md)
- [Agent Playbook 与确认执行](./guides/agent-playbooks.md)

### 参考资料

- [参考资料总览](./reference/README.md)
- [项目能力总览](./reference/capability-overview.md)
- [命令使用文档](./reference/command-reference.md)
- [角色与组织关系说明](./reference/role-reference.md)

### 架构专题

- [AI 架构专题](./architecture/README.md)
- [架构视图总览](./architecture/architecture-views.md)
- [Agent 工作流编排架构](./architecture/agent-workflow-orchestration.md)
- [统一 AI 平台架构总纲](./architecture/unified-ai-platform-handbook.md)
- [当前系统架构设计](./architecture/current-system-architecture-design.md)
- [当前系统整合图映射](./architecture/current-system-integration.md)
- [目标架构蓝图](./architecture/target-ai-architecture.md)
- [技术决策与工程规范](./architecture/technology-decisions.md)
- [迁移路线图](./architecture/migration-roadmap.md)
- [软件工程流程方案](./architecture/software-engineering-process.md)

### API

- [API 文档总览](./api/README.md)
- [API V1](./api/v1.md)

## 新增文档放置规则

- 启动方式、环境配置、目录理解、阅读顺序，放到 `getting-started/`
- 开发步骤、接入流程、技能规范、实操指南，放到 `guides/`
- 能力清单、命令说明、角色定义、稳定约束，放到 `reference/`
- 架构设计、技术选型、演进路线、多服务拆分，放到 `architecture/`
- 对外接口与版本说明，放到 `api/`
- `docs/` 根目录尽量只保留总入口，不再直接新增专题型 Markdown

## 命名与维护规范

- 文件名统一使用英文 `kebab-case`
- 文档标题保持中文，优先让阅读者一眼看懂主题
- 一篇文档尽量只讲一个主题，避免把“上手、架构、参考”混写在一起
- 新增文档时，记得同步更新对应目录下的 `README.md` 与本页导航
