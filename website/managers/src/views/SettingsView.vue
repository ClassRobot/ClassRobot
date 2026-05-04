<template>
  <div class="flex h-full flex-col gap-4">
    <div class="flex items-start justify-between gap-4">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">系统设置</h1>
        <p class="mt-1 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">
          管理核心应用参数、安全策略与外部服务连接
        </p>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-2 rounded-lg border border-outline-variant dark:border-zinc-700 px-3 py-2 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-400 transition-colors hover:bg-surface-container dark:hover:bg-zinc-800"
        @click="loadSettings"
      >
        <RefreshCw :size="16" :class="{ 'animate-spin': loading }" />
        刷新
      </button>
    </div>

    <div class="grid flex-1 grid-cols-12 gap-6 overflow-hidden">
      <nav class="col-span-3 flex flex-col gap-1">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          @click="activeTab = tab.key"
          class="rounded-lg px-4 py-3 text-left transition-colors"
          :class="activeTab === tab.key
            ? 'border border-primary/20 bg-primary/10 text-primary dark:border-primary-dark/20 dark:bg-primary-dark/15 dark:text-primary-dark'
            : 'text-on-surface-variant hover:bg-surface-container dark:text-zinc-400 dark:hover:bg-zinc-800'"
        >
          <span class="block font-body-sm text-body-sm font-medium">{{ tab.label }}</span>
          <span class="mt-0.5 block text-[11px] leading-4 opacity-75">{{ tab.description }}</span>
        </button>
      </nav>

      <section class="col-span-9 overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between border-b border-outline-variant bg-surface-bright px-5 py-4 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div>
            <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ currentTab?.label }}</h2>
            <p class="mt-0.5 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">{{ currentTab?.description }}</p>
          </div>
          <StatusChip v-if="hasChanges" status="warning" />
        </div>

        <div v-if="loading" class="flex h-full items-center justify-center py-16 text-on-surface-variant dark:text-zinc-500">
          加载中...
        </div>

        <form v-else class="h-full overflow-y-auto p-5 pb-24" @submit.prevent="save">
          <div class="grid grid-cols-1 gap-5">
            <label
              v-for="field in currentTab?.fields"
              :key="`${field.group}.${field.key}`"
              class="block"
            >
              <span class="mb-1.5 block font-body-sm text-body-sm font-medium text-on-surface dark:text-zinc-200">{{ field.label }}</span>

              <AppSelect
                v-if="field.type === 'select'"
                :model-value="fieldValue(field)"
                :options="selectOptions(field)"
                @update:model-value="updateField(field, String($event))"
              />

              <textarea
                v-else-if="field.type === 'textarea'"
                :value="fieldValue(field)"
                rows="10"
                spellcheck="false"
                class="w-full resize-y rounded-lg border border-outline-variant bg-code px-3 py-2 font-code-block text-code-block text-on-surface focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:focus:border-primary-dark dark:focus:ring-primary-dark/20"
                :placeholder="field.placeholder"
                @input="handleFieldInput(field, $event)"
              />

              <input
                v-else
                :value="fieldValue(field)"
                :type="field.type === 'password' ? 'password' : field.type === 'number' ? 'number' : 'text'"
                class="w-full rounded-lg border border-outline-variant bg-surface-container px-3 py-2 font-code-inline text-code-inline text-on-surface focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:focus:border-primary-dark dark:focus:ring-primary-dark/20"
                :placeholder="field.placeholder"
                @input="handleFieldInput(field, $event)"
              />

              <span class="mt-1.5 block font-body-sm text-[12px] text-on-surface-variant dark:text-zinc-500">{{ field.hint }}</span>
              <span v-if="isModified(field)" class="mt-1 block text-[11px] font-medium text-warning">已修改</span>
            </label>
          </div>

          <div v-if="activeTab === 'security'" class="mt-6 rounded-lg border border-warning/30 bg-warning/10 p-4 dark:border-amber-500/30 dark:bg-amber-500/10">
            <div class="flex items-start justify-between gap-4">
              <div>
                <div class="flex items-center gap-2 font-body-sm text-body-sm font-medium text-on-surface dark:text-zinc-100">
                  <Shield :size="16" class="text-warning" />
                  登录 Token 轮换
                </div>
                <p class="mt-1 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-400">
                  轮换后当前会话会失效，新 Token 会打印到后端日志。
                </p>
              </div>
              <button
                type="button"
                class="shrink-0 rounded-lg border border-warning/40 px-3 py-1.5 font-body-sm text-body-sm text-warning transition-colors hover:bg-warning/10"
                @click="handleRotateToken"
              >
                轮换 Token
              </button>
            </div>
          </div>

          <div v-if="message" class="mt-5 rounded-lg border px-4 py-3 font-body-sm text-body-sm" :class="messageClass">
            {{ message }}
          </div>
        </form>
      </section>
    </div>

    <div
      v-if="hasChanges"
      class="fixed bottom-0 left-sidebar right-0 z-40 flex items-center justify-between border-t border-outline-variant bg-surface-container-high px-6 py-3 dark:border-zinc-700 dark:bg-zinc-800"
    >
      <div class="flex items-center gap-3">
        <span class="flex items-center gap-2 font-body-md font-medium text-on-surface dark:text-zinc-200">
          <AlertTriangle :size="18" class="text-warning" />
          {{ modifiedFields.size }} 项未保存的更改
        </span>
        <span class="h-4 w-px bg-outline-variant dark:bg-zinc-600" />
        <span class="font-body-sm text-on-surface-variant dark:text-zinc-400">保存后通常需要重启服务生效</span>
      </div>
      <div class="flex gap-2">
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-lg border border-outline-variant px-4 py-1.5 font-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-700"
          @click="reset"
        >
          <RotateCcw :size="15" />
          重置
        </button>
        <button
          type="button"
          class="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-1.5 font-body-sm font-medium text-on-primary transition-opacity hover:opacity-90 disabled:opacity-50 dark:bg-primary-dark dark:text-zinc-900"
          :disabled="saving"
          @click="save"
        >
          <Save :size="15" />
          {{ saving ? '保存中...' : '保存并应用' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { fetchSettings, patchSettings, rotateToken } from '@/api/settings'
import { useAuthStore } from '@/composables/useAuth'
import type { SettingsPatchPayload, SettingsResponse } from '@/types/api'
import { AlertTriangle, RefreshCw, RotateCcw, Save, Shield } from 'lucide-vue-next'
import AppSelect from '@/components/AppSelect.vue'
import StatusChip from '@/components/StatusChip.vue'

type GroupKey = 'base' | 'ai' | 'models' | 'cache' | 'cos' | 'security'
type FieldType = 'text' | 'password' | 'number' | 'textarea' | 'select'

interface FieldConfig {
  group: GroupKey
  key: string
  label: string
  type: FieldType
  hint: string
  placeholder?: string
  options?: string[]
}

interface TabConfig {
  key: GroupKey
  label: string
  description: string
  fields: FieldConfig[]
}

const router = useRouter()
const auth = useAuthStore()
const activeTab = ref<GroupKey>('base')
const loading = ref(true)
const saving = ref(false)
const settings = ref<SettingsResponse | null>(null)
const modifiedFields = ref(new Set<string>())
const message = ref('')
const messageType = ref<'success' | 'error' | 'warning'>('success')

const formData = ref<Record<GroupKey, Record<string, unknown>>>({
  base: {},
  ai: {},
  models: {},
  cache: {},
  cos: {},
  security: {},
})

const tabs: TabConfig[] = [
  {
    key: 'base',
    label: '基础设置',
    description: '运行路径、代理与业务基础参数',
    fields: [
      { group: 'base', key: 'global_proxy', label: '全局代理', type: 'text', placeholder: 'http://127.0.0.1:7890', hint: '为空时不启用全局代理。' },
      { group: 'base', key: 'wsl_share_dir', label: 'WSL 共享目录', type: 'text', placeholder: '/mnt/d/share', hint: '用于跨环境共享文件的目录。' },
      { group: 'base', key: 'teacher_max_classes', label: '教师最大班级数', type: 'number', hint: '限制教师可关联的班级数量。' },
    ],
  },
  {
    key: 'ai',
    label: 'AI / RAG',
    description: '搜索增强与 RAGFlow 连接参数',
    fields: [
      { group: 'ai', key: 'googleapis_key', label: 'Google APIs Key', type: 'password', hint: '敏感字段会以掩码显示，修改后才会提交。' },
      { group: 'ai', key: 'ragflow_url', label: 'RAGFlow URL', type: 'text', placeholder: 'http://127.0.0.1:9380', hint: 'RAGFlow 服务地址。' },
      { group: 'ai', key: 'ragflow_key', label: 'RAGFlow Key', type: 'password', hint: '敏感字段会以掩码显示，修改后才会提交。' },
    ],
  },
  {
    key: 'models',
    label: '模型注册',
    description: 'LLM 超时与模型路由配置',
    fields: [
      { group: 'models', key: 'llm_timeout', label: '请求超时秒数', type: 'number', hint: '后端调用模型时的超时时间。' },
      { group: 'models', key: 'llm_configs', label: '模型配置 JSON', type: 'textarea', hint: '数组格式，字段包含 name/key/url/model/priority/tasks/multi_modal/supports_functools。' },
    ],
  },
  {
    key: 'cache',
    label: '缓存',
    description: 'Redis 或兼容缓存连接',
    fields: [
      { group: 'cache', key: 'cache_host', label: '缓存 Host', type: 'text', hint: '缓存服务主机名或 IP。' },
      { group: 'cache', key: 'cache_port', label: '缓存 Port', type: 'number', hint: '端口范围 1-65535。' },
    ],
  },
  {
    key: 'cos',
    label: '对象存储',
    description: 'COS 上传与访问配置',
    fields: [
      { group: 'cos', key: 'cos_secret_id', label: 'Secret ID', type: 'password', hint: '敏感字段会以掩码显示，修改后才会提交。' },
      { group: 'cos', key: 'cos_secret_key', label: 'Secret Key', type: 'password', hint: '敏感字段会以掩码显示，修改后才会提交。' },
      { group: 'cos', key: 'region', label: 'Region', type: 'text', placeholder: 'ap-beijing', hint: '对象存储地域。' },
      { group: 'cos', key: 'bucket', label: 'Bucket', type: 'text', hint: '对象存储桶名称。' },
      { group: 'cos', key: 'scheme', label: 'Scheme', type: 'select', options: ['https', 'http'], hint: '建议使用 https。' },
    ],
  },
  {
    key: 'security',
    label: '安全认证',
    description: '加密盐与本地后台令牌',
    fields: [
      { group: 'security', key: 'encrypt_salt', label: 'Encrypt Salt', type: 'password', hint: '用于本地加密场景，修改后需要重启。' },
    ],
  },
]

const numberFields = new Set(['base.teacher_max_classes', 'models.llm_timeout', 'cache.cache_port'])
const currentTab = computed(() => tabs.find((tab) => tab.key === activeTab.value))
const hasChanges = computed(() => modifiedFields.value.size > 0)
const messageClass = computed(() => {
  if (messageType.value === 'error') return 'border-error/30 bg-error/10 text-error dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-400'
  if (messageType.value === 'warning') return 'border-warning/30 bg-warning/10 text-warning dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-400'
  return 'border-primary/30 bg-primary/10 text-primary dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-400'
})

onMounted(() => loadSettings())

async function loadSettings() {
  loading.value = true
  message.value = ''
  try {
    settings.value = await fetchSettings()
    applySettings(settings.value)
    modifiedFields.value.clear()
  } catch (error) {
    showMessage(readError(error, '设置加载失败'), 'error')
  }
  loading.value = false
}

function applySettings(payload: SettingsResponse) {
  formData.value = {
    base: { ...payload.base },
    ai: { ...payload.ai },
    models: {
      llm_timeout: payload.models.llm_timeout,
      llm_configs: JSON.stringify(payload.models.llm_configs || [], null, 2),
    },
    cache: { ...payload.cache },
    cos: { ...payload.cos },
    security: { ...payload.security },
  }
}

function fieldKey(field: FieldConfig) {
  return `${field.group}.${field.key}`
}

function isModified(field: FieldConfig) {
  return modifiedFields.value.has(fieldKey(field))
}

function fieldValue(field: FieldConfig) {
  return String(formData.value[field.group][field.key] ?? '')
}

function selectOptions(field: FieldConfig) {
  return (field.options || []).map((option) => ({ label: option, value: option }))
}

function markModified(field: FieldConfig) {
  modifiedFields.value.add(fieldKey(field))
  message.value = ''
}

function handleFieldInput(field: FieldConfig, event: Event) {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement | null
  updateField(field, target?.value ?? '')
}

function updateField(field: FieldConfig, value: string) {
  formData.value[field.group][field.key] = value
  markModified(field)
}

function reset() {
  if (settings.value) applySettings(settings.value)
  modifiedFields.value.clear()
  message.value = ''
}

async function save() {
  if (!hasChanges.value || saving.value) return
  saving.value = true
  message.value = ''
  try {
    const payload = buildPatchPayload()
    const result = await patchSettings(payload)
    modifiedFields.value.clear()
    showMessage(result.restart_required ? '配置已保存，重启服务后生效。' : '配置已保存。', 'success')
    settings.value = await fetchSettings()
    applySettings(settings.value)
  } catch (error) {
    showMessage(readError(error, '保存失败'), 'error')
  }
  saving.value = false
}

function buildPatchPayload(): SettingsPatchPayload {
  const payload: SettingsPatchPayload = {}
  for (const item of modifiedFields.value) {
    const [group, key] = item.split('.') as [GroupKey, string]
    let value = formData.value[group][key]
    if (key === 'llm_configs') {
      value = JSON.parse(String(value || '[]'))
    } else if (numberFields.has(item)) {
      value = Number(value)
    }

    const groupPayload = { ...(payload[group] as Record<string, unknown> | undefined) }
    groupPayload[key] = value
    ;(payload as Record<GroupKey, Record<string, unknown>>)[group] = groupPayload
  }
  return payload
}

async function handleRotateToken() {
  try {
    await rotateToken()
    auth.clearSession()
    await router.push({ name: 'Login' })
  } catch (error) {
    showMessage(readError(error, 'Token 轮换失败'), 'error')
  }
}

function showMessage(text: string, type: 'success' | 'error' | 'warning') {
  message.value = text
  messageType.value = type
}

function readError(error: unknown, fallback: string) {
  const err = error as { response?: { data?: { detail?: string } }; message?: string }
  return err.response?.data?.detail || err.message || fallback
}
</script>
