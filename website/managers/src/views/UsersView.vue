<template>
  <div class="space-y-6">
    <section class="grid gap-4 xl:grid-cols-4">
      <MetricCard label="用户总数" :value="users?.total ?? 0" description="系统中可被后台查看和维护的全部用户。" tone="ink" />
      <MetricCard label="管理员" :value="adminCount" description="具备后台登录权限的管理员账号数量。" tone="amber" />
      <MetricCard label="教师档案" :value="teacherCount" description="已绑定教师身份资料的用户数量。" tone="sea" />
      <MetricCard label="学生档案" :value="studentCount" description="已绑定学生身份资料的用户数量。" tone="mint" />
    </section>

    <div class="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <SectionPanel title="用户目录" description="支持按用户名、昵称或角色检索，列表默认按用户 ID 倒序显示。">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <label class="block flex-1">
            <span class="mb-2 block text-sm font-medium text-slate-600">搜索用户</span>
            <input
              v-model.trim="keyword"
              type="search"
              placeholder="按用户名、昵称、邮箱或角色筛选"
              class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand-mint focus:ring-4 focus:ring-emerald-100"
            />
          </label>
          <button
            type="button"
            class="rounded-2xl bg-brand-ink px-5 py-3 text-sm font-medium text-white transition hover:-translate-y-0.5 hover:bg-slate-950"
            @click="startCreate"
          >
            新建用户
          </button>
        </div>

        <div class="mt-5 overflow-hidden rounded-[28px] border border-slate-200">
          <div class="max-h-[680px] overflow-auto">
            <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead class="bg-slate-50 text-slate-500">
                <tr>
                  <th class="px-4 py-3 font-medium">用户</th>
                  <th class="px-4 py-3 font-medium">身份</th>
                  <th class="px-4 py-3 font-medium">联系方式</th>
                  <th class="px-4 py-3 font-medium">状态</th>
                  <th class="px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 bg-white">
                <tr
                  v-for="item in filteredUsers"
                  :key="item.id"
                  class="align-top transition hover:bg-slate-50"
                  :class="editingUserId === item.id ? 'bg-brand-amber/5' : ''"
                >
                  <td class="px-4 py-4">
                    <div class="flex items-center gap-3">
                      <div class="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-ink text-sm font-semibold text-white">
                        {{ item.nickname.slice(0, 1).toUpperCase() }}
                      </div>
                      <div>
                        <p class="font-semibold text-brand-ink">{{ item.nickname }}</p>
                        <p class="mt-1 font-mono text-xs text-slate-500">{{ item.username }}</p>
                        <p class="mt-2 text-xs text-slate-400">创建于 {{ formatDateTime(item.created_at) }}</p>
                      </div>
                    </div>
                  </td>
                  <td class="px-4 py-4">
                    <div class="flex flex-wrap gap-2">
                      <span
                        v-for="role in item.roles"
                        :key="role"
                        class="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600"
                      >
                        {{ formatRoleLabel(role) }}
                      </span>
                    </div>
                    <div class="mt-3 flex flex-wrap gap-2 text-xs">
                      <span
                        class="rounded-full px-3 py-1"
                        :class="item.has_teacher_profile ? 'bg-brand-sea/10 text-brand-sea' : 'bg-slate-100 text-slate-500'"
                      >
                        教师档案 {{ formatYesNo(item.has_teacher_profile) }}
                      </span>
                      <span
                        class="rounded-full px-3 py-1"
                        :class="item.has_student_profile ? 'bg-brand-mint/10 text-emerald-700' : 'bg-slate-100 text-slate-500'"
                      >
                        学生档案 {{ formatYesNo(item.has_student_profile) }}
                      </span>
                    </div>
                  </td>
                  <td class="px-4 py-4 text-slate-600">
                    <p>{{ item.email || "未填写邮箱" }}</p>
                    <p class="mt-2">{{ item.phone || "未填写手机号" }}</p>
                  </td>
                  <td class="px-4 py-4">
                    <div class="flex flex-wrap gap-2">
                      <span
                        class="rounded-full px-3 py-1 text-xs"
                        :class="item.is_admin ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-500'"
                      >
                        {{ item.is_admin ? "管理员" : "普通账号" }}
                      </span>
                      <span
                        v-if="authStore.user?.id === item.id"
                        class="rounded-full bg-brand-ink/10 px-3 py-1 text-xs text-brand-ink"
                      >
                        当前登录
                      </span>
                    </div>
                    <p class="mt-3 text-xs text-slate-400">绑定数 {{ item.bind_count }} · 更新于 {{ formatDateTime(item.updated_at) }}</p>
                  </td>
                  <td class="px-4 py-4">
                    <div class="flex flex-col gap-2">
                      <button
                        type="button"
                        class="rounded-2xl border border-slate-200 px-3 py-2 text-xs text-slate-600 transition hover:border-brand-ink hover:text-brand-ink"
                        @click="startEdit(item)"
                      >
                        编辑
                      </button>
                      <button
                        type="button"
                        class="rounded-2xl border border-rose-200 px-3 py-2 text-xs text-rose-600 transition hover:bg-rose-50 disabled:opacity-60"
                        :disabled="deletingUserId === item.id || authStore.user?.id === item.id"
                        @click="handleDelete(item)"
                      >
                        {{ deletingUserId === item.id ? "删除中..." : "删除" }}
                      </button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </SectionPanel>

      <SectionPanel :title="editorTitle" :description="editorDescription">
        <form class="space-y-5" @submit.prevent="handleSave">
          <label class="block">
            <span class="mb-2 block text-sm font-medium text-slate-700">昵称</span>
            <input
              v-model.trim="form.nickname"
              type="text"
              placeholder="请输入用户昵称"
              class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand-amber focus:ring-4 focus:ring-amber-100"
            />
          </label>

          <label class="block">
            <span class="mb-2 block text-sm font-medium text-slate-700">用户名</span>
            <input
              v-model.trim="form.username"
              type="text"
              autocomplete="username"
              placeholder="请输入唯一用户名"
              class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand-amber focus:ring-4 focus:ring-amber-100"
            />
          </label>

          <label class="block">
            <span class="mb-2 block text-sm font-medium text-slate-700">
              {{ mode === "create" ? "登录密码" : "登录密码（留空表示不修改）" }}
            </span>
            <input
              v-model="form.password"
              type="password"
              autocomplete="new-password"
              placeholder="请输入密码"
              class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand-amber focus:ring-4 focus:ring-amber-100"
            />
          </label>

          <div class="grid gap-5 sm:grid-cols-2">
            <label class="block">
              <span class="mb-2 block text-sm font-medium text-slate-700">邮箱</span>
              <input
                v-model.trim="form.email"
                type="email"
                placeholder="选填"
                class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand-amber focus:ring-4 focus:ring-amber-100"
              />
            </label>
            <label class="block">
              <span class="mb-2 block text-sm font-medium text-slate-700">手机号</span>
              <input
                v-model.trim="form.phone"
                type="text"
                placeholder="选填"
                class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand-amber focus:ring-4 focus:ring-amber-100"
              />
            </label>
          </div>

          <label class="block">
            <span class="mb-2 block text-sm font-medium text-slate-700">性别</span>
            <input
              v-model.trim="form.gender"
              type="text"
              placeholder="选填，例如男 / 女"
              class="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-brand-amber focus:ring-4 focus:ring-amber-100"
            />
          </label>

          <label class="flex items-center gap-3 rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4">
            <input v-model="form.is_admin" type="checkbox" class="h-4 w-4 rounded border-slate-300 text-brand-ink" />
            <div>
              <p class="text-sm font-medium text-brand-ink">允许后台管理员登录</p>
              <p class="mt-1 text-xs leading-5 text-slate-500">
                只有开启该项后，用户才能通过当前管理端登录。
              </p>
            </div>
          </label>

          <p v-if="errorMessage" class="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {{ errorMessage }}
          </p>
          <p v-if="successMessage" class="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            {{ successMessage }}
          </p>

          <div class="flex flex-wrap gap-3">
            <button
              type="submit"
              class="rounded-2xl bg-brand-ink px-5 py-3 text-sm font-medium text-white transition hover:-translate-y-0.5 hover:bg-slate-950 disabled:opacity-70"
              :disabled="saving"
            >
              {{ saving ? "保存中..." : mode === "create" ? "创建用户" : "保存修改" }}
            </button>
            <button
              type="button"
              class="rounded-2xl border border-slate-200 px-5 py-3 text-sm text-slate-600 transition hover:border-brand-ink hover:text-brand-ink"
              @click="startCreate"
            >
              重置表单
            </button>
          </div>
        </form>
      </SectionPanel>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import MetricCard from "@/components/MetricCard.vue";
