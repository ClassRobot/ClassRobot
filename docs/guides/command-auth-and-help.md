# 命令鉴权与 Help/AutoGPT 统一机制

本文说明当前项目里“命令能不能用、`help` 怎么展示、AutoGPT 能看到什么命令”是如何统一起来的，便于后续继续扩展而不把权限逻辑写散。

## 设计目标

- 命令的帮助文档、展示目录、可用角色、AI 提示使用同一份元数据维护
- `help` 只展示当前用户真正可用的命令
- AutoGPT 只拿到当前用户真正可调用的命令目录
- 真实命令执行前仍要做运行时鉴权，不能只靠前端展示或 AI 规划阶段限制
- 新增命令时，开发者只需要补齐一份 `Helper` 元数据即可接入整套机制

## 核心链路

当前链路统一由 `Helper` 元数据驱动：

1. 各命令模块在 `__helpers__` 中声明命令说明
2. `src/plugins/helper/__init__.py` 在启动时调用 `bootstrap_helper_runtime(...)`
3. `utils/helper/runtime.py` 会做两件事
   - 汇总所有 `__helpers__` 到全局 `helper_menu`
   - 把对应 helper 绑定到 matcher 前置鉴权 handler
4. `utils/helper/depends.py` 根据 `user.roles` 过滤出当前用户可见的 `Helpers`
5. `help` 命令、AutoGPT 命令目录、后续 helper agent 都应基于这份“已过滤”的 `Helpers` 工作

可以把它理解成：

- `Helper` = 单条命令的事实来源
- `HelpersDepends` = 当前用户视角下的可见命令集
- `bind_helper_access_guard` = 最后一道真实执行闸门

## `Helper` 字段语义

定义位置：`utils/helper/schema.py`

### `roles`

- 表示“允许哪些角色使用”
- 语义是“命中任一角色即可”，不是“必须同时拥有全部角色”
- 例如：
  - `{student, teacher}` 表示学生或教师都能用
  - 不是要求用户同时既是学生又是教师

### `exclude_roles`

- 表示“这些角色即使命中 `roles` 也要额外禁止”
- 典型场景：
  - `roles={user, teacher}`
  - `exclude_roles={student}`
  - 用于表达“普通用户可以先创建教师身份，但学生不能走这条路径”

### `scopes`

- 表示该命令在帮助菜单里归属哪个目录
- 当前目录枚举：
  - `public`
  - `user`
  - `student`
  - `teacher`
  - `admin`

若不显式填写，系统会根据 `roles` 自动推断目录。

## `help` 分组展示规则

`help` 现在不是简单把所有命令列出来，而是按“当前用户真正可见的目录”分组：

- 公共命令：任何人都可直接使用
- 普通用户命令：账号级通用能力，学生/教师会继承
- 学生身份命令：学生当前可用，或普通用户可走的学生身份入口
- 教师身份命令：教师当前可用，或普通用户可走的教师身份入口
- 管理员命令：仅管理员可用

特别注意：

- 学生和教师都能用的命令，不会再在单一身份下同时展示到两个目录
- 例如“查询请假”如果学生和教师都可用：
  - 学生看到它时，会出现在“学生身份命令”
  - 教师看到它时，会出现在“教师身份命令”
- 普通用户仍然可以看到“加入班级”“修改教师信息”这类身份入口命令

对应实现：

- `Helper.is_available_for(...)`
- `Helper.visible_scopes_for(...)`
- `Helpers.group_by_scopes(...)`

## AutoGPT 如何复用同一套权限

AutoGPT 不再直接读取全量命令目录，而是依赖当前用户视角下的 `Helpers`：

- `src/plugins/autogpt/util.py`
  - `get_chat_session(...)` 会接收 `HelpersDepends`
- `src/plugins/autogpt/pipeline.py`
  - `MessageProcessingPipeline` 用当前用户 helpers 构建 `CommandToolCatalog`
- `src/plugins/autogpt/command_tools.py`
  - 只把当前 helpers 转成 Agent 可见的命令工具

因此：

- `help` 看不到的命令，AutoGPT 也不应该规划出来
- 即使模型仍然产出越权命令，`ValidateAutoTasksNode` 和 matcher 前置 guard 也会继续兜底

## 新增命令时的开发清单

新增一个命令时，建议按下面顺序做：

1. 在 `commands.py` 中定义 matcher
2. 同模块补一条 `Helper(...)` 到 `__helpers__`
3. 明确填写
   - `command`
   - `description`
   - `aliases`
   - `params`
   - `roles`
   - `exclude_roles`（如果需要）
   - `scopes`
   - `ai_description`（如果给 AutoGPT 额外约束会更稳）
4. 确认 helper 描述与真实 matcher 行为一致
5. 如果命令内部还存在业务侧身份判断，优先基于 `user.student` / `user.teacher` 或 `user.roles` 判断，不要继续依赖单值 `user.role`
6. 补单元测试

## 关于 `user.role` 与 `user.roles`

当前项目历史上同时存在：

- `user.role`：单值角色字段
- `user.roles`：根据用户绑定关系推导出来的真实角色集合

新的命令展示与鉴权逻辑应优先使用 `user.roles`。

原因：

- 一个用户可能同时具备多个身份
- 单值 `user.role` 无法准确表达“学生 + 班干部”或“教师 + 管理员”这类组合
- `help`、AutoGPT、统一鉴权 guard 都是围绕 `user.roles` 工作的

`user.role` 目前仍保留主要是兼容历史数据和旧代码，不建议再作为新增逻辑的唯一依据。

## 关键文件

- `utils/helper/schema.py`
- `utils/helper/runtime.py`
- `utils/helper/depends.py`
- `src/plugins/helper/__init__.py`
- `src/plugins/autogpt/command_tools.py`
- `src/plugins/autogpt/pipeline.py`
- `src/plugins/autogpt/util.py`

## 参考资料

- [NoneBot2 官方文档](https://nonebot.dev/)
- [NoneBot Alconna Matcher 最佳实践](https://nonebot.dev/docs/next/best-practice/alconna/matcher)
