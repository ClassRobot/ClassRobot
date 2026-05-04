<template>
  <div class="flex h-[calc(100vh-96px)] min-h-0 w-full flex-col gap-4 overflow-hidden">
    <h1 class="w-full shrink-0 font-h1 text-h1 text-on-surface dark:text-zinc-100">用户中心</h1>

    <div class="flex w-full shrink-0 items-center justify-between gap-3 rounded-xl border border-outline-variant bg-surface-container-lowest p-3 dark:border-zinc-800 dark:bg-zinc-900">
      <div class="flex min-w-0 flex-1 flex-wrap items-center gap-3">
        <div class="relative min-w-[220px] flex-1 sm:flex-none">
          <Search :size="16" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant dark:text-zinc-500" />
          <input
            v-model="search"
            class="h-9 w-full rounded-lg border border-outline-variant bg-surface-container py-1.5 pl-8 pr-3 text-body-sm text-on-surface focus:border-primary focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:focus:border-primary-dark sm:w-64"
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
      <button
        type="button"
        class="shrink-0 rounded-lg border border-outline-variant p-2 text-on-surface-variant transition-colors hover:bg-surface-container dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
        @click="fetchData"
      >
        <RefreshCw :size="16" />
      </button>
    </div>

    <div class="flex min-h-0 w-full flex-1 gap-0 overflow-hidden">
      <div class="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="min-h-0 flex-1 overflow-auto">
          <table class="w-full border-collapse whitespace-nowrap text-left">
            <thead class="sticky top-0 z-10 border-b border-outline-variant bg-surface-bright dark:border-zinc-800 dark:bg-zinc-900/50">
              <tr>
                <th class="w-[74px] p-[10px_12px] text-center font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">头像</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">用户名 / ID</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">角色</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">管理员</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">绑定数</th>
                <th class="w-10 p-[10px_12px] text-center font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-outline-variant font-body-sm text-body-sm text-on-surface dark:divide-zinc-800 dark:text-zinc-200">
              <tr v-if="users.length === 0">
                <td colspan="6" class="p-8 text-center text-on-surface-variant dark:text-zinc-500">暂无用户数据</td>
              </tr>
              <tr
                v-for="user in users"
                :key="user.id"
                class="cursor-pointer transition-colors hover:bg-surface-container dark:hover:bg-zinc-800/50"
                :class="{ 'bg-surface-container dark:bg-zinc-800/30': selectedUser?.id === user.id }"
                @click="selectUser(user.id)"
              >
                <td class="p-[10px_12px]">
                  <div class="flex justify-center">
                    <div class="flex h-10 w-10 items-center justify-center overflow-hidden rounded-xl bg-primary/15 text-sm font-semibold text-primary dark:bg-primary-dark/20 dark:text-primary-dark">
                      <img
                        v-if="getUserAvatarUrl(user)"
                        :src="getUserAvatarUrl(user) || undefined"
                        :alt="`${getUserDisplayName(user)} 的头像`"
                        class="h-full w-full object-cover"
                        @error="rememberBrokenAvatar(user.avatar)"
                      />
                      <span v-else>{{ getUserInitial(user) }}</span>
                    </div>
                  </div>
                </td>
                <td class="p-[10px_12px]">
                  <div class="font-medium">{{ user.nickname || user.username }}</div>
                  <div class="font-code-inline text-[11px] text-on-surface-variant dark:text-zinc-500">UID: {{ user.id }}</div>
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
                  <button type="button" class="rounded p-1 text-on-surface-variant transition-colors hover:text-primary dark:text-zinc-400 dark:hover:text-primary-dark">
                    <ChevronRight :size="18" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="flex shrink-0 items-center justify-between border-t border-outline-variant px-4 py-2 text-[11px] text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
          <span>共 {{ total }} 个用户，第 {{ page }}/{{ totalPages }} 页</span>
          <div class="flex gap-1">
            <button
              type="button"
              :disabled="page <= 1"
              class="rounded-lg border border-outline-variant px-2 py-1 text-body-sm hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800"
              @click="page--; fetchData()"
            >
              上一页
            </button>
            <button
              type="button"
              :disabled="page >= totalPages"
              class="rounded-lg border border-outline-variant px-2 py-1 text-body-sm hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800"
              @click="page++; fetchData()"
            >
              下一页
            </button>
          </div>
        </div>
      </div>

      <aside
        v-if="selectedUser"
        class="ml-4 flex h-full min-h-0 w-drawer-min shrink-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900"
      >
        <div class="flex shrink-0 items-center justify-between border-b border-outline-variant bg-surface-bright p-4 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div class="flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center overflow-hidden rounded-lg bg-primary/15 text-sm font-semibold text-primary dark:bg-primary-dark/20 dark:text-primary-dark">
              <img
                v-if="getUserAvatarUrl(selectedUserProfile)"
                :src="getUserAvatarUrl(selectedUserProfile) || undefined"
                :alt="`${getUserDisplayName(selectedUserProfile)} 的头像`"
                class="h-full w-full object-cover"
                @error="rememberBrokenAvatar(selectedUserProfile?.avatar)"
              />
              <span v-else>{{ getUserInitial(selectedUserProfile) }}</span>
            </div>
            <div>
              <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ selectedUser.nickname || selectedUser.username }}</h2>
              <div class="font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500">UID: {{ selectedUser.id }}</div>
            </div>
          </div>
          <div class="flex items-center gap-1">
            <button
              type="button"
              class="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-error-container/45 hover:text-error dark:text-zinc-400 dark:hover:bg-red-950/30 dark:hover:text-red-300"
              title="删除账号"
              @click="openDeleteUserConfirm"
            >
              <Trash2 :size="16" />
            </button>
            <button
              type="button"
              class="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container dark:text-zinc-400 dark:hover:bg-zinc-800"
              title="关闭详情"
              @click="selectedUser = null"
            >
              <X :size="18" />
            </button>
          </div>
        </div>

        <div v-if="userDetail" class="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4">
          <section>
            <h3 class="mb-2 border-b border-outline-variant pb-1 font-label-caps text-label-caps uppercase text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">基本信息</h3>
            <div class="grid grid-cols-2 gap-x-4 gap-y-3 text-body-sm">
              <div><div class="mb-0.5 text-[11px] text-on-surface-variant dark:text-zinc-500">邮箱</div><div class="text-on-surface dark:text-zinc-200">{{ userDetail.email || '-' }}</div></div>
              <div><div class="mb-0.5 text-[11px] text-on-surface-variant dark:text-zinc-500">手机</div><div class="text-on-surface dark:text-zinc-200">{{ userDetail.phone || '-' }}</div></div>
              <div><div class="mb-0.5 text-[11px] text-on-surface-variant dark:text-zinc-500">创建时间</div><div class="text-on-surface dark:text-zinc-200">{{ formatDate(userDetail.created_at) }}</div></div>
              <div><div class="mb-0.5 text-[11px] text-on-surface-variant dark:text-zinc-500">更新时间</div><div class="text-on-surface dark:text-zinc-200">{{ formatDate(userDetail.updated_at) }}</div></div>
            </div>
          </section>

          <section>
            <h3 class="mb-2 border-b border-outline-variant pb-1 font-label-caps text-label-caps uppercase text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">权限管理</h3>
            <div class="flex items-center justify-between rounded-lg border border-outline-variant bg-surface-container p-3 dark:border-zinc-800 dark:bg-zinc-800">
              <div>
                <div class="font-medium text-body-sm text-on-surface dark:text-zinc-200">系统管理员</div>
                <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">授予完整的系统配置权限</div>
              </div>
              <button
                type="button"
                class="relative h-5 w-10 rounded-full border transition-colors"
                :class="selectedUser.is_admin ? 'border-primary bg-primary dark:bg-primary-dark' : 'border-outline-variant bg-surface-variant dark:border-zinc-600 dark:bg-zinc-700'"
                @click="toggleAdmin"
              >
                <span class="absolute top-0.5 h-3.5 w-3.5 rounded-full bg-white transition-transform" :class="selectedUser.is_admin ? 'left-5' : 'left-0.5'" />
              </button>
            </div>
          </section>

          <section>
            <h3 class="mb-2 border-b border-outline-variant pb-1 font-label-caps text-label-caps uppercase text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">平台绑定</h3>
            <div
              v-if="bindNotice"
              class="mb-3 rounded-lg border px-3 py-2 text-[12px]"
              :class="bindNoticeTone === 'success'
                ? 'border-primary/20 bg-primary/10 text-primary dark:border-primary-dark/20 dark:bg-primary-dark/10 dark:text-primary-dark'
                : 'border-error/20 bg-error-container/60 text-error dark:border-red-800/50 dark:bg-red-900/30 dark:text-red-300'"
            >
              {{ bindNotice }}
            </div>
            <div v-if="userDetail.binds?.length" class="max-h-72 space-y-2.5 overflow-y-auto pr-1">
              <article
                v-for="bind in userDetail.binds"
                :key="bind.id"
                class="overflow-hidden rounded-xl border border-outline-variant bg-surface-container dark:border-zinc-800 dark:bg-zinc-800/65"
              >
                <div class="flex items-center gap-2 p-2.5">
                  <button
                    type="button"
                    class="flex min-w-0 flex-1 items-center gap-2.5 rounded-xl px-0.5 py-0.5 text-left transition-colors hover:bg-black/[0.02] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/20 dark:hover:bg-white/[0.03] dark:focus-visible:ring-primary-dark/25"
                    :aria-expanded="isBindExpanded(bind.id)"
                    @click="toggleBindExpanded(bind.id)"
                  >
                    <span class="inline-flex h-8 min-w-8 items-center justify-center rounded-lg bg-primary/12 px-2 font-code-inline text-[11px] font-semibold text-primary dark:bg-primary-dark/15 dark:text-primary-dark">
                      {{ platformShort(bind.platform_id) }}
                    </span>
                    <div class="min-w-0 flex-1">
                      <div class="truncate text-[15px] font-semibold leading-5 text-on-surface dark:text-zinc-100">{{ bind.platform_id }}</div>
                      <div class="mt-0.5 truncate text-[11px] text-on-surface-variant dark:text-zinc-500">平台账号绑定</div>
                      <div class="mt-1 flex min-w-0 items-center gap-3 text-[11px] text-on-surface-variant dark:text-zinc-500">
                        <div class="min-w-0 flex-1 truncate">
                          <span class="mr-1">账号标识</span>
                          <span class="font-code-inline text-on-surface dark:text-zinc-300">{{ bind.account_id || '-' }}</span>
                        </div>
                        <div class="min-w-0 flex-1 truncate">
                          <span class="mr-1">绑定名称</span>
                          <span class="text-on-surface dark:text-zinc-300">{{ bind.platform_id }}</span>
                        </div>
                      </div>
                    </div>
                    <span
                      class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border border-outline-variant bg-surface-container-low text-on-surface-variant transition-transform duration-200 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400"
                      :class="isBindExpanded(bind.id) ? 'rotate-90' : ''"
                    >
                      <ChevronRight :size="15" />
                    </span>
                  </button>

                  <button
                    type="button"
                    class="group relative inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-error/20 bg-error-container/35 text-error transition-colors hover:bg-error-container/60 dark:border-red-800/40 dark:bg-red-950/30 dark:text-red-300 dark:hover:bg-red-950/45"
                    aria-label="解除绑定"
                    @click.stop="openBindConfirm(bind)"
                  >
                    <Trash2 :size="13" />
                    <span class="pointer-events-none absolute right-[calc(100%+8px)] top-1/2 z-10 -translate-y-1/2 translate-x-1 whitespace-nowrap rounded-lg border border-outline-variant bg-surface-container-lowest px-2 py-1 text-[11px] font-medium text-on-surface opacity-0 shadow-[0_10px_24px_rgba(15,23,42,0.12)] transition-all duration-150 group-hover:translate-x-0 group-hover:opacity-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:shadow-[0_12px_28px_rgba(0,0,0,0.32)]">
                      解除绑定
                    </span>
                  </button>
                </div>

                <div
                  v-if="isBindExpanded(bind.id)"
                  class="border-t border-outline-variant/80 px-3.5 pb-3.5 pt-2.5 dark:border-zinc-800"
                >
                  <div class="grid grid-cols-2 gap-3 text-body-sm">
                    <div class="col-span-2 min-w-0">
                      <div class="mb-0.5 text-[11px] text-on-surface-variant dark:text-zinc-500">账号标识</div>
                      <div class="break-all font-code-inline text-code-inline text-on-surface dark:text-zinc-200">{{ bind.account_id || '-' }}</div>
                    </div>
                    <div class="min-w-0">
                      <div class="mb-0.5 text-[11px] text-on-surface-variant dark:text-zinc-500">绑定名称</div>
                      <div class="truncate text-on-surface dark:text-zinc-200">{{ bind.platform_id }}</div>
                    </div>
                    <div class="min-w-0">
                      <div class="mb-0.5 text-[11px] text-on-surface-variant dark:text-zinc-500">平台备注</div>
                      <div class="truncate text-on-surface dark:text-zinc-200">{{ bind.name || '未设置' }}</div>
                    </div>
                    <div>
                      <div class="mb-0.5 text-[11px] text-on-surface-variant dark:text-zinc-500">创建时间</div>
                      <div class="text-on-surface dark:text-zinc-200">{{ formatDateTime(bind.created_at) }}</div>
                    </div>
                    <div>
                      <div class="mb-0.5 text-[11px] text-on-surface-variant dark:text-zinc-500">更新时间</div>
                      <div class="text-on-surface dark:text-zinc-200">{{ formatDateTime(bind.updated_at) }}</div>
                    </div>
                  </div>
                </div>
              </article>
            </div>
            <div class="rounded-xl border border-dashed border-outline-variant bg-surface-container/40 px-4 py-5 text-center text-body-sm text-on-surface-variant dark:border-zinc-800 dark:bg-zinc-800/25 dark:text-zinc-500" v-else>
              当前用户暂无平台绑定
            </div>
          </section>

          <section>
            <div class="mb-2 flex border-b border-outline-variant dark:border-zinc-800">
              <button
                type="button"
                class="px-3 py-1.5 text-body-sm font-medium"
                :class="extTab === 'teacher' ? 'text-primary -mb-px border-b-2 border-primary dark:text-primary-dark' : 'text-on-surface-variant dark:text-zinc-400'"
                @click="extTab = 'teacher'"
              >
                教师扩展
              </button>
              <button
                type="button"
                class="px-3 py-1.5 text-body-sm font-medium"
                :class="extTab === 'student' ? 'text-primary -mb-px border-b-2 border-primary dark:text-primary-dark' : 'text-on-surface-variant dark:text-zinc-400'"
                @click="extTab = 'student'"
              >
                学生扩展
              </button>
            </div>
            <div v-if="extTab === 'teacher' && userDetail.teacher" class="space-y-1 text-body-sm text-on-surface dark:text-zinc-200">
              <div>姓名：{{ userDetail.teacher.name }}</div>
              <div>学校：{{ userDetail.teacher.school_name || '-' }}</div>
              <div>学院：{{ userDetail.teacher.college_name || '-' }}</div>
            </div>
            <div v-else-if="extTab === 'teacher'" class="text-body-sm text-on-surface-variant dark:text-zinc-500">无教师扩展信息</div>
            <div v-if="extTab === 'student' && userDetail.student" class="space-y-1 text-body-sm text-on-surface dark:text-zinc-200">
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

  <Teleport to="body">
    <div
      v-if="confirmDialog"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-[2px] dark:bg-black/60"
      @click.self="closeConfirmDialog()"
    >
      <div
        class="mx-auto flex max-h-[calc(100vh-32px)] flex-col overflow-hidden rounded-[22px] border border-outline-variant bg-surface-container-lowest shadow-[0_28px_72px_rgba(15,23,42,0.22)] dark:border-zinc-800 dark:bg-zinc-900 dark:shadow-[0_30px_90px_rgba(0,0,0,0.55)]"
        :style="{ width: confirmDialogWidth }"
        @click.stop
      >
        <div class="flex items-start gap-4 border-b border-outline-variant px-5 py-4 dark:border-zinc-800">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-error/15 bg-error-container/20 text-error dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300">
            <AlertTriangle :size="18" />
          </div>
          <div class="min-w-0 flex-1">
            <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ confirmDialog.title }}</h2>
            <p class="mt-1 text-body-sm leading-6 text-on-surface-variant dark:text-zinc-400">{{ confirmDialog.message }}</p>
          </div>
          <button
            type="button"
            class="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container dark:text-zinc-400 dark:hover:bg-zinc-800"
            :disabled="confirmBusy"
            @click="closeConfirmDialog()"
          >
            <X :size="16" />
          </button>
        </div>

        <div class="min-h-0 space-y-4 overflow-y-auto px-5 py-4">
          <div class="rounded-xl border border-outline-variant bg-surface-container-low px-4 py-3 dark:border-zinc-800 dark:bg-zinc-800/55">
            <div class="text-[11px] uppercase tracking-[0.14em] text-on-surface-variant dark:text-zinc-500">操作对象</div>
            <div class="mt-2 text-body-md font-semibold text-on-surface dark:text-zinc-100">{{ confirmDialog.targetLabel }}</div>
            <div class="mt-1 break-all font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-400">{{ confirmDialog.targetHint }}</div>
          </div>

          <div v-if="confirmErrorDetail" class="rounded-xl border border-error/20 bg-error-container/14 p-4 text-body-sm text-error dark:border-red-800/50 dark:bg-red-950/25 dark:text-red-200">
            <div class="inline-flex items-center rounded-full border border-error/15 bg-surface-container-lowest px-2 py-1 font-code-inline text-[11px] dark:border-red-800/40 dark:bg-zinc-950 dark:text-red-200">
              {{ confirmErrorDetail.code }}
            </div>
            <p class="mt-3 leading-6">{{ confirmErrorDetail.message }}</p>
            <p v-if="confirmErrorDetail.hint" class="mt-2 text-[12px] leading-5 text-on-surface-variant dark:text-red-100/80">
              建议：{{ confirmErrorDetail.hint }}
            </p>
            <div v-if="confirmErrorDetail.blockers?.length" class="mt-3 space-y-3">
              <div
                v-for="blocker in confirmErrorDetail.blockers"
                :key="`${blocker.code}-${blocker.message}`"
                class="rounded-xl border border-error/15 bg-surface-container-lowest p-3 dark:border-red-800/35 dark:bg-zinc-950/75"
              >
                <div class="font-medium text-error dark:text-red-200">{{ blocker.message }}</div>
                <div v-if="blocker.items?.length" class="mt-2 flex flex-wrap gap-2">
                  <span
                    v-for="item in blocker.items"
                    :key="item"
                    class="inline-flex max-w-full items-center rounded-full border border-error/15 bg-error-container/55 px-2.5 py-1 text-[11px] text-error dark:border-red-800/40 dark:bg-red-950/30 dark:text-red-200"
                  >
                    {{ item }}
                  </span>
                </div>
              </div>
            </div>
            <p v-if="confirmErrorDetail.detail" class="mt-3 rounded-xl bg-surface-container-lowest p-3 font-code-inline text-code-inline text-on-surface-variant dark:bg-zinc-950 dark:text-red-100/80">
              {{ confirmErrorDetail.detail }}
            </p>
          </div>
        </div>

        <div class="flex items-center justify-end gap-2 border-t border-outline-variant px-5 py-4 dark:border-zinc-800">
          <button
            type="button"
            class="rounded-lg border border-outline-variant px-4 py-2 text-body-sm text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
            :disabled="confirmBusy"
            @click="closeConfirmDialog()"
          >
            取消
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-lg border border-error/20 bg-error px-4 py-2 text-body-sm font-medium text-on-error transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-900/50 dark:bg-red-900 dark:text-white"
            :disabled="confirmBusy"
            @click="confirmDangerAction"
          >
            <Loader2 v-if="confirmBusy" :size="14" class="animate-spin" />
            <Trash2 v-else :size="14" />
            {{ confirmDialog.confirmLabel }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { deleteUser, deleteUserBind, fetchUserDetail, fetchUsers, patchUserAdmin } from '@/api/users'
import type {
  UserBindInfo,
  UserDetail,
  UserMutationErrorDetail,
  UserSummary,
} from '@/types/api'
import {
  AlertTriangle,
  ChevronRight,
  Loader2,
  RefreshCw,
  Search,
  Trash2,
  X,
} from 'lucide-vue-next'
import AppSelect from '@/components/AppSelect.vue'
import StatusChip from '@/components/StatusChip.vue'

interface ConfirmDialogState {
  kind: 'unbind' | 'delete-user'
  userId: number
  bindId?: number
  title: string
  message: string
  confirmLabel: string
  targetLabel: string
  targetHint: string
}

interface UserAvatarLike {
  nickname?: string | null
  username?: string | null
  avatar?: string | null
}

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
const expandedBindIds = ref<number[]>([])
const bindNotice = ref('')
const bindNoticeTone = ref<'success' | 'error'>('success')
const confirmDialog = ref<ConfirmDialogState | null>(null)
const confirmBusy = ref(false)
const confirmErrorDetail = ref<UserMutationErrorDetail | null>(null)
const brokenAvatarUrls = ref<string[]>([])

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
const confirmDialogWidth = computed(() =>
  confirmErrorDetail.value
    ? 'min(680px, calc(100vw - 32px))'
    : 'min(460px, calc(100vw - 32px))',
)
const selectedUserProfile = computed<UserAvatarLike | null>(() => userDetail.value ?? selectedUser.value)

let searchTimer: ReturnType<typeof setTimeout> | undefined

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchData()
  }, 300)
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
  } catch {
    /* silent */
  }
}

