# Skill 核心入口

`core.skills` 是项目 Skill 运行时的 canonical import。

当前运行时仍复用既有 Skill 实现和注册逻辑，但开发新功能时应优先从这里导入 `skill_registry` 或具体 Skill，而不是继续扩散到多个历史路径。

## 边界

- Skill
  - 描述一个相对独立、可被 Agent 选择的能力。
- Agent
  - 负责规划、调用 Skill、整合结果。
- WorkflowNode
  - 决定什么时候让 Agent 或 Skill 出场。

不要把 Skill 直接写成 Agent，也不要把 Skill 目录当成 Runtime 节点。

## 当前约定

- 运行时代码通过 `core.skills` 导入。
- Skill 元数据和运行时代码目前仍沿用现有项目结构。
- 后续如果迁移到 `resources/skills`，应先保证 `skill_registry` 和 `utils.config.skills_dir` 的统一入口不变。

