# 班级模块

`src/features/classes/` 负责和班级主归属直接相关的命令与流程，例如创建班级、加入班级、退出班级、入班申请与班级导入。

## 目录职责

- `commands.py`
  - 命令声明、参数定义、帮助元数据
- `__init__.py`
  - matcher 入口、交互编排和消息回复
- `services.py`
  - 班级查询、状态校验、申请处理等复用逻辑
- `presenters.py`
  - 列表、详情和确认文案渲染
- `depends.py`
  - 班级相关的依赖注入
- `importing.py`
  - 批量导入班级或成员时的数据清洗

## 当前关注的核心命令

- `添加班级`
- `查询班级`
- `删除班级`
- `加入班级`
- `退出班级`
- `查询入班申请`
- `处理入班申请`
- `修改班级加入方式`

## 维护约定

- “班级命令能不能进”放在命令权限和依赖层判断
- “当前用户能不能操作这个班级”放到 `services.py` 或领域规则里判断
- 尽量不要在 `__init__.py` 里重复写参数解析和状态校验

## 关联文档

- 命令口径：[命令使用文档](../../../docs/reference/command-reference.md)
- 身份与角色：[角色与组织关系说明](../../../docs/reference/role-reference.md)
- 命令权限与帮助：[命令鉴权与 Help/AutoGPT 统一机制](../../../docs/guides/command-auth-and-help.md)
