# 接口设计

## 接口前缀

建议新增后台专用 API 前缀：

```text
/api/v1/manager
```

当前项目已经在 `src/interfaces/http/path.py` 中使用 `/api/v1` 挂载通用接口，后台接口可以继续复用同一个 FastAPI app，但要放到独立 router 中。

建议代码位置：

```text
src/interfaces/http/managers/router.py
src/interfaces/http/managers/security.py
src/interfaces/http/managers/schemas.py
src/interfaces/http/managers/service.py
```

## 鉴权

后台使用项目启动时生成的 token 登录。

### 登录

```http
POST /api/v1/manager/auth/login
Content-Type: application/json
```

请求：

```json
{
  "token": "startup-token"
}
```

响应：

```json
{
  "access_token": "manager-session-token",
  "token_type": "bearer",
  "expires_in": 86400
}
```

### 当前会话

```http
GET /api/v1/manager/auth/me
Authorization: Bearer <access_token>
```

响应：

```json
{
  "authenticated": true,
  "role": "local_manager",
  "issued_at": "2026-05-03T21:00:00+08:00",
  "expires_at": "2026-05-04T21:00:00+08:00"
}
```

### 退出登录

```http
POST /api/v1/manager/auth/logout
Authorization: Bearer <access_token>
```

## 通用响应结构

成功响应可以直接返回业务数据。

错误响应统一：

```json
{
  "error": {
    "code": "MODEL_CONNECT_FAILED",
    "message": "模型连通性测试失败",
    "detail": "request timeout after 20s",
    "request_id": "req_..."
  }
}
```

## 分页结构

