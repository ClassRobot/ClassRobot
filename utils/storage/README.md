# 隔离文件空间

`utils.storage` 提供和 NoneBot 解耦的文件空间能力，用于把个人用户、群组、公共系统文件隔离到 `{data_dir}/storage` 下。

## 基础结构

```text
{data_dir}/storage/
├── public/
├── groups/{group_id}/
│   ├── chat/
│   └── home/
│       ├── documents/
│       ├── videos/
│       ├── images/
│       └── audio/
└── users/{user_id}/
    ├── chat/
    └── home/
        ├── documents/
        ├── videos/
        ├── images/
        └── audio/
```

## 聊天记录约定

`chat` 目录不仅保存运行时状态，也用于承载消息历史数据库：

- 系统群环境采集消息：
  - `storage/groups/{system_group_id}/chat/messages.db`
- 用户聊天消息：
  - `storage/users/{user_id}/chat/messages.db`
- 机器人回复消息：
  - 按回复目标落到对应的 `groups/{system_group_id}` 或 `users/{user_id}` 空间

这里的 `system_group_id` 指系统内 `Group.id`，不是平台原始群号。

当前统一消息表为 `messages`，并通过 `record_kind` 和 `direction` 区分：

- `collect`
  - 系统群环境采集消息
- `chat`
  - 人机聊天消息，包括私聊聊天、命令回复和群内机器人回复
- `inbound`
  - 用户或平台发给机器人的消息
- `outbound`
  - 机器人发出的消息

这样做的目的，是让 Agent 和后续开发能直接知道：

- 要看群环境上下文，就去系统群空间读 `collect`
- 要看人机聊天流，就读对应空间的 `chat`
- 要区分用户输入和机器人输出，就过滤 `direction`

## 使用方式

```python
from utils.storage import storage_manager

space = storage_manager.user_space(user.id)
space.mkdir("documents/project")
space.cd("documents/project")
space.touch("readme.txt")
display, entries = space.list_entries()
```

## 安全规则

- `home` 是用户可访问根目录，对外展示为 `~`。
- `chat` 用于会话记录和运行状态，不会被文件命令当作用户路径暴露。
- 所有用户输入路径都会被拆分并重新拼接到当前 `home` 下。
- `ls ../../other/home`、`rm ../../other/home` 等越界查询或删除会抛出 `PathEscapeError`。
- `cd ..` 在 `~` 下不会越界，只会停留在 `~`。
- `documents`、`videos`、`images`、`audio` 是默认分类目录，不能直接删除，但可以管理其内部文件。

## 扩展建议

- 后续聊天记录落盘时，应优先写入 `space.chat_dir`，不要混入 `home`。
- 后台管理或 Agent 工具需要访问文件时，应复用 `StorageManager` / `FileSpace`，不要自行拼接路径。
- 如果新增文件类型分类，只需要调整 `DEFAULT_HOME_DIRS`，新空间初始化时会自动创建目录。
- 如果新增消息历史能力，优先复用 `utils.storage.chat_history.ChatHistoryStore`，不要自行创建新的 SQLite 结构。
- 需要读取消息历史字段含义时，可参考 `docs/guides/message-history-storage.md`。
