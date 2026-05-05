<template>
  <div class="flex h-[calc(100vh-96px)] min-h-0 flex-col gap-4 overflow-hidden">
    <div class="flex shrink-0 flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">{{ pageTitle }}</h1>
        <p class="mt-1 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">
          {{ pageDescription }}
        </p>
      </div>
      <button
        type="button"
        class="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 font-body-sm text-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:bg-zinc-800"
        @click="reload"
      >
        <RefreshCw :size="15" :class="{ 'animate-spin': loading }" />
        刷新
      </button>
    </div>

    <div v-if="overview?.errors.length" class="shrink-0 rounded-lg border border-amber-500/25 bg-amber-50/80 px-3 py-2 text-body-sm text-amber-800 dark:border-amber-500/25 dark:bg-amber-950/30 dark:text-amber-200">
      {{ overview.errors[0] }}
    </div>

    <div
      v-if="notice"
      class="shrink-0 rounded-lg border px-3 py-2 text-body-sm"
      :class="noticeTone === 'success'
        ? 'border-primary/20 bg-primary/10 text-primary dark:border-primary-dark/20 dark:bg-primary-dark/10 dark:text-primary-dark'
        : 'border-error/20 bg-error-container/60 text-error dark:border-red-800/50 dark:bg-red-900/30 dark:text-red-300'"
    >
      {{ notice }}
    </div>

    <div class="grid shrink-0 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        v-for="card in statCards"
        :key="card.title"
        :title="card.title"
        :value="card.value"
        :sub="card.sub"
        :icon="card.icon"
      />
    </div>

    <div class="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
      <aside class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="shrink-0 border-b border-outline-variant bg-surface-bright p-3 dark:border-zinc-800 dark:bg-zinc-900/60">
          <div class="grid grid-cols-2 gap-1 rounded-lg border border-outline-variant bg-surface-container p-0.5 dark:border-zinc-700 dark:bg-zinc-800">
            <button
              v-for="tab in visibleTabs"
              :key="tab.key"
              type="button"
              class="flex h-9 items-center justify-center gap-1.5 rounded-md text-[12px] font-semibold transition-colors"
              :class="activeTab === tab.key ? activeSegmentClass : inactiveSegmentClass"
              @click="setTab(tab.key)"
            >
              <component :is="tab.icon" :size="13" />
              {{ tab.label }}
            </button>
          </div>

          <div class="mt-3 grid gap-2">
            <div class="relative">
              <Search :size="15" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant dark:text-zinc-500" />
              <input
                v-model="search"
                class="h-9 w-full rounded-lg border border-outline-variant bg-surface-container pl-8 pr-3 text-body-sm text-on-surface outline-none transition-colors focus:border-primary dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:focus:border-primary-dark"
                :placeholder="searchPlaceholder"
              />
            </div>
            <AppSelect
              v-if="activeTab === 'commands'"
              v-model="pluginFilter"
              :options="pluginFilterOptions"
              button-class="h-9"
            />
          </div>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto p-2">
          <template v-if="activeTab === 'commands'">
            <button
              v-for="commandItem in filteredCommands"
              :key="commandItem.id"
              type="button"
              class="item-row"
              :class="selectedCommand?.id === commandItem.id ? selectedItemClass : idleItemClass"
              @click="selectedCommandId = commandItem.id"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="truncate font-body-sm text-body-sm font-semibold">{{ commandItem.command }}</span>
                <div class="flex shrink-0 items-center gap-1">
                  <span class="rounded-full px-2 py-0.5 text-[11px]" :class="commandItem.available === false ? dangerChipClass : okChipClass">
                    {{ commandItem.available === false ? '已关闭' : '可用' }}
                  </span>
                  <span class="rounded-full px-2 py-0.5 text-[11px]" :class="commandItem.runtime_loaded ? okChipClass : mutedChipClass">
                    {{ commandItem.runtime_loaded ? '已载入' : '源码' }}
                  </span>
                </div>
              </div>
              <div class="mt-1 flex items-center gap-2 text-[11px] text-on-surface-variant dark:text-zinc-500">
                <span class="truncate">{{ namespaceLabel(commandItem.namespace) }} / {{ commandItem.plugin_name }}</span>
                <span>{{ commandItem.execution_mode ? executionModeLabel(commandItem.execution_mode) : matcherTypeLabel(commandItem.matcher_type) }}</span>
                <span v-if="commandItem.risk_level">{{ riskLevelLabel(commandItem.risk_level) }}</span>
              </div>
            </button>
            <EmptyState v-if="filteredCommands.length === 0" text="没有匹配的命令" />
          </template>

          <template v-else-if="activeTab === 'plugins'">
            <button
              v-for="plugin in filteredPlugins"
              :key="plugin.module_name"
              type="button"
              class="item-row"
              :class="selectedPlugin?.module_name === plugin.module_name ? selectedItemClass : idleItemClass"
              @click="selectedPluginModule = plugin.module_name"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="truncate font-body-sm text-body-sm font-semibold">{{ plugin.display_name || plugin.name }}</span>
                <div class="flex shrink-0 items-center gap-1">
                  <span class="rounded-full px-2 py-0.5 text-[11px]" :class="plugin.available ? okChipClass : dangerChipClass">
                    {{ plugin.available ? '可用' : '已关闭' }}
                  </span>
                  <span class="rounded-full px-2 py-0.5 text-[11px]" :class="plugin.loaded ? okChipClass : mutedChipClass">
                    {{ plugin.loaded ? '已加载' : sourceLabel(plugin.source) }}
                  </span>
                </div>
              </div>
              <div class="mt-1 truncate font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500">
                {{ plugin.module_name }}
              </div>
              <div class="mt-1 flex items-center gap-2 text-[11px] text-on-surface-variant dark:text-zinc-500">
                <span>{{ plugin.command_count }} 命令</span>
                <span>{{ plugin.service_command_count }} service</span>
                <span>{{ plugin.disabled_command_count }} 关闭</span>
              </div>
            </button>
            <EmptyState v-if="filteredPlugins.length === 0" text="没有匹配的插件" />
          </template>

          <template v-else-if="activeTab === 'adapters'">
            <button
              v-for="adapter in filteredAdapters"
              :key="adapter.module_name"
              type="button"
              class="item-row"
              :class="selectedAdapter?.module_name === adapter.module_name ? selectedItemClass : idleItemClass"
              @click="selectedAdapterModule = adapter.module_name"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="truncate font-body-sm text-body-sm font-semibold">{{ adapter.name }}</span>
                <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px]" :class="adapter.registered ? okChipClass : mutedChipClass">
                  {{ adapter.registered ? 'registered' : 'declared' }}
                </span>
              </div>
              <div class="mt-1 truncate font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500">
                {{ adapter.module_name }}
              </div>
            </button>
            <EmptyState v-if="filteredAdapters.length === 0" text="没有匹配的适配器" />
          </template>

          <template v-else>
            <button
              v-for="botItem in filteredBots"
              :key="botItem.self_id"
              type="button"
              class="item-row"
              :class="selectedBot?.self_id === botItem.self_id ? selectedItemClass : idleItemClass"
              @click="selectedBotId = botItem.self_id"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="truncate font-code-inline text-code-inline font-semibold">{{ botItem.self_id }}</span>
                <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px]" :class="okChipClass">online</span>
              </div>
              <div class="mt-1 truncate text-[11px] text-on-surface-variant dark:text-zinc-500">
                {{ botItem.adapter_name || botItem.adapter_module || 'unknown adapter' }}
              </div>
            </button>
            <EmptyState v-if="filteredBots.length === 0" text="当前暂无在线 Bot" />
          </template>
        </div>
      </aside>

      <section class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex shrink-0 items-center justify-between gap-3 border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/60">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <component :is="activeIcon" :size="18" class="shrink-0 text-primary dark:text-primary-dark" />
              <h2 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ detailTitle }}</h2>
            </div>
            <p class="mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">{{ detailSubtitle }}</p>
          </div>
          <span class="shrink-0 rounded-full px-2.5 py-1 text-[11px]" :class="overview?.status === 'ok' ? okChipClass : warnChipClass">
            {{ overview?.status === 'ok' ? '运行正常' : '有提示' }}
          </span>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto p-4">
          <template v-if="activeTab === 'commands' && selectedCommand">
            <div class="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_320px]">
              <div class="space-y-4">
                <DetailCard>
                  <div class="flex flex-wrap items-center gap-2">
                    <span
                      v-for="badge in commandStatusBadges"
                      :key="badge.key"
                      :class="[chipBaseClass, chipToneClass(badge.tone)]"
                    >
                      {{ badge.label }}
                    </span>
                  </div>
                  <p class="mt-3 text-body-sm leading-6 text-on-surface dark:text-zinc-200">
                    {{ selectedCommand.description || '暂无帮助描述，后续可以在插件 __helpers__ 中补充命令说明。' }}
                  </p>
                  <p v-if="selectedCommand.ai_description" class="mt-2 text-body-sm leading-6 text-on-surface-variant dark:text-zinc-400">
                    {{ selectedCommand.ai_description }}
                  </p>
                </DetailCard>

                <DetailCard title="可用性控制">
                  <div class="flex flex-col gap-3 lg:flex-row lg:items-center">
                    <div class="min-w-0 flex-1">
                      <input
                        v-model="commandReason"
                        class="h-10 w-full rounded-lg border border-outline-variant bg-surface-container px-3 text-body-sm text-on-surface outline-none transition-colors focus:border-primary dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:focus:border-primary-dark"
                        placeholder="关闭原因或恢复说明（可选）"
                      />
                    </div>
                    <button
                      type="button"
                      class="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg px-4 text-body-sm font-medium transition-colors lg:min-w-[148px]"
                      :class="selectedCommand.available === false
                        ? 'bg-primary text-on-primary hover:opacity-90 dark:bg-primary-dark dark:text-zinc-950'
                        : 'bg-error text-on-error hover:opacity-90 dark:bg-red-900 dark:text-white'"
                      :disabled="savingTarget === 'command'"
                      @click="toggleCommandAvailability"
                    >
                      <Save v-if="savingTarget !== 'command'" :size="14" />
                      <RefreshCw v-else :size="14" class="animate-spin" />
                      {{ selectedCommand.available === false ? '重新启用命令' : '软关闭命令' }}
                    </button>
                  </div>
                  <div v-if="selectedCommand.availability_reason" class="mt-2">
                    <p v-if="selectedCommand.availability_reason" class="text-[12px] text-on-surface-variant dark:text-zinc-500">
                      当前原因：{{ selectedCommand.availability_reason }}
                    </p>
                  </div>
                </DetailCard>

                <DetailCard title="命令参数">
                  <div v-if="selectedCommand.params.length" class="grid gap-2 sm:grid-cols-2">
                    <div
                      v-for="param in selectedCommand.params"
                      :key="param.name"
                      class="rounded-lg border px-3 py-2 transition-colors"
                      :class="paramCardClass(param)"
                    >
                      <div class="flex min-w-0 items-center justify-between gap-2">
                        <span class="truncate text-body-sm font-semibold text-on-surface dark:text-zinc-100">{{ param.name }}</span>
                        <span :class="[paramBadgeBaseClass, isParamRequired(param) ? requiredParamBadgeClass : optionalParamBadgeClass]">
                          {{ isParamRequired(param) ? '必填' : '可选' }}
                        </span>
                      </div>
                      <div class="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-on-surface-variant dark:text-zinc-400">
                        <span>{{ valueTypeLabel(param.value_type) }}</span>
                        <span>·</span>
                        <span>{{ paramModeLabel(param) }}</span>
                        <span v-if="param.source_name">· {{ param.source_name }}</span>
                      </div>
                      <p v-if="param.description" class="mt-1 line-clamp-2 text-[12px] leading-5 text-on-surface-variant dark:text-zinc-500">
                        {{ param.description }}
                      </p>
                    </div>
                  </div>
                  <p v-else class="text-body-sm text-on-surface-variant dark:text-zinc-500">无参数或未登记参数。</p>
                </DetailCard>

                <DetailCard title="源码定位">
                  <div class="grid gap-2 font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-400">
                    <span>{{ selectedCommand.file || '仅注册表元数据，无源码定位' }}<template v-if="selectedCommand.file">:{{ selectedCommand.line }}</template></span>
                    <span>{{ selectedCommand.module_name }}</span>
                    <span v-if="selectedCommand.matcher_name">matcher: {{ selectedCommand.matcher_name }}</span>
                  </div>
                </DetailCard>
              </div>

              <div class="space-y-4">
                <ChartPanel title="命令来源" sub="按源码目录统计" :option="sourceChartOption" height="170px" />
                <DetailCard title="别名">
                  <div v-if="selectedCommand.aliases.length" class="flex flex-wrap gap-2">
                    <span v-for="alias in selectedCommand.aliases" :key="alias" :class="infoChipClass">{{ alias }}</span>
                  </div>
                  <p v-else class="text-body-sm text-on-surface-variant dark:text-zinc-500">无别名。</p>
                </DetailCard>
                <DetailCard title="权限目录">
                  <div class="space-y-2 text-body-sm text-on-surface-variant dark:text-zinc-400">
                    <p>roles: {{ selectedCommand.roles.join(', ') || 'public' }}</p>
                    <p>exclude roles: {{ selectedCommand.exclude_roles?.join(', ') || '-' }}</p>
                    <p>scopes: {{ selectedCommand.scopes.join(', ') || '-' }}</p>
                    <p>metadata: {{ selectedCommand.metadata_source || '-' }}</p>
                    <p>tool: {{ selectedCommand.tool_name || '-' }}</p>
                  </div>
                </DetailCard>
                <DetailCard title="标签">
                  <div v-if="selectedCommand.tags?.length" class="flex flex-wrap gap-2">
                    <span v-for="tag in selectedCommand.tags" :key="tag" :class="infoChipClass">{{ tag }}</span>
                  </div>
                  <p v-else class="text-body-sm text-on-surface-variant dark:text-zinc-500">暂无标签。</p>
                </DetailCard>
              </div>
            </div>
          </template>

          <template v-else-if="activeTab === 'plugins' && selectedPlugin">
            <div class="grid gap-4 xl:grid-cols-2">
              <DetailCard title="插件信息">
                <div class="space-y-3 text-body-sm text-on-surface dark:text-zinc-200">
                  <InfoRow label="模块" :value="selectedPlugin.module_name" code />
                  <InfoRow label="来源" :value="sourceLabel(selectedPlugin.source)" />
                  <InfoRow label="状态" :value="selectedPlugin.loaded ? '已加载' : '未确认加载'" />
                  <InfoRow label="可用性" :value="selectedPlugin.available ? '可用' : '已软关闭'" />
                  <InfoRow label="类型" :value="selectedPlugin.type || '-'" />
                  <InfoRow label="命令数" :value="String(selectedPlugin.command_count)" />
                  <InfoRow label="Matcher" :value="String(selectedPlugin.matcher_count)" />
                </div>
              </DetailCard>
              <DetailCard title="插件控制">
                <div class="flex flex-col gap-3 lg:flex-row lg:items-center">
                  <div class="min-w-0 flex-1">
                    <input
                      v-model="pluginReason"
                      class="h-10 w-full rounded-lg border border-outline-variant bg-surface-container px-3 text-body-sm text-on-surface outline-none transition-colors focus:border-primary dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:focus:border-primary-dark"
                      placeholder="关闭原因或恢复说明（可选）"
                    />
                  </div>
                  <button
                    type="button"
                    class="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-lg px-4 text-body-sm font-medium transition-colors lg:min-w-[148px]"
                    :class="selectedPlugin.available
                      ? 'bg-error text-on-error hover:opacity-90 dark:bg-red-900 dark:text-white'
                      : 'bg-primary text-on-primary hover:opacity-90 dark:bg-primary-dark dark:text-zinc-950'"
                    :disabled="savingTarget === 'plugin'"
                    @click="togglePluginAvailability"
                  >
                    <Save v-if="savingTarget !== 'plugin'" :size="14" />
                    <RefreshCw v-else :size="14" class="animate-spin" />
                    {{ selectedPlugin.available ? '软关闭插件' : '重新启用插件' }}
                  </button>
                </div>
                <div v-if="selectedPlugin.availability_reason" class="mt-2">
                  <p v-if="selectedPlugin.availability_reason" class="text-[12px] text-on-surface-variant dark:text-zinc-500">
                    当前原因：{{ selectedPlugin.availability_reason }}
                  </p>
                </div>
              </DetailCard>
              <DetailCard title="说明">
                <p class="text-body-sm leading-6 text-on-surface dark:text-zinc-200">
                  {{ selectedPlugin.description || '暂无插件元数据描述。' }}
                </p>
                <pre v-if="selectedPlugin.usage" class="mt-3 max-h-52 overflow-auto rounded-lg bg-code p-3 font-code-inline text-code-inline text-on-surface-variant dark:bg-zinc-950 dark:text-zinc-400"><code>{{ selectedPlugin.usage }}</code></pre>
              </DetailCard>
              <DetailCard title="适配器支持">
                <div v-if="selectedPlugin.supported_adapters.length" class="flex flex-wrap gap-2">
                  <span v-for="adapter in selectedPlugin.supported_adapters" :key="adapter" :class="infoChipClass">{{ adapter }}</span>
                </div>
                <p v-else class="text-body-sm text-on-surface-variant dark:text-zinc-500">未声明适配器限制。</p>
              </DetailCard>
              <DetailCard title="子插件">
                <div class="text-body-sm text-on-surface-variant dark:text-zinc-400">
                  parent: {{ selectedPlugin.parent || '-' }}<br />
                  sub plugins: {{ selectedPlugin.sub_plugin_count }}
                </div>
              </DetailCard>
              <DetailCard title="命令画像">
                <div class="grid grid-cols-2 gap-3 text-body-sm text-on-surface-variant dark:text-zinc-400">
                  <p>可用命令：{{ selectedPlugin.available_command_count }}</p>
                  <p>关闭命令：{{ selectedPlugin.disabled_command_count }}</p>
                  <p>Service：{{ selectedPlugin.service_command_count }}</p>
                  <p>Agent 可调：{{ selectedPlugin.agent_callable_command_count }}</p>
                  <p>高风险：{{ selectedPlugin.high_risk_command_count }}</p>
                </div>
              </DetailCard>
            </div>
          </template>

          <template v-else-if="activeTab === 'adapters' && selectedAdapter">
            <div class="grid gap-4 xl:grid-cols-2">
              <DetailCard title="适配器注册">
                <div class="space-y-3 text-body-sm">
                  <InfoRow label="名称" :value="selectedAdapter.name" />
                  <InfoRow label="模块" :value="selectedAdapter.module_name" code />
                  <InfoRow label="类模块" :value="selectedAdapter.class_module || '-'" code />
                  <InfoRow label="类名" :value="selectedAdapter.class_name || '-'" />
                  <InfoRow label="运行时键" :value="selectedAdapter.runtime_key || '-'" />
                  <InfoRow label="状态" :value="selectedAdapter.registered ? '已注册到 Driver' : '仅在 pyproject 声明'" />
                </div>
              </DetailCard>
              <DetailCard title="连接情况">
                <div class="flex items-center gap-3">
                  <div class="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10 text-primary dark:bg-primary-dark/15 dark:text-primary-dark">
                    <Bot :size="24" />
                  </div>
                  <div>
                    <div class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ selectedAdapter.bot_count }}</div>
                    <p class="text-body-sm text-on-surface-variant dark:text-zinc-500">当前在线 Bot</p>
                  </div>
                </div>
              </DetailCard>
            </div>
          </template>

          <template v-else-if="activeTab === 'bots' && selectedBot">
            <div class="grid gap-4 xl:grid-cols-2">
              <DetailCard title="Bot 连接">
                <div class="space-y-3 text-body-sm">
                  <InfoRow label="Self ID" :value="selectedBot.self_id" code />
                  <InfoRow label="类型" :value="selectedBot.type || '-'" />
                  <InfoRow label="适配器" :value="selectedBot.adapter_name || '-'" />
                  <InfoRow label="适配器模块" :value="selectedBot.adapter_module || '-'" code />
                  <InfoRow label="状态" :value="selectedBot.connected ? '在线' : '离线'" />
                </div>
              </DetailCard>
            </div>
          </template>

          <div v-else class="flex h-full min-h-[260px] items-center justify-center rounded-xl border border-dashed border-outline-variant text-center text-body-sm text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
            选择左侧项目查看详情
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onMounted, ref, watch } from 'vue'
import {
  Bot,
  Command,
  Cpu,
  FlaskConical,
  Lock,
  Plug,
  Puzzle,
  RefreshCw,
  Save,
  Search,
} from 'lucide-vue-next'
import AppSelect from '@/components/AppSelect.vue'
import ChartPanel from '@/components/ChartPanel.vue'
import {
  fetchNoneBotOverview,
  updateNoneBotCommandAvailability,
  updateNoneBotPluginAvailability,
} from '@/api/nonebot'
import type {
  NoneBotAdapterItem,
  NoneBotBotItem,
  NoneBotCommandItem,
  NoneBotCommandParam,
  NoneBotOverviewResponse,
  NoneBotPluginItem,
  NoneBotStats,
} from '@/types/api'
import { useTheme } from '@/composables/useTheme'

