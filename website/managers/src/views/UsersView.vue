<template>
  <div class="flex flex-col h-full gap-4">
    <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100 shrink-0">用户中心</h1>

    <!-- Toolbar -->
    <div class="flex items-center justify-between rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 p-3 shrink-0">
      <div class="flex items-center gap-3">
        <div class="relative">
          <Search :size="16" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant dark:text-zinc-500" />
          <input
            v-model="search"
            class="pl-8 pr-3 py-1.5 text-body-sm rounded-lg border border-outline-variant dark:border-zinc-700 bg-surface-container dark:bg-zinc-800 text-on-surface dark:text-zinc-200 focus:outline-none focus:border-primary dark:focus:border-primary-dark w-64"
            placeholder="搜索用户..."
            @input="onSearch"
          />
        </div>
        <AppSelect
          v-model="roleFilter"
          :options="roleOptions"
          wrapper-class="w-[132px]"
          @change="fetchData"
        />
        <AppSelect
          v-model="adminFilter"
          :options="adminOptions"
          wrapper-class="w-[148px]"
          @change="fetchData"
        />
      </div>
      <button @click="fetchData" class="p-2 rounded-lg border border-outline-variant dark:border-zinc-700 text-on-surface-variant dark:text-zinc-400 hover:bg-surface-container dark:hover:bg-zinc-800 transition-colors">
        <RefreshCw :size="16" />
      </button>
    </div>

    <!-- Content area with table + optional drawer -->
    <div class="flex flex-1 min-h-0 gap-0">
      <div class="flex-1 flex flex-col min-w-0 rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 overflow-hidden">
        <div class="overflow-auto flex-1">
          <table class="w-full text-left border-collapse whitespace-nowrap">
            <thead class="bg-surface-bright dark:bg-zinc-900/50 border-b border-outline-variant dark:border-zinc-800 sticky top-0 z-10">
              <tr>
                <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">用户名 / ID</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">角色</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">管理员</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">绑定数</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase w-10 text-center">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-outline-variant dark:divide-zinc-800 font-body-sm text-body-sm text-on-surface dark:text-zinc-200">
              <tr v-if="users.length === 0">
                <td colspan="5" class="p-8 text-center text-on-surface-variant dark:text-zinc-500">暂无用户数据</td>
              </tr>
              <tr
                v-for="user in users"
                :key="user.id"
                class="hover:bg-surface-container dark:hover:bg-zinc-800/50 cursor-pointer transition-colors"
                :class="{ 'bg-surface-container dark:bg-zinc-800/30': selectedUser?.id === user.id }"
                @click="selectUser(user.id)"
              >
                <td class="p-[10px_12px]">
                  <div class="font-medium">{{ user.nickname || user.username }}</div>
                  <div class="text-[11px] text-on-surface-variant dark:text-zinc-500 font-code-inline">UID: {{ user.id }}</div>
                </td>
                <td class="p-[10px_12px]">
                  <span class="inline-flex items-center gap-1 text-on-surface-variant dark:text-zinc-400">
                    {{ user.roles?.join(', ') || '普通用户' }}
                  </span>
                </td>
                <td class="p-[10px_12px]">
                  <StatusChip :status="user.is_admin ? 'success' : 'not_configured'" />
                </td>
                <td class="p-[10px_12px] text-on-surface-variant dark:text-zinc-400">{{ user.bind_count }}</td>
                <td class="p-[10px_12px] text-center">
                  <button class="p-1 text-on-surface-variant dark:text-zinc-400 hover:text-primary dark:hover:text-primary-dark rounded transition-colors">
                    <ChevronRight :size="18" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="flex items-center justify-between px-4 py-2 border-t border-outline-variant dark:border-zinc-800 text-[11px] text-on-surface-variant dark:text-zinc-500">
          <span>共 {{ total }} 个用户，第 {{ page }}/{{ totalPages }} 页</span>
          <div class="flex gap-1">
            <button :disabled="page <= 1" @click="page--; fetchData()" class="px-2 py-1 rounded-lg border border-outline-variant dark:border-zinc-700 hover:bg-surface-container dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed text-body-sm">上一页</button>
            <button :disabled="page >= totalPages" @click="page++; fetchData()" class="px-2 py-1 rounded-lg border border-outline-variant dark:border-zinc-700 hover:bg-surface-container dark:hover:bg-zinc-800 disabled:opacity-40 disabled:cursor-not-allowed text-body-sm">下一页</button>
          </div>
        </div>
      </div>

      <!-- Detail drawer -->
      <aside v-if="selectedUser" class="w-drawer-min shrink-0 border-l border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 flex flex-col overflow-hidden ml-4 rounded-xl border">
        <div class="flex items-center justify-between p-4 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 dark:bg-primary-dark/20 text-primary dark:text-primary-dark font-semibold text-sm">
              {{ (selectedUser.nickname || selectedUser.username).charAt(0).toUpperCase() }}
            </div>
            <div>
              <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ selectedUser.nickname || selectedUser.username }}</h2>
              <div class="font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500">UID: {{ selectedUser.id }}</div>
            </div>
          </div>
          <button @click="selectedUser = null" class="p-1.5 text-on-surface-variant dark:text-zinc-400 hover:bg-surface-container dark:hover:bg-zinc-800 rounded-lg transition-colors">
            <X :size="18" />
          </button>
        </div>

        <div class="flex-1 overflow-y-auto p-4 flex flex-col gap-5" v-if="userDetail">
          <!-- Basic info -->
          <section>
            <h3 class="font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase mb-2 pb-1 border-b border-outline-variant dark:border-zinc-800">基本信息</h3>
            <div class="grid grid-cols-2 gap-y-3 gap-x-4 text-body-sm">
              <div><div class="text-[11px] text-on-surface-variant dark:text-zinc-500 mb-0.5">邮箱</div><div class="text-on-surface dark:text-zinc-200">{{ userDetail.email || '-' }}</div></div>
              <div><div class="text-[11px] text-on-surface-variant dark:text-zinc-500 mb-0.5">手机</div><div class="text-on-surface dark:text-zinc-200">{{ userDetail.phone || '-' }}</div></div>
              <div><div class="text-[11px] text-on-surface-variant dark:text-zinc-500 mb-0.5">创建时间</div><div class="text-on-surface dark:text-zinc-200">{{ formatDate(userDetail.created_at) }}</div></div>
              <div><div class="text-[11px] text-on-surface-variant dark:text-zinc-500 mb-0.5">更新时间</div><div class="text-on-surface dark:text-zinc-200">{{ formatDate(userDetail.updated_at) }}</div></div>
            </div>
          </section>

          <!-- Permissions -->
          <section>
            <h3 class="font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase mb-2 pb-1 border-b border-outline-variant dark:border-zinc-800">权限管理</h3>
            <div class="flex items-center justify-between rounded-lg border border-outline-variant dark:border-zinc-800 bg-surface-container dark:bg-zinc-800 p-3">
              <div>
                <div class="font-medium text-body-sm text-on-surface dark:text-zinc-200">系统管理员</div>
                <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">授予完整的系统配置权限</div>
              </div>
              <button
                @click="toggleAdmin"
                class="relative w-10 h-5 rounded-full border transition-colors"
                :class="selectedUser.is_admin ? 'bg-primary dark:bg-primary-dark border-primary' : 'bg-surface-variant dark:bg-zinc-700 border-outline-variant dark:border-zinc-600'"
              >
                <span class="absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white transition-transform" :class="selectedUser.is_admin ? 'left-5' : 'left-0.5'" />
              </button>
            </div>
          </section>

          <!-- Platform bindings -->
          <section v-if="userDetail.binds?.length">
            <h3 class="font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase mb-2 pb-1 border-b border-outline-variant dark:border-zinc-800">平台绑定</h3>
            <div class="rounded-lg border border-outline-variant dark:border-zinc-800 bg-code dark:bg-zinc-800 p-3 font-code-block text-code-block text-on-surface dark:text-zinc-300 overflow-x-auto">
              <pre class="whitespace-pre-wrap"><code>{{ JSON.stringify(userDetail.binds, null, 2) }}</code></pre>
            </div>
          </section>

          <!-- Teacher / Student extensions -->
          <section>
            <div class="flex border-b border-outline-variant dark:border-zinc-800 mb-2">
              <button class="px-3 py-1.5 text-body-sm font-medium" :class="extTab === 'teacher' ? 'text-primary dark:text-primary-dark border-b-2 border-primary -mb-px' : 'text-on-surface-variant dark:text-zinc-400'" @click="extTab = 'teacher'">教师扩展</button>
              <button class="px-3 py-1.5 text-body-sm font-medium" :class="extTab === 'student' ? 'text-primary dark:text-primary-dark border-b-2 border-primary -mb-px' : 'text-on-surface-variant dark:text-zinc-400'" @click="extTab = 'student'">学生扩展</button>
            </div>
            <div v-if="extTab === 'teacher' && userDetail.teacher" class="text-body-sm text-on-surface dark:text-zinc-200 space-y-1">
              <div>姓名：{{ userDetail.teacher.name }}</div>
              <div>学校：{{ userDetail.teacher.school_name || '-' }}</div>
              <div>学院：{{ userDetail.teacher.college_name || '-' }}</div>
            </div>
            <div v-else-if="extTab === 'teacher'" class="text-body-sm text-on-surface-variant dark:text-zinc-500">无教师扩展信息</div>
            <div v-if="extTab === 'student' && userDetail.student" class="text-body-sm text-on-surface dark:text-zinc-200 space-y-1">
              <div>姓名：{{ userDetail.student.name }}</div>
              <div>班级：{{ userDetail.student.classes_name || '-' }}</div>
              <div>学校：{{ userDetail.student.school_name || '-' }}</div>
            </div>
            <div v-else-if="extTab === 'student'" class="text-body-sm text-on-surface-variant dark:text-zinc-500">无学生扩展信息</div>
          </section>
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { fetchUsers, fetchUserDetail, patchUserAdmin } from '@/api/users'
import type { UserSummary, UserDetail } from '@/types/api'
import { Search, RefreshCw, ChevronRight, X } from 'lucide-vue-next'
import AppSelect from '@/components/AppSelect.vue'
import StatusChip from '@/components/StatusChip.vue'

