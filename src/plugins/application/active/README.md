# active 主动应用插件

`active` 放用户主动触发的应用插件，最常见入口是命令。

## 放什么

- `on_agent_command`、`on_alconna`、`on_command` 等命令入口。
- 用户主动调用的班级、用户、教师、学生、文件、课表、请假等业务。
- Agent 可以调用的 service-style 命令入口。
- 查询消息历史、统计聊天记录等用户主动发起的历史能力。

## 不放什么

- 只负责采集、监听、注入的底层能力。
- 跨平台发送、命令注册框架、会话解析框架。

## 例子

```text
active/
├── user/
├── classes/
├── file_manager/
├── message_history/
├── notice/
└── autogpt/
```
