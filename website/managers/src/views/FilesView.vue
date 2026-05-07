<template>
  <div class="flex h-[calc(100vh-96px)] min-h-0 flex-col gap-4 overflow-hidden">
    <div class="flex shrink-0 flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">文件空间</h1>
        <p class="mt-1 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">
          浏览用户与群组隔离存储，进行文本维护与目录清理
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

    <div v-if="message" class="shrink-0 rounded-lg border px-3 py-2 text-body-sm" :class="messageClass">
      {{ message }}
    </div>

    <div class="grid shrink-0 grid-cols-2 gap-3 xl:grid-cols-4">
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">空间</span>
          <FolderKanban :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ spaces.length }}</div>
        <div class="mt-1 text-body-sm text-on-surface-variant dark:text-zinc-500">当前 {{ kindLabel(activeKind) }}</div>
      </div>
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">已关联</span>
          <Link2 :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ linkedSpaces }}</div>
        <div class="mt-1 text-body-sm text-on-surface-variant dark:text-zinc-500">数据库实体已映射</div>
      </div>
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">文件数</span>
          <Files :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ totalFiles }}</div>
        <div class="mt-1 text-body-sm text-on-surface-variant dark:text-zinc-500">当前筛选空间累计</div>
      </div>
      <div class="rounded-xl border border-outline-variant bg-surface-container-lowest p-4 dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex items-center justify-between">
          <span class="font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">容量</span>
          <HardDrive :size="16" class="text-primary dark:text-primary-dark" />
        </div>
        <div class="mt-3 font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ totalSizeText }}</div>
        <div class="mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">{{ selectedSpace?.title || '尚未选择空间' }}</div>
      </div>
    </div>

    <div class="grid min-h-0 flex-1 grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <aside class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="shrink-0 border-b border-outline-variant bg-surface-bright p-3 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div class="grid grid-cols-2 gap-1 rounded-lg border border-outline-variant bg-surface-container p-0.5 dark:border-zinc-700 dark:bg-zinc-800">
            <button
              v-for="kind in spaceKinds"
              :key="kind"
              type="button"
              class="flex h-9 items-center justify-center gap-1.5 rounded-md text-[12px] font-semibold transition-colors"
              :class="activeKind === kind ? activeSegmentClass : inactiveSegmentClass"
              @click="switchKind(kind)"
            >
              <User v-if="kind === 'user'" :size="14" />
              <Users v-else :size="14" />
              {{ kindLabel(kind) }}
            </button>
          </div>

          <div class="relative mt-3">
            <Search :size="15" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant dark:text-zinc-500" />
            <input
              v-model="search"
              class="h-9 w-full rounded-lg border border-outline-variant bg-surface-container pl-8 pr-3 text-body-sm text-on-surface outline-none transition-colors focus:border-primary dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:focus:border-primary-dark"
              placeholder="搜索空间名称、用户、班级..."
              @input="scheduleSearch"
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
              <span
                class="shrink-0 rounded-full px-2 py-0.5 text-[11px]"
                :class="space.linked ? okChipClass : warnChipClass"
              >
                {{ space.linked ? '已关联' : '孤立空间' }}
              </span>
            </div>
            <div class="mt-3 flex items-center justify-between text-[11px] text-on-surface-variant dark:text-zinc-500">
              <span>{{ space.file_count }} 文件 / {{ space.directory_count }} 目录</span>
              <span>{{ formatBytes(space.total_size) }}</span>
            </div>
          </button>

          <div v-if="spaces.length === 0" class="p-6 text-center text-body-sm text-on-surface-variant dark:text-zinc-500">
            当前暂无匹配的文件空间
          </div>
        </div>
      </aside>

      <section class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="shrink-0 border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/50">
          <div class="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <FolderOpen :size="18" class="shrink-0 text-primary dark:text-primary-dark" />
                <h2 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">
                  {{ selectedSpace?.title || '选择文件空间' }}
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
                {{ selectedSpace?.space_root || '从左侧选择一个用户或群组文件空间后开始浏览' }}
              </p>
            </div>

            <div class="flex flex-wrap items-center gap-2">
              <button
                type="button"
                class="inline-flex h-9 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 text-body-sm text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
                :disabled="!selectedSpace"
                @click="goParent"
              >
                <ArrowUp :size="14" />
                返回上级
              </button>
              <button
                type="button"
                class="inline-flex h-9 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 text-body-sm text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
                :disabled="!selectedSpace"
                @click="startDirectoryCreation"
              >
                <FolderPlus :size="14" />
                新建目录
              </button>
              <button
                type="button"
                class="inline-flex h-9 items-center gap-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 text-body-sm text-on-surface transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200 dark:hover:bg-zinc-800"
                :disabled="!selectedSpace"
                @click="startTextDraft"
              >
                <FilePlus2 :size="14" />
                新建文本
              </button>
              <button
                type="button"
                class="inline-flex h-9 items-center gap-2 rounded-lg border border-error/20 bg-error-container/35 px-3 text-body-sm text-error transition-colors hover:bg-error-container/55 disabled:cursor-not-allowed disabled:opacity-50 dark:border-red-900/45 dark:bg-red-950/30 dark:text-red-300 dark:hover:bg-red-950/45"
                :disabled="!selectedSpace"
                @click="openDeleteSpaceDialog"
              >
                <Trash2 :size="14" />
                删除空间
              </button>
            </div>
          </div>
        </div>

        <div class="grid min-h-0 flex-1 grid-cols-1 overflow-hidden xl:grid-cols-[minmax(0,1fr)_380px]">
          <div class="flex min-w-0 flex-col overflow-hidden border-b border-outline-variant dark:border-zinc-800 xl:border-b-0 xl:border-r">
            <div class="shrink-0 border-b border-outline-variant px-4 py-3 dark:border-zinc-800">
              <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <div class="min-w-0">
                  <div class="text-[11px] uppercase tracking-[0.14em] text-on-surface-variant dark:text-zinc-500">当前目录</div>
                  <div class="mt-1 truncate font-code-inline text-code-inline text-on-surface dark:text-zinc-100">
                    {{ directoryPath }}
                  </div>
                </div>
                <div v-if="creatingDirectory" class="flex min-w-0 items-center gap-2">
                  <input
                    v-model="newDirectoryName"
                    class="h-9 min-w-0 rounded-lg border border-outline-variant bg-surface-container px-3 text-body-sm text-on-surface outline-none transition-colors focus:border-primary dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:focus:border-primary-dark"
                    placeholder="目录名或相对路径"
                    @keydown.enter.prevent="submitDirectoryCreation"
                  />
                  <button
                    type="button"
                    class="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-3 text-body-sm font-medium text-on-primary transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-primary-dark dark:text-zinc-950"
                    :disabled="actionBusy"
                    @click="submitDirectoryCreation"
                  >
                    <Loader2 v-if="actionBusy" :size="14" class="animate-spin" />
                    <Check v-else :size="14" />
                    创建
                  </button>
                  <button
                    type="button"
                    class="inline-flex h-9 items-center rounded-lg border border-outline-variant px-3 text-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                    @click="cancelDirectoryCreation"
                  >
                    取消
                  </button>
                </div>
              </div>
            </div>

            <div class="min-h-0 flex-1 overflow-auto">
              <table class="w-full border-collapse text-left">
                <thead class="sticky top-0 z-10 border-b border-outline-variant bg-surface-bright dark:border-zinc-800 dark:bg-zinc-900">
                  <tr>
                    <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">名称</th>
                    <th class="w-28 p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">类型</th>
                    <th class="w-28 p-[10px_12px] text-right font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">大小</th>
                    <th class="w-40 p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">更新时间</th>
                    <th class="w-12 p-[10px_12px] text-center font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">操作</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-outline-variant text-body-sm text-on-surface dark:divide-zinc-800 dark:text-zinc-200">
                  <tr v-if="!selectedSpace">
                    <td colspan="5" class="p-8 text-center text-on-surface-variant dark:text-zinc-500">
                      从左侧选择一个文件空间
                    </td>
                  </tr>
                  <tr v-else-if="directoryEntries.length === 0">
                    <td colspan="5" class="p-8 text-center text-on-surface-variant dark:text-zinc-500">
                      当前目录暂无文件
                    </td>
                  </tr>
                  <tr
                    v-for="entry in directoryEntries"
                    :key="entry.path"
                    class="transition-colors hover:bg-surface-container dark:hover:bg-zinc-800/55"
                    :class="{ 'bg-surface-container dark:bg-zinc-800/35': selectedEntryPath === entry.path }"
                  >
                    <td class="p-[10px_12px]">
                      <button
                        type="button"
                        class="flex min-w-0 items-center gap-2 text-left"
                        @click="openEntry(entry)"
                      >
                        <Folder v-if="entry.is_dir" :size="16" class="shrink-0 text-primary dark:text-primary-dark" />
                        <FileText v-else :size="16" class="shrink-0 text-on-surface-variant dark:text-zinc-500" />
                        <span class="truncate">{{ entry.name }}</span>
                      </button>
                    </td>
                    <td class="p-[10px_12px] text-on-surface-variant dark:text-zinc-500">
                      {{ entry.is_dir ? '目录' : entry.extension || '文件' }}
                    </td>
                    <td class="p-[10px_12px] text-right text-on-surface-variant dark:text-zinc-500">
                      {{ entry.is_dir ? '-' : formatBytes(entry.size) }}
                    </td>
                    <td class="p-[10px_12px] text-on-surface-variant dark:text-zinc-500">
                      {{ formatDateTime(entry.updated_at) }}
                    </td>
                    <td class="p-[10px_12px] text-center">
                      <button
                        type="button"
                        class="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-error-container/45 hover:text-error dark:text-zinc-400 dark:hover:bg-red-950/30 dark:hover:text-red-300"
                        @click="openDeleteDialog(entry)"
                      >
                        <Trash2 :size="15" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <aside class="flex min-h-0 flex-col overflow-hidden">
            <div class="shrink-0 border-b border-outline-variant px-4 py-3 dark:border-zinc-800">
              <div class="flex items-center justify-between gap-3">
                <div class="min-w-0">
                  <h3 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">
                    {{ inspectorTitle }}
                  </h3>
                  <p class="mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">
                    {{ inspectorSubtitle }}
                  </p>
                </div>
                <button
                  v-if="editorPath"
                  type="button"
                  class="inline-flex h-9 items-center gap-2 rounded-lg bg-primary px-3 text-body-sm font-medium text-on-primary transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-primary-dark dark:text-zinc-950"
                  :disabled="saveDisabled"
                  @click="saveEditor"
                >
                  <Loader2 v-if="saving" :size="14" class="animate-spin" />
                  <Save v-else :size="14" />
                  保存
                </button>
              </div>
            </div>

            <div class="min-h-0 flex-1 overflow-y-auto p-4">
              <template v-if="editorPath">
                <div v-if="editorNotice" class="mb-3 rounded-lg border border-amber-500/25 bg-amber-50/80 px-3 py-2 text-body-sm text-amber-800 dark:border-amber-500/25 dark:bg-amber-950/30 dark:text-amber-200">
                  {{ editorNotice }}
                </div>

                <div class="mb-3 rounded-xl border border-outline-variant bg-surface-container-low p-3 dark:border-zinc-800 dark:bg-zinc-800/55">
                  <div class="text-[11px] uppercase tracking-[0.14em] text-on-surface-variant dark:text-zinc-500">目标路径</div>
                  <input
                    v-model="editorPath"
                    class="mt-2 h-10 w-full rounded-lg border border-outline-variant bg-surface-container px-3 font-code-inline text-code-inline text-on-surface outline-none transition-colors focus:border-primary dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-primary-dark"
                    placeholder="~/documents/new-file.txt"
                  />
                </div>

                <textarea
                  v-model="editorContent"
                  class="min-h-[360px] w-full resize-y rounded-xl border border-outline-variant bg-surface-container px-3 py-3 font-code-inline text-code-inline text-on-surface outline-none transition-colors focus:border-primary dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100 dark:focus:border-primary-dark"
                  :readonly="Boolean(selectedPreview?.truncated && !editorIsDraft)"
                />
              </template>

              <template v-else-if="selectedSpace">
                <div class="space-y-4">
                  <div class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/55">
                    <div class="mb-3 flex items-center gap-2 text-body-sm font-medium text-on-surface dark:text-zinc-200">
                      <HardDrive :size="15" />
                      空间概览
                    </div>
                    <div class="grid grid-cols-2 gap-3 text-body-sm">
                      <div>
                        <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">当前目录</div>
                        <div class="mt-1 font-code-inline text-code-inline text-on-surface dark:text-zinc-200">{{ selectedSpace.cwd }}</div>
                      </div>
                      <div>
                        <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">总容量</div>
                        <div class="mt-1 text-on-surface dark:text-zinc-200">{{ formatBytes(selectedSpace.total_size) }}</div>
                      </div>
                      <div>
                        <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">文件数量</div>
                        <div class="mt-1 text-on-surface dark:text-zinc-200">{{ selectedSpace.file_count }}</div>
                      </div>
                      <div>
                        <div class="text-[11px] text-on-surface-variant dark:text-zinc-500">目录数量</div>
                        <div class="mt-1 text-on-surface dark:text-zinc-200">{{ selectedSpace.directory_count }}</div>
                      </div>
                    </div>
                  </div>

                  <div class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/55">
                    <div class="mb-3 flex items-center gap-2 text-body-sm font-medium text-on-surface dark:text-zinc-200">
                      <FolderTree :size="15" />
                      默认目录
                    </div>
                    <div class="flex flex-wrap gap-2">
                      <span
                        v-for="directory in selectedSpace.default_directories"
                        :key="directory"
                        class="rounded-full bg-surface-container px-2.5 py-1 text-[12px] text-on-surface-variant dark:bg-zinc-900 dark:text-zinc-400"
                      >
                        {{ directory }}
                      </span>
                    </div>
                  </div>

                  <div class="rounded-xl border border-outline-variant bg-surface-container-low p-4 dark:border-zinc-800 dark:bg-zinc-800/55">
                    <div class="mb-2 text-[11px] uppercase tracking-[0.14em] text-on-surface-variant dark:text-zinc-500">状态</div>
                    <div class="flex items-center justify-between text-body-sm">
                      <span class="text-on-surface dark:text-zinc-200">关联状态</span>
                      <span :class="selectedSpace.linked ? 'text-primary dark:text-primary-dark' : 'text-amber-700 dark:text-amber-300'">
                        {{ selectedSpace.linked ? '已关联' : '孤立空间' }}
                      </span>
                    </div>
                    <div class="mt-2 flex items-center justify-between text-body-sm">
                      <span class="text-on-surface dark:text-zinc-200">会话状态文件</span>
                      <span class="text-on-surface-variant dark:text-zinc-500">{{ selectedSpace.has_chat_state ? '存在' : '未创建' }}</span>
                    </div>
                    <div class="mt-2 flex items-center justify-between text-body-sm">
                      <span class="text-on-surface dark:text-zinc-200">最近更新时间</span>
                      <span class="text-on-surface-variant dark:text-zinc-500">{{ formatDateTime(selectedSpace.updated_at) }}</span>
                    </div>
                  </div>
                </div>
              </template>

              <div v-else class="flex min-h-[260px] items-center justify-center rounded-xl border border-dashed border-outline-variant text-center text-body-sm text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
                选择一个文件空间后查看目录和文件内容
              </div>
            </div>
          </aside>
        </div>
      </section>
    </div>
  </div>

  <DangerConfirmDialog
    :open="Boolean(deleteSpaceDialog)"
    :busy="actionBusy"
    :error-message="deleteSpaceError"
    title="确认删除文件空间"
    message="将清理当前空间下的 home、chat 以及相关运行目录，包含内部文件、会话状态和聊天数据库。该操作不可恢复。"
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

  <Teleport to="body">
    <div
      v-if="deleteDialog"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4 backdrop-blur-[2px] dark:bg-black/60"
      @click.self="closeDeleteDialog"
    >
      <div class="w-[min(440px,calc(100vw-32px))] overflow-hidden rounded-[22px] border border-outline-variant bg-surface-container-lowest shadow-[0_28px_72px_rgba(15,23,42,0.22)] dark:border-zinc-800 dark:bg-zinc-900 dark:shadow-[0_30px_90px_rgba(0,0,0,0.55)]">
        <div class="flex items-start gap-4 border-b border-outline-variant px-5 py-4 dark:border-zinc-800">
          <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-error/15 bg-error-container/20 text-error dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300">
            <AlertTriangle :size="18" />
          </div>
          <div class="min-w-0 flex-1">
            <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">确认删除文件条目</h2>
            <p class="mt-1 text-body-sm leading-6 text-on-surface-variant dark:text-zinc-400">
              将删除当前文件或目录。目录删除会递归清理内部内容，请确认没有需要保留的数据。
            </p>
          </div>
        </div>

        <div class="space-y-4 px-5 py-4">
          <div class="rounded-xl border border-outline-variant bg-surface-container-low px-4 py-3 dark:border-zinc-800 dark:bg-zinc-800/55">
            <div class="text-[11px] uppercase tracking-[0.14em] text-on-surface-variant dark:text-zinc-500">目标路径</div>
            <div class="mt-2 break-all font-code-inline text-code-inline text-on-surface dark:text-zinc-100">{{ deleteDialog.path }}</div>
          </div>
        </div>

        <div class="flex items-center justify-end gap-2 border-t border-outline-variant px-5 py-4 dark:border-zinc-800">
          <button
            type="button"
            class="rounded-lg border border-outline-variant px-4 py-2 text-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
            :disabled="actionBusy"
            @click="closeDeleteDialog"
          >
            取消
          </button>
          <button
            type="button"
            class="inline-flex items-center gap-2 rounded-lg border border-error/20 bg-error px-4 py-2 text-body-sm font-medium text-on-error transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 dark:border-red-900/50 dark:bg-red-900 dark:text-white"
            :disabled="actionBusy"
            @click="confirmDelete"
          >
            <Loader2 v-if="actionBusy" :size="14" class="animate-spin" />
            <Trash2 v-else :size="14" />
            确认删除
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AlertTriangle,
  ArrowUp,
  Check,
  FilePlus2,
  FileText,
  Files,
  Folder,
  FolderKanban,
  FolderOpen,
  FolderPlus,
  FolderTree,
  HardDrive,
  Link2,
  Loader2,
  RefreshCw,
  Save,
  Search,
  Trash2,
  User,
  Users,
} from 'lucide-vue-next'
import DangerConfirmDialog from '@/components/DangerConfirmDialog.vue'
import {
  createFileSpaceDirectory,
  deleteFileSpace,
  deleteFileSpaceEntry,
  fetchFileSpaceDetail,
  fetchFileSpaceEntries,
  fetchFileSpaces,
  readFileSpaceText,
  writeFileSpaceText,
} from '@/api/files'
import type {
  FileSpaceDetail,
  FileSpaceEntry,
  FileSpaceKind,
  FileSpaceListResponse,
  FileSpaceSummary,
  FileSpaceTextPreview,
} from '@/types/api'

