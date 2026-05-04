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
}

export interface StatusCheckRequest {
  targets?: string[]
}

// ─── Users ──────────────────────────────────────────────────
export interface UserSummary {
  id: number
  nickname: string
  username: string
  email: string | null
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
