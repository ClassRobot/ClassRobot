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

            <div class="grid min-w-0 gap-2 md:grid-cols-2 2xl:grid-cols-[176px_140px_140px_140px_auto]">
              <AppDatePicker
                v-model="messageDate"
                :available-dates="availableMessageDates"
                button-class="h-9"
                :disabled="!selectedSpace || availableMessageDates.length === 0"
                @change="applyMessageDate"
              />
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
              <button
                type="button"
                class="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-error/20 bg-error-container/35 px-3 text-body-sm text-error transition-colors hover:bg-error-container/55 disabled:cursor-not-allowed disabled:opacity-50 dark:border-red-900/45 dark:bg-red-950/30 dark:text-red-300 dark:hover:bg-red-950/45"
                :disabled="!selectedSpace"
                @click="openDeleteSpaceDialog"
              >
                <Trash2 :size="14" />
                删除空间
              </button>
            </div>
          </div>
        </div>

        <div class="grid min-h-0 flex-1 grid-cols-1 overflow-hidden xl:grid-cols-[minmax(0,1fr)_360px]">
          <div class="flex min-w-0 flex-col overflow-hidden border-b border-outline-variant dark:border-zinc-800 xl:border-b-0 xl:border-r">
            <div
              ref="messageScrollRef"
              class="min-h-0 flex-1 overflow-y-auto bg-[radial-gradient(circle_at_top,rgba(59,130,246,0.08),transparent_38%)] p-4 dark:bg-[radial-gradient(circle_at_top,rgba(56,189,248,0.08),transparent_34%)]"
            >
              <template v-if="selectedSpace">
                <div class="space-y-3">
                  <button
                    v-for="messageItem in orderedMessages"
                    :key="messageItem.event_key"
                    type="button"
                    class="group flex w-full text-left transition-transform duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/35 dark:focus-visible:ring-primary-dark/35"
                    :class="isSystemMessage(messageItem)
                      ? 'justify-center'
                      : (isAssistantMessage(messageItem) ? 'justify-end' : 'justify-start')"
                    @click="selectedMessageKey = messageItem.event_key"
                  >
                    <div
                      v-if="isSystemMessage(messageItem)"
                      class="flex w-full max-w-[820px] flex-col items-center"
                    >
                      <div class="mb-2 inline-flex items-center gap-2 rounded-full border border-amber-200/80 bg-amber-50/90 px-3 py-1.5 dark:border-amber-500/25 dark:bg-amber-500/10">
                        <span
                          class="flex h-8 w-8 items-center justify-center rounded-full border border-amber-300/70 bg-amber-100 text-[12px] font-semibold text-amber-800 dark:border-amber-400/35 dark:bg-amber-400/18 dark:text-amber-100"
                        >
                          {{ messageAvatarText(messageItem) }}
                        </span>
                        <span class="max-w-[180px] truncate text-[12px] font-semibold text-amber-900 dark:text-amber-100">
                          {{ messageDisplayName(messageItem) }}
                        </span>
                        <span class="rounded-full px-2 py-0.5 text-[10px]" :class="actorChipClass(messageItem.actor_role)">
                          {{ actorRoleLabel(messageItem.actor_role) }}
                        </span>
                      </div>

                      <div
                        class="w-full rounded-[24px] border px-4 py-3 shadow-[0_16px_34px_-28px_rgba(245,158,11,0.8)] transition-all duration-200"
                        :class="messageBubbleClass(messageItem, selectedMessage?.event_key === messageItem.event_key)"
                      >
                        <div class="mb-2 flex flex-wrap items-center gap-2">
                          <span class="rounded-full px-2 py-0.5 text-[10px]" :class="recordChipClass(messageItem.record_kind)">
                            {{ recordKindLabel(messageItem.record_kind) }}
                          </span>
                          <span class="rounded-full px-2 py-0.5 text-[10px]" :class="directionChipClass(messageItem.direction)">
                            {{ directionLabel(messageItem.direction) }}
                          </span>
                        </div>
                        <div class="whitespace-pre-wrap break-words text-[13px] leading-6 text-on-surface dark:text-zinc-100">
                          <template
                            v-for="(segment, segmentIndex) in messageTextSegments(messageItem)"
                            :key="`${messageItem.event_key}-system-${segmentIndex}`"
                          >
                            <mark
                              v-if="segment.matchIndex !== null"
                              :data-search-match-id="searchMatchDomId(segment.matchIndex)"
                              :class="searchHighlightClass(segment.matchIndex)"
                            >
                              {{ segment.text }}
                            </mark>
                            <span v-else>{{ segment.text }}</span>
                          </template>
                        </div>
                      </div>

                      <div class="mt-2 flex flex-wrap items-center justify-center gap-2 text-[11px] text-on-surface-variant dark:text-zinc-500">
                        <span>{{ formatDateTime(messageItem.created_at) }}</span>
                        <span class="h-1 w-1 rounded-full bg-current/40"></span>
                        <span class="font-code-inline text-code-inline">{{ messageItem.message_id || '消息 ID 未记录' }}</span>
                      </div>
                    </div>

                    <div
                      v-else
                      class="flex w-full max-w-[900px] items-start gap-3"
                      :class="isAssistantMessage(messageItem) ? 'flex-row-reverse' : ''"
                    >
                      <div
                        class="mt-7 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl border text-[14px] font-semibold shadow-[0_18px_30px_-24px_rgba(15,23,42,0.55)] transition-transform duration-200 group-hover:-translate-y-0.5"
                        :class="messageAvatarClass(messageItem)"
                      >
                        {{ messageAvatarText(messageItem) }}
                      </div>

                      <div class="min-w-0 max-w-[84%]">
                        <div
                          class="mb-1.5 flex items-center gap-2 px-1"
                          :class="isAssistantMessage(messageItem) ? 'justify-end' : 'justify-start'"
                        >
                          <span class="truncate text-[13px] font-semibold text-on-surface dark:text-zinc-100">
                            {{ messageDisplayName(messageItem) }}
                          </span>
                          <span class="rounded-full px-2 py-0.5 text-[10px]" :class="actorChipClass(messageItem.actor_role)">
                            {{ actorRoleLabel(messageItem.actor_role) }}
                          </span>
                          <span class="rounded-full px-2 py-0.5 text-[10px]" :class="recordChipClass(messageItem.record_kind)">
                            {{ recordKindLabel(messageItem.record_kind) }}
                          </span>
                        </div>

                        <div
                          class="rounded-[24px] border px-4 py-3 shadow-[0_18px_36px_-26px_rgba(15,23,42,0.46)] transition-all duration-200"
                          :class="messageBubbleClass(messageItem, selectedMessage?.event_key === messageItem.event_key)"
                        >
                          <div class="whitespace-pre-wrap break-words text-[13px] leading-6 text-on-surface dark:text-zinc-100">
                            <template
                              v-for="(segment, segmentIndex) in messageTextSegments(messageItem)"
                              :key="`${messageItem.event_key}-chat-${segmentIndex}`"
                            >
                              <mark
                                v-if="segment.matchIndex !== null"
                                :data-search-match-id="searchMatchDomId(segment.matchIndex)"
                                :class="searchHighlightClass(segment.matchIndex)"
                              >
                                {{ segment.text }}
                              </mark>
                              <span v-else>{{ segment.text }}</span>
                            </template>
                          </div>
                        </div>

                        <div
                          class="mt-1.5 flex flex-wrap items-center gap-2 px-1 text-[11px] text-on-surface-variant dark:text-zinc-500"
                          :class="isAssistantMessage(messageItem) ? 'justify-end' : 'justify-start'"
                        >
                          <span class="rounded-full px-2 py-0.5 text-[10px]" :class="directionChipClass(messageItem.direction)">
                            {{ directionLabel(messageItem.direction) }}
                          </span>
                          <span>{{ formatDateTime(messageItem.created_at) }}</span>
                          <span class="h-1 w-1 rounded-full bg-current/40"></span>
                          <span class="font-code-inline text-code-inline">{{ messageItem.message_id || '消息 ID 未记录' }}</span>
                        </div>
                      </div>
                    </div>
                  </button>
                </div>

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

            <div class="shrink-0 border-t border-outline-variant px-4 py-3 dark:border-zinc-800">
              <div class="grid gap-3 xl:grid-cols-[minmax(180px,1fr)_minmax(340px,460px)] xl:items-center 2xl:grid-cols-[minmax(200px,1fr)_minmax(400px,500px)]">
                <div class="min-w-0">
                  <div class="text-[11px] uppercase tracking-[0.14em] text-on-surface-variant dark:text-zinc-500">消息流</div>
                  <div class="mt-1 text-body-sm text-on-surface dark:text-zinc-100">
                    <div class="truncate">
                      {{ selectedSpace ? messageSummaryText : '当前没有选中的聊天空间' }}
                    </div>
                    <div
                      v-if="selectedSpace && messageDate"
                      class="mt-2 inline-flex items-center gap-1.5 rounded-full border border-primary/12 bg-primary/6 px-2.5 py-1 text-[11px] text-primary dark:border-primary-dark/18 dark:bg-primary-dark/10 dark:text-primary-dark"
                    >
                      <CalendarDays :size="12" />
                      指定日期：{{ messageDate }}
                    </div>
                  </div>
                </div>

                <div class="flex min-w-0 items-center gap-2 xl:self-center xl:justify-self-end">
                  <div class="flex h-10 min-w-0 flex-1 items-center gap-1 rounded-xl border border-outline-variant bg-surface-container-lowest px-2 shadow-sm dark:border-zinc-700 dark:bg-zinc-900">
                    <Search :size="15" class="ml-1 shrink-0 text-on-surface-variant dark:text-zinc-500" />
                    <input
                      v-model="messageQuery"
                      class="h-8 min-w-0 flex-1 bg-transparent px-1 text-body-sm text-on-surface outline-none placeholder:text-on-surface-variant disabled:cursor-not-allowed disabled:opacity-50 dark:text-zinc-100 dark:placeholder:text-zinc-500"
                      placeholder="查找当前日期消息"
                      :disabled="!selectedSpace"
                      @input="handleMessageSearchInput"
                      @keydown.enter.exact.prevent="jumpToNextSearchMatch"
                      @keydown.enter.shift.prevent="jumpToPreviousSearchMatch"
                    />
                    <span class="shrink-0 rounded-md bg-surface-container px-2 py-1 font-code-inline text-[11px] text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400">
                      {{ searchPositionText }}
                    </span>
                    <button
                      type="button"
                      class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-40 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                      :disabled="!hasSearchMatches"
                      title="上一个"
                      @click="jumpToPreviousSearchMatch"
                    >
                      <ChevronUp :size="15" />
                    </button>
                    <button
                      type="button"
                      class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-40 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                      :disabled="!hasSearchMatches"
                      title="下一个"
                      @click="jumpToNextSearchMatch"
                    >
                      <ChevronDown :size="15" />
                    </button>
                    <button
                      type="button"
                      class="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-on-surface-variant transition-colors hover:bg-surface-container-high hover:text-on-surface disabled:cursor-not-allowed disabled:opacity-40 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100"
                      :disabled="!messageQuery"
                      title="清空查找"
                      @click="clearMessageSearch"
                    >
                      <X :size="14" />
                    </button>
                  </div>
                  <span class="shrink-0 rounded-full bg-surface-container px-2.5 py-1 text-[11px] text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400">
                    {{ messageTotal }} 条
                  </span>
                </div>
              </div>
            </div>
          </div>

          <aside class="flex min-h-0 flex-col overflow-hidden">
            <div class="shrink-0 border-b border-outline-variant px-4 py-3 dark:border-zinc-800">
              <h3 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">
                {{ selectedMessage ? '消息详情' : '空间概览' }}
              </h3>
              <p class="mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">
                {{ selectedMessage ? messageDisplayName(selectedMessage) : (selectedSpace?.chat_path || '选择消息后查看完整内容') }}
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
                      <template
                        v-for="(segment, segmentIndex) in messageTextSegments(selectedMessage)"
                        :key="`${selectedMessage.event_key}-detail-${segmentIndex}`"
                      >
                        <mark
                          v-if="segment.matchIndex !== null"
                          :class="searchHighlightClass(segment.matchIndex)"
                        >
                          {{ segment.text }}
                        </mark>
                        <span v-else>{{ segment.text }}</span>
                      </template>
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

  <DangerConfirmDialog
    :open="Boolean(deleteSpaceDialog)"
    :busy="messageLoading"
    :error-message="deleteSpaceError"
    title="确认删除聊天记录空间"
    message="将删除当前聊天空间下的消息数据库与聊天目录，包含用户消息、机器人回复、采集记录以及运行态缓存。该操作不可恢复。"
    :target-label="deleteSpaceDialog?.title || ''"
    :target-hint="deleteSpaceDialog?.hint || ''"
    confirm-label="确认删除"
    width="min(560px, calc(100vw - 32px))"
    @close="closeDeleteSpaceDialog"
    @confirm="confirmDeleteSpace"
  >
    <template #details>
      <div
        v-if="deleteSpaceDialog"
        class="rounded-xl border border-outline-variant bg-surface-container-low px-4 py-3 dark:border-zinc-800 dark:bg-zinc-800/55"
      >
        <div class="grid grid-cols-2 gap-3 text-body-sm">
          <div>
            <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">空间类型</div>
            <div class="mt-1 text-on-surface dark:text-zinc-100">{{ kindLabel(deleteSpaceDialog.kind) }}</div>
          </div>
          <div>
            <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">空间标识</div>
            <div class="mt-1 font-code-inline text-code-inline text-on-surface dark:text-zinc-100">{{ deleteSpaceDialog.ownerId }}</div>
          </div>
        </div>
      </div>
    </template>
  </DangerConfirmDialog>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  CalendarDays,
  ChevronDown,
  ChevronUp,
  ChartColumnBig,
  Database,
  History,
  Link2,
  MessagesSquare,
  RefreshCw,
  Search,
  Trash2,
  UserRound,
  Users,
  X,
} from 'lucide-vue-next'
import AppDatePicker from '@/components/AppDatePicker.vue'
import AppSelect from '@/components/AppSelect.vue'
import DangerConfirmDialog from '@/components/DangerConfirmDialog.vue'
import {
  deleteChatHistorySpace,
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

interface MessageSearchMatch {
  messageKey: string
  start: number
  end: number
  matchIndex: number
}

interface MessageTextSegment {
  text: string
  matchIndex: number | null
}

const loading = ref(false)
const messageLoading = ref(false)
const activeKind = ref<ChatHistorySpaceKind>('user')
const spaceSearch = ref('')
const messageQuery = ref('')
const messageDate = ref('')
const recordKindFilter = ref<'all' | ChatHistoryRecordKind>('all')
const actorRoleFilter = ref<'all' | ChatHistoryActorRole>('all')
const directionFilter = ref<'all' | ChatHistoryDirection>('all')
const storageRoot = ref('')
const spaces = ref<ChatHistorySpaceSummary[]>([])
const selectedSpace = ref<ChatHistorySpaceSummary | null>(null)
const spaceDetail = ref<ChatHistorySpaceDetail | null>(null)
const messages = ref<ChatHistoryMessage[]>([])
const availableMessageDates = ref<string[]>([])
const selectedMessageKey = ref('')
const messageTotal = ref(0)
const notice = ref('')
const noticeTone = ref<'success' | 'error'>('success')
const deleteSpaceDialog = ref<{ key: string; kind: ChatHistorySpaceKind; ownerId: string; title: string; hint: string } | null>(null)
const deleteSpaceError = ref('')
const messageScrollRef = ref<HTMLElement | null>(null)
const activeSearchMatchIndex = ref(0)

let spaceSearchTimer: ReturnType<typeof setTimeout> | undefined
const route = useRoute()
const router = useRouter()

const spaceKinds: ChatHistorySpaceKind[] = ['user', 'group']

const totalMessages = computed(() => spaces.value.reduce((sum, item) => sum + item.message_count, 0))
const totalCollectMessages = computed(() => spaces.value.reduce((sum, item) => sum + item.record_counts.collect, 0))
const totalChatMessages = computed(() => spaces.value.reduce((sum, item) => sum + item.record_counts.chat, 0))
const storageRootText = computed(() => storageRoot.value || '等待读取 storage 根目录')
const selectedMessage = computed(() => messages.value.find((item) => item.event_key === selectedMessageKey.value) || null)
const orderedMessages = computed(() => [...messages.value].reverse())
const normalizedMessageQuery = computed(() => messageQuery.value.trim())
const messageSearchMatchMap = computed(() => {
  const query = normalizedMessageQuery.value
  const matchMap = new Map<string, MessageSearchMatch[]>()
  if (!query) return matchMap

  let matchIndex = 0
  for (const message of orderedMessages.value) {
    const ranges = findSearchRanges(messagePreviewText(message), query)
    if (ranges.length === 0) continue

    matchMap.set(
      message.event_key,
      ranges.map((range) => ({
        messageKey: message.event_key,
        start: range.start,
        end: range.end,
        matchIndex: matchIndex++,
      })),
    )
  }
  return matchMap
})
const messageSearchMatches = computed(() => Array.from(messageSearchMatchMap.value.values()).flat())
const searchTotal = computed(() => messageSearchMatches.value.length)
const hasSearchMatches = computed(() => searchTotal.value > 0)
const activeSearchIndex = computed(() => {
  if (!hasSearchMatches.value) return -1
  return Math.min(activeSearchMatchIndex.value, searchTotal.value - 1)
})
const searchPositionText = computed(() => {
  if (!normalizedMessageQuery.value) return '查找'
  if (!hasSearchMatches.value) return '0 项'
  return `第 ${activeSearchIndex.value + 1} 项，共 ${searchTotal.value} 项`
})
const messageSummaryText = computed(() => {
  if (!selectedSpace.value) return ''
  const parts = [`共 ${messageTotal.value} 条消息`]
  if (messageDate.value) parts.push(`日期：${messageDate.value}`)
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
  const requestedKind = normalizeRouteKind(route.query.kind)
  if (requestedKind) {
    activeKind.value = requestedKind
  }
  void reloadAll()
})

watch([recordKindFilter, actorRoleFilter, directionFilter], () => {
  if (!selectedSpace.value) return
  void loadMessages()
})

watch(messageSearchMatches, (matches) => {
  if (matches.length === 0) {
    activeSearchMatchIndex.value = 0
    return
  }
  if (activeSearchMatchIndex.value >= matches.length) {
    activeSearchMatchIndex.value = matches.length - 1
  }
})

watch(() => [route.query.kind, route.query.ownerId], () => {
  const requestedKind = normalizeRouteKind(route.query.kind)
  const requestedOwnerId = getRouteOwnerId()
  if (requestedKind === activeKind.value && requestedOwnerId === (selectedSpace.value?.owner_id || '')) {
    return
  }
  if (requestedKind) {
    activeKind.value = requestedKind
  }
  void reloadAll()
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
  let payload: ChatHistorySpaceListResponse = await fetchChatHistorySpaces({
    kind: activeKind.value,
    q: spaceSearch.value.trim() || undefined,
  })
  const requestedOwnerId = getRequestedOwnerId(activeKind.value)
  if (requestedOwnerId && spaceSearch.value.trim() && !payload.items.some((item) => item.owner_id === requestedOwnerId)) {
    spaceSearch.value = ''
    payload = await fetchChatHistorySpaces({ kind: activeKind.value })
  }
  storageRoot.value = payload.root
  spaces.value = payload.items

  const currentKey = selectedSpace.value?.key
  const nextSpace = payload.items.find((item) => item.owner_id === requestedOwnerId)
    || payload.items.find((item) => item.key === currentKey)
    || payload.items[0]
    || null
  selectedSpace.value = nextSpace
  if (nextSpace) {
    await loadSpaceDetail(nextSpace.kind, nextSpace.owner_id)
  } else {
    spaceDetail.value = null
    availableMessageDates.value = []
    messageDate.value = ''
    messages.value = []
    selectedMessageKey.value = ''
    messageTotal.value = 0
  }
  syncSelectionQuery(nextSpace)
}

async function switchKind(kind: ChatHistorySpaceKind) {
  if (activeKind.value === kind) return
  activeKind.value = kind
  selectedSpace.value = null
  spaceDetail.value = null
  availableMessageDates.value = []
  messages.value = []
  selectedMessageKey.value = ''
  messageDate.value = ''
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

async function selectSpace(space: ChatHistorySpaceSummary) {
  if (selectedSpace.value?.key === space.key) return
  selectedSpace.value = space
  availableMessageDates.value = []
  messageDate.value = ''
  selectedMessageKey.value = ''
  try {
    await loadSpaceDetail(space.kind, space.owner_id)
    syncSelectionQuery(selectedSpace.value)
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
        record_kind: recordKindFilter.value,
        actor_role: actorRoleFilter.value,
        direction: directionFilter.value,
        message_date: messageDate.value || undefined,
      },
    )
    availableMessageDates.value = payload.available_dates || []
    messageDate.value = payload.message_date || ''
    messages.value = payload.items
    messageTotal.value = payload.total
    if (!payload.items.some((item) => item.event_key === selectedMessageKey.value)) {
      selectedMessageKey.value = payload.items[0]?.event_key || ''
    }
    await revealSearchMatchOrBottom()
  } catch (error) {
    showNotice(extractErrorMessage(error, '消息记录加载失败'), 'error')
  } finally {
    messageLoading.value = false
  }
}

function applyMessageDate() {
  if (!selectedSpace.value) return
  void loadMessages()
}

function handleMessageSearchInput() {
  activeSearchMatchIndex.value = 0
  void revealFirstSearchMatch()
}

function clearMessageSearch() {
  messageQuery.value = ''
  activeSearchMatchIndex.value = 0
  void scrollMessageListToBottom()
}

function jumpToNextSearchMatch() {
  if (!hasSearchMatches.value) return
  setActiveSearchMatch(activeSearchIndex.value + 1)
}

function jumpToPreviousSearchMatch() {
  if (!hasSearchMatches.value) return
  setActiveSearchMatch(activeSearchIndex.value - 1)
}

function setActiveSearchMatch(nextIndex: number) {
  const total = searchTotal.value
  if (total <= 0) return
  activeSearchMatchIndex.value = (nextIndex + total) % total
  const match = messageSearchMatches.value[activeSearchIndex.value]
  if (match) {
    selectedMessageKey.value = match.messageKey
  }
  void scrollToActiveSearchMatch()
}

function openDeleteSpaceDialog() {
  if (!selectedSpace.value) return
  deleteSpaceError.value = ''
  deleteSpaceDialog.value = {
    key: selectedSpace.value.key,
    kind: selectedSpace.value.kind,
    ownerId: selectedSpace.value.owner_id,
    title: selectedSpace.value.title,
    hint: selectedSpace.value.db_path,
  }
}

function closeDeleteSpaceDialog() {
  if (messageLoading.value) return
  deleteSpaceDialog.value = null
  deleteSpaceError.value = ''
}

async function confirmDeleteSpace() {
  const dialog = deleteSpaceDialog.value
  if (!dialog) return

  messageLoading.value = true
  deleteSpaceError.value = ''
  try {
    await deleteChatHistorySpace(dialog.kind, dialog.ownerId)
    if (selectedSpace.value?.key === dialog.key) {
      selectedSpace.value = null
      spaceDetail.value = null
      availableMessageDates.value = []
      messages.value = []
      selectedMessageKey.value = ''
      messageTotal.value = 0
    }
    deleteSpaceDialog.value = null
    showNotice('聊天记录空间已删除', 'success')
    await loadSpaces()
  } catch (error) {
    deleteSpaceError.value = extractErrorMessage(error, '聊天记录空间删除失败，请稍后重试')
  } finally {
    messageLoading.value = false
  }
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

function isSystemMessage(message: ChatHistoryMessage) {
  return message.actor_role === 'system'
}

function isAssistantMessage(message: ChatHistoryMessage) {
  if (isSystemMessage(message)) return false
  return message.actor_role === 'assistant' || message.direction === 'outbound'
}

function messageDisplayName(message: ChatHistoryMessage) {
  const fallback = isSystemMessage(message)
    ? '系统消息'
    : (isAssistantMessage(message) ? '机器人' : '用户')
  return message.user_name?.trim() || fallback
}

function messageInitial(value: string | null | undefined) {
  const normalized = value?.trim()
  if (!normalized) return '访'
  return normalized.charAt(0).toUpperCase()
}

function messageAvatarText(message: ChatHistoryMessage) {
  if (isSystemMessage(message)) return '系'
  if (isAssistantMessage(message)) return '机'
  return messageInitial(message.user_name)
}

function messageAvatarClass(message: ChatHistoryMessage) {
  if (isSystemMessage(message)) {
    return 'border-amber-300/70 bg-amber-100 text-amber-800 dark:border-amber-400/35 dark:bg-amber-400/18 dark:text-amber-100'
  }
  if (isAssistantMessage(message)) {
    return 'border-primary/20 bg-primary text-white dark:border-primary-dark/30 dark:bg-primary-dark dark:text-zinc-950'
  }
  return 'border-slate-200 bg-white text-slate-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100'
}

function messageBubbleClass(message: ChatHistoryMessage, active: boolean) {
  if (isSystemMessage(message)) {
    return [
      'border-amber-200/85 bg-amber-50/95 dark:border-amber-500/25 dark:bg-amber-500/8',
      active ? 'ring-2 ring-amber-400/30 dark:ring-amber-400/25 shadow-[0_22px_44px_-32px_rgba(245,158,11,0.9)]' : 'hover:border-amber-300/85 dark:hover:border-amber-400/30',
    ].join(' ')
  }
  if (isAssistantMessage(message)) {
    return [
      'border-primary/20 bg-[linear-gradient(135deg,rgba(59,130,246,0.14),rgba(255,255,255,0.94))] dark:border-primary-dark/25 dark:bg-[linear-gradient(135deg,rgba(56,189,248,0.18),rgba(24,24,27,0.96))]',
      active ? 'ring-2 ring-primary/25 dark:ring-primary-dark/25 shadow-[0_22px_44px_-30px_rgba(37,99,235,0.8)]' : 'hover:border-primary/30 dark:hover:border-primary-dark/35',
    ].join(' ')
  }
  return [
    'border-slate-200/85 bg-[linear-gradient(180deg,rgba(255,255,255,0.98),rgba(248,250,252,0.94))] dark:border-zinc-700/85 dark:bg-[linear-gradient(180deg,rgba(39,39,42,0.95),rgba(24,24,27,0.98))]',
    active ? 'ring-2 ring-slate-300/70 dark:ring-zinc-500/35 shadow-[0_22px_44px_-30px_rgba(15,23,42,0.55)]' : 'hover:border-slate-300/85 dark:hover:border-zinc-600',
  ].join(' ')
}

function messagePreviewText(message: ChatHistoryMessage) {
  return message.display_text || message.raw_text || message.plain_text || '该消息没有可展示的文本内容'
}

function findSearchRanges(text: string, query: string) {
  const normalizedText = text.toLocaleLowerCase()
  const normalizedQuery = query.trim().toLocaleLowerCase()
  if (!normalizedQuery) return []

  const ranges: Array<{ start: number; end: number }> = []
  let cursor = 0
  while (cursor < normalizedText.length) {
    const start = normalizedText.indexOf(normalizedQuery, cursor)
    if (start < 0) break
    ranges.push({ start, end: start + normalizedQuery.length })
    cursor = start + normalizedQuery.length
  }
  return ranges
}

function messageTextSegments(message: ChatHistoryMessage): MessageTextSegment[] {
  const text = messagePreviewText(message)
  const matches = messageSearchMatchMap.value.get(message.event_key) || []
  if (matches.length === 0) {
    return [{ text, matchIndex: null }]
  }

  const segments: MessageTextSegment[] = []
  let cursor = 0
  for (const match of matches) {
    if (match.start > cursor) {
      segments.push({ text: text.slice(cursor, match.start), matchIndex: null })
    }
    segments.push({
      text: text.slice(match.start, match.end),
      matchIndex: match.matchIndex,
    })
    cursor = match.end
  }

  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), matchIndex: null })
  }
  return segments
}

