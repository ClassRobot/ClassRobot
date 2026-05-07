# AI 架构专题

> 核验日期：2026-05-05

## 目标

本专题用于定义 ClassRobot 下一阶段的 AI 原生架构目标态。它不受当前 `NoneBot + 插件 + AutoGPT` 实现边界限制，但会尽量复用仓库里已经存在的 `src/agents/skills/`、`utils/llm/agents/`、帮助系统、OCR/文档解析等资产。

说明：如果其他较早文档仍提到 `skills/` 或 `utils/skills/`，请分别映射到 `src/agents/skills/builtin/` 与 `src/agents/skills/`。

这套方案追求的是“前沿但可靠”：

- 优先采用主流官方协议与能力边界，而不是一次性堆功能
- 优先可恢复、可审计、可观测、可评测的工作流
- 优先领域能力内聚，再让 Agent 调用领域能力
- 优先统一 Tool 和 MCP 协议，再扩展多 Agent 和外部互联

## 文档导航

### 主读文档

- [Harness Engineering 架构蓝图](./harness-engineering-architecture.md)
  - 适合先理解“为什么项目要从做功能，升级到做 harness”，以及 Harness 分层如何映射到当前仓库
- [架构视图总览](./architecture-views.md)
  - 适合先快速建立“系统边界、分层和运行流程”的整体图景
- [统一 AI 平台架构总纲](./unified-ai-platform-handbook.md)
  - 适合统一 Domain、Tool、Skill、Agent、RAG、MCP、Workflow 等概念边界
- [Agent 工作流编排架构](./agent-workflow-orchestration.md)
  - 适合理解 AutoGPT 为什么正在演进成显式工作流
- [命令与 Agent 一体化架构设计](./command-agent-unified-architecture.md)
  - 适合理解命令系统、`Helper`、统一执行器和 Agent 工具目录如何收敛
- [迁移路线图](./migration-roadmap.md)
  - 适合安排阶段性重构顺序
- [软件工程流程方案](./software-engineering-process.md)
  - 适合建立长期开发、测试、发布和治理规范

### 兼容页

下面几篇文档为了兼容历史链接仍然保留，但其内容已经被主读文档拆分吸收：

- [当前系统架构设计](./current-system-architecture-design.md)
- [当前系统整合图映射](./current-system-integration.md)
- [目标架构蓝图](./target-ai-architecture.md)
- [技术决策与工程规范](./technology-decisions.md)

## 适用范围

本专题覆盖以下内容：

- 机器人多渠道接入
- AI Agent 编排与工作流
- Skill、Tool、MCP 的职责边界
- RAG 与知识库建设
- 面向校园信息化场景的领域服务拆分方式
- 安全、审批、审计、评测与观测

本专题不直接展开以下细节：

- 单个插件的命令语法设计
- 具体学校业务系统适配逻辑
- 前端后台页面的视觉设计

## 前沿且可靠的判断标准

当一个方案同时满足以下条件时，才视为本项目的推荐路线：

- 能对应到公开、主流、仍在演进中的官方标准或官方文档
- 能支撑持久化工作流，而不是只靠一次模型调用完成业务
- 能区分知识检索、工具执行、业务写操作和权限审批
- 能让外部 Agent 通过标准协议接入，或把本系统能力对外暴露
- 能逐步演进，而不是一开始就被迫拆成重型微服务

## 官方资料依据

以下资料用于校验本专题中的关键设计方向：

- [Model Context Protocol: Architecture](https://modelcontextprotocol.io/docs/learn/architecture)
- [Model Context Protocol: Build with agent skills](https://modelcontextprotocol.io/docs/develop/build-with-agent-skills)
- [OpenAI API Docs: Tools](https://platform.openai.com/docs/guides/tools)
- [OpenAI API Docs: Models](https://developers.openai.com/api/docs/models)
- [OpenAI: Harness engineering](https://openai.com/index/harness-engineering/)
- [OpenAI: Symphony](https://openai.com/index/open-source-codex-orchestration-symphony/)
- [OpenAI Symphony SPEC](https://github.com/openai/symphony/blob/main/SPEC.md)
- [LangGraph Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph Durable Execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)
- [RAGFlow Official Site](https://ragflow.io/)
- [RAGFlow Official GitHub](https://github.com/infiniflow/ragflow)
- [OpenClaw Gateway architecture](https://docs.openclaw.ai/concepts/architecture)
- [OpenClaw Agent runtime](https://docs.openclaw.ai/concepts/agent)
- [OpenClaw Context Engine](https://docs.openclaw.ai/concepts/context-engine)
- [OpenClaw Memory Overview](https://docs.openclaw.ai/concepts/memory)
- [OpenClaw Delegate Architecture](https://docs.openclaw.ai/concepts/delegate-architecture)

## 阅读建议

- 如果你想先通过图理解“系统边界、分层、领域关系和运行时流程”，先读“架构视图总览”
- 如果你想理解当前 Agent 为什么要走“显式工作流 + NoneBot2 命令复用”的路线，先读“Agent 工作流编排架构”
- 如果你想理解为什么后续要把 Agent、Prompt、Skill、RAG 和测试一起收敛成 Harness，先读“Harness Engineering 架构蓝图”
- 如果你想理解命令系统为什么要和 Agent 工具目录、统一执行器收敛到同一套元数据，先读“命令与 Agent 一体化架构设计”
- 如果你现在概念很多、思路很乱，先读“统一 AI 平台架构总纲”
- 如果你要安排真实开发顺序，接着读“迁移路线图”
- 如果你要把团队协作、测试、发布和运维流程落地，再读“软件工程流程方案”
