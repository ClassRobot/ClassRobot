# Storage 核心入口

`core.storage` 是聊天记录、本地文件空间和本地 RAG 的 canonical import。

## 主要能力

- `ChatHistoryStore`
  - 用户人机聊天、群聊采集记录、统计与检索。
- `StorageManager`
  - 用户/群文件空间。
- `LocalRagService`
  - 本地语义索引与召回。

## 隐私边界

- 私聊历史只能属于当前系统用户空间。
- 群消息只能属于当前系统群空间。
- 不允许越级读取其他用户聊天记录。
- 文件空间必须用系统实体 ID 做所有权，不允许直接用平台 ID 作为存储根。

