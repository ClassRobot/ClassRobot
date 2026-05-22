# application 应用插件

`application` 放用户能直接感知的业务插件。它们通常提供命令、菜单、交互流程或自动业务动作。

```text
application/
├── active/    # 用户主动触发，例如命令
└── passive/   # 系统自动触发，但仍属于用户业务
```

## active 与 passive

| 类型 | 判断标准 | 例子 |
| --- | --- | --- |
| `active` | 用户主动发命令或明确触发 | 班级、请假、文件管理、帮助、AutoGPT |
| `passive` | 系统自动触发，用户能感知结果 | 自动欢迎、自动提醒、自动通知分发 |

## 放什么

- 面向用户的命令声明和交互入口。
- 调用 `platform`、`core`、`models` 或 `plugins/library` 的业务编排。
- 该业务自己的权限、展示、参数模型和 README。

## 不放什么

- 跨平台发送底层实现。
- 可被多个插件复用的消息采集、身份注入、文件空间解析等能力。
- 不依赖业务的通用工具。

## 常用内部结构

```text
<plugin>/
├── __init__.py
├── README.md
├── commands.py 或 commands/
├── services.py 或 services/
├── permissions.py
├── schemas.py
├── resolvers.py
└── presenters.py
```

命令开发细节由 `platform/commands/README.md` 说明，具体业务命令由插件自己的 README 说明。
