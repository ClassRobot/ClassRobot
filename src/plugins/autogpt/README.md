# AutoGPT 兼容入口

这个目录现在只保留 NoneBot 插件入口与旧导入兼容桥。

- 新的运行时实现：`core/agent/runtime/`
- 运行时开发文档：`core/agent/runtime/README.md`
- Agent 继承标准：`core/agent/README.md`

新代码不要再从 `src.plugins.autogpt.*` 非入口模块导入运行时实现。