type AreaKey = 'plugin' | 'bot'
type TabKey = 'commands' | 'plugins' | 'adapters' | 'bots'
type ChipTone = 'ok' | 'warn' | 'danger' | 'muted' | 'info'

const props = withDefaults(defineProps<{
  mode?: AreaKey
}>(), {
  mode: 'plugin',
})

const StatCard = defineComponent({
  props: {
    title: { type: String, required: true },
    value: { type: Number, required: true },
    sub: { type: String, required: true },
    icon: { type: Object, required: true },
  },
  setup(props) {
    return () => h('div', { class: 'rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900' }, [
      h('div', { class: 'flex items-center justify-between' }, [
        h('span', { class: 'font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500' }, props.title),
        h(props.icon, { size: 16, class: 'text-primary dark:text-primary-dark' }),
      ]),
      h('div', { class: 'mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100' }, String(props.value)),
      h('div', { class: 'mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500' }, props.sub),
    ])
  },
})

const EmptyState = defineComponent({
  props: { text: { type: String, required: true } },
  setup(props) {
    return () => h('div', { class: 'p-8 text-center text-body-sm text-on-surface-variant dark:text-zinc-500' }, props.text)
  },
})

const DetailCard = defineComponent({
  props: { title: { type: String, default: '' } },
  setup(props, { slots }) {
    return () => h('section', { class: 'rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45' }, [
      props.title ? h('h3', { class: 'mb-3 font-body-sm text-body-sm font-semibold text-on-surface dark:text-zinc-100' }, props.title) : null,
      slots.default?.(),
    ])
  },
})

