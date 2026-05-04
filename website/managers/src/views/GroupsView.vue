<template>
  <div class="flex h-[calc(100vh-96px)] min-h-0 w-full flex-col gap-4 overflow-hidden">
    <h1 class="w-full shrink-0 font-h1 text-h1 text-on-surface dark:text-zinc-100">群组中心</h1>

    <div class="flex w-full shrink-0 items-center justify-between gap-3 rounded-xl border border-outline-variant bg-surface-container-lowest p-3 dark:border-zinc-800 dark:bg-zinc-900">
      <div class="flex min-w-0 flex-1 flex-wrap items-center gap-3">
        <div class="relative min-w-[240px] flex-1 sm:flex-none">
          <Search :size="16" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant dark:text-zinc-500" />
          <input
            v-model="search"
            class="h-9 w-full rounded-lg border border-outline-variant bg-surface-container py-1.5 pl-8 pr-3 text-body-sm text-on-surface focus:border-primary focus:outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:focus:border-primary-dark sm:w-72"
            placeholder="搜索群组、班级、平台..."
            @input="onSearch"
          />
        </div>
        <AppSelect
          v-model="platformFilter"
          :options="platformOptions"
          wrapper-class="w-[142px]"
          @change="fetchData"
        />
        <AppSelect
          v-model="joinMethodFilter"
          :options="joinMethodOptions"
          wrapper-class="w-[150px]"
          @change="fetchData"
        />
      </div>
      <button
        type="button"
        class="shrink-0 rounded-lg border border-outline-variant p-2 text-on-surface-variant transition-colors hover:bg-surface-container dark:border-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800"
        title="刷新群组列表"
        @click="fetchData"
      >
        <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
      </button>
    </div>

    <div class="flex min-h-0 w-full flex-1 gap-0 overflow-hidden">
      <div class="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="min-h-0 flex-1 overflow-auto">
          <table class="w-full border-collapse whitespace-nowrap text-left">
            <thead class="sticky top-0 z-10 border-b border-outline-variant bg-surface-bright dark:border-zinc-800 dark:bg-zinc-900/50">
              <tr>
                <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">群组 / 班级</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">平台绑定</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">创建者</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">教师 / 学生</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">入群方式</th>
                <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">申请</th>
                <th class="w-10 p-[10px_12px] text-center font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-outline-variant font-body-sm text-body-sm text-on-surface dark:divide-zinc-800 dark:text-zinc-200">
              <tr v-if="listError">
                <td colspan="7" class="p-8 text-center text-error dark:text-red-300">{{ listError }}</td>
              </tr>
              <tr v-else-if="groups.length === 0">
                <td colspan="7" class="p-8 text-center text-on-surface-variant dark:text-zinc-500">暂无群组数据</td>
              </tr>
              <tr
                v-for="group in groups"
                :key="group.id"
                class="cursor-pointer transition-colors hover:bg-surface-container dark:hover:bg-zinc-800/50"
                :class="{ 'bg-surface-container dark:bg-zinc-800/30': selectedGroup?.id === group.id }"
                @click="selectGroup(group.id)"
              >
                <td class="p-[10px_12px]">
                  <div class="flex min-w-0 items-center gap-3">
                    <div class="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/12 text-primary dark:bg-primary-dark/15 dark:text-primary-dark">
                      <component :is="group.class_info ? School : MessageSquare" :size="18" />
                    </div>
                    <div class="min-w-0">
                      <div class="truncate font-medium">{{ group.name }}</div>
                      <div class="truncate text-[11px] text-on-surface-variant dark:text-zinc-500">
                        {{ group.class_info?.name || '未关联班级' }}
                      </div>
                    </div>
                  </div>
                </td>
                <td class="p-[10px_12px]">
                  <div class="flex max-w-[220px] flex-wrap gap-1.5">
                    <span
                      v-for="platform in group.platforms"
                      :key="platform"
                      class="rounded-full border border-outline-variant bg-surface-container-low px-2 py-0.5 font-code-inline text-[11px] text-on-surface-variant dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400"
                    >
                      {{ platformShort(platform) }}
                    </span>
                    <span v-if="group.platforms.length === 0" class="text-on-surface-variant dark:text-zinc-500">-</span>
                  </div>
                </td>
                <td class="p-[10px_12px]">
                  <div class="flex items-center gap-2">
                    <UserAvatar :user="group.creator" size="sm" />
                    <div class="min-w-0">
                      <div class="truncate">{{ group.creator?.nickname || group.creator?.username || '-' }}</div>
                      <div class="font-code-inline text-[11px] text-on-surface-variant dark:text-zinc-500">
                        UID: {{ group.creator?.id || '-' }}
                      </div>
                    </div>
                  </div>
                </td>
                <td class="p-[10px_12px] text-on-surface-variant dark:text-zinc-400">
                  {{ group.teacher_count }} / {{ group.student_count }}
                </td>
                <td class="p-[10px_12px]">
                  <span class="inline-flex rounded-full border border-outline-variant bg-surface-container-low px-2 py-0.5 text-[11px] text-on-surface-variant dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-400">
                    {{ joinMethodLabel(group.join_method) }}
                  </span>
                </td>
                <td class="p-[10px_12px] text-on-surface-variant dark:text-zinc-400">
                  {{ group.pending_join_count }}
                </td>
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
          <span>共 {{ total }} 个群组，第 {{ page }}/{{ totalPages }} 页</span>
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
        v-if="selectedGroup"
        class="ml-4 flex h-full min-h-0 w-drawer-min shrink-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900"
      >
        <div class="flex shrink-0 items-center justify-between border-b border-outline-variant bg-surface-bright p-4 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div class="flex min-w-0 items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/15 text-primary dark:bg-primary-dark/20 dark:text-primary-dark">
              <component :is="selectedGroup.class_info ? School : MessageSquare" :size="20" />
            </div>
            <div class="min-w-0">
              <h2 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ selectedGroup.name }}</h2>
              <div class="truncate text-[11px] text-on-surface-variant dark:text-zinc-500">
                {{ selectedGroup.class_info?.name || '未关联班级' }}
              </div>
            </div>
          </div>
          <button
            type="button"
            class="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container dark:text-zinc-400 dark:hover:bg-zinc-800"
            title="关闭详情"
            @click="selectedGroup = null; groupDetail = null; detailError = ''"
          >
            <X :size="18" />
          </button>
        </div>

        <div v-if="groupDetail" class="flex min-h-0 flex-1 flex-col gap-5 overflow-y-auto p-4">
          <section>
            <h3 class="mb-2 border-b border-outline-variant pb-1 font-label-caps text-label-caps uppercase text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">组织概况</h3>
            <div class="grid grid-cols-3 gap-2">
              <div class="rounded-lg border border-outline-variant bg-surface-container p-3 dark:border-zinc-800 dark:bg-zinc-800/65">
                <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">教师</div>
                <div class="mt-1 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ groupDetail.teacher_count }}</div>
              </div>
              <div class="rounded-lg border border-outline-variant bg-surface-container p-3 dark:border-zinc-800 dark:bg-zinc-800/65">
                <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">学生</div>
                <div class="mt-1 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ groupDetail.student_count }}</div>
              </div>
              <div class="rounded-lg border border-outline-variant bg-surface-container p-3 dark:border-zinc-800 dark:bg-zinc-800/65">
                <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">申请</div>
                <div class="mt-1 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ groupDetail.pending_join_count }}</div>
              </div>
            </div>
          </section>

          <section>
            <h3 class="mb-2 border-b border-outline-variant pb-1 font-label-caps text-label-caps uppercase text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">班级信息</h3>
            <div v-if="groupDetail.class_detail" class="grid grid-cols-2 gap-x-4 gap-y-3 text-body-sm">
              <InfoItem label="班级名称" :value="groupDetail.class_detail.name" />
              <InfoItem label="入群方式" :value="joinMethodLabel(groupDetail.join_method)" />
              <InfoItem label="学校" :value="groupDetail.class_detail.school_name || '-'" />
              <InfoItem label="学院" :value="groupDetail.class_detail.college_name || '-'" />
              <InfoItem label="专业" :value="groupDetail.class_detail.major_name || '-'" />
              <InfoItem label="更新时间" :value="formatDate(groupDetail.class_detail.updated_at)" />
            </div>
            <div v-else class="rounded-xl border border-dashed border-outline-variant bg-surface-container/40 px-4 py-5 text-center text-body-sm text-on-surface-variant dark:border-zinc-800 dark:bg-zinc-800/25 dark:text-zinc-500">
              当前群组暂无班级信息
            </div>
          </section>

          <section>
            <h3 class="mb-2 border-b border-outline-variant pb-1 font-label-caps text-label-caps uppercase text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">平台绑定</h3>
            <div v-if="groupDetail.binds.length" class="max-h-44 space-y-2 overflow-y-auto pr-1">
              <article
                v-for="bind in groupDetail.binds"
                :key="bind.id"
                class="rounded-lg border border-outline-variant bg-surface-container p-3 dark:border-zinc-800 dark:bg-zinc-800/65"
              >
                <div class="flex items-start justify-between gap-3">
                  <div class="min-w-0">
                    <div class="truncate font-medium text-on-surface dark:text-zinc-100">{{ bind.platform_id }}</div>
                    <div class="mt-1 truncate text-[11px] text-on-surface-variant dark:text-zinc-500">{{ bind.name || '未命名平台' }}</div>
                  </div>
                  <span class="shrink-0 rounded-full bg-primary/10 px-2 py-0.5 font-code-inline text-[11px] text-primary dark:bg-primary-dark/15 dark:text-primary-dark">
                    {{ platformShort(bind.platform_id) }}
                  </span>
                </div>
                <div class="mt-3 grid grid-cols-2 gap-3 text-body-sm">
                  <InfoItem label="频道 / 群" :value="bind.channel_id" mono />
                  <InfoItem label="Guild" :value="bind.guild_id || '-'" mono />
                </div>
              </article>
            </div>
            <div v-else class="rounded-xl border border-dashed border-outline-variant bg-surface-container/40 px-4 py-5 text-center text-body-sm text-on-surface-variant dark:border-zinc-800 dark:bg-zinc-800/25 dark:text-zinc-500">
              当前群组暂无平台绑定
            </div>
          </section>

          <section>
            <div class="mb-2 flex border-b border-outline-variant dark:border-zinc-800">
              <button
                v-for="tab in memberTabs"
                :key="tab.value"
                type="button"
                class="px-3 py-1.5 text-body-sm font-medium"
                :class="memberTab === tab.value ? 'text-primary -mb-px border-b-2 border-primary dark:text-primary-dark' : 'text-on-surface-variant dark:text-zinc-400'"
                @click="memberTab = tab.value"
              >
                {{ tab.label }}
              </button>
            </div>
            <div class="max-h-72 overflow-y-auto pr-1">
              <div v-if="memberTab === 'teachers'" class="space-y-2">
                <MemberRow
                  v-for="teacher in groupDetail.teachers"
                  :key="teacher.id"
                  :user="teacher.user"
                  :name="teacher.name"
                  :sub="teacher.college_name || teacher.school_name || '-'"
                  :meta="teacher.class_role || teacher.role || '-'"
                />
                <EmptyRow v-if="groupDetail.teachers.length === 0" text="暂无教师信息" />
              </div>
              <div v-else-if="memberTab === 'students'" class="space-y-2">
                <MemberRow
                  v-for="student in groupDetail.students"
                  :key="student.id"
                  :user="student.user"
                  :name="student.name"
                  :sub="student.school_name || '-'"
                  :meta="student.role || '-'"
                />
                <EmptyRow v-if="groupDetail.students.length === 0" text="暂无学生信息" />
              </div>
              <div v-else class="space-y-2">
                <MemberRow
                  v-for="request in groupDetail.join_requests"
                  :key="request.id"
                  :user="request.user"
                  :name="request.user?.nickname || request.user?.username || '未知用户'"
                  :sub="request.describe || '未填写说明'"
                  :meta="formatDate(request.created_at)"
                />
                <EmptyRow v-if="groupDetail.join_requests.length === 0" text="暂无入班申请" />
              </div>
            </div>
          </section>
        </div>
        <div v-else-if="detailError" class="flex min-h-0 flex-1 items-center justify-center p-4">
          <div class="w-full rounded-xl border border-error/20 bg-error-container/55 px-4 py-5 text-center text-body-sm text-on-error-container dark:border-red-900/60 dark:bg-red-950/35 dark:text-red-300">
            {{ detailError }}
          </div>
        </div>
        <div v-else class="flex min-h-0 flex-1 items-center justify-center text-body-sm text-on-surface-variant dark:text-zinc-500">
          加载中...
        </div>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { ChevronRight, MessageSquare, RefreshCw, School, Search, X } from 'lucide-vue-next'