const loading = ref(false)
const saving = ref(false)
const actionBusy = ref(false)
const search = ref('')
const activeKind = ref<FileSpaceKind>('user')
const storageRoot = ref('')
const spaces = ref<FileSpaceSummary[]>([])
const selectedSpace = ref<FileSpaceSummary | null>(null)
const spaceDetail = ref<FileSpaceDetail | null>(null)
const selectedEntryPath = ref('')
const selectedPreview = ref<FileSpaceTextPreview | null>(null)
const editorPath = ref('')
const editorContent = ref('')
const editorIsDraft = ref(false)
const creatingDirectory = ref(false)
const newDirectoryName = ref('')
const message = ref('')
const messageTone = ref<'success' | 'error'>('success')
const deleteDialog = ref<{ path: string; recursive: boolean } | null>(null)
const deleteSpaceDialog = ref<{ key: string; kind: FileSpaceKind; ownerId: string; title: string; hint: string } | null>(null)
const deleteSpaceError = ref('')

let searchTimer: ReturnType<typeof setTimeout> | undefined
const route = useRoute()
const router = useRouter()

const spaceKinds: FileSpaceKind[] = ['user', 'group']

const linkedSpaces = computed(() => spaces.value.filter((item) => item.linked).length)
const totalFiles = computed(() => spaces.value.reduce((sum, item) => sum + item.file_count, 0))
const totalSize = computed(() => spaces.value.reduce((sum, item) => sum + item.total_size, 0))
const totalSizeText = computed(() => formatBytes(totalSize.value))
const storageRootText = computed(() => storageRoot.value || '等待读取 storage 根目录')
const directoryPath = computed(() => spaceDetail.value?.path || selectedSpace.value?.cwd || '~')
const directoryEntries = computed(() => spaceDetail.value?.items || [])
const editorNotice = computed(() => {
  if (editorIsDraft.value) return '这是一个新的文本草稿，保存后会直接写入文件空间。'
  if (selectedPreview.value?.truncated) return '当前文件预览已截断，为避免误覆盖，暂不允许直接保存。'
  return ''
})
const inspectorTitle = computed(() => editorPath.value ? '文本编辑器' : '空间概览')
const inspectorSubtitle = computed(() => editorPath.value ? editorPath.value : (selectedSpace.value?.home_path || ''))
const saveDisabled = computed(() => {
  if (!selectedSpace.value || !editorPath.value) return true
  if (saving.value) return true
  return Boolean(selectedPreview.value?.truncated && !editorIsDraft.value)
})
const messageClass = computed(() => messageTone.value === 'success'
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
    showMessage(extractErrorMessage(error, '文件空间信息加载失败'), 'error')
  } finally {
    loading.value = false
  }
}