const InfoRow = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true },
    code: { type: Boolean, default: false },
  },
  setup(props) {
    return () => h('div', { class: 'flex items-start justify-between gap-3' }, [
      h('span', { class: 'shrink-0 text-on-surface-variant dark:text-zinc-500' }, props.label),
      h('span', {
        class: [
          'min-w-0 break-all text-right text-on-surface dark:text-zinc-200',
          props.code ? 'font-code-inline text-code-inline' : '',
        ],
      }, props.value),
    ])
  },
})

const pluginTabs: { key: TabKey; label: string; icon: object }[] = [
  { key: 'commands', label: '命令', icon: Command },
  { key: 'plugins', label: '插件', icon: Puzzle },
]

const botTabs: { key: TabKey; label: string; icon: object }[] = [
  { key: 'adapters', label: '适配器', icon: Plug },
  { key: 'bots', label: 'Bot', icon: Bot },
]

const tabs = [...pluginTabs, ...botTabs]

const { isDark } = useTheme()
const overview = ref<NoneBotOverviewResponse | null>(null)
const loading = ref(false)
const savingTarget = ref<'command' | 'plugin' | ''>('')
const activeTab = ref<TabKey>(props.mode === 'plugin' ? 'commands' : 'adapters')
const search = ref('')
const pluginFilter = ref('')
const selectedCommandId = ref('')
const selectedPluginModule = ref('')
const selectedAdapterModule = ref('')
const selectedBotId = ref('')
const commandReason = ref('')
const pluginReason = ref('')
const notice = ref('')
const noticeTone = ref<'success' | 'error'>('success')

