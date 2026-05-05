<template>
  <div class="flex h-[calc(100vh-96px)] min-h-0 flex-col gap-4 overflow-hidden">
    <div class="flex shrink-0 flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">聊天记录</h1>
        <p class="mt-1 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">
          查看用户私聊与系统群采集消息，辅助排查上下文、绑定和历史记录问题
        </p>
      </div>
      <div class="flex items-center gap-2">
        <span class="rounded-full border border-outline-variant bg-surface-container-lowest px-3 py-1 font-code-inline text-code-inline text-on-surface-variant dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
          {{ storageRootText }}
        </span>
        <button
          type="button"
          class="flex h-9 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 font-body-sm text-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
          @click="reloadAll"
        >
          <RefreshCw :size="15" :class="{ 'animate-spin': loading }" />
          刷新
        </button>
      </div>
    </div>

    <div v-if="notice" class="shrink-0 rounded-lg border px-3 py-2 text-body-sm" :class="noticeClass">
      {{ notice }}
    </div>

    <div class="grid shrink-0 grid-cols-2 gap-3 xl:grid-cols-4">
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">空间</span>
          <History :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ spaces.length }}</div>
        <div class="mt-1 text-body-sm text-on-surface-variant dark:text-zinc-500">当前 {{ kindLabel(activeKind) }}</div>
      </div>
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">消息数</span>
          <MessagesSquare :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ totalMessages }}</div>
        <div class="mt-1 text-body-sm text-on-surface-variant dark:text-zinc-500">当前筛选空间累计</div>
      </div>
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">群聊采集</span>
          <Users :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ totalCollectMessages }}</div>
        <div class="mt-1 text-body-sm text-on-surface-variant dark:text-zinc-500">系统群上下文消息</div>
      </div>
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">私聊聊天</span>
          <UserRound :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ totalChatMessages }}</div>
        <div class="mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">{{ selectedSpace?.title || '尚未选择空间' }}</div>
      </div>
    </div>

    <div class="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <aside class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="shrink-0 border-b border-outline-variant bg-surface-bright p-3 dark:border-zinc-800 dark:bg-zinc-900/60">
          <div class="grid grid-cols-2 gap-1 rounded-lg border border-outline-variant bg-surface-container p-0.5 dark:border-zinc-700 dark:bg-zinc-800">
            <button
              v-for="kind in spaceKinds"
              :key="kind"
              type="button"
              class="flex h-9 items-center justify-center gap-1.5 rounded-md text-[12px] font-semibold transition-colors"
              :class="activeKind === kind ? activeSegmentClass : inactiveSegmentClass"
              @click="switchKind(kind)"
            >
              <UserRound v-if="kind === 'user'" :size="14" />
              <Users v-else :size="14" />
              {{ kindLabel(kind) }}
            </button>
          </div>

          <div class="relative mt-3">
            <Search :size="15" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant dark:text-zinc-500" />
            <input
              v-model="spaceSearch"
              class="h-9 w-full rounded-lg border border-outline-variant bg-surface-container pl-8 pr-3 text-body-sm text-on-surface outline-none transition-colors focus:border-primary dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:focus:border-primary-dark"
              placeholder="搜索用户、班级、平台、消息..."
              @input="scheduleSpaceSearch"
            />
          </div>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto p-2">
          <button
            v-for="space in spaces"
            :key="space.key"
            type="button"
            class="mb-2 w-full rounded-xl border px-3 py-3 text-left transition-colors"
            :class="selectedSpace?.key === space.key
              ? 'border-primary/35 bg-primary/10 dark:border-primary-dark/30 dark:bg-primary-dark/10'
              : 'border-outline-variant bg-surface-container-low hover:bg-surface-container dark:border-zinc-800 dark:bg-zinc-800/45 dark:hover:bg-zinc-800/70'"
            @click="selectSpace(space)"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="truncate font-body-sm text-body-sm font-semibold text-on-surface dark:text-zinc-100">
                  {{ space.title }}
                </div>
                <div class="mt-1 truncate text-[11px] text-on-surface-variant dark:text-zinc-500">
                  {{ space.subtitle || space.owner_id }}
                </div>
              </div>
              <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px]" :class="space.linked ? okChipClass : warnChipClass">
                {{ space.linked ? '已关联' : '孤立空间' }}
              </span>
            </div>

            <div class="mt-3 grid grid-cols-2 gap-2 text-[11px] text-on-surface-variant dark:text-zinc-500">
              <span>{{ space.message_count }} 条消息</span>
              <span class="text-right">{{ formatDateTime(space.latest_message_at) }}</span>
            </div>
            <div class="mt-2 truncate text-[11px] text-on-surface-variant dark:text-zinc-500">
              {{ latestPreviewText(space) }}
            </div>
          </button>

          <div v-if="spaces.length === 0" class="p-6 text-center text-body-sm text-on-surface-variant dark:text-zinc-500">
            当前暂无匹配的聊天记录空间
          </div>
        </div>
      </aside>

      <section class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="shrink-0 border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/60">
          <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <History :size="18" class="shrink-0 text-primary dark:text-primary-dark" />
                <h2 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">
                  {{ selectedSpace?.title || '选择聊天空间' }}
                </h2>
                <span
                  v-if="selectedSpace"
                  class="rounded-full px-2 py-0.5 text-[11px]"
                  :class="selectedSpace.linked ? okChipClass : warnChipClass"
                >
                  {{ selectedSpace.linked ? '实体已关联' : '孤立空间' }}
                </span>
              </div>
              <p class="mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">
                {{ selectedSpace?.db_path || '从左侧选择一个聊天空间后查看消息内容' }}
              </p>
            </div>

            <div class="grid min-w-0 gap-2 lg:grid-cols-[minmax(220px,1fr)_140px_140px_140px]">
              <div class="relative min-w-0">
                <Search :size="15" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant dark:text-zinc-500" />
                <input
                  v-model="messageQuery"
                  class="h-9 w-full rounded-lg border border-outline-variant bg-surface-container pl-8 pr-3 text-body-sm text-on-surface outline-none transition-colors focus:border-primary disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:focus:border-primary-dark"
                  placeholder="搜索当前空间消息内容"
                  :disabled="!selectedSpace"
                  @input="scheduleMessageSearch"
                />
              </div>
              <AppSelect
                v-model="recordKindFilter"
                :options="recordKindOptions"
                button-class="h-9"
                :disabled="!selectedSpace"
              />
              <AppSelect
                v-model="actorRoleFilter"
                :options="actorRoleOptions"
                button-class="h-9"
                :disabled="!selectedSpace"
              />
              <AppSelect
                v-model="directionFilter"
                :options="directionOptions"
                button-class="h-9"
                :disabled="!selectedSpace"
              />
            </div>
          </div>
        </div>

        <div class="grid min-h-0 flex-1 grid-cols-1 overflow-hidden xl:grid-cols-[minmax(0,1fr)_360px]">
          <div class="flex min-w-0 flex-col overflow-hidden border-b border-outline-variant dark:border-zinc-800 xl:border-b-0 xl:border-r">
            <div class="flex shrink-0 items-center justify-between gap-3 border-b border-outline-variant px-4 py-3 dark:border-zinc-800">
              <div class="min-w-0">
                <div class="text-[11px] uppercase tracking-[0.14em] text-on-surface-variant dark:text-zinc-500">消息流</div>
                <div class="mt-1 truncate text-body-sm text-on-surface dark:text-zinc-100">
                  {{ selectedSpace ? messageSummaryText : '当前没有选中的聊天空间' }}
                </div>
              </div>
              <span class="shrink-0 rounded-full bg-surface-container px-2.5 py-1 text-[11px] text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400">
                {{ messageTotal }} 条
              </span>
            </div>

            <div class="min-h-0 flex-1 overflow-y-auto p-3">
              <template v-if="selectedSpace">
                <button
                  v-for="messageItem in messages"
                  :key="messageItem.event_key"
                  type="button"
                  class="mb-2 w-full rounded-xl border p-3 text-left transition-colors"
                  :class="selectedMessage?.event_key === messageItem.event_key
                    ? 'border-primary/35 bg-primary/10 dark:border-primary-dark/30 dark:bg-primary-dark/10'
                    : 'border-outline-variant bg-surface-container-low hover:bg-surface-container dark:border-zinc-800 dark:bg-zinc-800/45 dark:hover:bg-zinc-800/70'"
                  @click="selectedMessageKey = messageItem.event_key"
                >
                  <div class="flex items-start justify-between gap-3">
                    <div class="min-w-0">
                      <div class="flex items-center gap-2">
                        <span class="truncate font-body-sm text-body-sm font-semibold text-on-surface dark:text-zinc-100">
                          {{ messageItem.user_name }}
                        </span>
                        <span class="rounded-full px-2 py-0.5 text-[11px]" :class="actorChipClass(messageItem.actor_role)">
                          {{ actorRoleLabel(messageItem.actor_role) }}
                        </span>
                        <span class="rounded-full px-2 py-0.5 text-[11px]" :class="recordChipClass(messageItem.record_kind)">
                          {{ recordKindLabel(messageItem.record_kind) }}
                        </span>
                        <span class="rounded-full px-2 py-0.5 text-[11px]" :class="directionChipClass(messageItem.direction)">
                          {{ directionLabel(messageItem.direction) }}
                        </span>
                      </div>
                      <div class="mt-2 text-body-sm leading-6 text-on-surface dark:text-zinc-200">
                        {{ messageItem.display_text || '该消息没有可展示的文本内容' }}
                      </div>
                    </div>
                    <div class="shrink-0 text-right text-[11px] text-on-surface-variant dark:text-zinc-500">
                      <div>{{ formatDateTime(messageItem.created_at) }}</div>
                      <div class="mt-1 font-code-inline text-code-inline">
                        {{ messageItem.message_id || 'no-id' }}
                      </div>
                    </div>
                  </div>
                </button>

                <div v-if="!messageLoading && messages.length === 0" class="flex min-h-[240px] items-center justify-center rounded-xl border border-dashed border-outline-variant text-center text-body-sm text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
                  当前筛选条件下没有消息记录
                </div>

                <div v-if="messageLoading" class="flex min-h-[240px] items-center justify-center text-body-sm text-on-surface-variant dark:text-zinc-500">
                  <RefreshCw :size="16" class="mr-2 animate-spin" />
                  正在加载消息记录
                </div>
              </template>

              <div v-else class="flex min-h-[260px] items-center justify-center rounded-xl border border-dashed border-outline-variant text-center text-body-sm text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
                从左侧选择一个聊天空间
              </div>
            </div>

            <div class="flex shrink-0 items-center justify-between gap-3 border-t border-outline-variant px-4 py-3 dark:border-zinc-800">
              <span class="text-[11px] text-on-surface-variant dark:text-zinc-500">
                第 {{ page }} / {{ pageCount }} 页
              </span>
              <div class="flex items-center gap-2">
                <button
                  type="button"
                  class="inline-flex h-9 items-center rounded-lg border border-outline-variant px-3 text-body-sm text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                  :disabled="!selectedSpace || page <= 1 || messageLoading"
                  @click="changePage(page - 1)"
                >
                  上一页
                </button>
                <button
                  type="button"
                  class="inline-flex h-9 items-center rounded-lg border border-outline-variant px-3 text-body-sm text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                  :disabled="!selectedSpace || page >= pageCount || messageLoading"
                  @click="changePage(page + 1)"
                >
                  下一页
                </button>
              </div>
            </div>
          </div>

          <aside class="flex min-h-0 flex-col overflow-hidden">
            <div class="shrink-0 border-b border-outline-variant px-4 py-3 dark:border-zinc-800">
              <h3 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">
                {{ selectedMessage ? '消息详情' : '空间概览' }}
              </h3>
              <p class="mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">
                {{ selectedMessage ? selectedMessage.user_name : (selectedSpace?.chat_path || '选择消息后查看完整内容') }}
              </p>
            </div>

            <div class="min-h-0 flex-1 overflow-y-auto p-4">
              <template v-if="selectedMessage">
                <div class="space-y-4">
                  <section class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45">
                    <div class="mb-3 flex flex-wrap items-center gap-2">
                      <span class="rounded-full px-2 py-0.5 text-[11px]" :class="actorChipClass(selectedMessage.actor_role)">
                        {{ actorRoleLabel(selectedMessage.actor_role) }}
                      </span>
                      <span class="rounded-full px-2 py-0.5 text-[11px]" :class="recordChipClass(selectedMessage.record_kind)">
                        {{ recordKindLabel(selectedMessage.record_kind) }}
                      </span>
                      <span class="rounded-full px-2 py-0.5 text-[11px]" :class="directionChipClass(selectedMessage.direction)">
                        {{ directionLabel(selectedMessage.direction) }}
                      </span>
                    </div>
                    <p class="whitespace-pre-wrap break-words text-body-sm leading-7 text-on-surface dark:text-zinc-100">
                      {{ selectedMessage.display_text || '该消息没有可展示的文本内容' }}
                    </p>
                  </section>

                  <section class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45">
                    <h4 class="mb-3 font-body-sm text-body-sm font-semibold text-on-surface dark:text-zinc-100">消息元数据</h4>
                    <div class="space-y-2 text-body-sm text-on-surface-variant dark:text-zinc-400">
                      <p>创建时间：{{ formatDateTime(selectedMessage.created_at) }}</p>
                      <p>归属空间：{{ selectedMessage.owner_kind }} / {{ selectedMessage.owner_id }}</p>
                      <p>平台：{{ selectedMessage.platform || '未记录' }}</p>
                      <p>平台名称：{{ selectedMessage.platform_name || '未记录' }}</p>
                      <p>频道/群 ID：{{ selectedMessage.channel_id || '私聊或未记录' }}</p>
                      <p>Guild ID：{{ selectedMessage.guild_id || '未记录' }}</p>
                      <p>Bot ID：{{ selectedMessage.bot_id || '未记录' }}</p>
                      <p>平台发送者 ID：{{ selectedMessage.platform_user_id || '未记录' }}</p>
                      <p>用户 ID：{{ selectedMessage.user_id }}</p>
                      <p>消息 ID：{{ selectedMessage.message_id || '未记录' }}</p>
                      <p class="break-all font-code-inline text-code-inline">event_key：{{ selectedMessage.event_key }}</p>
                    </div>
                  </section>

                  <section class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45">
                    <h4 class="mb-3 font-body-sm text-body-sm font-semibold text-on-surface dark:text-zinc-100">扩展元数据</h4>
                    <pre class="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-surface-container px-3 py-3 font-code-inline text-code-inline text-on-surface dark:bg-zinc-900 dark:text-zinc-200">{{ formatMetadata(selectedMessage.metadata) }}</pre>
                  </section>

                  <section class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45">
                    <h4 class="mb-3 font-body-sm text-body-sm font-semibold text-on-surface dark:text-zinc-100">原始内容</h4>
                    <pre class="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-surface-container px-3 py-3 font-code-inline text-code-inline text-on-surface dark:bg-zinc-900 dark:text-zinc-200">{{ selectedMessage.raw_text || selectedMessage.plain_text }}</pre>
                  </section>
                </div>
              </template>

              <template v-else-if="selectedSpace">
                <div class="space-y-4">
                  <section class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45">
                    <div class="mb-3 flex items-center gap-2 text-body-sm font-medium text-on-surface dark:text-zinc-200">
                      <Database :size="15" />
                      聊天数据库
                    </div>
                    <div class="space-y-2 text-body-sm text-on-surface-variant dark:text-zinc-400">
                      <p class="break-all font-code-inline text-code-inline">{{ selectedSpace.db_path }}</p>
                      <p>数据库大小：{{ formatBytes(selectedSpace.db_size) }}</p>
                      <p>参与者数量：{{ selectedSpace.participant_count }}</p>
                      <p>最近消息：{{ formatDateTime(selectedSpace.latest_message_at) }}</p>
                    </div>
                  </section>

                  <section class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45">
                    <div class="mb-3 flex items-center gap-2 text-body-sm font-medium text-on-surface dark:text-zinc-200">
                      <ChartColumnBig :size="15" />
                      消息结构
                    </div>
                    <div class="grid grid-cols-2 gap-3 text-body-sm">
                      <div>
                        <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">聊天消息</div>
                        <div class="mt-1 text-on-surface dark:text-zinc-200">{{ selectedSpace.record_counts.chat }}</div>
                      </div>
                      <div>
                        <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">采集消息</div>
                        <div class="mt-1 text-on-surface dark:text-zinc-200">{{ selectedSpace.record_counts.collect }}</div>
                      </div>
                      <div>
                        <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">用户消息</div>
                        <div class="mt-1 text-on-surface dark:text-zinc-200">{{ selectedSpace.actor_counts.user }}</div>
                      </div>
                      <div>
                        <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">助手消息</div>
                        <div class="mt-1 text-on-surface dark:text-zinc-200">{{ selectedSpace.actor_counts.assistant }}</div>
                      </div>
                      <div>
                        <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">入站消息</div>
                        <div class="mt-1 text-on-surface dark:text-zinc-200">{{ selectedSpace.direction_counts.inbound }}</div>
                      </div>
                      <div>
                        <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">出站消息</div>
                        <div class="mt-1 text-on-surface dark:text-zinc-200">{{ selectedSpace.direction_counts.outbound }}</div>
                      </div>
                    </div>
                  </section>

                  <section class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/45">
                    <div class="mb-3 flex items-center gap-2 text-body-sm font-medium text-on-surface dark:text-zinc-200">
                      <Link2 :size="15" />
                      关联实体
                    </div>
                    <div class="space-y-2 text-body-sm text-on-surface-variant dark:text-zinc-400">
                      <p>关联状态：{{ selectedSpace.linked ? '已关联' : '孤立空间' }}</p>
                      <p v-if="selectedSpace.owner?.type === 'user'">用户名：{{ selectedSpace.owner.username || '-' }}</p>
                      <p v-if="selectedSpace.owner?.type === 'group'">群组：{{ selectedSpace.owner.group_name || '-' }}</p>
                      <p v-if="selectedSpace.owner?.type === 'group'">班级：{{ selectedSpace.owner.class_name || '-' }}</p>
                    </div>
                    <div v-if="selectedSpace.owner?.platforms?.length" class="mt-3 flex flex-wrap gap-2">
                      <span
                        v-for="platform in selectedSpace.owner.platforms"
                        :key="platform"
                        class="rounded-full bg-surface-container px-2.5 py-1 text-[12px] text-on-surface-variant dark:bg-zinc-900 dark:text-zinc-400"
                      >
                        {{ platform }}
                      </span>
                    </div>
                  </section>
                </div>
              </template>

              <div v-else class="flex min-h-[260px] items-center justify-center rounded-xl border border-dashed border-outline-variant text-center text-body-sm text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
                选择消息后查看详情，或先选择一个聊天空间
              </div>
            </div>
          </aside>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  ChartColumnBig,
  Database,
  History,
  Link2,
  MessagesSquare,
  RefreshCw,
  Search,
  UserRound,
  Users,
} from 'lucide-vue-next'
import AppSelect from '@/components/AppSelect.vue'
import {
  fetchChatHistoryMessages,
  fetchChatHistorySpaceDetail,
  fetchChatHistorySpaces,
} from '@/api/chatHistory'
import type {
  ChatHistoryActorRole,
  ChatHistoryDirection,
  ChatHistoryMessage,
  ChatHistoryMessageListResponse,
  ChatHistoryRecordKind,
  ChatHistorySpaceDetail,
  ChatHistorySpaceKind,
  ChatHistorySpaceListResponse,
  ChatHistorySpaceSummary,
} from '@/types/api'