import AppSelect from '@/components/AppSelect.vue'
import { fetchGroupDetail, fetchGroups } from '@/api/groups'
import type { GroupDetail, GroupSummary, ManagerUserBrief } from '@/types/api'

const pageSize = 20
const groups = ref<GroupSummary[]>([])
const total = ref(0)
const page = ref(1)
const search = ref('')
const platformFilter = ref('')
const joinMethodFilter = ref('')
const selectedGroup = ref<GroupSummary | null>(null)
const groupDetail = ref<GroupDetail | null>(null)
const loading = ref(false)
const listError = ref('')
const detailError = ref('')
const memberTab = ref<'teachers' | 'students' | 'requests'>('teachers')
let searchTimer: ReturnType<typeof setTimeout> | undefined

const joinMethodOptions = [
  { label: '入群方式：不限', value: '' },
  { label: '直接加入', value: 'direct' },
  { label: '申请加入', value: 'apply' },
  { label: '邀请加入', value: 'invite' },
]

const platformOptions = computed(() => {
  const platformIds = new Set<string>()
  for (const group of groups.value) {
    for (const platform of group.platforms) {
      platformIds.add(platform)
    }
  }
  const dynamicOptions = [...platformIds].sort().map((platform) => ({
    label: platformShort(platform),
    value: platform,
  }))
  return [{ label: '全部平台', value: '' }, ...dynamicOptions]
})

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const memberTabs = [
  { label: '教师', value: 'teachers' as const },
  { label: '学生', value: 'students' as const },
  { label: '申请', value: 'requests' as const },
]

