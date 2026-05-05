# Agent 目录说明

`src/agents/` 用来承载项目里与 AI Agent 直接相关、但又不属于 NoneBot 命令入口本身的通用能力。

这里更强调“能力边界”和“运行时入口”，而不是平台消息接入。平台侧对话编排仍然主要在 `src/plugins/autogpt/`。

当前约定如下：

- `src/agents/skills/`
  - Skill 体系的标准入口，包含注册表、运行时绑定和内置 skill 清单
- `src/agents/skills/builtin/`
  - 内置 skill 元数据与运行时模块
- `src/plugins/autogpt/`
  - NoneBot 侧的 Agent 编排入口与工作流执行链路

这样放置的目的有两个：

1. 让 Agent 领域代码集中，而不是散落在仓库根目录和 `utils/` 下。
2. 保持“接入层”和“Agent 能力层”分离，后续继续扩展时更容易维护。

## 建议阅读

- 如果你想理解 Skill 规范：看 [Skill 系统说明](../../docs/guides/skill-system.md)
- 如果你想理解 Agent 主链路：看 [AutoGPT 模块说明](../plugins/autogpt/README.md)
- 如果你想理解整体架构边界：看 [架构视图总览](../../docs/architecture/architecture-views.md)
