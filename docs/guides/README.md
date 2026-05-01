# 开发指南

本目录面向正在开发、重构或扩展系统的协作者，重点收录“怎么做”和“按什么规范做”的文档。

## 当前收录

- [Skill 系统说明](./skill-system.md)
  - 说明 skill 的目录规范、自动加载机制、手动注册方式和开发者接入步骤
- [消息处理流程](./message-processing-flow.md)
  - 说明平台消息如何进入系统，并流经权限、流水线、Agent、RAG 与技能层
- [AutoGPT 智能能力改进方案](./agent-module.md)
  - 说明 `autogpt` 的设计目的、当前流程、问题点与后续 Agent 化改造路线

## 适合放在这里的文档

- 新能力如何接入
- Agent、Skill、Tool、MCP、RAG 的实操流程
- 平台适配、消息编排、任务处理、异步回调等过程型说明
- 面向开发者的规范、步骤、最佳实践

## 阅读建议

- 要扩展能力边界，先读 [Skill 系统说明](./skill-system.md)
- 要理解请求在系统中怎么流动，先读 [消息处理流程](./message-processing-flow.md)
- 要开发或调整智能能力，先读 [AutoGPT 智能能力改进方案](./agent-module.md)
- 要进一步看架构层面的边界与演进路线，再进入 [架构专题](../architecture/README.md)