import SectionPanel from "@/components/SectionPanel.vue";
import { normalizeApiError } from "@/api/client";
import { createAdminUser, deleteAdminUser, fetchAdminUsers, updateAdminUser } from "@/api/modules/admin";
import { useAuthStore } from "@/stores/auth";
import type { AdminUserCreateRequest, AdminUserItem, AdminUserListResponse, AdminUserUpdateRequest } from "@/types/admin";
import { formatDateTime, formatRoleLabel, formatYesNo } from "@/utils/formatters";

type EditorMode = "create" | "edit";

interface UserEditorState {
  nickname: string;
  username: string;
  password: string;
  email: string;
  phone: string;
  gender: string;
  is_admin: boolean;
}

const authStore = useAuthStore();

const users = ref<AdminUserListResponse | null>(null);
const keyword = ref("");
const mode = ref<EditorMode>("create");
const editingUserId = ref<number | null>(null);
const saving = ref(false);
const deletingUserId = ref<number | null>(null);
const errorMessage = ref("");
const successMessage = ref("");
const form = reactive<UserEditorState>({
  nickname: "",
  username: "",
  password: "",
  email: "",
  phone: "",
  gender: "",
  is_admin: false,
});

const filteredUsers = computed(() => {
  const source = users.value?.items ?? [];
  if (!keyword.value) {
    return source;
  }
  const value = keyword.value.toLowerCase();
  return source.filter((item) =>
    [item.nickname, item.username, item.email, item.phone, ...item.roles]
      .map((entry) => String(entry ?? "").toLowerCase())
      .some((entry) => entry.includes(value)),
  );
});