列表接口统一使用：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 0
}
```

查询参数：

| 参数 | 含义 |
| --- | --- |
| `page` | 页码，从 1 开始 |
| `page_size` | 每页数量 |
| `q` | 关键词 |
| `sort` | 排序字段 |
| `order` | `asc` 或 `desc` |

## 总览接口

### 获取总览

```http
GET /api/v1/manager/overview
```

响应：

```json
{
  "runtime": {
    "status": "ok",
    "started_at": "2026-05-03T21:00:00+08:00",
    "python_version": "3.12",
    "driver": "~fastapi+~httpx+~websockets+~aiohttp"
  },
  "assets": {
    "skills": 5,
    "prompts": 8,
    "models": 1,
    "agent_runs": 12,
    "pending_workflows": 1
  },
  "alerts": [
    {
      "level": "warning",
      "source": "ragflow",
      "message": "RAGFlow 未配置"
    }
  ]
}
```

## 用户中心接口

### 用户列表

```http
GET /api/v1/manager/users?q=&role=&is_admin=&page=1&page_size=20
```

响应字段：

```json
{
  "items": [
    {
      "id": 1,
      "nickname": "Nakamoto",
      "username": "user_x",
      "email": null,
      "phone": null,
      "roles": ["user", "admin"],
      "is_admin": true,
      "bind_count": 2,
      "has_teacher": false,
      "has_student": false,
      "created_at": "2026-05-03T21:00:00+08:00"
    }
  ],
  "page": 1,
  "page_size": 20,
  "total": 1
}
```

### 用户详情

```http
GET /api/v1/manager/users/{user_id}
```

详情需要聚合：

- `User`
- `UserBind`
- `Teacher`
- `Student`
- `StudentExtra`

### 修改管理员标记

```http
PATCH /api/v1/manager/users/{user_id}/admin
```

请求：

```json
{
  "is_admin": true
}
```

### 删除平台绑定

```http
DELETE /api/v1/manager/users/{user_id}/binds/{bind_id}
```

说明：高风险操作，需要前端二次确认。

## 系统状态接口

### 状态总览

```http
GET /api/v1/manager/status
```

响应：

```json
{
  "database": {
    "status": "ok",
    "url_masked": "sqlite:///db.sqlite3",
    "alembic_version": "ec39cb48b105"
  },
  "cache": {
    "status": "warning",
    "host": "localhost",
    "port": 6379,
    "message": "连接失败"
  },
  "paths": {
    "data_dir": {
      "path": "...",
      "exists": true
    }
  },
  "models": {
    "configured": 1,
    "available": 1
  }
}
```

### 单项检测

```http
POST /api/v1/manager/status/check
```

请求：

```json
{
  "targets": ["database", "cache", "models", "prompts", "skills", "cos", "ragflow"]
}
```

## 系统设置接口

### 获取设置

```http
GET /api/v1/manager/settings
```

响应按分组返回，并对密钥脱敏：

```json
{
  "base": {
    "global_proxy": null,
    "wsl_share_dir": null,
    "teacher_max_classes": 6
  },
  "ai": {
    "googleapis_key": "sk-***",
    "ragflow_url": null,
    "ragflow_key": null
  },
  "cache": {
    "cache_host": "localhost",
    "cache_port": 6379
  }
}
```

### 更新设置

```http
PATCH /api/v1/manager/settings
```

请求：

```json
{
  "base": {
    "teacher_max_classes": 8
  },
  "cache": {
    "cache_port": 6379
  }
}
```

响应：

```json
{
  "saved": true,
  "restart_required": true,
  "changed_keys": ["teacher_max_classes"]
}
```

说明：

- 本期可以先将项目设置写回 `.env` 或管理后台配置文件。
- 对当前进程无法即时生效的配置，必须返回 `restart_required: true`。
- 密钥字段如果前端未修改，不应回传明文或掩码覆盖原值。

### 轮换后台 token

```http
POST /api/v1/manager/settings/security/rotate-token
```

响应：

```json
{
  "rotated": true,
  "new_token_preview": "mgr_****abcd",
  "message": "新 token 已输出到控制台，请重新登录"
}
```

## Skill 管理接口

### 列表

```http
GET /api/v1/manager/skills
```

响应：

```json
{
  "items": [
    {
      "name": "ocr",
      "description": "OCR 检测与识别",
      "path": "src/core/skills/builtin/ocr",
      "has_runtime": true,
      "loaded": true,
      "updated_at": "2026-05-03T15:02:02+08:00"
    }
  ]
}
```

### 详情

```http
GET /api/v1/manager/skills/{name}
```

返回 `SKILL.md` 摘要、runtime 信息和加载状态。

### 重载

```http
POST /api/v1/manager/skills/reload
```

## Prompt 管理接口

### 列表

```http
GET /api/v1/manager/prompts
```

### 详情

```http
GET /api/v1/manager/prompts/{name}
```

### 更新

```http
PUT /api/v1/manager/prompts/{name}
```

请求：

```json
{
  "content": "..."
}
```

保存前必须：

- 校验文件名只能来自 `resources/prompts/`。
- 创建备份。
- 执行 Jinja 模板解析。

### 校验

```http
POST /api/v1/manager/prompts/{name}/validate
```

## Model 管理接口

### 模型配置列表

```http
GET /api/v1/manager/models
```

### 更新模型配置

```http
PUT /api/v1/manager/models
```

请求：

```json
{
  "llm_timeout": 60,
  "llm_configs": [
    {
      "name": "main",
      "key": "sk-...",
      "url": "https://example.com/v1",
      "model": "model-name",
      "priority": 100,
      "tasks": ["chat", "summary"],
      "multi_modal": false,
      "supports_functools": false
    }
  ]
}
```

### 测试模型

```http
POST /api/v1/manager/models/{name}/test
```

响应：

```json
{
  "ok": true,
  "latency_ms": 812,
  "model": "model-name"
}
```

## Agent 管理接口

### 运行记录

```http
GET /api/v1/manager/agents/runs?status=&kind=&q=&page=1&page_size=20
```

### 运行详情

```http
GET /api/v1/manager/agents/runs/{trace_id}
```

### 检查点列表

```http
GET /api/v1/manager/agents/checkpoints?status=&page=1&page_size=20
```

### 删除检查点

```http
DELETE /api/v1/manager/agents/checkpoints/{user_id}
```

说明：删除检查点会影响待确认工作流恢复，需要二次确认。

## MCP / 集成接口

### 集成状态

```http
GET /api/v1/manager/integrations
```

响应：

```json
{
  "mcp": {
    "status": "planned",
    "message": "当前仓库尚未接入 MCP 注册表"
  },
  "ragflow": {
    "status": "not_configured"
  },
  "cos": {
    "status": "configured"
  }
}
```

## 运维调试接口

### 日志文件列表

```http
GET /api/v1/manager/logs
```

### 读取日志

```http
GET /api/v1/manager/logs/read?path=&offset=&limit=500
```

### 自动化动作列表

```http
GET /api/v1/manager/operations/actions
```

### 执行动作

```http
POST /api/v1/manager/operations/actions/{action_id}/run
```

允许的动作必须来自白名单，例如：

- `check_config`
- `check_database`
- `reload_skills`
- `validate_prompts`
- `test_models`
- `generate_sql`
- `run_unit_tests`

响应：

```json
{
  "action_id": "validate_prompts",
  "status": "completed",
  "exit_code": 0,
  "duration_ms": 320,
  "stdout": "...",
  "stderr": ""
}
```

## WebSocket / SSE

日志 tail 和长任务进度建议后续使用 SSE：

```http
GET /api/v1/manager/events
```

事件类型：

- `log_line`
- `operation_started`
- `operation_progress`
- `operation_completed`
- `operation_failed`
- `status_changed`