const loading = ref(false)
const messageLoading = ref(false)
const activeKind = ref<ChatHistorySpaceKind>('user')
const spaceSearch = ref('')
const messageQuery = ref('')
const recordKindFilter = ref<'all' | ChatHistoryRecordKind>('all')
const actorRoleFilter = ref<'all' | ChatHistoryActorRole>('all')
const directionFilter = ref<'all' | ChatHistoryDirection>('all')
const storageRoot = ref('')
const spaces = ref<ChatHistorySpaceSummary[]>([])
const selectedSpace = ref<ChatHistorySpaceSummary | null>(null)
const spaceDetail = ref<ChatHistorySpaceDetail | null>(null)
const messages = ref<ChatHistoryMessage[]>([])
const selectedMessageKey = ref('')
const page = ref(1)
const pageSize = 50
const messageTotal = ref(0)
const notice = ref('')
const noticeTone = ref<'success' | 'error'>('success')

let spaceSearchTimer: ReturnType<typeof setTimeout> | undefined
let messageSearchTimer: ReturnType<typeof setTimeout> | undefined

const spaceKinds: ChatHistorySpaceKind[] = ['user', 'group']

const totalMessages = computed(() => spaces.value.reduce((sum, item) => sum + item.message_count, 0))
const totalCollectMessages = computed(() => spaces.value.reduce((sum, item) => sum + item.record_counts.collect, 0))
const totalChatMessages = computed(() => spaces.value.reduce((sum, item) => sum + item.record_counts.chat, 0))
const storageRootText = computed(() => storageRoot.value || '等待读取 storage 根目录')
const selectedMessage = computed(() => messages.value.find((item) => item.event_key === selectedMessageKey.value) || null)
const pageCount = computed(() => Math.max(1, Math.ceil(messageTotal.value / pageSize)))
const messageSummaryText = computed(() => {
  if (!selectedSpace.value) return ''
  const keyword = messageQuery.value.trim()
  const parts = [`共 ${messageTotal.value} 条结果`]
  if (keyword) parts.push(`关键词：${keyword}`)
  if (recordKindFilter.value !== 'all') parts.push(recordKindLabel(recordKindFilter.value))
  if (actorRoleFilter.value !== 'all') parts.push(actorRoleLabel(actorRoleFilter.value))
  if (directionFilter.value !== 'all') parts.push(directionLabel(directionFilter.value))
  return parts.join(' · ')
})
const recordKindOptions = [
  { label: '全部类型', value: 'all' },
  { label: '聊天消息', value: 'chat' },
  { label: '采集消息', value: 'collect' },
]
const actorRoleOptions = [
  { label: '全部角色', value: 'all' },
  { label: '用户消息', value: 'user' },
  { label: '助手消息', value: 'assistant' },
  { label: '系统消息', value: 'system' },
]
const directionOptions = [
  { label: '全部方向', value: 'all' },
  { label: '用户发来', value: 'inbound' },
  { label: '机器人发出', value: 'outbound' },
]