onMounted(() => fetchData())

function onSearch() {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchData()
  }, 300)
}

async function fetchData() {
  loading.value = true
  listError.value = ''
  try {
    const res = await fetchGroups({
      q: search.value || undefined,
      platform_id: platformFilter.value || undefined,
      join_method: joinMethodFilter.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    groups.value = res.items
    total.value = res.total
    if (selectedGroup.value && !groups.value.some((item) => item.id === selectedGroup.value?.id)) {
      selectedGroup.value = null
      groupDetail.value = null
      detailError.value = ''
    }
  } catch (e: unknown) {
    listError.value = getErrorMessage(e, '无法加载群组列表，请确认后端服务状态后重试')
    groups.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function selectGroup(groupId: number) {
  const group = groups.value.find((item) => item.id === groupId)
  if (!group) return
  selectedGroup.value = group
  memberTab.value = 'teachers'
  groupDetail.value = null
  detailError.value = ''
  try {
    groupDetail.value = await fetchGroupDetail(groupId)
  } catch (e: unknown) {
    detailError.value = getErrorMessage(e, '无法加载群组详情，请稍后重试')
  }
}

function joinMethodLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    direct: '直接加入',
    apply: '申请加入',
    invite: '邀请加入',
  }
  return value ? labels[value] || value : '未配置'
}

function platformShort(platformId: string) {
  const labels: Record<string, string> = {
    'qq.qq_api': 'QQ',
    'onebot11.qq_client': 'OB11',
    'onebot12.qq_client': 'OB12',
  }
  return labels[platformId] || platformId
}

function formatDate(iso: string | null | undefined) {
  if (!iso) return '-'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

function getErrorMessage(error: unknown, fallback: string) {
  const err = error as { response?: { data?: { detail?: string | { message?: string } } } }
  const detail = err.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  return fallback
}

function getUserDisplayName(user: ManagerUserBrief | null | undefined) {
  return user?.nickname || user?.username || '未知用户'
}

function getUserInitial(user: ManagerUserBrief | null | undefined) {
  return getUserDisplayName(user).charAt(0).toUpperCase() || '?'
}

function avatarClass(size: 'sm' | 'md') {
  return [
    'flex shrink-0 items-center justify-center overflow-hidden bg-primary/15 font-semibold text-primary dark:bg-primary-dark/20 dark:text-primary-dark',
    size === 'sm' ? 'h-8 w-8 rounded-lg text-[12px]' : 'h-10 w-10 rounded-xl text-sm',
  ]
}

const UserAvatar = defineComponent({
  props: {
    user: {
      type: Object as () => ManagerUserBrief | null,
      default: null,
    },
    size: {
      type: String as () => 'sm' | 'md',
      default: 'md',
    },
  },
  setup(props) {
    return () => h(
      'div',
      { class: avatarClass(props.size) },
      props.user?.avatar
        ? h('img', {
            src: props.user.avatar,
            alt: `${getUserDisplayName(props.user)} 的头像`,
            class: 'h-full w-full object-cover',
          })
        : getUserInitial(props.user),
    )
  },
})

const InfoItem = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true },
    mono: { type: Boolean, default: false },
  },
  setup(props) {
    return () => h('div', { class: 'min-w-0' }, [
      h('div', { class: 'mb-0.5 text-[11px] text-on-surface-variant dark:text-zinc-500' }, props.label),
      h(
        'div',
        {
          class: [
            'truncate text-on-surface dark:text-zinc-200',
            props.mono ? 'font-code-inline text-code-inline' : '',
          ],
        },
        props.value,
      ),
    ])
  },
})

