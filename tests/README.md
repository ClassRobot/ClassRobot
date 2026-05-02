# Tests

测试目录按功能领域组织，避免不同层级的测试混在一起。

- `autogpt/`: AutoGPT 编排、命令工具目录、进度提示、会话 observation 等测试。
- `commands/`: 机器人基础命令的元数据、Helper 注册、别名、命令纯逻辑测试。
- `commands/classes/`: 班级命令相关的纯逻辑测试。
- `conftest.py`: nonebug / NoneBot 测试初始化和项目插件加载 fixture。

原则：

- 命令测试只验证命令自身、Helper 元数据和命令纯逻辑。
- AutoGPT 测试验证 Agent 如何消费命令能力，例如 `CommandToolCatalog`。
- 需要真实 matcher 行为时再使用 nonebug 场景测试，避免普通单元测试依赖真实平台事件。