async function selectUser(id: number) {
  const user = users.value.find((item) => item.id === id)
  if (!user) return
  selectedUser.value = user
  extTab.value = 'teacher'
  expandedBindIds.value = []
  bindNotice.value = ''
  try {
    userDetail.value = await fetchUserDetail(id)
  } catch {
    userDetail.value = null
  }
}

async function toggleAdmin() {
  if (!selectedUser.value) return
  try {
    const updated = await patchUserAdmin(selectedUser.value.id, { is_admin: !selectedUser.value.is_admin })
    Object.assign(selectedUser.value, updated)
    if (userDetail.value) Object.assign(userDetail.value, updated)
  } catch {
    /* silent */
  }
}

function isBindExpanded(bindId: number) {
  return expandedBindIds.value.includes(bindId)
}

function toggleBindExpanded(bindId: number) {
  expandedBindIds.value = isBindExpanded(bindId)
    ? expandedBindIds.value.filter((id) => id !== bindId)
    : [...expandedBindIds.value, bindId]
}

function getUserDisplayName(user: UserAvatarLike | null | undefined) {
  const displayName = (user?.nickname || user?.username || '未知用户').trim()
  return displayName || '未知用户'
}

function getUserInitial(user: UserAvatarLike | null | undefined) {
  return getUserDisplayName(user).charAt(0).toUpperCase() || '?'
}

