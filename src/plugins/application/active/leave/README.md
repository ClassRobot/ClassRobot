# 请假模块

`src/plugins/application/active/leave/` 负责学生请假、请假列表查询、请假删除以及教师推送配置。

## 模块作用

该模块主要处理请假业务：

- 学生发起请假
- 学生、班干部、教师查询请假记录
- 删除请假记录
- 教师设置请假推送对象

## 当前命令

### `请假`

- 作用：提交请假原因、时间说明与可选请假条图片
- 权限：`UserRole.student`
- help 目录：`学生身份命令`
- Agent：不开放给 Agent
- 执行模式：交互式命令

### `请假列表`

- 别名：`查询请假`
- 作用：查询自己发布的请假，或班级范围内可管理的请假
- 权限：`UserRole.student`、`UserRole.teacher`、`UserRole.class_cadre`
- help 目录：`学生身份命令`、`教师身份命令`

### `设置请假推送`

- 作用：设置请假消息要推送给哪些班干部
- 权限：`UserRole.teacher`
- help 目录：`教师身份命令`

### `删除请假`

- 作用：删除自己发布的请假，或删除自己有权管理的请假记录
- 权限：`UserRole.student`、`UserRole.teacher`、`UserRole.class_cadre`
- help 目录：`学生身份命令`、`教师身份命令`
- 风险等级：`high`

## 使用示例

```text
请假 今天下午发烧，需要请假半天 [请假条图片]
请假列表
查询请假
设置请假推送 班长 学习委员
删除请假 12 13
```

## 权限说明

- 学生可以发起和删除自己的请假
- 班干部和教师可根据班级管理权限查询或删除相关请假
- 动态范围判断仍由依赖与业务逻辑处理

## 代码结构

- `commands.py`
  命令声明、权限元数据、help 元数据
- `__init__.py`
  matcher 交互流程
- `depends.py`
  请假相关依赖
- `manage.py`
  请假处理与业务管理逻辑
- `prompt.py`
  请假相关提示词
- `schema.py`
  请假数据结构

## 扩展建议

- 如果后续加入“审批流程”“请假统计”，建议拆出 `services.py` 与 `presenters.py`
