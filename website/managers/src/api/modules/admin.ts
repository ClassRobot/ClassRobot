import { apiClient } from "@/api/client";
import type {
  AdminAgentOverviewResponse,
  AdminAuthStatusResponse,
  AdminBotListResponse,
  AdminCommandListResponse,
  AdminDatabaseOverviewResponse,
  AdminLoginRequest,
  AdminLoginResponse,
  AdminModelListResponse,
  AdminOverviewResponse,
  AdminPluginListResponse,
  AdminSkillListResponse,
  AdminSystemStatusResponse,
  AdminUserCreateRequest,
  AdminUserItem,
  AdminUserListResponse,
  AdminUserUpdateRequest,
} from "@/types/admin";


export async function fetchAdminAuthStatus() {
  const { data } = await apiClient.get<AdminAuthStatusResponse>("/admin/auth/status");
  return data;
}


export async function loginAdmin(payload: AdminLoginRequest) {
  const { data } = await apiClient.post<AdminLoginResponse>("/admin/auth/login", payload);
  return data;
}


export async function fetchAdminMe() {
  const { data } = await apiClient.get<AdminUserItem>("/admin/auth/me");
  return data;
}


export async function fetchAdminOverview() {
  const { data } = await apiClient.get<AdminOverviewResponse>("/admin/overview");
  return data;
}


export async function fetchAdminUsers() {
  const { data } = await apiClient.get<AdminUserListResponse>("/admin/users");
  return data;
}


export async function createAdminUser(payload: AdminUserCreateRequest) {
  const { data } = await apiClient.post<AdminUserItem>("/admin/users", payload);
  return data;
}


export async function updateAdminUser(userId: number, payload: AdminUserUpdateRequest) {
  const { data } = await apiClient.patch<AdminUserItem>(`/admin/users/${userId}`, payload);
  return data;
}


export async function deleteAdminUser(userId: number) {
  await apiClient.delete(`/admin/users/${userId}`);
}


export async function fetchAdminCommands() {
  const { data } = await apiClient.get<AdminCommandListResponse>("/admin/commands");
  return data;
}


export async function fetchAdminPlugins() {
  const { data } = await apiClient.get<AdminPluginListResponse>("/admin/plugins");
  return data;
}


export async function fetchAdminSkills() {
  const { data } = await apiClient.get<AdminSkillListResponse>("/admin/skills");
  return data;
}


export async function fetchAdminModels() {
  const { data } = await apiClient.get<AdminModelListResponse>("/admin/models");
  return data;
}


export async function fetchAdminBots() {
  const { data } = await apiClient.get<AdminBotListResponse>("/admin/bots");
  return data;
}


export async function fetchAdminAgents() {
  const { data } = await apiClient.get<AdminAgentOverviewResponse>("/admin/agents");
  return data;
}


export async function fetchAdminDatabase() {
  const { data } = await apiClient.get<AdminDatabaseOverviewResponse>("/admin/database");
  return data;
}


export async function fetchAdminSystem() {
  const { data } = await apiClient.get<AdminSystemStatusResponse>("/admin/system");
  return data;
}
