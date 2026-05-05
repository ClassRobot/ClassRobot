# 机器人系统功能插件

`src/plugins/` 是面向最终用户的主功能入口目录，主要承载 NoneBot matcher、消息入口和围绕聊天平台展开的功能编排。

## 当前目录

- `autogpt/`
  - 自然语言入口、消息流水线、显式工作流与命令调度
- `curriculum/`
  - 课表相关能力
- `helper/`
  - `help` 命令与帮助系统入口
- `leave/`
  - 请假相关能力
- `notice/`
  - 通知相关能力
- `tasks/`
  - 任务与作业相关能力
- `find_at/`
  - 群内检索与 `at` 协作能力
- `file_manager/`
  - 文件管理相关能力

## 维护约定

- 用户直接交互的命令入口优先放这里
- 业务规则不要全部堆在 matcher 中，应该尽量下沉到 `src/managers/`、service 层或共享模块
- AI 编排相关入口统一收敛到 `src/plugins/autogpt/`

## 关联文档

- 消息流：[消息处理流程](../../docs/guides/message-processing-flow.md)
- 命令与 Agent 收敛：[命令与 Agent 一体化架构设计](../../docs/architecture/command-agent-unified-architecture.md)
