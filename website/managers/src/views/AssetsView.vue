<template>
  <div class="space-y-6">
    <section class="grid gap-4 xl:grid-cols-4">
      <MetricCard label="命令插件" :value="plugins?.total ?? 0" description="当前进程内已加载的命令插件。" tone="ink" />
      <MetricCard label="项目技能" :value="skills?.total ?? 0" description="Skill 注册中心中声明的全部技能。" tone="sea" />
      <MetricCard label="模型配置" :value="models?.total ?? 0" description="当前接入的大模型配置项数量。" tone="amber" />
      <MetricCard label="运行 Bot" :value="bots?.total ?? 0" description="当前已经连接的 Bot 实例数量。" tone="mint" />
    </section>

    <div class="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
      <SectionPanel title="命令插件" description="NoneBot 运行时已加载的插件，当前默认保持只读。">
        <div class="overflow-hidden rounded-[28px] border border-slate-200">
          <div class="max-h-[420px] overflow-auto">
            <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead class="bg-slate-50 text-slate-500">
                <tr>
                  <th class="px-4 py-3 font-medium">插件</th>
                  <th class="px-4 py-3 font-medium">模块</th>
                  <th class="px-4 py-3 font-medium">类别</th>
                  <th class="px-4 py-3 font-medium">命令</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 bg-white">
                <tr v-for="plugin in plugins?.items ?? []" :key="plugin.module_name" class="align-top hover:bg-slate-50">
                  <td class="px-4 py-4">
                    <p class="font-semibold text-brand-ink">{{ plugin.name }}</p>
                    <p class="mt-2 text-xs text-slate-400">{{ plugin.helper_count }} 个命令</p>
                  </td>
                  <td class="px-4 py-4 font-mono text-xs text-slate-600">{{ plugin.module_name }}</td>
                  <td class="px-4 py-4">
                    <span class="rounded-full bg-brand-sea/10 px-3 py-1 text-xs text-brand-sea">
                      {{ plugin.category }}
                    </span>
                  </td>
                  <td class="px-4 py-4 text-slate-600">
                    <div class="flex flex-wrap gap-2">
                      <span
                        v-for="command in plugin.commands"
                        :key="command"
                        class="rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs text-slate-600"
                      >
                        {{ command }}
                      </span>
                      <span v-if="plugin.commands.length === 0" class="text-slate-400">未暴露命令</span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </SectionPanel>

      <SectionPanel title="运行 Bot" description="Bot 连接状态由 NoneBot 运行时托管，后台仅提供只读观测。">
        <div class="space-y-3">
          <div
            v-for="bot in bots?.items ?? []"
            :key="`${bot.adapter}-${bot.self_id}`"
            class="rounded-3xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
          >
            <div class="flex items-start justify-between gap-4">
              <div>
                <p class="font-semibold text-brand-ink">{{ bot.adapter }}</p>
                <p class="mt-1 font-mono text-xs text-slate-500">{{ bot.self_id }}</p>
                <p class="mt-3 text-sm text-slate-600">{{ bot.type }}</p>
              </div>
              <span
                class="rounded-full px-3 py-1 text-xs"
                :class="bot.connected ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-600'"
              >
                {{ bot.connected ? "已连接" : "离线" }}
              </span>
            </div>
          </div>
          <div
            v-if="(bots?.items ?? []).length === 0"
            class="rounded-3xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500"
          >
            当前没有已连接的 Bot。
          </div>
        </div>
      </SectionPanel>
    </div>

    <div class="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
      <SectionPanel title="项目技能" description="这里展示的是项目技能清单以及其是否已在运行时加载。">
        <div class="grid gap-3">
          <div
            v-for="skill in skills?.items ?? []"
            :key="skill.name"
            class="rounded-3xl border border-slate-200 bg-slate-50 px-4 py-4"
          >
            <div class="flex items-start justify-between gap-4">
              <div>
                <p class="font-semibold text-brand-ink">{{ skill.name }}</p>
                <p class="mt-2 text-sm leading-6 text-slate-600">{{ skill.description }}</p>
                <p class="mt-3 font-mono text-xs text-slate-400">{{ skill.root }}</p>
              </div>
              <span
                class="rounded-full px-3 py-1 text-xs"
                :class="skill.runtime_loaded ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-600'"
              >
                {{ skill.runtime_loaded ? "已加载" : "未加载" }}
              </span>
            </div>
          </div>
        </div>
      </SectionPanel>

      <SectionPanel title="模型配置" description="模型列表来自项目配置，当前适合做只读审查和排障，不建议直接在运行态改写。">
        <div class="overflow-hidden rounded-[28px] border border-slate-200">
          <div class="max-h-[420px] overflow-auto">
            <table class="min-w-full divide-y divide-slate-200 text-left text-sm">
              <thead class="bg-slate-50 text-slate-500">
                <tr>
                  <th class="px-4 py-3 font-medium">名称</th>
                  <th class="px-4 py-3 font-medium">模型</th>
                  <th class="px-4 py-3 font-medium">任务</th>
                  <th class="px-4 py-3 font-medium">能力</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-100 bg-white">
                <tr v-for="model in models?.items ?? []" :key="`${model.name}-${model.model}`" class="align-top hover:bg-slate-50">
                  <td class="px-4 py-4">
                    <p class="font-semibold text-brand-ink">{{ model.name }}</p>
                    <p class="mt-2 font-mono text-xs text-slate-400">priority {{ model.priority }}</p>
                  </td>
                  <td class="px-4 py-4 text-slate-600">
                    <p class="font-mono text-xs">{{ model.model }}</p>
                    <p class="mt-2 break-all text-xs text-slate-400">{{ model.url }}</p>
                  </td>
                  <td class="px-4 py-4">
                    <div class="flex flex-wrap gap-2">
                      <span
                        v-for="task in model.tasks"
                        :key="task"
                        class="rounded-full bg-brand-amber/10 px-3 py-1 text-xs text-amber-700"
                      >
                        {{ task }}
                      </span>
                    </div>
                  </td>
                  <td class="px-4 py-4">
                    <div class="flex flex-wrap gap-2">
                      <span
                        class="rounded-full px-3 py-1 text-xs"
                        :class="model.multi_modal ? 'bg-brand-sea/10 text-brand-sea' : 'bg-slate-100 text-slate-500'"
                      >
                        多模态 {{ model.multi_modal ? "开启" : "关闭" }}
                      </span>
                      <span
                        class="rounded-full px-3 py-1 text-xs"
                        :class="model.supports_functools ? 'bg-brand-mint/10 text-emerald-700' : 'bg-slate-100 text-slate-500'"
                      >
                        Functools {{ model.supports_functools ? "支持" : "不支持" }}
                      </span>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </SectionPanel>
    </div>

    <p v-if="errorMessage" class="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
      {{ errorMessage }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import MetricCard from "@/components/MetricCard.vue";
import SectionPanel from "@/components/SectionPanel.vue";
import { normalizeApiError } from "@/api/client";
import { fetchAdminBots, fetchAdminModels, fetchAdminPlugins, fetchAdminSkills } from "@/api/modules/admin";
import type {
  AdminBotListResponse,
  AdminModelListResponse,
  AdminPluginListResponse,
  AdminSkillListResponse,
} from "@/types/admin";

const plugins = ref<AdminPluginListResponse | null>(null);
const skills = ref<AdminSkillListResponse | null>(null);
const models = ref<AdminModelListResponse | null>(null);
const bots = ref<AdminBotListResponse | null>(null);
const errorMessage = ref("");

onMounted(async () => {
  try {
    const [pluginData, skillData, modelData, botData] = await Promise.all([
      fetchAdminPlugins(),
      fetchAdminSkills(),
      fetchAdminModels(),
      fetchAdminBots(),
    ]);
    plugins.value = pluginData;
    skills.value = skillData;
    models.value = modelData;
    bots.value = botData;
  } catch (error) {
    errorMessage.value = normalizeApiError(error);
  }
});
</script>