async function loadSpaces() {
  let payload: FileSpaceListResponse = await fetchFileSpaces({
    kind: activeKind.value,
    q: search.value.trim() || undefined,
  })
  const requestedOwnerId = getRequestedOwnerId(activeKind.value)
  if (requestedOwnerId && search.value.trim() && !payload.items.some((item) => item.owner_id === requestedOwnerId)) {
    search.value = ''
    payload = await fetchFileSpaces({ kind: activeKind.value })
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
    resetInspector()
  }
  syncSelectionQuery(nextSpace)
}

async function switchKind(kind: FileSpaceKind) {
  if (activeKind.value === kind) return
  activeKind.value = kind
  selectedSpace.value = null
  spaceDetail.value = null
  resetInspector()
  try {
    await loadSpaces()
  } catch (error) {
    showMessage(extractErrorMessage(error, '文件空间信息加载失败'), 'error')
  }
}

function scheduleSearch() {
  if (searchTimer) window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => {
    void reloadAll()
  }, 260)
}

async function selectSpace(space: FileSpaceSummary) {
  if (selectedSpace.value?.key === space.key) return
  selectedSpace.value = space
  try {
    await loadSpaceDetail(space.kind, space.owner_id)
    syncSelectionQuery(selectedSpace.value)
  } catch (error) {
    showMessage(extractErrorMessage(error, '文件空间详情加载失败'), 'error')
  }
}

