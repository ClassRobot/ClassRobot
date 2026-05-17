# ClassRobot
[![Unit Tests](https://github.com/ClassRobot/ClassRobot/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/ClassRobot/ClassRobot/actions/workflows/unit-tests.yml)

## 项目简介

ClassRobot 是一个面向校园、班级与组织管理场景的智能机器人系统。当前工程以 NoneBot2 作为用户侧消息入口，并逐步把命令系统、Agent 编排、Skill 能力、RAG 检索、本地存储和管理后台收敛到同一套架构边界中。

这套系统的目标不是简单堆叠几个聊天命令，而是把“身份、组织、班级、课表、作业、文件、消息记录、AI 编排”这些长期会演进的能力，整理成可维护、可测试、可扩展的工程体系。

## 你会在仓库里看到什么

- `src/features/`
  - 用户侧 NoneBot 功能入口，负责命令声明、事件接入和轻量参数接线。
- `src/interfaces/http/`
  - HTTP 接口入口与本地管理后台 API。
- `core/`
  - Agent、LLM、Storage、Skill 等系统级核心能力。
- `utils/`
  - 配置、ORM 模型、命令封装、帮助系统与共享工具。
- `resources/`
  - Prompt、模板、模型资源和 Agent 编排资源。
- `docs/`
  - 项目文档中心。

## 推荐阅读顺序

如果你第一次接手这个仓库，建议按下面的顺序阅读：

1. [文档中心](./docs/README.md)
2. [配置说明](./docs/getting-started/configuration.md)
3. [项目结构说明](./docs/getting-started/project-structure.md)
4. [消息处理流程](./docs/guides/message-processing-flow.md)
5. [架构视图总览](./docs/architecture/architecture-views.md)

如果你已经准备开始开发：

- 命令与权限开发：看 [开发指南](./docs/guides/README.md) 和 [命令统一封装说明](./utils/commands/README.md)
- Agent 与工作流开发：看 [AI 架构专题](./docs/architecture/README.md)
- 管理后台开发：看 [本地管理后台文档](./docs/managers/README.md)

## 文档入口

- [文档中心](./docs/README.md)
- [快速上手](./docs/getting-started/README.md)
- [开发指南](./docs/guides/README.md)
- [架构专题](./docs/architecture/README.md)
- [参考资料](./docs/reference/README.md)
- [管理后台](./docs/managers/README.md)