const noticeClass = computed(() => noticeTone.value === 'success'
  ? 'border-primary/20 bg-primary/10 text-primary dark:border-primary-dark/20 dark:bg-primary-dark/10 dark:text-primary-dark'
  : 'border-error/20 bg-error-container/60 text-error dark:border-red-800/50 dark:bg-red-900/30 dark:text-red-300')

const activeSegmentClass = 'bg-surface-container-lowest text-primary shadow-sm dark:bg-zinc-900 dark:text-primary-dark'
const inactiveSegmentClass = 'text-on-surface-variant hover:text-on-surface dark:text-zinc-400 dark:hover:text-zinc-100'
const okChipClass = 'bg-primary/10 text-primary dark:bg-primary-dark/15 dark:text-primary-dark'
const warnChipClass = 'bg-amber-500/10 text-amber-700 dark:bg-amber-400/10 dark:text-amber-300'

onMounted(() => {
  void reloadAll()
})

watch([recordKindFilter, actorRoleFilter, directionFilter], () => {
  if (!selectedSpace.value) return
  page.value = 1
  void loadMessages()
})

async function reloadAll() {
  loading.value = true
  try {
    await loadSpaces()
  } catch (error) {
    showNotice(extractErrorMessage(error, '聊天记录空间加载失败'), 'error')
  } finally {
    loading.value = false
  }
}

