export interface AdminNameValue {
  name: string;
  value: number;
}

export interface AdminMetric {
  key: string;
  label: string;
  value: number;
  description: string;
}

export interface AdminUserItem {
  id: number;
  nickname: string;
  username: string;
  email?: string | null;
  phone?: string | null;
  gender?: string | null;
  is_admin: boolean;
  roles: string[];
  has_teacher_profile: boolean;
  has_student_profile: boolean;
  bind_count: number;
  created_at: string;
  updated_at: string;
}

export interface AdminAuthStatusResponse {
  auth_mode: string;
  admin_account_count: number;
  session_secret_configured: boolean;
  frontend_dist_exists: boolean;
  generated_at: string;
}

export interface AdminLoginRequest {
  username: string;
  password: string;
}

export interface AdminLoginResponse {
  access_token: string;
  token_type: "bearer";
  expires_at: string;
  user: AdminUserItem;
}

export interface AdminOverviewResponse {
  generated_at: string;
  metrics: AdminMetric[];
  command_scope_distribution: AdminNameValue[];
  workflow_status_distribution: AdminNameValue[];
}

export interface AdminCommandItem {
  command: string;
  description: string;
  aliases: string[];
  scopes: string[];
  roles: string[];
  exclude_roles: string[];
  tags: string[];
  params: string[];
  ai_description?: string | null;
}

export interface AdminCommandListResponse {
  generated_at: string;
  total: number;
  scope_distribution: AdminNameValue[];
  items: AdminCommandItem[];
}

export interface AdminPluginItem {
  name: string;
  module_name: string;
  category: string;
  helper_count: number;
  commands: string[];
  read_only: boolean;
}

export interface AdminPluginListResponse {
  generated_at: string;
  total: number;
  items: AdminPluginItem[];
}

export interface AdminSkillItem {
  name: string;
  description: string;
  root: string;
  runtime_loaded: boolean;
  read_only: boolean;
}

export interface AdminSkillListResponse {
  generated_at: string;
  total: number;
  items: AdminSkillItem[];
}

export interface AdminModelItem {
  name: string;
  model: string;
  url: string;
  priority: number;
  tasks: string[];
  multi_modal: boolean;
  supports_functools: boolean;
  read_only: boolean;
}

export interface AdminModelListResponse {
  generated_at: string;
  total: number;
  items: AdminModelItem[];
}

export interface AdminBotItem {
  self_id: string;
  adapter: string;
  type: string;
  connected: boolean;
  read_only: boolean;
}

export interface AdminBotListResponse {
  generated_at: string;
  total: number;
  items: AdminBotItem[];
}

export interface AdminAgentSessionItem {
  user_id: number;
  updated_at: string;
  lock: boolean;
  helper_count: number;
  has_pending_workflow: boolean;
  last_trace_id: string;
  last_intent?: string | null;
  pending_goal?: string | null;
}

export interface AdminAgentOverviewResponse {
  generated_at: string;
  metrics: AdminMetric[];
  approval_status_distribution: AdminNameValue[];
  recent_sessions: AdminAgentSessionItem[];
}

export interface AdminDatabaseTableMetric {
  key: string;
  label: string;
  count: number;
}

export interface AdminDatabaseOverviewResponse {
  generated_at: string;
  tables: AdminDatabaseTableMetric[];
}

export interface AdminSystemDirectory {
  key: string;
  label: string;
  path: string;
  exists: boolean;
}

export interface AdminSystemStatusResponse {
  generated_at: string;
  app_name: string;
  environment: string;
  python_version: string;
  platform: string;
  fastapi_enabled: boolean;
  route_count: number;
  plugin_count: number;
  loaded_plugins: string[];
  directories: AdminSystemDirectory[];
}

export interface AdminUserListResponse {
  generated_at: string;
  total: number;
  items: AdminUserItem[];
}

export interface AdminUserCreateRequest {
  nickname: string;
  username: string;
  password: string;
  email?: string | null;
  phone?: string | null;
  gender?: string | null;
  is_admin: boolean;
}

export interface AdminUserUpdateRequest {
  nickname?: string | null;
  username?: string | null;
  password?: string | null;
  email?: string | null;
  phone?: string | null;
  gender?: string | null;
  is_admin?: boolean | null;
}