const emptyStats: NoneBotStats = {
  plugins: 0,
  loaded_plugins: 0,
  commands: 0,
  documented_commands: 0,
  available_commands: 0,
  disabled_commands: 0,
  service_commands: 0,
  agent_callable_commands: 0,
  registry_commands: 0,
  adapters: 0,
  registered_adapters: 0,
  bots: 0,
  online_bots: 0,
}

const stats = computed(() => overview.value?.stats || emptyStats)
const commands = computed(() => overview.value?.commands || [])
const plugins = computed(() => overview.value?.plugins || [])
const adapters = computed(() => overview.value?.adapters || [])
const bots = computed(() => overview.value?.bots || [])
const pageTitle = computed(() => props.mode === 'plugin' ? 'Plugin 管理' : 'Bot 管理')
const pageDescription = computed(() => props.mode === 'plugin'
  ? '集中查看 NoneBot 命令、命令别名、插件元数据与源码定位。'
  : '集中查看 NoneBot 适配器声明、运行时注册状态与在线 Bot。')
const statCards = computed(() => props.mode === 'plugin'
  ? [
    { title: '插件', value: stats.value.plugins, sub: `${stats.value.loaded_plugins} 已加载`, icon: Puzzle },
    { title: '命令', value: stats.value.commands, sub: `${stats.value.documented_commands} 有帮助元数据`, icon: Command },
    { title: '可用命令', value: stats.value.available_commands, sub: `${stats.value.disabled_commands} 已软关闭`, icon: Lock },
    { title: 'Service', value: stats.value.service_commands, sub: `${stats.value.agent_callable_commands} 可被 Agent 调用`, icon: FlaskConical },
  ]
  : [
    { title: '适配器', value: stats.value.adapters, sub: `${stats.value.registered_adapters} 已注册`, icon: Plug },
    { title: 'Bot', value: stats.value.bots, sub: `${stats.value.online_bots} 在线`, icon: Bot },
    { title: 'Service 命令', value: stats.value.service_commands, sub: `${stats.value.registry_commands} 来自统一注册表`, icon: Cpu },
    { title: 'Agent 可调', value: stats.value.agent_callable_commands, sub: `${stats.value.available_commands} 当前可用`, icon: Command },
  ])

