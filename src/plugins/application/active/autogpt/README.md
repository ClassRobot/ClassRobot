# AutoGPT 用户侧入口

这个目录只保留 NoneBot 插件入口、会话接线和消息发送逻辑。

- 新的运行时实现：`src/core/agent/runtime/`
- 运行时开发文档：`src/core/agent/runtime/README.md`
- Agent 继承标准：`src/core/agent/README.md`

新代码如果要修改 AutoGPT 运行时，请直接进入 `src.core.agent.runtime` 对应模块；不要在这个入口目录中堆积运行时实现。