async function loadSpaces() {
  const payload: ChatHistorySpaceListResponse = await fetchChatHistorySpaces({
    kind: activeKind.value,
    q: spaceSearch.value.trim() || undefined,
  })
  storageRoot.value = payload.root
  spaces.value = payload.items

  const currentKey = selectedSpace.value?.key
  const nextSpace = payload.items.find((item) => item.key === currentKey) || payload.items[0] || null
  selectedSpace.value = nextSpace
  if (nextSpace) {
    await loadSpaceDetail(nextSpace.kind, nextSpace.owner_id)
  } else {
    spaceDetail.value = null
    messages.value = []
    selectedMessageKey.value = ''
    messageTotal.value = 0
  }
}

async function switchKind(kind: ChatHistorySpaceKind) {
  if (activeKind.value === kind) return
  activeKind.value = kind
  selectedSpace.value = null
  spaceDetail.value = null
  messages.value = []
  selectedMessageKey.value = ''
  page.value = 1
  try {
    await loadSpaces()
  } catch (error) {
    showNotice(extractErrorMessage(error, '聊天记录空间加载失败'), 'error')
  }
}

function scheduleSpaceSearch() {
  if (spaceSearchTimer) window.clearTimeout(spaceSearchTimer)
  spaceSearchTimer = window.setTimeout(() => {
    void reloadAll()
  }, 260)
}

