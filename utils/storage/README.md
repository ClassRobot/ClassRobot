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
