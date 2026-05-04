<template>
  <div class="flex flex-col gap-4 h-full">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">Skill 管理</h1>
        <p class="font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500 mt-1">内置能力模块的加载状态与详情</p>
      </div>
      <button @click="handleReload" :disabled="reloading" class="flex items-center gap-2 rounded-lg bg-primary dark:bg-primary-dark text-on-primary dark:text-zinc-900 px-4 py-2 font-body-sm font-medium hover:opacity-90 disabled:opacity-50 transition-all">
        <RefreshCw :size="16" :class="{ 'animate-spin': reloading }" />
        {{ reloading ? '重载中...' : '重载全部' }}
      </button>
    </div>

    <div class="flex-1 rounded-xl border border-outline-variant dark:border-zinc-800 bg-surface-container-lowest dark:bg-zinc-900 overflow-hidden flex flex-col">
      <div class="overflow-auto flex-1">
        <table class="w-full text-left border-collapse whitespace-nowrap">
          <thead class="bg-surface-bright dark:bg-zinc-900/50 border-b border-outline-variant dark:border-zinc-800 sticky top-0 z-10">
            <tr>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">名称</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">描述</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">Runtime</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase">加载状态</th>
              <th class="p-[10px_12px] font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500 uppercase w-10 text-center">操作</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-outline-variant dark:divide-zinc-800 font-body-sm text-body-sm text-on-surface dark:text-zinc-200">
            <tr v-if="skills.length === 0"><td colspan="5" class="p-8 text-center text-on-surface-variant dark:text-zinc-500">暂无 Skill</td></tr>
            <tr v-for="skill in skills" :key="skill.name" class="hover:bg-surface-container dark:hover:bg-zinc-800/50 cursor-pointer transition-colors" @click="selectSkill(skill.name)">
              <td class="p-[10px_12px] font-medium">{{ skill.name }}</td>
              <td class="p-[10px_12px] text-on-surface-variant dark:text-zinc-400">{{ skill.description }}</td>
              <td class="p-[10px_12px]"><StatusChip :status="skill.has_runtime ? 'success' : 'not_configured'" /></td>
              <td class="p-[10px_12px]"><StatusChip :status="skill.loaded ? 'ok' : 'error'" /></td>
              <td class="p-[10px_12px] text-center">
                <button class="p-1 text-on-surface-variant dark:text-zinc-400 hover:text-primary dark:hover:text-primary-dark rounded"><ChevronRight :size="18" /></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Detail drawer -->
    <Teleport to="body">
      <div v-if="selectedSkill" class="fixed inset-0 z-50">
        <div class="absolute inset-0 bg-black/10 dark:bg-black/40" @click="selectedSkill = null" />
        <aside class="fixed right-0 top-topbar bottom-0 w-drawer-max bg-surface-container-lowest dark:bg-zinc-900 border-l border-outline-variant dark:border-zinc-800 flex flex-col shadow-xl rounded-l-xl">
          <div class="flex items-center justify-between p-4 border-b border-outline-variant dark:border-zinc-800 bg-surface-bright dark:bg-zinc-900/50">
            <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ selectedSkill.name }}</h2>
            <button @click="selectedSkill = null" class="p-1.5 text-on-surface-variant dark:text-zinc-400 hover:bg-surface-container dark:hover:bg-zinc-800 rounded-lg"><X :size="18" /></button>
          </div>
          <div class="flex-1 overflow-y-auto p-4 space-y-4">
            <div><span class="font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500">路径</span><div class="font-code-inline text-code-inline text-on-surface dark:text-zinc-200 mt-1">{{ selectedSkill.path }}</div></div>
            <div><span class="font-label-caps text-label-caps text-on-surface-variant dark:text-zinc-500">SKILL.md</span><pre class="mt-1 rounded-lg border border-outline-variant dark:border-zinc-800 bg-code dark:bg-zinc-800 p-3 font-code-block text-code-block text-on-surface dark:text-zinc-300 overflow-x-auto"><code>{{ skillDetail?.body || '加载中...' }}</code></pre></div>
          </div>
        </aside>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchSkills, fetchSkill, reloadSkills } from '@/api/skills'
import type { SkillSummary, SkillDetail } from '@/types/api'
import { RefreshCw, ChevronRight, X } from 'lucide-vue-next'
import StatusChip from '@/components/StatusChip.vue'

const skills = ref<SkillSummary[]>([])
const selectedSkill = ref<SkillSummary | null>(null)
const skillDetail = ref<SkillDetail | null>(null)
const reloading = ref(false)

onMounted(async () => { try { skills.value = (await fetchSkills()).items } catch { /* */ } })

async function selectSkill(name: string) {
  const s = skills.value.find(i => i.name === name)
  if (!s) return
  selectedSkill.value = s
  try { skillDetail.value = await fetchSkill(name) } catch { skillDetail.value = null }
}

async function handleReload() {
  reloading.value = true
  try {
    const result = await reloadSkills()
    skills.value = result.skills
  } catch { /* */ }
  reloading.value = false
}
</script>