async function loadSpaceDetail(kind: FileSpaceKind, ownerId: string) {
  resetInspector()
  spaceDetail.value = await fetchFileSpaceDetail(kind, ownerId)
  selectedSpace.value = selectedSpace.value
    ? ({ ...selectedSpace.value, ...spaceDetail.value } as FileSpaceSummary)
    : ({ ...spaceDetail.value } as FileSpaceSummary)
}

async function loadEntries(path?: string) {
  if (!selectedSpace.value) return
  try {
    const payload = await fetchFileSpaceEntries(selectedSpace.value.kind, selectedSpace.value.owner_id, { path })
    if (!spaceDetail.value) return
    spaceDetail.value = { ...spaceDetail.value, ...payload }
  } catch (error) {
    showMessage(extractErrorMessage(error, '目录读取失败'), 'error')
  }
}

async function goParent() {
  if (!spaceDetail.value?.can_go_up) return
  await loadEntries(spaceDetail.value.parent_path)
  resetInspector()
}

async function openEntry(entry: FileSpaceEntry) {
  selectedEntryPath.value = entry.path
  if (entry.is_dir) {
    await loadEntries(entry.path)
    resetInspector()
    return
  }

  try {
    const preview = await readFileSpaceText(selectedSpace.value!.kind, selectedSpace.value!.owner_id, { path: entry.path })
    selectedPreview.value = preview
    editorPath.value = preview.path
    editorContent.value = preview.content
    editorIsDraft.value = false
  } catch (error) {
    showMessage(extractErrorMessage(error, '文件预览失败，可能不是可直接读取的文本文件'), 'error')
  }
}