function scheduleMessageSearch() {
  if (!selectedSpace.value) return
  if (messageSearchTimer) window.clearTimeout(messageSearchTimer)
  messageSearchTimer = window.setTimeout(() => {
    page.value = 1
    void loadMessages()
  }, 260)
}

async function selectSpace(space: ChatHistorySpaceSummary) {
  if (selectedSpace.value?.key === space.key) return
  selectedSpace.value = space
  page.value = 1
  selectedMessageKey.value = ''
  try {
    await loadSpaceDetail(space.kind, space.owner_id)
  } catch (error) {
    showNotice(extractErrorMessage(error, '聊天空间详情加载失败'), 'error')
  }
}

async function loadSpaceDetail(kind: ChatHistorySpaceKind, ownerId: string) {
  spaceDetail.value = await fetchChatHistorySpaceDetail(kind, ownerId)
  selectedSpace.value = selectedSpace.value
    ? ({ ...selectedSpace.value, ...spaceDetail.value } as ChatHistorySpaceSummary)
    : ({ ...spaceDetail.value } as ChatHistorySpaceSummary)
  await loadMessages()
}

async function loadMessages() {
  if (!selectedSpace.value) return
  messageLoading.value = true
  try {
    const payload: ChatHistoryMessageListResponse = await fetchChatHistoryMessages(
      selectedSpace.value.kind,
      selectedSpace.value.owner_id,
      {
        q: messageQuery.value.trim() || undefined,
        record_kind: recordKindFilter.value,
        actor_role: actorRoleFilter.value,
        direction: directionFilter.value,
        page: page.value,
        page_size: pageSize,
      },
    )
    messages.value = payload.items
    messageTotal.value = payload.total
    if (!payload.items.some((item) => item.event_key === selectedMessageKey.value)) {
      selectedMessageKey.value = payload.items[0]?.event_key || ''
    }
  } catch (error) {
    showNotice(extractErrorMessage(error, '消息记录加载失败'), 'error')
  } finally {
    messageLoading.value = false
  }
}