const adminCount = computed(() => (users.value?.items ?? []).filter((item) => item.is_admin).length);
const teacherCount = computed(() => (users.value?.items ?? []).filter((item) => item.has_teacher_profile).length);
const studentCount = computed(() => (users.value?.items ?? []).filter((item) => item.has_student_profile).length);

const editorTitle = computed(() => (mode.value === "create" ? "创建后台用户" : "编辑用户资料"));
const editorDescription = computed(() =>
  mode.value === "create"
    ? "创建新的系统用户账号，并决定是否赋予后台管理员登录权限。"
    : "修改当前选中用户的基础资料。高风险约束仍由后端统一校验。",
);

function toNullable(value: string): string | null {
  const normalized = value.trim();
  return normalized ? normalized : null;
}

function resetEditor() {
  form.nickname = "";
  form.username = "";
  form.password = "";
  form.email = "";
  form.phone = "";
  form.gender = "";
  form.is_admin = false;
}

function applyCreateState(clearMessages = true) {
  mode.value = "create";
  editingUserId.value = null;
  errorMessage.value = "";
  if (clearMessages) {
    successMessage.value = "";
  }
  resetEditor();
}

function startCreate() {
  applyCreateState(true);
}

function applyEditState(user: AdminUserItem, clearMessages = true) {
  mode.value = "edit";
  editingUserId.value = user.id;
  errorMessage.value = "";
  if (clearMessages) {
    successMessage.value = "";
  }
  form.nickname = user.nickname;
  form.username = user.username;
  form.password = "";
  form.email = user.email ?? "";
  form.phone = user.phone ?? "";
  form.gender = user.gender ?? "";
  form.is_admin = user.is_admin;
}

function startEdit(user: AdminUserItem) {
  applyEditState(user, true);
}

async function loadUsers() {
  users.value = await fetchAdminUsers();
}

async function handleSave() {
  errorMessage.value = "";
  successMessage.value = "";

  if (!form.nickname || !form.username) {
    errorMessage.value = "昵称和用户名不能为空。";
    return;
  }
  if (mode.value === "create" && !form.password) {
    errorMessage.value = "创建用户时必须填写登录密码。";
    return;
  }

  saving.value = true;
  try {
    if (mode.value === "create") {
      const payload: AdminUserCreateRequest = {
        nickname: form.nickname,
        username: form.username,
        password: form.password,
        email: toNullable(form.email),
        phone: toNullable(form.phone),
        gender: toNullable(form.gender),
        is_admin: form.is_admin,
      };
      await createAdminUser(payload);
      applyCreateState(false);
      successMessage.value = "用户已创建。";
    } else if (editingUserId.value !== null) {
      const payload: AdminUserUpdateRequest = {
        nickname: form.nickname,
        username: form.username,
        email: toNullable(form.email),
        phone: toNullable(form.phone),
        gender: toNullable(form.gender),
        is_admin: form.is_admin,
      };
      if (form.password.trim()) {
        payload.password = form.password;
      }
      const updatedUser = await updateAdminUser(editingUserId.value, payload);
      applyEditState(updatedUser, false);
      successMessage.value = "用户资料已更新。";
      if (authStore.user?.id === updatedUser.id) {
        authStore.setCurrentUser(updatedUser);
      }
    }
    await loadUsers();
  } catch (error) {
    errorMessage.value = normalizeApiError(error);
  } finally {
    saving.value = false;
  }
}

async function handleDelete(user: AdminUserItem) {
  errorMessage.value = "";
  successMessage.value = "";
  if (!window.confirm(`确认删除用户「${user.nickname} / ${user.username}」吗？`)) {
    return;
  }
  deletingUserId.value = user.id;
  try {
    await deleteAdminUser(user.id);
    if (editingUserId.value === user.id) {
      applyCreateState(false);
    }
    await loadUsers();
    successMessage.value = "用户已删除。";
  } catch (error) {
    errorMessage.value = normalizeApiError(error);
  } finally {
    deletingUserId.value = null;
  }
}

onMounted(async () => {
  applyCreateState(false);
  try {
    await loadUsers();
  } catch (error) {
    errorMessage.value = normalizeApiError(error);
  }
});
</script>
