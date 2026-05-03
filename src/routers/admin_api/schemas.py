from datetime import datetime

from pydantic import BaseModel, Field


class AdminNameValue(BaseModel):
    """描述名称和值组成的简单统计项。"""

    name: str = Field(description="统计项名称")
    value: int = Field(description="统计项数值")


class AdminMetric(BaseModel):
    """描述后台首页展示的指标卡片。"""

    key: str = Field(description="指标键")
    label: str = Field(description="指标标题")
    value: int = Field(description="指标值")
    description: str = Field(description="指标说明")


class AdminUserItem(BaseModel):
    """描述后台中的用户信息摘要。"""

    id: int
    nickname: str
    username: str
    email: str | None = None
    phone: str | None = None
    gender: str | None = None
    is_admin: bool
    roles: list[str]
    has_teacher_profile: bool
    has_student_profile: bool
    bind_count: int
    created_at: datetime
    updated_at: datetime


class AdminAuthStatusResponse(BaseModel):
    """描述后台认证基础状态。"""

    auth_mode: str
    admin_account_count: int
    session_secret_configured: bool
    frontend_dist_exists: bool
    generated_at: datetime


class AdminLoginRequest(BaseModel):
    """描述管理员登录请求。"""

    username: str = Field(min_length=1, description="管理员用户名")
    password: str = Field(min_length=1, description="管理员密码")


class AdminLoginResponse(BaseModel):
    """描述管理员登录结果。"""

    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user: AdminUserItem


class AdminOverviewResponse(BaseModel):
    """描述后台仪表盘总览。"""

    generated_at: datetime
    metrics: list[AdminMetric]
    command_scope_distribution: list[AdminNameValue]
    workflow_status_distribution: list[AdminNameValue]


class AdminCommandItem(BaseModel):
    """描述单条命令的管理视图。"""

    command: str
    description: str
    aliases: list[str]
    scopes: list[str]
    roles: list[str]
    exclude_roles: list[str]
    tags: list[str]
    params: list[str]
    ai_description: str | None = None


class AdminCommandListResponse(BaseModel):
    """描述命令管理页的数据。"""

    generated_at: datetime
    total: int
    scope_distribution: list[AdminNameValue]
    items: list[AdminCommandItem]


class AdminPluginItem(BaseModel):
    """描述命令插件的只读信息。"""

    name: str
    module_name: str
    category: str
    helper_count: int
    commands: list[str]
    read_only: bool = True


class AdminPluginListResponse(BaseModel):
    """描述命令插件视图的数据。"""

    generated_at: datetime
    total: int
    items: list[AdminPluginItem]


class AdminSkillItem(BaseModel):
    """描述项目内 skill 信息。"""

    name: str
    description: str
    root: str
    runtime_loaded: bool
    read_only: bool = True


class AdminSkillListResponse(BaseModel):
    """描述 skill 列表。"""

    generated_at: datetime
    total: int
    items: list[AdminSkillItem]


class AdminModelItem(BaseModel):
    """描述大模型配置项。"""

    name: str
    model: str
    url: str
    priority: int
    tasks: list[str]
    multi_modal: bool
    supports_functools: bool
    read_only: bool = True


class AdminModelListResponse(BaseModel):
    """描述模型配置视图的数据。"""

    generated_at: datetime
    total: int
    items: list[AdminModelItem]


class AdminBotItem(BaseModel):
    """描述当前正在运行的 bot。"""

    self_id: str
    adapter: str
    type: str
    connected: bool
    read_only: bool = True


class AdminBotListResponse(BaseModel):
    """描述当前运行 bot 列表。"""

    generated_at: datetime
    total: int
    items: list[AdminBotItem]


class AdminAgentSessionItem(BaseModel):
    """描述当前内存中的 Agent 会话。"""

    user_id: int
    updated_at: datetime
    lock: bool
    helper_count: int
    has_pending_workflow: bool
    last_trace_id: str
    last_intent: str | None = None
    pending_goal: str | None = None


class AdminAgentOverviewResponse(BaseModel):
    """描述 Agent 运行态总览。"""

    generated_at: datetime
    metrics: list[AdminMetric]
    approval_status_distribution: list[AdminNameValue]
    recent_sessions: list[AdminAgentSessionItem]


class AdminDatabaseTableMetric(BaseModel):
    """描述数据库中单个核心表的数量统计。"""

    key: str
    label: str
    count: int


class AdminDatabaseOverviewResponse(BaseModel):
    """描述数据库管理首页的统计数据。"""

    generated_at: datetime
    tables: list[AdminDatabaseTableMetric]


class AdminSystemDirectory(BaseModel):
    """描述系统目录信息。"""

    key: str
    label: str
    path: str
    exists: bool


class AdminSystemStatusResponse(BaseModel):
    """描述系统运行态和基础环境信息。"""

    generated_at: datetime
    app_name: str
    environment: str
    python_version: str
    platform: str
    fastapi_enabled: bool
    route_count: int
    plugin_count: int
    loaded_plugins: list[str]
    directories: list[AdminSystemDirectory]


class AdminUserListResponse(BaseModel):
    """描述后台用户管理列表。"""

    generated_at: datetime
    total: int
    items: list[AdminUserItem]


class AdminUserCreateRequest(BaseModel):
    """描述创建后台用户请求。"""

    nickname: str = Field(min_length=1, max_length=64)
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=11)
    gender: str | None = Field(default=None, max_length=8)
    is_admin: bool = False


class AdminUserUpdateRequest(BaseModel):
    """描述更新后台用户请求。"""

    nickname: str | None = Field(default=None, min_length=1, max_length=64)
    username: str | None = Field(default=None, min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=1, max_length=128)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=11)
    gender: str | None = Field(default=None, max_length=8)
    is_admin: bool | None = None