async function changePage(nextPage: number) {
  if (!selectedSpace.value || nextPage < 1 || nextPage > pageCount.value) return
  page.value = nextPage
  await loadMessages()
}

function latestPreviewText(space: ChatHistorySpaceSummary) {
  if (!space.latest_message_preview) return '暂无消息内容'
  const role = actorRoleLabel(space.latest_message_actor_role as ChatHistoryActorRole | 'unknown')
  const userName = space.latest_message_user_name || '未知发送者'
  return `${role} · ${userName}：${space.latest_message_preview}`
}

function kindLabel(kind: ChatHistorySpaceKind) {
  return kind === 'user' ? '用户私聊' : '群聊采集'
}

function recordKindLabel(value: ChatHistoryRecordKind | 'all') {
  const labels: Record<string, string> = {
    all: '全部类型',
    chat: '聊天消息',
    collect: '采集消息',
  }
  return labels[value] || value
}

function actorRoleLabel(value: ChatHistoryActorRole | 'all' | 'unknown') {
  const labels: Record<string, string> = {
    all: '全部角色',
    user: '用户',
    assistant: '助手',
    system: '系统',
    unknown: '消息',
  }
  return labels[value] || value
}

function directionLabel(value: ChatHistoryDirection | 'all' | 'unknown') {
  const labels: Record<string, string> = {
    all: '全部方向',
    inbound: '入站',
    outbound: '出站',
    unknown: '方向未知',
  }
  return labels[value] || value
}