const activeSegmentClass = 'bg-surface-container-lowest text-primary shadow-sm dark:bg-zinc-900 dark:text-primary-dark'
const inactiveSegmentClass = 'text-on-surface-variant hover:text-on-surface dark:text-zinc-400 dark:hover:text-zinc-100'
const selectedItemClass = 'border-primary/30 bg-primary/10 text-primary dark:border-primary-dark/30 dark:bg-primary-dark/12 dark:text-primary-dark'
const idleItemClass = 'border-transparent text-on-surface hover:bg-surface-container dark:text-zinc-200 dark:hover:bg-zinc-800/70'
const chipBaseClass = 'inline-flex shrink-0 items-center rounded-full px-2.5 py-1 text-[11px] font-medium leading-none'
const okChipClass = 'bg-primary/10 text-primary dark:bg-primary-dark/15 dark:text-primary-dark'
const warnChipClass = 'bg-amber-500/10 text-amber-700 dark:bg-amber-400/10 dark:text-amber-300'
const mutedChipClass = 'bg-surface-container text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400'
const infoChipClass = 'rounded-full bg-sky-500/10 px-2 py-0.5 text-[11px] text-sky-700 dark:bg-sky-400/10 dark:text-sky-300'
const dangerChipClass = 'bg-red-500/10 text-red-700 dark:bg-red-500/12 dark:text-red-300'
const paramBadgeBaseClass = 'inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-medium leading-none'
const requiredParamBadgeClass = 'bg-amber-500/15 text-amber-700 dark:bg-amber-400/15 dark:text-amber-300'
const optionalParamBadgeClass = 'bg-sky-500/12 text-sky-700 dark:bg-sky-400/12 dark:text-sky-300'