function startDirectoryCreation() {
  creatingDirectory.value = true
  newDirectoryName.value = ''
}

function cancelDirectoryCreation() {
  creatingDirectory.value = false
  newDirectoryName.value = ''
}

async function submitDirectoryCreation() {
  if (!selectedSpace.value || !newDirectoryName.value.trim()) return
  actionBusy.value = true
  try {
    await createFileSpaceDirectory(selectedSpace.value.kind, selectedSpace.value.owner_id, {
      path: joinSpacePath(directoryPath.value, newDirectoryName.value),
    })
    showMessage('目录已创建', 'success')
    cancelDirectoryCreation()
    await loadEntries(directoryPath.value)
  } catch (error) {
    showMessage(extractErrorMessage(error, '目录创建失败'), 'error')
  } finally {
    actionBusy.value = false
  }
}

function startTextDraft() {
  if (!selectedSpace.value) return
  selectedPreview.value = null
  selectedEntryPath.value = ''
  editorIsDraft.value = true
  editorPath.value = joinSpacePath(directoryPath.value, 'untitled.txt')
  editorContent.value = ''
}

async function saveEditor() {
  if (!selectedSpace.value || !editorPath.value) return
  saving.value = true
  try {
    await writeFileSpaceText(selectedSpace.value.kind, selectedSpace.value.owner_id, {
      path: editorPath.value,
      content: editorContent.value,
    })
    showMessage('文件内容已保存', 'success')
    editorIsDraft.value = false
    selectedPreview.value = await readFileSpaceText(selectedSpace.value.kind, selectedSpace.value.owner_id, {
      path: editorPath.value,
    })
    editorContent.value = selectedPreview.value.content
    await loadEntries(directoryPath.value)
  } catch (error) {
    showMessage(extractErrorMessage(error, '文件保存失败'), 'error')
  } finally {
    saving.value = false
  }
}