function actorChipClass(value: ChatHistoryActorRole) {
  if (value === 'assistant') return 'bg-sky-500/10 text-sky-700 dark:bg-sky-400/12 dark:text-sky-300'
  if (value === 'system') return 'bg-amber-500/10 text-amber-700 dark:bg-amber-400/12 dark:text-amber-300'
  return okChipClass
}

function directionChipClass(value: ChatHistoryDirection) {
  return value === 'outbound'
    ? 'bg-rose-500/10 text-rose-700 dark:bg-rose-400/12 dark:text-rose-300'
    : 'bg-slate-500/10 text-slate-700 dark:bg-slate-400/12 dark:text-slate-300'
}

function recordChipClass(value: ChatHistoryRecordKind) {
  return value === 'collect'
    ? 'bg-violet-500/10 text-violet-700 dark:bg-violet-400/12 dark:text-violet-300'
    : 'bg-emerald-500/10 text-emerald-700 dark:bg-emerald-400/12 dark:text-emerald-300'
}

function formatMetadata(value: Record<string, unknown>) {
  try {
    return JSON.stringify(value || {}, null, 2)
  } catch {
    return '{}'
  }
}

function formatBytes(value: number) {
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = value
  let index = 0
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024
    index += 1
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`
}

function formatDateTime(value: string | null | undefined) {
  if (!value) return '暂无记录'
  try {
    return new Date(value).toLocaleString('zh-CN')
  } catch {
    return value
  }
}

function showNotice(text: string, tone: 'success' | 'error') {
  notice.value = text
  noticeTone.value = tone
}

function extractErrorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  return fallback
}
</script>
