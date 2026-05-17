# 上手指南

本目录面向第一次接手项目、第一次配置环境，或准备开始读代码的开发者。它的重点不是讲“所有细节”，而是帮你尽快建立运行环境、目录认知和阅读顺序。

## 建议阅读顺序

1. [配置说明](./configuration.md)
2. [项目结构说明](./project-structure.md)
3. [架构视图总览](../architecture/architecture-views.md)
4. [消息处理流程](../guides/message-processing-flow.md)
5. [项目能力总览](../reference/capability-overview.md)

## 当前收录

- [配置说明](./configuration.md)
  - 说明 `.env` 中各个参数如何填写、哪些必须、哪些按需启用
- [项目结构说明](./project-structure.md)
  - 说明源码、资源、skill、工具层与文档层应该如何摆放
- [架构视图总览](../architecture/architecture-views.md)
  - 用多张 Mermaid 图说明系统边界、模块分层、领域关系和运行时流程

## 适合谁先读

- 想把项目跑起来的人
- 想快速看懂当前目录结构的人
- 想在开始开发前先建立整体心智模型的人

## 放置建议

- 与“跑起来”直接相关的文档优先放这里
- 与“项目结构认知”直接相关的文档优先放这里
- 如果内容更偏开发步骤、接入流程、扩展规范，应放到 `docs/guides/`
- 如果内容更偏稳定事实、清单或手册，应放到 `docs/reference/`
