# Skill 资源目录

`resources/skills/` 用来存放 Skill 的资源化定义文件，也就是给 Agent 和注册表读取的 `SKILL.md`。

这里放的是：

- Skill 名称
- Skill 描述
- 面向 Agent 或开发者的使用说明

这里不放的是：

- Python 运行时代码
- 第三方 SDK 调用逻辑
- 临时调试脚本

## 目录约定

- `resources/skills/<skill-name>/SKILL.md`
  - Skill 的资源定义文件。
- `core/skills/builtin/<skill-name>/runtime.py`
  - Skill 的运行时代码入口。

## 维护规则

- 新增 Skill 时，先写 `resources/skills/<name>/SKILL.md`，再决定是否需要 `runtime.py`。
- Skill 资源和 Skill 代码要分层维护，不要再把 `SKILL.md` 放回 `core/skills/builtin/`。
- 如果一个 Skill 只有定义、暂时没有运行时代码，也允许只保留 `SKILL.md`。
