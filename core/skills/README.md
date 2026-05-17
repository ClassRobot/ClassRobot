# Skill 核心入口

`core.skills` 是项目 Skill 运行时的统一入口。无论是 Agent、管理后台还是命令侧，只要需要读取 Skill 元数据、加载 Skill 运行时或访问注册表，都应从这里进入，而不是在业务层直接扫描目录。

## 先理解三个概念

- `Skill`
  - 一个相对独立、可被 Agent 选择和调用的能力单元。
- `Agent`
  - 负责理解目标、选择 Skill、调用命令并整合结果。
- `WorkflowNode`
  - 负责决定某个阶段该让 Agent 思考、让 Skill 执行，还是让命令系统处理。

这三者分工不同，不要把 Skill 写成 Agent，也不要把 Skill 目录误当成工作流节点目录。

## 当前约定

- 统一导入入口：`core.skills`
- Skill 元数据：`core/skills/builtin/<name>/SKILL.md`
- Skill 运行时：`core/skills/builtin/<name>/runtime.py`
- 注册与发现：通过 `skill_registry` 统一完成

## 维护建议

- 新增 Skill 时，先补 `SKILL.md`，再决定是否需要 `runtime.py`
- 业务模块不要自行维护第二套 Skill 扫描逻辑
- 如果未来需要迁移 Skill 资源目录，优先保持统一导入入口不变，再迁移物理路径