function openDeleteDialog(entry: FileSpaceEntry) {
  deleteDialog.value = {
    path: entry.path,
    recursive: entry.is_dir,
  }
}

function closeDeleteDialog() {
  if (actionBusy.value) return
  deleteDialog.value = null
}

function openDeleteSpaceDialog() {
  if (!selectedSpace.value) return
  deleteSpaceError.value = ''
  deleteSpaceDialog.value = {
    key: selectedSpace.value.key,
    kind: selectedSpace.value.kind,
    ownerId: selectedSpace.value.owner_id,
    title: selectedSpace.value.title,
    hint: selectedSpace.value.space_root,
  }
}

function closeDeleteSpaceDialog() {
  if (actionBusy.value) return
  deleteSpaceDialog.value = null
  deleteSpaceError.value = ''
}

async function confirmDeleteSpace() {
  const dialog = deleteSpaceDialog.value
  if (!dialog) return

  actionBusy.value = true
  deleteSpaceError.value = ''
  try {
    await deleteFileSpace(dialog.kind, dialog.ownerId)
    if (selectedSpace.value?.key === dialog.key) {
      selectedSpace.value = null
      spaceDetail.value = null
      resetInspector()
    }
    deleteSpaceDialog.value = null
    showMessage('文件空间已删除', 'success')
    await loadSpaces()
  } catch (error) {
    deleteSpaceError.value = extractErrorMessage(error, '文件空间删除失败，请稍后重试')
  } finally {
    actionBusy.value = false
  }
}