function getUserAvatarUrl(user: UserAvatarLike | null | undefined) {
  const avatarUrl = user?.avatar?.trim()
  if (!avatarUrl) return null
  return brokenAvatarUrls.value.includes(avatarUrl) ? null : avatarUrl
}

function rememberBrokenAvatar(avatarUrl: string | null | undefined) {
  const normalizedAvatarUrl = avatarUrl?.trim()
  if (!normalizedAvatarUrl || brokenAvatarUrls.value.includes(normalizedAvatarUrl)) {
    return
  }
  brokenAvatarUrls.value = [...brokenAvatarUrls.value, normalizedAvatarUrl]
}

function openBindConfirm(bind: UserBindInfo) {
  if (!selectedUser.value) return
  confirmErrorDetail.value = null
  confirmDialog.value = {
    kind: 'unbind',
    userId: selectedUser.value.id,
    bindId: bind.id,
    title: '确认解除平台绑定',
    message: '将移除当前平台账号与该用户之间的绑定关系，后续如需恢复需要重新绑定。',
    confirmLabel: '确认解除',
    targetLabel: bind.platform_id,
    targetHint: `账号 ID: ${bind.account_id || '-'}`,
  }
}

function openDeleteUserConfirm() {
  if (!selectedUser.value) return
  confirmErrorDetail.value = null
  confirmDialog.value = {
    kind: 'delete-user',
    userId: selectedUser.value.id,
    title: '确认删除账号',
    message: '将删除当前用户账号及其可级联清理的数据。该操作不可恢复，建议确认关联关系已经处理完毕。',
    confirmLabel: '确认删除',
    targetLabel: selectedUser.value.nickname || selectedUser.value.username,
    targetHint: `UID: ${selectedUser.value.id} · 绑定数: ${selectedUser.value.bind_count}`,
  }
}

