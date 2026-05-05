# 开发指南

本目录面向正在开发、重构或扩展系统的协作者，重点收录“怎么做”和“按什么规范做”的文档。

## 当前收录

- [Skill 系统说明](./skill-system.md)
  - 说明 skill 的目录规范、自动加载机制、手动注册方式和开发者接入步骤
- [消息处理流程](./message-processing-flow.md)
  - 说明平台消息如何进入系统，并流经权限、流水线、Agent、RAG 与技能层
- [命令鉴权与 Help/AutoGPT 统一机制](./command-auth-and-help.md)
  - 说明 `Helper` 元数据如何统一驱动命令鉴权、帮助目录和 AutoGPT 可见命令集
- [AutoGPT 智能能力改进方案](./agent-module.md)
  - 说明 `autogpt` 的设计目的、当前流程、问题点与后续 Agent 化改造路线
  - 同时记录当前已落地的显式工作流层和 NoneBot2 融合方式
- [Agent Playbook 与确认执行](./agent-playbooks.md)
  - 说明工作流模板如何命中、待确认工作流如何恢复，以及为什么继续复用 NoneBot2 命令体系

## 适合放在这里的文档

- 新能力如何接入
- Agent、Skill、Tool、MCP、RAG 的实操流程
- 平台适配、消息编排、任务处理、异步回调等过程型说明
- 面向开发者的规范、步骤、最佳实践

## 阅读建议

- 要扩展能力边界，先读 [Skill 系统说明](./skill-system.md)
- 要理解请求在系统中怎么流动，先读 [消息处理流程](./message-processing-flow.md)
- 要扩展命令、权限或帮助目录，先读 [命令鉴权与 Help/AutoGPT 统一机制](./command-auth-and-help.md)
- 如果你要进一步重构命令系统与 Agent 共用能力内核，再读 [命令与 Agent 一体化架构设计](../architecture/command-agent-unified-architecture.md)
- 要开发或调整智能能力，先读 [AutoGPT 智能能力改进方案](./agent-module.md)
- 要理解工作流模板和确认恢复机制，接着读 [Agent Playbook 与确认执行](./agent-playbooks.md)
- 要进一步看架构层面的边界与演进路线，再进入 [架构专题](../architecture/README.md)