const users = ref<UserSummary[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const search = ref('')
const roleFilter = ref('')
const adminFilter = ref('')
const selectedUser = ref<UserSummary | null>(null)
const userDetail = ref<UserDetail | null>(null)
const extTab = ref<'teacher' | 'student'>('teacher')
const roleOptions = [
  { label: '全部角色', value: '' },
  { label: '教师', value: 'teacher' },
  { label: '学生', value: 'student' },
  { label: '管理员', value: 'admin' },
]
const adminOptions = [
  { label: '管理员：不限', value: '' },
  { label: '管理员：是', value: 'true' },
  { label: '管理员：否', value: 'false' },
]

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))

let searchTimer: ReturnType<typeof setTimeout>
function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { page.value = 1; fetchData() }, 300)
}

onMounted(() => fetchData())

async function fetchData() {
  try {
    const res = await fetchUsers({
      q: search.value || undefined,
      role: roleFilter.value || undefined,
      is_admin: adminFilter.value === '' ? undefined : adminFilter.value === 'true',
      page: page.value,
      page_size: pageSize,
    })
    users.value = res.items
    total.value = res.total
  } catch { /* silent */ }
}

async function selectUser(id: number) {
  const user = users.value.find(u => u.id === id)
  if (!user) return
  selectedUser.value = user
  try {
    userDetail.value = await fetchUserDetail(id)
  } catch { userDetail.value = null }
}

async function toggleAdmin() {
  if (!selectedUser.value) return
  try {
    const updated = await patchUserAdmin(selectedUser.value.id, { is_admin: !selectedUser.value.is_admin })
    Object.assign(selectedUser.value, updated)
    if (userDetail.value) Object.assign(userDetail.value, updated)
  } catch { /* silent */ }
}

function formatDate(iso: string) {
  try { return new Date(iso).toLocaleDateString('zh-CN') } catch { return iso }
}
</script>