function closeConfirmDialog(force = false) {
  if (confirmBusy.value && !force) return
  confirmDialog.value = null
  confirmErrorDetail.value = null
}

async function confirmDangerAction() {
  const dialog = confirmDialog.value
  if (!dialog) return

  confirmBusy.value = true
  confirmErrorDetail.value = null

  try {
    if (dialog.kind === 'unbind' && typeof dialog.bindId === 'number') {
      await executeBindRemoval(dialog.userId, dialog.bindId)
    } else {
      await executeUserDelete(dialog.userId)
    }
    closeConfirmDialog(true)
  } catch (error) {
    confirmErrorDetail.value = parseUserMutationError(
      error,
      dialog.kind === 'unbind' ? '解除绑定失败，请稍后重试。' : '删除账号失败，请稍后重试。',
    )
  } finally {
    confirmBusy.value = false
  }
}

async function executeBindRemoval(userId: number, bindId: number) {
  await deleteUserBind(userId, bindId)

  const summary = users.value.find((item) => item.id === userId)
  if (summary && summary.bind_count > 0) {
    summary.bind_count -= 1
  }

  if (userDetail.value?.id === userId) {
    userDetail.value.binds = userDetail.value.binds.filter((bind) => bind.id !== bindId)
    expandedBindIds.value = expandedBindIds.value.filter((id) => id !== bindId)
    if (userDetail.value.bind_count > 0) {
      userDetail.value.bind_count -= 1
    }
  }

  bindNoticeTone.value = 'success'
  bindNotice.value = '平台绑定已解除'
}