async function confirmDelete() {
  if (!selectedSpace.value || !deleteDialog.value) return
  actionBusy.value = true
  try {
    await deleteFileSpaceEntry(selectedSpace.value.kind, selectedSpace.value.owner_id, {
      path: deleteDialog.value.path,
      recursive: deleteDialog.value.recursive,
    })
    if (selectedEntryPath.value === deleteDialog.value.path) {
      resetInspector()
    }
    showMessage('文件条目已删除', 'success')
    deleteDialog.value = null
    await loadEntries(directoryPath.value)
  } catch (error) {
    showMessage(extractErrorMessage(error, '删除失败'), 'error')
  } finally {
    actionBusy.value = false
  }
}

function resetInspector() {
  selectedEntryPath.value = ''
  selectedPreview.value = null
  editorPath.value = ''
  editorContent.value = ''
  editorIsDraft.value = false
}

function showMessage(text: string, tone: 'success' | 'error') {
  message.value = text
  messageTone.value = tone
}

function normalizeRouteKind(value: unknown): FileSpaceKind | null {
  return value === 'user' || value === 'group' ? value : null
}

function getRouteOwnerId() {
  return typeof route.query.ownerId === 'string' ? route.query.ownerId.trim() : ''
}

function getRequestedOwnerId(kind: FileSpaceKind) {
  return normalizeRouteKind(route.query.kind) === kind ? getRouteOwnerId() : ''
}

function syncSelectionQuery(space: FileSpaceSummary | null) {
  const nextKind = space?.kind || activeKind.value
  const nextOwnerId = space?.owner_id || ''
  if (normalizeRouteKind(route.query.kind) === nextKind && getRouteOwnerId() === nextOwnerId) {
    return
  }

  void router.replace({
    name: 'Files',
    query: {
      ...route.query,
      kind: nextKind,
      ownerId: nextOwnerId || undefined,
    },
  })
}

function kindLabel(kind: FileSpaceKind) {
  return kind === 'user' ? '用户空间' : '群组空间'
}

function joinSpacePath(base: string, next: string) {
  const value = next.trim()
  if (!value) return base
  if (value === '~' || value.startsWith('~/')) return value
  const normalized = value.replace(/^\/+/, '')
  return base === '~' ? `~/${normalized}` : `${base}/${normalized}`
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

function extractErrorMessage(error: unknown, fallback: string) {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) {
    return detail
  }
  return fallback
}
</script>