function searchMatchDomId(matchIndex: number) {
  return `chat-search-match-${matchIndex}`
}

function searchHighlightClass(matchIndex: number) {
  return matchIndex === activeSearchIndex.value
    ? 'rounded-md bg-amber-300/95 px-0.5 text-slate-950 shadow-[0_0_0_1px_rgba(245,158,11,0.32)] dark:bg-amber-300 dark:text-slate-950'
    : 'rounded-md bg-amber-200/68 px-0.5 text-current dark:bg-amber-500/24 dark:text-zinc-100'
}

async function scrollMessageListToBottom() {
  await nextTick()
  const container = messageScrollRef.value
  if (!container) return
  container.scrollTop = container.scrollHeight
}

async function revealFirstSearchMatch() {
  if (!normalizedMessageQuery.value || !hasSearchMatches.value) {
    await scrollMessageListToBottom()
    return
  }
  setActiveSearchMatch(searchTotal.value - 1)
}

async function scrollToActiveSearchMatch() {
  await nextTick()
  const container = messageScrollRef.value
  if (!container || activeSearchIndex.value < 0) return

  const target = container.querySelector<HTMLElement>(
    `[data-search-match-id="${searchMatchDomId(activeSearchIndex.value)}"]`,
  )
  if (!target) {
    await scrollMessageListToBottom()
    return
  }
  target.scrollIntoView({ block: 'center', behavior: 'smooth' })
}

async function revealSearchMatchOrBottom() {
  if (normalizedMessageQuery.value && hasSearchMatches.value) {
    await scrollToActiveSearchMatch()
    return
  }
  await scrollMessageListToBottom()
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

function normalizeRouteKind(value: unknown): ChatHistorySpaceKind | null {
  return value === 'user' || value === 'group' ? value : null
}

function getRouteOwnerId() {
  return typeof route.query.ownerId === 'string' ? route.query.ownerId.trim() : ''
}

function getRequestedOwnerId(kind: ChatHistorySpaceKind) {
  return normalizeRouteKind(route.query.kind) === kind ? getRouteOwnerId() : ''
}

function syncSelectionQuery(space: ChatHistorySpaceSummary | null) {
  const nextKind = space?.kind || activeKind.value
  const nextOwnerId = space?.owner_id || ''
  if (normalizeRouteKind(route.query.kind) === nextKind && getRouteOwnerId() === nextOwnerId) {
    return
  }

  void router.replace({
    name: 'ChatHistory',
    query: {
      ...route.query,
      kind: nextKind,
      ownerId: nextOwnerId || undefined,
    },
  })
}

function extractErrorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  return fallback
}
</script>
