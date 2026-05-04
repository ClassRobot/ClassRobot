<template>
  <div class="flex flex-col gap-4 h-full">
    <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100 shrink-0">Prompt 管理</h1>

    <div class="flex flex-1 min-h-0 gap-0">
      <!-- File list -->
      <div class="w-[280px] shrink-0 rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 overflow-y-auto">
        <div class="px-4 py-3 border-b border-outline-variant dark:border-zinc-800 font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">模板文件</div>
        <div v-if="prompts.length === 0" class="p-4 text-body-sm text-on-surface-variant dark:text-zinc-500">暂无模板</div>
        <button
          v-for="p in prompts"
          :key="p.name"
          @click="selectPrompt(p.name)"
          class="w-full text-left px-4 py-2.5 font-code-inline text-code-inline transition-colors hover:bg-surface-container dark:hover:bg-zinc-800 flex items-center justify-between"
          :class="activeName === p.name ? 'bg-primary/10 dark:bg-primary-dark/15 text-primary dark:text-primary-dark font-medium border-r-[3px] border-primary dark:border-primary-dark' : 'text-on-surface dark:text-zinc-300'"
        >
          <span>{{ p.name }}</span>
          <StatusChip :status="p.valid ? 'ok' : 'error'" />
        </button>
      </div>

      <!-- Editor -->
      <div class="flex-1 ml-4 rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 flex flex-col overflow-hidden">
        <div v-if="!activeName" class="flex-1 flex items-center justify-center text-on-surface-variant dark:text-zinc-500">请从左侧选择一个模板</div>
        <template v-else>
          <div class="flex items-center justify-between px-4 py-3 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50">
            <span class="font-code-inline text-code-inline text-on-surface dark:text-zinc-200">{{ activeName }}</span>
            <div class="flex gap-2">
              <button @click="validate" class="flex items-center gap-1.5 rounded-lg px-3 py-1.5 border border-outline-variant dark:border-zinc-700 text-on-surface dark:text-zinc-200 font-body-sm hover:bg-surface-container dark:hover:bg-zinc-800 transition-colors">
                <CheckCheck :size="14" /> 校验
              </button>
              <button @click="save" :disabled="saving" class="flex items-center gap-1.5 rounded-lg bg-primary dark:bg-primary-dark text-on-primary dark:text-zinc-900 px-3 py-1.5 font-body-sm font-medium hover:opacity-90 disabled:opacity-50 transition-all">
                {{ saving ? '保存中...' : '保存' }}
              </button>
            </div>
          </div>
          <textarea
            v-model="content"
            class="flex-1 p-4 bg-code dark:bg-zinc-800 font-code-block text-code-block text-on-surface dark:text-zinc-200 resize-none focus:outline-none border-0"
            spellcheck="false"
          />
          <div v-if="validationMsg" class="px-4 py-2 border-t text-body-sm" :class="valid ? 'bg-primary/10 dark:bg-emerald-500/10 text-primary dark:text-emerald-400' : 'bg-error/10 dark:bg-red-500/10 text-error dark:text-red-400'">
            {{ validationMsg }}
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchPrompts, fetchPrompt, updatePrompt, validatePrompt } from '@/api/prompts'
import type { PromptSummary } from '@/types/api'
import { CheckCheck } from 'lucide-vue-next'
import StatusChip from '@/components/StatusChip.vue'

const prompts = ref<PromptSummary[]>([])
const activeName = ref('')
const content = ref('')
const saving = ref(false)
const valid = ref(true)
const validationMsg = ref('')

onMounted(async () => { try { prompts.value = (await fetchPrompts()).items } catch { /* */ } })

async function selectPrompt(name: string) {
  activeName.value = name
  try {
    const p = await fetchPrompt(name)
    content.value = p.content
    valid.value = p.valid
    validationMsg.value = p.validation_message
  } catch { /* */ }
}

async function validate() {
  if (!activeName.value) return
  try {
    const r = await validatePrompt(activeName.value)
    valid.value = r.valid
    validationMsg.value = r.valid ? '校验通过' : r.validation_message
  } catch (e: unknown) {
    validationMsg.value = (e as Error).message || '校验失败'
    valid.value = false
  }
}

async function save() {
  if (!activeName.value || saving.value) return
  saving.value = true
  try {
    await updatePrompt(activeName.value, content.value)
    validationMsg.value = '保存成功'
    valid.value = true
  } catch (e: unknown) {
    validationMsg.value = (e as Error).message || '保存失败'
    valid.value = false
  }
  saving.value = false
}
</script>