const searchPlaceholder = computed(() => {
  if (activeTab.value === 'commands') return '搜索命令、别名、文件...'
  if (activeTab.value === 'plugins') return '搜索插件名称或模块...'
  if (activeTab.value === 'adapters') return '搜索适配器...'
  return '搜索 Bot ID 或适配器...'
})

const activeArea = computed<AreaKey>(() => props.mode)
const visibleTabs = computed(() => activeArea.value === 'plugin' ? pluginTabs : botTabs)

const pluginFilterOptions = computed(() => [
  { label: '全部插件', value: '' },
  ...plugins.value
    .filter((plugin) => plugin.command_count > 0)
    .map((plugin) => ({ label: plugin.display_name || plugin.name, value: plugin.module_name })),
])

const filteredCommands = computed(() => {
  const keyword = normalize(search.value)
  return commands.value.filter((item) => {
    if (pluginFilter.value && item.plugin_module !== pluginFilter.value) return false
    if (!keyword) return true
    return [
      item.command,
      item.aliases.join(' '),
      item.description,
      item.ai_description || '',
      item.file,
      item.plugin_name,
      item.namespace,
      item.execution_mode || '',
      item.risk_level || '',
    ].some((value) => normalize(value).includes(keyword))
  })
})

const filteredPlugins = computed(() => {
  const keyword = normalize(search.value)
  if (!keyword) return plugins.value
  return plugins.value.filter((item) => [
    item.name,
    item.display_name,
    item.module_name,
    item.description,
  ].some((value) => normalize(value).includes(keyword)))
})

