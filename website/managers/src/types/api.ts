// API type definitions mirroring the backend schemas in src/routers/managers/schemas.py

// ─── Generic ────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

export interface ApiError {
  error: {
    code: string
    message: string
    detail?: string
    request_id?: string
  }
}

// ─── Auth ───────────────────────────────────────────────────
export interface LoginRequest {
  token: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface AuthMeResponse {
  authenticated: boolean
  role: 'local_manager'
  issued_at: string
  expires_at: string
}

// ─── Overview ───────────────────────────────────────────────
export type StatusLevel = 'ok' | 'warning' | 'error' | 'not_configured' | 'configured'

export interface RuntimeInfo {
  status: StatusLevel
  python_version: string
  driver: string
  environment?: string
  host?: string
  port?: number
}

export interface OverviewAssets {
  skills: number
  prompts: number
  models: number
  agent_runs: number
  pending_workflows: number
}

export interface OverviewAlert {
  source: string
  level: StatusLevel
  message: string
}

export interface OverviewResponse {
  runtime: RuntimeInfo
  assets: OverviewAssets
  alerts: OverviewAlert[]
  recent_runs: AgentRunSummary[]
}

// ─── Status ─────────────────────────────────────────────────
export interface DatabaseStatus {
  status: StatusLevel
  alembic_version?: string
  tables?: Record<string, number>
  message?: string
}

export interface CacheStatus {
  status: StatusLevel
  host: string
  port: number
  message?: string
}

export interface PathInfo {
  path: string
  exists: boolean
  is_dir: boolean
}

export interface ModelStatusSummary {
  status: StatusLevel
  configured: number
  timeout: number
  names: string[]
}

export interface CosStatus {
  status: StatusLevel
  region: string
  bucket: string
  scheme: string
}

export interface RagflowStatus {
  status: StatusLevel
  url?: string
  has_key: boolean
}

export interface StatusResponse {
  runtime?: RuntimeInfo
  database?: DatabaseStatus
  cache?: CacheStatus
  paths?: Record<string, PathInfo>
  models?: ModelStatusSummary
  cos?: CosStatus
  ragflow?: RagflowStatus
  system?: SystemMetrics
}

export interface StatusCheckRequest {
  targets?: string[]
}

export interface SystemCpuMetrics {
  percent: number | null
  count: number | null
  physical_count?: number | null
  load_average?: number[] | null
}

export interface SystemMemoryMetrics {
  total: number
  available?: number
  used: number
  free: number
  percent: number
}

export interface SystemDiskMetrics {
  device: string
  mountpoint: string
  fstype: string
  total: number
  used: number
  free: number
  percent: number
}

export interface SystemProcessMetrics {
  pid: number
  cpu_percent: number
  memory_rss: number
  memory_percent: number
  threads: number
  started_at: string
  uptime_seconds: number
}

export interface SystemMetrics {
  status: StatusLevel
  timestamp: string
  message?: string
  cpu: SystemCpuMetrics
  memory: SystemMemoryMetrics | null
  swap: SystemMemoryMetrics | null
  disks: SystemDiskMetrics[]
  process: SystemProcessMetrics | null
}

// ─── Databases ──────────────────────────────────────────────
export interface DatabaseConnection {
  id: string
  name: string
  status: 'connected' | 'error'
  kind: string
  dialect: string | null
  driver: string | null
  url: string | null
  database: string | null
  editable: boolean
}

export interface DatabaseConnectionResponse {
  items: DatabaseConnection[]
  total: number
}

export interface DatabaseColumn {
  name: string
  type: string
  nullable: boolean
  default: string | null
  primary_key: boolean
  sensitive: boolean
}

export interface DatabaseForeignKey {
  name: string | null
  source_table: string
  source_columns: string[]
  target_schema: string | null
  target_table: string
  target_columns: string[]
  label: string
}

export interface DatabaseTableSchema {
  name: string
  schema: string | null
  columns: DatabaseColumn[]
  primary_key: string[]
  foreign_keys: DatabaseForeignKey[]
}

export interface DatabaseSchemaResponse {
  database_id: string
  schema: string | null
  default_schema: string | null
  schemas: string[]
  tables: DatabaseTableSchema[]
  relationships: DatabaseForeignKey[]
}

export interface DatabaseTableSummary {
  name: string
  schema: string | null
  column_count: number
  row_count: number | null
  primary_key: string[]
  foreign_key_count: number
  editable: boolean
}

export interface DatabaseTableListResponse {
  database_id: string
  schema: string | null
  items: DatabaseTableSummary[]
  total: number
}

export type DatabaseRow = Record<string, unknown>

export interface DatabaseTableRowsResponse {
  database_id: string
  schema: string | null
  table: string
  columns: DatabaseColumn[]
  primary_key: string[]
  items: DatabaseRow[]
  page: number
  page_size: number
  total: number
}

export interface DatabaseRowUpdateRequest {
  pk: Record<string, unknown>
  values: Record<string, unknown>
}

export interface DatabaseRowUpdateResponse {
  updated: boolean
  database_id: string
  schema: string | null
  table: string
  pk: Record<string, unknown>
  row: DatabaseRow | null
}

export interface DatabaseMutationErrorDetail {
  code: string
  message: string
  column?: string
  columns?: string[]
  hint?: string
  detail?: string
  expected?: string
  received_type?: string
  received_value?: string
  database_error_type?: string
}

// ─── Users ──────────────────────────────────────────────────
export interface UserSummary {
  id: number
  nickname: string
  username: string
  email: string | null
  avatar: string | null
  phone: string | null
  roles: string[]
  is_admin: boolean
  bind_count: number
  has_teacher: boolean
  has_student: boolean
  created_at: string
  updated_at: string
}

export interface UserBindInfo {
  id: number
  name: string
  platform_id: string
  account_id: string
  created_at: string
  updated_at: string
}

export interface TeacherInfo {
  id: number
  name: string
  role: string
  school_id: number
  school_name: string | null
  college_id: number
  college_name: string | null
  classes: { id: number; name: string }[]
  created_at: string
  updated_at: string
}

export interface StudentExtraInfo {
  student_code: string | null
  dormitory: string | null
  political_status: string | null
  family_contact: string | null
  family_address: string | null
  nation: string | null
}

export interface StudentInfo {
  id: number
  name: string
  role: string
  school_id: number
  school_name: string | null
  classes_id: number
  classes_name: string
  created_at: string
  updated_at: string
  extra: StudentExtraInfo
}

export interface UserDetail extends UserSummary {
  avatar: string | null
  gender: string | null
  birthday: string | null
  binds: UserBindInfo[]
  teacher: TeacherInfo | null
  student: StudentInfo | null
}

export interface AdminPatchRequest {
  is_admin: boolean
}

export interface UserDeleteResponse {
  deleted: boolean
  user_id: number
}

export interface UserMutationBlocker {
  code: string
  message: string
  items?: string[]
}

export interface UserMutationErrorDetail {
  code: string
  message: string
  hint?: string
  detail?: string
  blockers?: UserMutationBlocker[]
}

// ─── Groups / Classes ──────────────────────────────────────
export interface ManagerUserBrief {
  id: number
  nickname: string
  username: string
  avatar: string | null
}

export interface GroupClassInfo {
  id: number
  name: string
  school_id: number | null
  school_name: string | null
  college_id: number | null
  college_name: string | null
  major_id: number | null
  major_name: string | null
  student_count: number
  teacher_count: number
  pending_join_count: number
  created_at: string
  updated_at: string
}

export interface GroupSummary {
  id: number
  name: string
  creator: ManagerUserBrief | null
  join_method: string | null
  class_info: GroupClassInfo | null
  bind_count: number
  platforms: string[]
  student_count: number
  teacher_count: number
  pending_join_count: number
  created_at: string
  updated_at: string
}

export interface GroupBindInfo {
  id: number
  name: string | null
  platform_id: string
  channel_id: string
  guild_id: string | null
  created_at: string
  updated_at: string
}

export interface GroupMemberTeacher {
  id: number
  name: string
  role: string | null
  class_role: string | null
  school_name: string | null
  college_name: string | null
  user: ManagerUserBrief | null
}

export interface GroupMemberStudent {
  id: number
  name: string
  role: string | null
  school_name: string | null
  user: ManagerUserBrief | null
}

export interface GroupJoinRequest {
  id: number
  user: ManagerUserBrief | null
  join_method: string | null
  describe: string | null
  created_at: string
}

export interface GroupDetail extends GroupSummary {
  group: {
    id: number
    name: string
    creator: ManagerUserBrief | null
    join_method: string | null
    created_at: string
    updated_at: string
  }
  class_detail: GroupClassInfo | null
  binds: GroupBindInfo[]
  teachers: GroupMemberTeacher[]
  students: GroupMemberStudent[]
  join_requests: GroupJoinRequest[]
}

// ─── Settings ───────────────────────────────────────────────
export interface BaseSettings {
  global_proxy: string | null
  wsl_share_dir: string | null
  teacher_max_classes: number
}

export interface AiSettings {
  googleapis_key: string | null
  ragflow_url: string | null
  ragflow_key: string | null
}

export interface CacheSettings {
  cache_host: string
  cache_port: number
}

export interface CosSettings {
  cos_secret_id: string | null
  cos_secret_key: string | null
  region: string
  bucket: string
  scheme: string
}

export interface SecuritySettings {
  encrypt_salt: string | null
}

export interface ModelConfigItem {
  name: string
  key: string
  url: string
  model: string
  priority: number
  tasks: string[]
  multi_modal: boolean
  supports_functools: boolean
}

export interface ModelSettingsSummary {
  llm_timeout: number
  llm_configs: ModelConfigItem[]
}

export interface SettingsResponse {
  base: BaseSettings
  ai: AiSettings
  cache: CacheSettings
  cos: CosSettings
  security: SecuritySettings
  models: ModelSettingsSummary
}

export interface SettingsPatchPayload {
  base?: Partial<BaseSettings>
  ai?: Partial<AiSettings>
  cache?: Partial<CacheSettings>
  cos?: Partial<CosSettings>
  security?: Partial<SecuritySettings>
  models?: Partial<ModelSettingsSummary>
}

export interface SettingsSaveResult {
  saved: boolean
  restart_required: boolean
  changed_keys: string[]
}

// ─── Skills ─────────────────────────────────────────────────
export interface SkillSummary {
  name: string
  description: string
  path: string
  has_runtime: boolean
  loaded: boolean
  updated_at: number | null
}

export interface SkillDetail extends SkillSummary {
  skill_file: string
  body: string
}

export interface SkillReloadResult {
  reloaded: boolean
  loaded_classes: string[]
  skills: SkillSummary[]
}

// ─── Prompts ────────────────────────────────────────────────
export interface PromptSummary {
  name: string
  path: string
  size: number
  updated_at: string
  valid: boolean
  validation_message: string
}

export interface PromptDetail extends PromptSummary {
  content: string
}

export interface PromptUpdateRequest {
  content: string
}

export interface PromptSaveResult {
  saved: boolean
  valid: boolean
  validation_message?: string
  backup_path?: string
}

// ─── Models (LLM) ──────────────────────────────────────────
export interface ModelSettingsUpdateRequest {
  llm_timeout?: number
  llm_configs?: ModelConfigItem[]
}

export interface ModelTestResult {
  ok: boolean
  latency_ms?: number
  model?: string
  message?: string
}

// ─── Agents ─────────────────────────────────────────────────
export interface AgentRunSummary {
  id: number
  user_id: number
  trace_id: string
  source_trace_id: string | null
  kind: string
  status: string
  goal: string | null
  summary: string | null
  playbook_id: string | null
  playbook_name: string | null
  approval_type: string | null
  approval_status: string | null
  approval_reason: string | null
  started_at: string | null
  finished_at: string | null
  created_at: string
  updated_at: string
}

export interface AgentRunDetail extends AgentRunSummary {
  workflow_data: unknown
}

export interface AgentCheckpointSummary {
  id: number
  user_id: number
  trace_id: string
  kind: string
  status: string
  goal: string | null
  summary: string | null
  playbook_id: string | null
  playbook_name: string | null
  created_at: string
  updated_at: string
}

export interface AgentCheckpointDetail extends AgentCheckpointSummary {
  workflow_data: unknown
}

// ─── Integrations ───────────────────────────────────────────
export interface IntegrationStatusItem {
  status: StatusLevel
  message?: string
}

export interface IntegrationsResponse {
  mcp: IntegrationStatusItem
  ragflow: RagflowStatus
  cos: CosStatus
  models: ModelStatusSummary
}

// ─── NoneBot Runtime ───────────────────────────────────────
export interface NoneBotConfigAdapter {
  name: string
  module_name: string
}

export interface NoneBotRuntimeConfig {
  plugins: string[]
  plugin_dirs: string[]
  adapters: NoneBotConfigAdapter[]
  errors: string[]
}

export interface NoneBotRuntimeInfo {
  initialized: boolean
  driver: string | null
  environment: string | null
  host: string | null
  port: number | null
  config: NoneBotRuntimeConfig
  errors: string[]
}

export interface NoneBotStats {
  plugins: number
  loaded_plugins: number
  commands: number
  documented_commands: number
  adapters: number
  registered_adapters: number
  bots: number
  online_bots: number
}

export interface NoneBotPluginItem {
  name: string
  module_name: string
  display_name: string
  description: string
  usage: string
  type: string | null
  homepage: string | null
  supported_adapters: string[]
  loaded: boolean
  source: 'runtime' | 'source_scan' | 'pyproject'
  matcher_count: number
  sub_plugin_count: number
  parent: string | null
  command_count: number
}

export interface NoneBotCommandParam {
  name: string
  description: string | null
  mode: string | null
}

export interface NoneBotCommandItem {
  id: string
  command: string
  aliases: string[]
  matcher_type: 'command' | 'alconna'
  priority: string | number | null
  block: string | boolean | null
  skip_for_unmatch: string | boolean | null
  signature: string
  documented: boolean
  description: string
  roles: string[]
  scopes: string[]
  params: NoneBotCommandParam[]
  matcher_name: string | null
  file: string
  line: number
  module_name: string
  plugin_module: string
  plugin_name: string
  namespace: string
  source: 'source_scan'
  runtime_loaded: boolean
}

export interface NoneBotAdapterItem {
  name: string
  module_name: string
  class_module: string | null
  runtime_key: string | null
  class_name: string | null
  registered: boolean
  source: 'runtime' | 'pyproject'
  bot_count: number
}

export interface NoneBotBotItem {
  self_id: string
  type: string | null
  adapter_name: string | null
  adapter_module: string | null
  connected: boolean
  status: 'online'
}

export interface NoneBotListResponse<T> {
  items: T[]
  total: number
  errors: string[]
}

export interface NoneBotOverviewResponse {
  status: 'ok' | 'warning'
  runtime: NoneBotRuntimeInfo
  stats: NoneBotStats
  command_sources: Record<string, number>
  plugins: NoneBotPluginItem[]
  commands: NoneBotCommandItem[]
  adapters: NoneBotAdapterItem[]
  bots: NoneBotBotItem[]
  errors: string[]
}

// ─── Logs ───────────────────────────────────────────────────
export interface LogFileItem {
  name: string
  path: string
  relative_path?: string
  size: number
  updated_at: number
}

export interface LogReadResult {
  path: string
  offset: number
  limit: number
  total_lines: number
  lines: string[]
}

// ─── Operations ─────────────────────────────────────────────
export interface ActionItem {
  action_id: string
  title: string
  risk: 'low' | 'medium'
}

export interface ActionRunResult {
  action_id: string
  status: 'completed' | 'failed'
  exit_code: number
  duration_ms: number
  error: string
  result: Record<string, unknown>
}

export interface TerminalCommandItem {
  command_id: string
  title: string
  description: string
  risk: 'low' | 'medium'
  cwd: string
  command: string
  available: boolean
  timeout: number
}

export interface TerminalRunResult {
  command_id: string
  status: 'completed' | 'failed'
  exit_code: number
  duration_ms: number
  timed_out: boolean
  error: string
  stdout: string
  stderr: string
  cwd: string
  command: string
}

export interface TerminalExecuteRequest {
  command: string
  cwd?: string
  timeout?: number
}

export interface AutomationScriptItem {
  id: string
  title: string
  description: string
  command: string
  cwd: string
  risk: 'low' | 'medium'
  timeout: number
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface AutomationScriptPayload {
  id?: string
  title: string
  description?: string
  command: string
  cwd?: string
  risk?: 'low' | 'medium'
  timeout?: number
  enabled?: boolean
}

export interface AuditLogItem {
  timestamp: string
  event_type: string
  action: string
  status: string
  actor: string
  session_id: string | null
  detail: Record<string, unknown>
}

export interface AuditLogResponse {
  items: AuditLogItem[]
  total: number
  path: string
}
