# 班级机器人
[![Unit Tests](https://github.com/ClassRobot/ClassRobot/actions/workflows/unit-tests.yml/badge.svg)](https://github.com/ClassRobot/ClassRobot/actions/workflows/unit-tests.yml)

## 项目简介

ClassRobot 是一个面向校园与班级场景的机器人系统，当前以 NoneBot 为运行入口，逐步融合命令系统、Agent 编排、Skill 能力、RAG 检索和本地管理后台。

它的目标不只是“做几个聊天命令”，而是把班级管理、作业与课表、身份与组织关系、文档处理、图像生成和 AI 编排收敛到一套更稳定的工程边界里。

## 项目结构

- `src/`: NoneBot 插件与路由
- `utils/`: 共享配置、模型、LLM 和工具能力
- `src/agents/skills/`: Agent Skill 的标准入口与内置能力目录
- `resources/`: prompts、HTML 模板、OCR 模型等非源码资源
- `scripts/`: 辅助脚本
- `migrations/`: 数据库迁移
- `docs/`: 说明文档

## 文档入口

- 项目总入口：`docs/README.md`
- 快速上手：`docs/getting-started/README.md`
- 开发与扩展：`docs/guides/README.md`
- 架构设计：`docs/architecture/README.md`
- 本地管理后台：`docs/managers/README.md`

如果你是第一次接手仓库，推荐先读：

1. `docs/getting-started/project-structure.md`
2. `docs/getting-started/configuration.md`
3. `docs/guides/message-processing-flow.md`
4. `docs/architecture/architecture-views.md`
