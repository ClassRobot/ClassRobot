# 数据来源与权限策略

本文档回答两个核心问题：

- 管理后台的数据到底来自哪里。
- 不同类型的数据和操作应该受到什么级别的约束。

阅读这篇时可以始终记住一个原则：管理后台不是“万能数据库控制台”，而是一个受约束的项目运维界面。

## 数据来源分类

管理后台的数据不是单一数据库 CRUD，而是数据库、配置、文件系统和运行时探针的组合。

| 类型 | 示例 | 读写策略 |
| --- | --- | --- |
| 数据库 | 用户、绑定、Agent 运行记录 | ORM 读取，少量受控写入 |
| 文件系统 | Prompt、Skill、日志 | 读取为主，Prompt 可编辑 |
| 配置 | `.env`、NoneBot config、localstore | 设置页受控写入 |
| 运行时 | token、SkillRegistry、模型连通性 | 当前进程内查询或执行 |
| 外部服务 | Redis、RagFlow、COS、模型 Provider | 健康检查和连通性测试 |

## 数据库模型

### 用户中心

| 模型 | 用途 |
| --- | --- |
| `User` | 账号主体、管理员标记、基础资料 |
| `UserBind` | 平台账号绑定 |
| `Teacher` | 用户的教师扩展身份 |
| `Student` | 用户的学生扩展身份 |
| `StudentExtra` | 学号、寝室、家庭联系方式等学生扩展资料 |

### Agent 管理

| 模型 | 用途 |
| --- | --- |
| `AgentWorkflowRun` | 每次 Agent 工作流历史记录 |
| `AgentWorkflowCheckpoint` | 每个用户最近一次可恢复工作流状态 |

### 文件中心关联

| 模型 | 用途 |
| --- | --- |
| `Files` | 任务附件、请假证明、其他文件引用 |

文件中心本期不作为一级页面，但日志、任务导出和异常诊断可能需要读取文件元数据。

## 配置来源

### 全局配置

来源：`src/platform/config.py`

| 字段 | 含义 | 设置页分组 |
| --- | --- | --- |
| `wsl_share_dir` | WSL 共享目录 | 基础 |
| `global_proxy` | 全局代理 | 基础 |
| `googleapis_key` | Google / Gemini Key | AI / RAG |
| `ragflow_key` | RagFlow Key | AI / RAG |
| `ragflow_url` | RagFlow URL | AI / RAG |
| `teacher_max_classes` | 教师最大班级数 | 基础 |

### 模型配置

来源：`src/core/llm/config.py`

| 字段 | 含义 |
| --- | --- |
| `llm_configs` | 模型配置列表 |
| `llm_timeout` | LLM 请求超时 |
| `name` | 模型配置名称 |
| `key` | 模型 API Key |
| `url` | 模型 Base URL |
| `model` | 模型名称 |
| `priority` | 路由优先级 |
| `tasks` | 偏好的任务类型 |
| `multi_modal` | 是否支持多模态 |
| `supports_functools` | 是否支持工具调用 |

### 缓存配置

来源：`src/core/cache/config.py`

| 字段 | 含义 |
| --- | --- |
| `cache_host` | Redis host |
| `cache_port` | Redis port |

### COS 配置

来源：`src/shared/tools/cos/config.py`

| 字段 | 含义 |
| --- | --- |
| `cos_secret_id` | 腾讯云 SecretId |
| `cos_secret_key` | 腾讯云 SecretKey |
| `region` | 地域 |
| `bucket` | 存储桶 |
| `scheme` | 访问协议 |

### 加密配置

来源：`src/shared/encrypt/config.py`

| 字段 | 含义 |
| --- | --- |
| `encrypt_salt` | 加密盐 |

## 文件来源

### Prompt

目录：`resources/prompts/`

当前文件：

- `agent_plan.jinja`
- `auto_task.jinja`
- `autogpt.jinja`
- `extract.jinja`
- `intent_route.jinja`
- `output.jinja`
- `user.jinja`

### Skill

目录：`src/core/skills/builtin/`

当前 Skill：

- `document-to-image`
- `image-generation`
- `markdown-to-image`
- `ocr`
- `qr-code`

### 日志

当前仓库没有统一日志目录约定，后台可以先支持：

- `.codex/tmp/*.log`
- NoneBot 标准输出。
- 部署目录下的 NapCat 日志索引。

后续建议新增统一日志目录或日志聚合服务。

## 权限模型

本期后台只有一个本地管理员角色：

```text
local_manager
```

鉴权来源是项目启动时生成的后台 token。

## 操作级别

| 级别 | 示例 | 要求 |
| --- | --- | --- |
| 只读 | 查看状态、查看用户、查看 Prompt | 登录即可 |
| 普通写 | 编辑 Prompt、保存非密钥设置 | 登录 + 表单校验 |
| 敏感写 | 更新密钥、模型 Key、COS Secret | 登录 + 二次确认 |
| 危险操作 | 删除检查点、解除绑定、轮换 token | 登录 + 二次确认 + 结果记录 |
| 自动化执行 | 运行测试、生成 SQL、重载 Skill | 登录 + 白名单动作 |

## 密钥处理

密钥字段必须遵守：

- 列表和详情中只显示掩码。
- 不提供明文查看接口。
- 未修改时不回传密钥字段。
- 更新密钥时只提交新值。
- 写入前后不在日志中输出密钥。
- 接口错误信息不得包含密钥。

掩码规则：

```text
空值: null
短值: ***
长值: 前 4 位 + **** + 后 4 位
```

## 配置写入策略

建议分两类配置：

### 项目运行配置

例如模型、缓存、COS、RAGFlow。

这些配置当前来自 NoneBot 启动配置，保存后通常需要重启才完全生效。

接口必须返回：

```json
{
  "restart_required": true
}
```

### 后台自身配置

例如 Skill 启停状态、后台 UI 偏好、最近动作记录。

建议写入：

```text
config_dir / "manager-settings.json"
```

这类配置可以当前进程即时生效。

## 审计建议

本期可以先不建审计表，但接口层要保留记录点。

后续可新增：

```text
ManagerAuditLog
```

建议字段：

| 字段 | 含义 |
| --- | --- |
| `id` | 主键 |
| `action` | 操作名称 |
| `target_type` | 目标类型 |
| `target_id` | 目标 ID |
| `risk_level` | 风险等级 |
| `success` | 是否成功 |
| `message` | 结果摘要 |
| `created_at` | 时间 |

## 安全边界

- 后台默认不对公网暴露。
- 后台路由必须全部挂鉴权依赖。
- 自动化动作必须白名单，禁止任意命令输入。
- 文件读取必须限制在允许目录内。
- Prompt 编辑必须限制在 `resources/prompts/`。
- 日志读取必须限制在允许日志路径内。
- 删除和重置操作必须二次确认。