async function executeUserDelete(userId: number) {
  await deleteUser(userId)

  const nextTotal = Math.max(0, total.value - 1)
  const nextPage = Math.max(1, Math.ceil(nextTotal / pageSize))
  if (page.value > nextPage) {
    page.value = nextPage
  }

  users.value = users.value.filter((item) => item.id !== userId)
  total.value = nextTotal

  if (selectedUser.value?.id === userId) {
    selectedUser.value = null
    userDetail.value = null
    expandedBindIds.value = []
    bindNotice.value = ''
  }

  await fetchData()
}

function formatDate(iso: string) {
  try {
    return new Date(iso).toLocaleDateString('zh-CN')
  } catch {
    return iso
  }
}

function formatDateTime(iso: string) {
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

function platformShort(platformId: string) {
  const labels: Record<string, string> = {
    'qq.qq_api': 'QQ',
    'onebot11.qq_client': 'OB11',
    'onebot12.qq_client': 'OB12',
  }
  return labels[platformId] || 'BIND'
}

function parseUserMutationError(error: unknown, fallback: string): UserMutationErrorDetail {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return {
      code: 'request_failed',
      message: detail,
    }
  }
  if (isRecord(detail)) {
    return {
      code: readString(detail.code, 'user_action_failed'),
      message: readString(detail.message, fallback),
      hint: readOptionalString(detail.hint),
      detail: readOptionalString(detail.detail),
      blockers: Array.isArray(detail.blockers)
        ? detail.blockers
            .filter(isRecord)
            .map((item) => ({
              code: readString(item.code, 'user_blocker'),
              message: readString(item.message, '存在未清理的关联数据'),
              items: readStringArray(item.items),
            }))
        : [],
    }
  }
  return {
    code: 'user_action_failed',
    message: readString((error as { message?: unknown }).message, fallback),
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function readString(value: unknown, fallback: string) {
  return typeof value === 'string' && value.trim() ? value : fallback
}

function readOptionalString(value: unknown) {
  return typeof value === 'string' && value.trim() ? value : undefined
}

function readStringArray(value: unknown) {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
}
</script>