const filteredAdapters = computed(() => {
  const keyword = normalize(search.value)
  if (!keyword) return adapters.value
  return adapters.value.filter((item) => [
    item.name,
    item.module_name,
    item.class_module || '',
    item.class_name || '',
  ].some((value) => normalize(value).includes(keyword)))
})

const filteredBots = computed(() => {
  const keyword = normalize(search.value)
  if (!keyword) return bots.value
  return bots.value.filter((item) => [
    item.self_id,
    item.type || '',
    item.adapter_name || '',
    item.adapter_module || '',
  ].some((value) => normalize(value).includes(keyword)))
})

const selectedCommand = computed<NoneBotCommandItem | null>(() => {
  return commands.value.find((item) => item.id === selectedCommandId.value) || filteredCommands.value[0] || null
})

const selectedPlugin = computed<NoneBotPluginItem | null>(() => {
  return plugins.value.find((item) => item.module_name === selectedPluginModule.value) || filteredPlugins.value[0] || null
})

const selectedAdapter = computed<NoneBotAdapterItem | null>(() => {
  return adapters.value.find((item) => item.module_name === selectedAdapterModule.value) || filteredAdapters.value[0] || null
})

const selectedBot = computed<NoneBotBotItem | null>(() => {
  return bots.value.find((item) => item.self_id === selectedBotId.value) || filteredBots.value[0] || null
})

const activeIcon = computed(() => tabs.find((tab) => tab.key === activeTab.value)?.icon || Command)
const detailTitle = computed(() => {
  if (activeTab.value === 'commands') return selectedCommand.value?.command || '命令详情'
  if (activeTab.value === 'plugins') return selectedPlugin.value?.display_name || '插件详情'
  if (activeTab.value === 'adapters') return selectedAdapter.value?.name || '适配器详情'
  return selectedBot.value?.self_id || 'Bot 详情'
})
const detailSubtitle = computed(() => {
  if (activeTab.value === 'commands') {
    if (!selectedCommand.value) return '选择命令查看源码与权限元数据'
    return `${selectedCommand.value.plugin_module} · ${selectedCommand.value.file || '注册表元数据'}`
  }
  if (activeTab.value === 'plugins') return selectedPlugin.value?.module_name || '选择插件查看运行时状态'
  if (activeTab.value === 'adapters') return selectedAdapter.value?.module_name || '选择适配器查看注册状态'
  return selectedBot.value?.adapter_module || '当前没有在线 Bot'
})

const sourceChartOption = computed<Record<string, unknown>>(() => {
  const entries = Object.entries(overview.value?.command_sources || {})
  return {
    color: isDark.value ? ['#4da394', '#38bdf8', '#fbbf24', '#a78bfa'] : ['#28645a', '#0ea5e9', '#d97706', '#7c3aed'],
    tooltip: { trigger: 'item' },
    legend: {
      bottom: 0,
      icon: 'circle',
      textStyle: { color: isDark.value ? '#a1a1aa' : '#475569', fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['46%', '72%'],
        center: ['50%', '42%'],
        avoidLabelOverlap: true,
        label: { show: false },
        data: entries.map(([name, value]) => ({ name: namespaceLabel(name), value })),
      },
    ],
  }
})

const commandStatusBadges = computed(() => {
  const command = selectedCommand.value
  if (!command) return []
  return [
    {
      key: 'matcher',
      label: matcherTypeLabel(command.matcher_type),
      tone: command.matcher_type === 'alconna' ? 'info' : 'muted',
    },
    {
      key: 'documented',
      label: command.documented ? '帮助已登记' : '仅源码识别',
      tone: command.documented ? 'ok' : 'warn',
    },
    {
      key: 'runtime',
      label: command.runtime_loaded ? '运行时已载入' : '未确认载入',
      tone: command.runtime_loaded ? 'ok' : 'muted',
    },
    {
      key: 'availability',
      label: command.available === false ? '命令已关闭' : '命令可用',
      tone: command.available === false ? 'danger' : 'ok',
    },
    {
      key: 'execution',
      label: executionModeLabel(command.execution_mode),
      tone: command.execution_mode === 'service'
        ? 'info'
        : command.execution_mode === 'disabled'
          ? 'danger'
          : 'muted',
    },
    {
      key: 'risk',
      label: riskLevelLabel(command.risk_level),
      tone: command.risk_level === 'high'
        ? 'danger'
        : command.risk_level === 'medium'
          ? 'warn'
          : 'muted',
    },
    {
      key: 'agent',
      label: command.agent_callable ? 'Agent 可调' : 'Agent 不可调',
      tone: command.agent_callable ? 'ok' : 'muted',
    },
  ] satisfies { key: string; label: string; tone: ChipTone }[]
})

onMounted(() => reload())

async function reload() {
  loading.value = true
  try {
    overview.value = await fetchNoneBotOverview()
    ensureSelection()
    commandReason.value = selectedCommand.value?.availability_reason || ''
    pluginReason.value = selectedPlugin.value?.availability_reason || ''
  } finally {
    loading.value = false
  }
}

function setTab(tab: TabKey) {
  activeTab.value = tab
  search.value = ''
  if (tab !== 'commands') {
    pluginFilter.value = ''
  }
  ensureSelection()
}