const MemberRow = defineComponent({
  props: {
    user: {
      type: Object as () => ManagerUserBrief | null,
      default: null,
    },
    name: { type: String, required: true },
    sub: { type: String, required: true },
    meta: { type: String, required: true },
  },
  setup(props) {
    return () => h(
      'div',
      { class: 'flex items-center gap-3 rounded-lg border border-outline-variant bg-surface-container p-2.5 dark:border-zinc-800 dark:bg-zinc-800/65' },
      [
        h(UserAvatar, { user: props.user, size: 'sm' }),
        h('div', { class: 'min-w-0 flex-1' }, [
          h('div', { class: 'truncate font-medium text-on-surface dark:text-zinc-100' }, props.name),
          h('div', { class: 'truncate text-[11px] text-on-surface-variant dark:text-zinc-500' }, props.sub),
        ]),
        h('span', { class: 'shrink-0 rounded-full bg-surface-container-low px-2 py-0.5 text-[11px] text-on-surface-variant dark:bg-zinc-900 dark:text-zinc-400' }, props.meta),
      ],
    )
  },
})

const EmptyRow = defineComponent({
  props: {
    text: { type: String, required: true },
  },
  setup(props) {
    return () => h(
      'div',
      { class: 'rounded-xl border border-dashed border-outline-variant bg-surface-container/40 px-4 py-5 text-center text-body-sm text-on-surface-variant dark:border-zinc-800 dark:bg-zinc-800/25 dark:text-zinc-500' },
      props.text,
    )
  },
})
</script>
