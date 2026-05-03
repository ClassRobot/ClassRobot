# Agent 目录说明

`src/agents/` 用来承载项目里与 AI Agent 直接相关、但又不属于 NoneBot 命令入口本身的通用能力。

当前约定如下：

- `src/agents/skills/`: Skill 体系的标准入口，包含注册表、运行时绑定和内置 skill 清单
- `src/plugins/autogpt/`: NoneBot 侧的 Agent 编排入口与工作流执行链路

这样放置的目的有两个：

1. 让 Agent 领域代码集中，而不是散落在仓库根目录和 `utils/` 下。
2. 保持“接入层”和“Agent 能力层”分离，后续继续扩展时更容易维护。