function ensureSelection() {
  selectedCommandId.value ||= commands.value[0]?.id || ''
  selectedPluginModule.value ||= plugins.value[0]?.module_name || ''
  selectedAdapterModule.value ||= adapters.value[0]?.module_name || ''
  selectedBotId.value ||= bots.value[0]?.self_id || ''
}

function normalize(value: string | null | undefined) {
  return (value || '').trim().toLowerCase()
}

function namespaceLabel(value: string) {
  const labels: Record<string, string> = {
    managers: '管理域',
    plugins: '插件域',
    others: '扩展域',
  }
  return labels[value] || value || 'unknown'
}

function sourceLabel(value: string) {
  const labels: Record<string, string> = {
    runtime: '运行时',
    source_scan: '源码扫描',
    pyproject: 'pyproject 声明',
    command_registry: '统一注册表',
  }
  return labels[value] || value
}

function matcherTypeLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    alconna: 'Alconna',
    command: '普通命令',
    registered: '注册表命令',
  }
  return labels[value || ''] || value || '未知类型'
}

function executionModeLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    service: 'Service 执行',
    interactive: '交互命令',
    legacy_event: '事件兼容',
    disabled: '已禁用',
  }
  return labels[value || ''] || value || '未标记执行'
}

function riskLevelLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    low: '低风险',
    medium: '中风险',
    high: '高风险',
  }
  return labels[value || ''] || value || '未标记风险'
}

function chipToneClass(tone: ChipTone) {
  const classes: Record<ChipTone, string> = {
    ok: okChipClass,
    warn: warnChipClass,
    danger: dangerChipClass,
    muted: mutedChipClass,
    info: 'bg-sky-500/10 text-sky-700 dark:bg-sky-400/10 dark:text-sky-300',
  }
  return classes[tone]
}

function isParamRequired(param: NoneBotCommandParam) {
  if (typeof param.required === 'boolean') return param.required
  return !['?', '*'].includes(param.mode || '')
}

function isParamMultiple(param: NoneBotCommandParam) {
  return Boolean(param.multiple || param.mode === '+' || param.mode === '*')
}

function paramModeLabel(param: NoneBotCommandParam) {
  if (isParamMultiple(param)) {
    return isParamRequired(param) ? '至少 1 个，可多值' : '0 个或多个'
  }
  return isParamRequired(param) ? '单值参数' : '可省略'
}

function valueTypeLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    string: '文本',
    integer: '整数',
    number: '数值',
    boolean: '布尔',
  }
  return labels[value || ''] || value || '文本'
}

function paramCardClass(param: NoneBotCommandParam) {
  return isParamRequired(param)
    ? 'border-amber-500/20 bg-amber-500/5 dark:border-amber-400/20 dark:bg-amber-400/5'
    : 'border-sky-500/20 bg-sky-500/5 dark:border-sky-400/20 dark:bg-sky-400/5'
}

watch(() => props.mode, (mode) => {
  activeTab.value = mode === 'plugin' ? 'commands' : 'adapters'
  search.value = ''
  pluginFilter.value = ''
  ensureSelection()
})

watch(selectedCommand, (command) => {
  commandReason.value = command?.availability_reason || ''
})

watch(selectedPlugin, (plugin) => {
  pluginReason.value = plugin?.availability_reason || ''
})

async function toggleCommandAvailability() {
  if (!selectedCommand.value) return
  savingTarget.value = 'command'
  try {
    const nextEnabled = !(selectedCommand.value.available ?? true)
    await updateNoneBotCommandAvailability(selectedCommand.value.command, {
      enabled: nextEnabled,
      reason: commandReason.value,
    })
    notice.value = nextEnabled
      ? `命令 ${selectedCommand.value.command} 已重新启用`
      : `命令 ${selectedCommand.value.command} 已软关闭`
    noticeTone.value = 'success'
    await reload()
  } catch {
    notice.value = '命令状态更新失败'
    noticeTone.value = 'error'
  } finally {
    savingTarget.value = ''
  }
}

async function togglePluginAvailability() {
  if (!selectedPlugin.value) return
  savingTarget.value = 'plugin'
  try {
    const nextEnabled = !selectedPlugin.value.available
    await updateNoneBotPluginAvailability(selectedPlugin.value.module_name, {
      enabled: nextEnabled,
      reason: pluginReason.value,
    })
    notice.value = nextEnabled
      ? `插件 ${selectedPlugin.value.display_name || selectedPlugin.value.name} 已重新启用`
      : `插件 ${selectedPlugin.value.display_name || selectedPlugin.value.name} 已软关闭`
    noticeTone.value = 'success'
    await reload()
  } catch {
    notice.value = '插件状态更新失败'
    noticeTone.value = 'error'
  } finally {
    savingTarget.value = ''
  }
}
</script>

<style scoped>
.item-row {
  margin-bottom: 0.25rem;
  width: 100%;
  border-radius: 0.625rem;
  border-width: 1px;
  padding: 0.625rem 0.75rem;
  text-align: left;
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease;
}
</style>
