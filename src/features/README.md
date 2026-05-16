# Features 入口层说明

`src.features` 表示用户侧薄入口层的目标结构。

这里的职责应该只有：

- NoneBot matcher / command 入口
- 参数收集
- 权限边界
- 把请求交给 `core` 中的统一能力
- 返回结果给用户

不应该做的事：

- 堆放复杂业务规则
- 直接操作底层存储细节
- 复制 Agent / Runtime / LLM / Storage 的封装逻辑

当前仓库里仍有部分历史功能保留在 `src.managers`、`src.plugins`、`src.others`。新功能设计时，优先遵循这里的薄入口标准，再逐步迁移旧目录。

