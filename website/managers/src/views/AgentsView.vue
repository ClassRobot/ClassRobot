<template>
  <div class="flex h-[calc(100vh-96px)] min-h-0 flex-col gap-4 overflow-hidden">
    <div class="flex shrink-0 flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
      <div>
        <h1 class="font-h1 text-h1 text-on-surface dark:text-zinc-100">Agent 管理</h1>
        <p class="mt-1 font-body-sm text-body-sm text-on-surface-variant dark:text-zinc-500">
          查看 AutoGPT 模块、编排链路、配置边界与运行轨迹
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

    <div class="grid shrink-0 grid-cols-2 gap-3 lg:grid-cols-5">
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
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <BrainCircuit :size="17" class="text-primary dark:text-primary-dark" />
              <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ activeTab === 'flow' ? 'Runtime 节点' : 'Agent 模块' }}</h2>
            </div>
            <span class="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary dark:bg-primary-dark/15 dark:text-primary-dark">
              {{ sidebarModules.length }} 个
            </span>
          </div>
          <div class="relative mt-3">
            <Search :size="15" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant dark:text-zinc-500" />
            <input
              v-model="moduleSearch"
              class="h-9 w-full rounded-lg border border-outline-variant bg-surface-container pl-8 pr-3 text-body-sm text-on-surface outline-none transition-colors focus:border-primary dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:focus:border-primary-dark"
              placeholder="搜索模块、能力、源码..."
            />
          </div>
        </div>

        <div class="min-h-0 flex-1 overflow-y-auto p-2">
          <button
            v-for="module in filteredModules"
            :key="module.id"
            type="button"
            :draggable="activeTab === 'flow'"
            class="module-row"
            :class="selectedModule?.id === module.id ? selectedModuleClass : idleModuleClass"
            @dragstart="handlePaletteDragStart($event, module)"
            @click="selectedModuleId = module.id"
          >
            <div class="flex min-w-0 items-start justify-between gap-2">
              <div class="min-w-0">
                <div class="truncate font-body-sm text-body-sm font-semibold">{{ module.name }}</div>
                <div class="mt-1 truncate font-code-inline text-code-inline opacity-70">{{ module.source }}</div>
              </div>
              <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px]" :class="module.status === 'enabled' ? okChipClass : dangerChipClass">
                {{ module.status === 'enabled' ? '已接入' : '缺失' }}
              </span>
            </div>
            <div class="mt-2 flex flex-wrap gap-1.5">
              <span
                v-for="capability in module.capabilities.slice(0, 3)"
                :key="capability"
                class="rounded-full bg-surface-container px-2 py-0.5 text-[11px] text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400"
              >
                {{ capability }}
              </span>
            </div>
          </button>
          <EmptyState v-if="filteredModules.length === 0" :text="activeTab === 'flow' ? '没有匹配的 Runtime 节点' : '没有匹配的 Agent 模块'" />
        </div>

        <div class="shrink-0 border-t border-outline-variant bg-surface-bright p-3 dark:border-zinc-800 dark:bg-zinc-900/60">
          <div class="mb-2 flex items-center gap-2 text-body-sm font-semibold text-on-surface dark:text-zinc-100">
            <SlidersHorizontal :size="15" />
            控制边界
          </div>
          <div class="space-y-2">
            <div
              v-for="control in overview?.controls || []"
              :key="control.id"
              class="rounded-lg border border-outline-variant bg-surface-container-low px-3 py-2 dark:border-zinc-800 dark:bg-zinc-800/45"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="truncate text-body-sm font-medium text-on-surface dark:text-zinc-100">{{ control.name }}</span>
                <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px]" :class="control.supported ? okChipClass : mutedChipClass">
                  {{ control.supported ? '可用' : '只读' }}
                </span>
              </div>
              <p class="mt-1 line-clamp-2 text-[12px] leading-5 text-on-surface-variant dark:text-zinc-500">
                {{ control.description }}
              </p>
            </div>
          </div>
        </div>
      </aside>

      <section class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
        <div class="flex shrink-0 flex-col gap-3 border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/60 lg:flex-row lg:items-center lg:justify-between">
          <div class="min-w-0">
            <div class="flex items-center gap-2">
              <component :is="activeTabIcon" :size="18" class="shrink-0 text-primary dark:text-primary-dark" />
              <h2 class="truncate font-h2 text-h2 text-on-surface dark:text-zinc-100">{{ activeTitle }}</h2>
            </div>
            <p class="mt-1 truncate text-body-sm text-on-surface-variant dark:text-zinc-500">{{ activeSubtitle }}</p>
          </div>
          <div class="grid shrink-0 grid-cols-5 gap-1 rounded-lg border border-outline-variant bg-surface-container p-0.5 dark:border-zinc-700 dark:bg-zinc-800">
            <button
              v-for="tab in mainTabs"
              :key="tab.key"
              type="button"
              class="inline-flex h-8 min-w-[76px] items-center justify-center gap-1.5 whitespace-nowrap rounded-md px-3 text-[12px] font-semibold transition-colors"
              :class="activeTab === tab.key ? activeSegmentClass : inactiveSegmentClass"
              @click="activeTab = tab.key"
            >
              <component :is="tab.icon" :size="13" />
              {{ tab.label }}
            </button>
          </div>
        </div>

        <div class="min-h-0 flex-1 overflow-hidden">
          <div v-if="activeTab === 'overview'" class="grid h-full min-h-0 grid-cols-1 gap-4 overflow-y-auto p-4 2xl:grid-cols-[minmax(0,1fr)_360px]">
            <div class="space-y-4">
              <DetailCard title="模块详情">
                <template v-if="selectedModule">
                  <div class="flex flex-wrap items-center gap-2">
                    <span :class="[chipBaseClass, okChipClass]">{{ selectedModule.category }}</span>
                    <span :class="[chipBaseClass, selectedModule.configurable ? okChipClass : mutedChipClass]">
                      {{ selectedModule.configurable ? '可配置' : '只读配置' }}
                    </span>
                    <span :class="[chipBaseClass, selectedModule.draft_configurable ? okChipClass : mutedChipClass]">
                      {{ selectedModule.draft_configurable ? '草稿可配置' : '无配置草稿' }}
                    </span>
                    <span :class="[chipBaseClass, selectedModule.toggleable ? okChipClass : mutedChipClass]">
                      {{ selectedModule.toggleable ? '支持启停' : '无模块启停' }}
                    </span>
                  </div>
                  <p class="mt-3 text-body-sm leading-6 text-on-surface dark:text-zinc-200">{{ selectedModule.description }}</p>
                  <div class="mt-4 grid gap-3 lg:grid-cols-2">
                    <InfoTile label="源码" :value="selectedModule.source" code />
                    <InfoTile label="控制说明" :value="selectedModule.control_note" />
                  </div>
                  <div class="mt-4 flex flex-wrap gap-2">
                    <span v-for="capability in selectedModule.capabilities" :key="capability" :class="infoChipClass">
                      {{ capability }}
                    </span>
                  </div>
                </template>
              </DetailCard>

              <DetailCard title="工作流模板">
                <div class="grid gap-3 xl:grid-cols-2">
                  <div
                    v-for="playbook in overview?.playbooks || []"
                    :key="playbook.id"
                    class="rounded-xl border border-outline-variant bg-surface-container-lowest p-3 dark:border-zinc-800 dark:bg-zinc-900/60"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <span class="truncate text-body-sm font-semibold text-on-surface dark:text-zinc-100">{{ playbook.name }}</span>
                      <span class="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary dark:bg-primary-dark/15 dark:text-primary-dark">
                        {{ playbook.step_count }} 步
                      </span>
                    </div>
                    <p class="mt-1 line-clamp-2 text-[12px] leading-5 text-on-surface-variant dark:text-zinc-500">{{ playbook.description }}</p>
                    <div class="mt-3 flex flex-wrap gap-1.5">
                      <span
                        v-for="step in playbook.steps"
                        :key="`${playbook.id}-${step.command}`"
                        class="rounded-full bg-surface-container px-2 py-0.5 text-[11px] text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400"
                      >
                        {{ step.command }}
                      </span>
                    </div>
                  </div>
                </div>
              </DetailCard>
            </div>

            <div class="space-y-4">
              <ChartPanel title="运行状态" sub="按工作流状态统计" :option="statusChartOption" height="180px" />
              <ChartPanel title="工作流类型" sub="按 kind 分布统计" :option="kindChartOption" height="180px" />
              <DetailCard title="Skill 能力">
                <div class="max-h-[260px] overflow-y-auto pr-1">
                  <div
                    v-for="skill in overview?.skills || []"
                    :key="skill.name"
                    class="mb-2 rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900/60"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <span class="truncate text-body-sm font-semibold text-on-surface dark:text-zinc-100">{{ skill.name }}</span>
                      <span class="rounded-full px-2 py-0.5 text-[11px]" :class="skill.loaded ? okChipClass : mutedChipClass">
                        {{ skill.loaded ? '已加载' : '文档' }}
                      </span>
                    </div>
                    <p class="mt-1 line-clamp-2 text-[12px] leading-5 text-on-surface-variant dark:text-zinc-500">{{ skill.description }}</p>
                  </div>
                </div>
              </DetailCard>
            </div>
          </div>

          <div v-else-if="activeTab === 'flow'" class="grid h-full min-h-0 grid-cols-1 gap-4 overflow-hidden p-4 xl:grid-cols-[minmax(0,1fr)_320px]">
            <section class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
              <div class="flex shrink-0 flex-col gap-3 border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/60 lg:flex-row lg:items-center lg:justify-between">
                <div class="min-w-0">
                  <div class="flex items-center gap-2">
                    <Network :size="16" class="text-primary dark:text-primary-dark" />
                    <h3 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">编排画布</h3>
                    <span class="rounded-full px-2 py-0.5 text-[11px]" :class="designer?.runtime.enabled ? okChipClass : mutedChipClass">
                      {{ designer?.runtime.enabled ? '编排图生效' : '编排不可用' }}
                    </span>
                  </div>
                  <p class="mt-1 truncate text-[12px] text-on-surface-variant dark:text-zinc-500">
                    {{ designer?.capabilities.message || '保存草稿后可选择热更新到后续 Agent 轮次。' }}
                  </p>
                </div>
                <div class="flex items-center gap-2">
                  <button
                    type="button"
                    class="inline-flex h-9 w-9 items-center justify-center gap-2 rounded-lg border border-outline-variant text-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800 2xl:w-auto 2xl:px-3"
                    title="恢复默认编排图"
                    @click="resetDesignerDraft"
                  >
                    <RefreshCw :size="14" />
                    <span class="hidden 2xl:inline">默认编排图</span>
                  </button>
                  <button
                    type="button"
                    class="inline-flex h-9 w-9 items-center justify-center gap-2 rounded-lg bg-primary text-body-sm font-semibold text-on-primary transition-colors hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60 dark:bg-primary-dark dark:text-zinc-950 2xl:w-auto 2xl:px-3"
                    :disabled="designerSaving"
                    title="保存编排草稿"
                    @click="saveDesignerDraft()"
                  >
                    <Save :size="14" />
                    <span class="hidden 2xl:inline">{{ designerSaving ? '保存中...' : '保存草稿' }}</span>
                  </button>
                  <button
                    type="button"
                    class="inline-flex h-9 w-9 items-center justify-center gap-2 rounded-lg border border-primary/20 bg-primary/10 text-body-sm font-semibold text-primary transition-colors hover:bg-primary/15 disabled:cursor-not-allowed disabled:opacity-60 dark:border-primary-dark/25 dark:bg-primary-dark/12 dark:text-primary-dark dark:hover:bg-primary-dark/18 2xl:w-auto 2xl:px-3"
                    :disabled="designerSaving || designerApplying"
                    title="保存并热更新到运行时"
                    @click="saveDesignerDraft(true)"
                  >
                    <PlayCircle :size="14" />
                    <span class="hidden 2xl:inline">{{ designerApplying ? '应用中...' : '保存并热更新' }}</span>
                  </button>
                </div>
              </div>

              <div class="min-h-0 flex-1 overflow-auto p-3">
                <div
                  class="designer-canvas relative rounded-2xl border border-dashed border-outline-variant bg-surface-container-low dark:border-zinc-800 dark:bg-zinc-950/40"
                  :style="{ width: `${canvasSize.width}px`, height: `${canvasSize.height}px` }"
                  @dragover.prevent
                  @drop="handleDesignerDrop"
                >
                  <svg class="pointer-events-none absolute inset-0 h-full w-full" :viewBox="`0 0 ${canvasSize.width} ${canvasSize.height}`">
                    <defs>
                      <marker id="agent-arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto" markerUnits="strokeWidth">
                        <path d="M0,0 L0,6 L9,3 z" class="fill-primary dark:fill-primary-dark" />
                      </marker>
                    </defs>
                    <line
                      v-for="edge in designerEdges"
                      :key="`line-${edge.id}`"
                      :x1="edgeLine(edge).x1"
                      :y1="edgeLine(edge).y1"
                      :x2="edgeLine(edge).x2"
                      :y2="edgeLine(edge).y2"
                      class="stroke-primary/55 dark:stroke-primary-dark/55"
                      stroke-width="2"
                      marker-end="url(#agent-arrow)"
                    />
                  </svg>

                  <button
                    v-for="node in designerNodes"
                    :key="node.id"
                    type="button"
                    draggable="true"
                    class="designer-node absolute w-[192px] rounded-2xl border p-3 text-left shadow-sm transition-colors"
                    :class="[
                      selectedDesignerNode?.id === node.id ? 'border-primary bg-primary/10 text-primary dark:border-primary-dark dark:bg-primary-dark/12 dark:text-primary-dark' : 'border-outline-variant bg-surface-container-lowest text-on-surface hover:border-primary/40 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-100 dark:hover:border-primary-dark/50',
                      linkSourceNodeId === node.id ? 'ring-2 ring-primary/30 dark:ring-primary-dark/30' : ''
                    ]"
                    :style="{ left: `${node.x}px`, top: `${node.y}px` }"
                    @dragstart="handleNodeDragStart($event, node)"
                    @click.stop="handleDesignerNodeClick(node)"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <span class="truncate text-body-sm font-semibold">{{ node.label }}</span>
                      <span class="h-2 w-2 rounded-full" :class="node.enabled ? 'bg-primary dark:bg-primary-dark' : 'bg-outline dark:bg-zinc-600'" />
                    </div>
                    <p class="mt-1 truncate font-code-inline text-code-inline opacity-75">{{ node.node_type || node.module_id }}</p>
                    <div class="mt-2 flex items-center justify-between gap-2">
                      <span class="rounded-full bg-surface-container px-2 py-0.5 text-[11px] text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400">
                        {{ node.phase }}
                      </span>
                      <span v-if="isDesignerNodeRequired(node)" class="rounded-full bg-red-500/10 px-2 py-0.5 text-[11px] text-red-700 dark:bg-red-500/12 dark:text-red-300">
                        必需
                      </span>
                      <span v-else-if="node.runtime_applied" class="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] text-primary dark:bg-primary-dark/15 dark:text-primary-dark">
                        已应用
                      </span>
                      <span v-if="Object.keys(node.config || {}).length" class="rounded-full bg-sky-500/10 px-2 py-0.5 text-[11px] text-sky-700 dark:bg-sky-400/10 dark:text-sky-300">
                        已配置
                      </span>
                    </div>
                  </button>

                  <div
                    v-if="designerNodes.length === 0"
                    class="absolute inset-6 flex items-center justify-center rounded-2xl border border-dashed border-outline-variant bg-surface-container-lowest/70 text-body-sm text-on-surface-variant dark:border-zinc-800 dark:bg-zinc-900/50 dark:text-zinc-500"
                  >
                    从左侧拖入 Agent 模块开始编排
                  </div>
                </div>
              </div>
            </section>

            <aside class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
              <div class="shrink-0 border-b border-outline-variant px-4 py-3 dark:border-zinc-800">
                <div class="flex items-center gap-2">
                  <Settings2 :size="16" class="text-primary dark:text-primary-dark" />
                  <h3 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">节点配置</h3>
                </div>
                <p class="mt-1 text-[12px] leading-5 text-on-surface-variant dark:text-zinc-500">
                  节点顺序会写入运行时配置；模型等参数随配置保存，后续由节点级模型策略读取。
                </p>
              </div>
              <div class="min-h-0 flex-1 overflow-y-auto p-3">
                <template v-if="selectedDesignerNode">
                  <div class="rounded-xl border border-outline-variant bg-surface-container-low p-3 dark:border-zinc-800 dark:bg-zinc-800/45">
                    <label class="text-[12px] font-medium text-on-surface-variant dark:text-zinc-500">节点名称</label>
                    <input
                      :value="selectedDesignerNode.label"
                      class="mt-1 h-9 w-full rounded-lg border border-outline-variant bg-surface-container-lowest px-3 text-body-sm text-on-surface outline-none focus:border-primary dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-primary-dark"
                      @input="setSelectedNodeLabel"
                    />
                    <p class="mt-2 font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500">
                      {{ selectedDesignerNode.node_type }} · {{ selectedDesignerModule?.source || selectedDesignerNode.module_id }}
                    </p>
                  </div>

                  <div class="mt-3 rounded-xl border border-outline-variant bg-surface-container-low p-3 dark:border-zinc-800 dark:bg-zinc-800/45">
                    <div class="flex items-center justify-between gap-3">
                      <div>
                        <div class="text-body-sm font-semibold text-on-surface dark:text-zinc-100">运行时启用</div>
                        <p class="mt-1 text-[12px] leading-5 text-on-surface-variant dark:text-zinc-500">
                          必需节点不能关闭；可选节点关闭后不会进入 Runtime 图执行顺序。
                        </p>
                      </div>
                      <button
                        type="button"
                        class="rounded-lg px-2.5 py-1 text-[12px] font-semibold transition-colors"
                        :class="selectedDesignerNode.enabled ? okChipClass : mutedChipClass"
                        :disabled="isDesignerNodeRequired(selectedDesignerNode)"
                        @click="toggleSelectedDesignerNode"
                      >
                        {{ selectedDesignerNode.enabled ? '启用' : '停用' }}
                      </button>
                    </div>
                  </div>

                  <div class="mt-3 space-y-3">
                    <div
                      v-for="field in designerConfigSchema"
                      :key="field.key"
                      class="rounded-xl border border-outline-variant bg-surface-container-low p-3 dark:border-zinc-800 dark:bg-zinc-800/45"
                    >
                      <div class="mb-2 flex items-center justify-between gap-2">
                        <span class="text-body-sm font-semibold text-on-surface dark:text-zinc-100">{{ field.label }}</span>
                        <span class="rounded-full px-2 py-0.5 text-[11px]" :class="field.runtime_supported ? okChipClass : mutedChipClass">
                          {{ field.runtime_supported ? '运行时' : '已保存' }}
                        </span>
                      </div>
                      <AppSelect
                        v-if="field.type === 'select'"
                        :model-value="selectedConfigValue(field.key)"
                        :options="fieldOptions(field)"
                        :placeholder="field.placeholder || '继承默认'"
                        button-class="h-9"
                        @update:model-value="setSelectedNodeConfig(field.key, $event)"
                      />
                      <input
                        v-else-if="field.type === 'number'"
                        :value="selectedConfigValue(field.key)"
                        type="number"
                        :min="field.min"
                        :max="field.max"
                        :step="field.step"
                        class="h-9 w-full rounded-lg border border-outline-variant bg-surface-container-lowest px-3 text-body-sm text-on-surface outline-none focus:border-primary dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-primary-dark"
                        :placeholder="field.placeholder || '继承默认'"
                        @input="setSelectedNumberConfig(field, $event)"
                      />
                      <p class="mt-2 text-[12px] leading-5 text-on-surface-variant dark:text-zinc-500">{{ field.description }}</p>
                    </div>
                  </div>

                  <div class="mt-3 grid grid-cols-2 gap-2">
                    <button
                      type="button"
                      class="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-outline-variant text-body-sm text-on-surface transition-colors hover:bg-surface-container dark:border-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-800"
                      @click="startDesignerLink(selectedDesignerNode)"
                    >
                      <Link2 :size="14" />
                      连接下一步
                    </button>
                    <button
                      type="button"
                      class="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-red-500/20 text-body-sm text-red-700 transition-colors hover:bg-red-500/10 dark:border-red-500/25 dark:text-red-300 dark:hover:bg-red-500/12"
                      :disabled="isDesignerNodeRequired(selectedDesignerNode)"
                      :class="isDesignerNodeRequired(selectedDesignerNode) ? 'cursor-not-allowed opacity-50' : ''"
                      @click="removeSelectedDesignerNode"
                    >
                      <Trash2 :size="14" />
                      删除节点
                    </button>
                  </div>

                  <div class="mt-3 rounded-xl border border-outline-variant bg-surface-container-low p-3 dark:border-zinc-800 dark:bg-zinc-800/45">
                    <div class="mb-2 flex items-center gap-2 text-body-sm font-semibold text-on-surface dark:text-zinc-100">
                      <GitBranch :size="14" />
                      链路关系
                    </div>
                    <div v-if="designerEdges.length" class="space-y-2">
                      <div
                        v-for="edge in designerEdges"
                        :key="`edge-${edge.id}`"
                        class="flex items-center gap-2 rounded-lg bg-surface-container-lowest px-2 py-2 text-[12px] text-on-surface-variant dark:bg-zinc-900/70 dark:text-zinc-400"
                      >
                        <span class="min-w-0 flex-1 truncate">{{ getDesignerNode(edge.source)?.label || edge.source }} → {{ getDesignerNode(edge.target)?.label || edge.target }}</span>
                        <button type="button" class="shrink-0 rounded-md p-1 transition-colors hover:bg-red-500/10 hover:text-red-600 dark:hover:text-red-300" @click="removeDesignerEdge(edge.id)">
                          <Trash2 :size="13" />
                        </button>
                      </div>
                    </div>
                    <p v-else class="text-[12px] text-on-surface-variant dark:text-zinc-500">暂无链路，点击“连接下一步”后选择目标节点。</p>
                  </div>

                  <div class="mt-3 rounded-xl border border-outline-variant bg-surface-container-low p-3 dark:border-zinc-800 dark:bg-zinc-800/45">
                    <label class="text-[12px] font-medium text-on-surface-variant dark:text-zinc-500">草稿备注</label>
                    <textarea
                      v-model="designerNote"
                      rows="3"
                      class="mt-1 w-full resize-none rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 text-body-sm text-on-surface outline-none focus:border-primary dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:focus:border-primary-dark"
                      placeholder="记录这次编排草稿的意图..."
                    />
                  </div>
                </template>
                <EmptyState v-else text="请选择或拖入一个 Agent 节点" />
              </div>
              <div v-if="designerMessage" class="shrink-0 border-t border-outline-variant px-3 py-2 text-[12px] leading-5 text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
                {{ designerMessage }}
              </div>
            </aside>
          </div>

          <div v-else-if="activeTab === 'live'" class="grid h-full min-h-0 grid-cols-1 gap-4 overflow-hidden p-4 xl:grid-cols-[340px_minmax(0,1fr)_360px]">
            <section class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
              <div class="shrink-0 border-b border-outline-variant bg-surface-bright p-3 dark:border-zinc-800 dark:bg-zinc-900/60">
                <div class="flex items-center justify-between gap-2">
                  <div>
                    <div class="text-body-sm font-semibold text-on-surface dark:text-zinc-100">实时 Trace</div>
                    <p class="mt-1 text-[12px] text-on-surface-variant dark:text-zinc-500">
                      {{ liveStatus?.enabled ? `${liveStatus.active_count} 条运行中 · ${liveSocketState === 'connected' ? 'WebSocket 已连接' : '等待连接'}` : '未启用 AGENT_LIVE_TRACE_ENABLED' }}
                    </p>
                  </div>
                  <span class="rounded-full px-2 py-0.5 text-[11px]" :class="liveStatus?.enabled ? okChipClass : mutedChipClass">
                  {{ liveStatus?.enabled ? (liveSocketState === 'connected' ? 'WS Live' : 'Dev Trace On') : 'Off' }}
                  </span>
                </div>
              </div>
              <div class="min-h-0 flex-1 overflow-y-auto p-2">
                <button
                  v-for="trace in liveTraces"
                  :key="trace.trace_id"
                  type="button"
                  class="module-row"
                  :class="selectedLiveTraceId === trace.trace_id ? selectedModuleClass : idleModuleClass"
                  @click="selectLiveTrace(trace.trace_id)"
                >
                  <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0">
                      <div class="truncate font-code-inline text-code-inline">{{ trace.trace_id }}</div>
                      <div class="mt-1 line-clamp-2 text-[12px] leading-5 opacity-75">{{ trace.message_preview || '-' }}</div>
                    </div>
                    <StatusChip :status="trace.status" />
                  </div>
                  <div class="mt-2 flex flex-wrap gap-1.5">
                    <span :class="infoChipClass">{{ trace.current_stage || 'session' }}</span>
                    <span v-if="trace.current_tool" :class="chipBaseClass + ' ' + mutedChipClass">{{ trace.current_tool }}</span>
                  </div>
                </button>
                <EmptyState v-if="liveTraces.length === 0" text="暂无实时 trace；开启配置后发送一条消息即可看到链路。" />
              </div>
            </section>

            <section class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
              <div class="flex shrink-0 items-center justify-between gap-3 border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/60">
                <div class="min-w-0">
                  <h3 class="truncate font-body-sm text-body-sm font-semibold text-on-surface dark:text-zinc-100">
                    {{ liveDetail?.trace_id || '选择一条 Trace' }}
                  </h3>
                  <p class="mt-1 truncate text-[12px] text-on-surface-variant dark:text-zinc-500">
                    {{ liveDetail ? `${liveDetail.current_stage} / ${liveDetail.current_node || '-'}` : '事件时间线会按执行顺序实时刷新' }}
                  </p>
                </div>
                <button type="button" class="rounded-lg border border-outline-variant px-2 py-1 text-[12px] transition-colors hover:bg-surface-container dark:border-zinc-700 dark:hover:bg-zinc-800" @click="refreshLiveTraceConnection">
                  刷新
                </button>
              </div>
              <div class="min-h-0 flex-1 overflow-y-auto p-3">
                <div v-if="liveDetail?.events.length" class="space-y-2">
                  <button
                    v-for="event in liveDetail.events"
                    :key="event.sequence"
                    type="button"
                    class="w-full rounded-xl border border-outline-variant bg-surface-container-low p-3 text-left transition-colors hover:border-primary/40 dark:border-zinc-800 dark:bg-zinc-800/45 dark:hover:border-primary-dark/40"
                    :class="selectedLiveEvent?.sequence === event.sequence ? 'border-primary/60 dark:border-primary-dark/60' : ''"
                    @click="selectedLiveEvent = event"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <div class="flex min-w-0 items-center gap-2">
                        <span class="rounded-full bg-surface-container-lowest px-2 py-0.5 text-[11px] text-on-surface-variant dark:bg-zinc-900 dark:text-zinc-400">#{{ event.sequence }}</span>
                        <span class="truncate font-code-inline text-code-inline text-on-surface dark:text-zinc-100">{{ event.event_type }}</span>
                      </div>
                      <span class="shrink-0 rounded-full px-2 py-0.5 text-[11px]" :class="event.status === 'failed' ? dangerChipClass : event.status === 'completed' ? okChipClass : mutedChipClass">
                        {{ event.status || 'event' }}
                      </span>
                    </div>
                    <div class="mt-2 flex flex-wrap gap-1.5">
                      <span :class="infoChipClass">{{ event.stage || '-' }}</span>
                      <span v-if="event.node_label || event.node_type" :class="chipBaseClass + ' ' + mutedChipClass">{{ event.node_label || event.node_type }}</span>
                      <span v-if="event.tool_name" :class="chipBaseClass + ' ' + mutedChipClass">{{ event.tool_name }}</span>
                      <span v-if="event.duration_ms !== null" :class="chipBaseClass + ' ' + mutedChipClass">{{ Math.round(event.duration_ms || 0) }}ms</span>
                    </div>
                    <p v-if="event.observation_summary || event.error" class="mt-2 line-clamp-2 text-[12px] leading-5 text-on-surface-variant dark:text-zinc-500">
                      {{ event.error || event.observation_summary }}
                    </p>
                  </button>
                </div>
                <EmptyState v-else text="暂无事件。发送消息后可看到 turn、route、plan、tool call、reply 等阶段。" />
              </div>
            </section>

            <aside class="flex min-h-0 flex-col overflow-hidden rounded-xl border border-outline-variant bg-surface-container-lowest dark:border-zinc-800 dark:bg-zinc-900">
              <div class="shrink-0 border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/60">
                <h3 class="font-body-sm text-body-sm font-semibold text-on-surface dark:text-zinc-100">事件详情</h3>
                <p class="mt-1 text-[12px] text-on-surface-variant dark:text-zinc-500">参数已脱敏并截断，只用于开发态排障。</p>
              </div>
              <div class="min-h-0 flex-1 overflow-y-auto p-4">
                <template v-if="selectedLiveEvent">
                  <div class="grid gap-3">
                    <InfoTile label="阶段" :value="selectedLiveEvent.stage || '-'" />
                    <InfoTile label="节点" :value="selectedLiveEvent.node_label || selectedLiveEvent.node_type || '-'" />
                    <InfoTile label="工具 / 模型" :value="selectedLiveEvent.tool_name || selectedLiveEvent.model_name || '-'" />
                    <InfoTile label="时间" :value="formatTime(selectedLiveEvent.created_at)" />
                  </div>
                  <div v-if="selectedLiveEvent.observation_summary" class="mt-4 rounded-lg bg-surface-container p-3 text-body-sm leading-6 text-on-surface dark:bg-zinc-800 dark:text-zinc-200">
                    {{ selectedLiveEvent.observation_summary }}
                  </div>
                  <div v-if="selectedLiveEvent.error" class="mt-4 rounded-lg bg-red-500/10 p-3 text-body-sm leading-6 text-red-700 dark:text-red-300">
                    {{ selectedLiveEvent.error }}
                  </div>
                  <pre class="mt-4 max-h-[360px] overflow-auto rounded-lg bg-surface-container p-3 font-code-inline text-[11px] leading-5 text-on-surface dark:bg-zinc-800 dark:text-zinc-200">{{ formatJson(selectedLiveEvent.params_preview) }}</pre>
                </template>
                <EmptyState v-else text="点击时间线事件查看参数预览、工具名、耗时和错误。" />
              </div>
            </aside>
          </div>

          <div v-else-if="activeTab === 'config'" class="h-full min-h-0 overflow-y-auto p-4">
            <DetailCard title="Agent 参数预设">
              <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p class="text-body-sm leading-6 text-on-surface dark:text-zinc-200">
                    这里展示编排画布中每个 Agent 节点的参数草稿。节点启用状态与顺序可热更新到 Runtime；模型、温度等字段会随配置保存，等待节点级模型策略消费。
                  </p>
                  <p class="mt-1 text-[12px] text-on-surface-variant dark:text-zinc-500">
                    保存状态：{{ designer?.draft.updated_at ? formatTime(designer.draft.updated_at) : '尚未保存' }}
                  </p>
                  <p class="mt-1 text-[12px] text-on-surface-variant dark:text-zinc-500">
                    运行时：{{ runtimeStatusText }}
                  </p>
                </div>
                <span class="shrink-0 rounded-full px-3 py-1 text-[12px] font-medium" :class="designer?.applied_to_runtime ? okChipClass : mutedChipClass">
                  {{ designer?.applied_to_runtime ? '已同步 Runtime' : '草稿未应用' }}
                </span>
              </div>
              <div class="mt-3 grid gap-3 xl:grid-cols-2">
                <div
                  v-for="node in designerNodes"
                  :key="`config-node-${node.id}`"
                  class="rounded-xl border border-outline-variant bg-surface-container-lowest p-3 dark:border-zinc-800 dark:bg-zinc-900/60"
                >
                  <div class="flex items-center justify-between gap-2">
                    <span class="truncate text-body-sm font-semibold text-on-surface dark:text-zinc-100">{{ node.label }}</span>
                    <button type="button" class="rounded-lg px-2 py-1 text-[12px] text-primary transition-colors hover:bg-primary/10 dark:text-primary-dark dark:hover:bg-primary-dark/12" @click="activeTab = 'flow'; selectedDesignerNodeId = node.id">
                      编辑
                    </button>
                  </div>
                  <p class="mt-1 truncate font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500">{{ node.module_id }}</p>
                  <div v-if="Object.keys(node.config || {}).length" class="mt-3 flex flex-wrap gap-1.5">
                    <span
                      v-for="(value, key) in node.config"
                      :key="`${node.id}-${String(key)}`"
                      class="rounded-full bg-sky-500/10 px-2 py-0.5 text-[11px] text-sky-700 dark:bg-sky-400/10 dark:text-sky-300"
                    >
                      {{ key }}={{ value }}
                    </span>
                  </div>
                  <p v-else class="mt-3 text-[12px] text-on-surface-variant dark:text-zinc-500">继承系统默认配置</p>
                </div>
              </div>
            </DetailCard>

            <div class="mt-4 grid gap-4 xl:grid-cols-2">
              <DetailCard v-for="group in configGroups" :key="group.name" :title="group.name">
                <div class="space-y-3">
                  <div
                    v-for="item in group.items"
                    :key="item.id"
                    class="rounded-lg border border-outline-variant bg-surface-container-lowest p-3 dark:border-zinc-800 dark:bg-zinc-900/60"
                  >
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0">
                        <div class="flex items-center gap-2">
                          <span class="truncate text-body-sm font-semibold text-on-surface dark:text-zinc-100">{{ item.name }}</span>
                          <span class="rounded-full px-2 py-0.5 text-[11px]" :class="item.editable || item.toggleable ? okChipClass : mutedChipClass">
                            {{ item.editable || item.toggleable ? '可操作' : '只读' }}
                          </span>
                        </div>
                        <p class="mt-1 text-[12px] leading-5 text-on-surface-variant dark:text-zinc-500">{{ item.description }}</p>
                      </div>
                      <Settings2 :size="15" class="shrink-0 text-on-surface-variant dark:text-zinc-500" />
                    </div>
                    <div class="mt-3 rounded-lg bg-surface-container px-3 py-2 font-code-inline text-code-inline text-on-surface dark:bg-zinc-800 dark:text-zinc-200">
                      {{ item.value }}
                    </div>
                    <div class="mt-2 truncate font-code-inline text-[11px] text-on-surface-variant dark:text-zinc-500">
                      source: {{ item.source }}
                    </div>
                  </div>
                </div>
              </DetailCard>
            </div>
          </div>

          <div v-else class="flex h-full min-h-0 flex-col overflow-hidden">
            <div class="flex shrink-0 flex-col gap-3 border-b border-outline-variant bg-surface-bright px-4 py-3 dark:border-zinc-800 dark:bg-zinc-900/60 lg:flex-row lg:items-center lg:justify-between">
              <div class="grid grid-cols-4 gap-1 rounded-lg border border-outline-variant bg-surface-container p-0.5 dark:border-zinc-700 dark:bg-zinc-800">
                <button
                  v-for="seg in segments"
                  :key="seg.key"
                  type="button"
                  class="h-8 rounded-md px-3 text-[12px] font-semibold transition-colors"
                  :class="activeSegment === seg.key ? activeSegmentClass : inactiveSegmentClass"
                  @click="setSegment(seg.key)"
                >
                  {{ seg.label }}
                  <span v-if="seg.key === 'pending' && pendingCount" class="ml-1 rounded-full bg-warning/20 px-1.5 py-0.5 text-[10px] text-warning dark:bg-amber-500/20 dark:text-amber-300">
                    {{ pendingCount }}
                  </span>
                </button>
              </div>
              <div class="flex min-w-0 items-center gap-2">
                <div class="relative min-w-[220px] flex-1">
                  <Search :size="15" class="absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant dark:text-zinc-500" />
                  <input
                    v-model="search"
                    :disabled="isCheckpointSegment"
                    class="h-9 w-full rounded-lg border border-outline-variant bg-surface-container pl-8 pr-3 text-body-sm text-on-surface outline-none transition-colors focus:border-primary disabled:cursor-not-allowed disabled:opacity-60 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:focus:border-primary-dark"
                    :placeholder="isCheckpointSegment ? '检查点按状态筛选' : '搜索 trace、目标、摘要...'"
                    @input="onSearch"
                  />
                </div>
                <AppSelect
                  v-if="activeSegment === 'runs'"
                  v-model="kindFilter"
                  :options="kindOptions"
                  wrapper-class="w-[132px]"
                  button-class="h-9"
                  @change="page = 1; fetchData()"
                />
              </div>
            </div>

            <div class="min-h-0 flex-1 overflow-auto">
              <table class="w-full border-collapse text-left">
                <thead class="sticky top-0 z-10 border-b border-outline-variant bg-surface-bright dark:border-zinc-800 dark:bg-zinc-900">
                  <tr>
                    <th class="whitespace-nowrap p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">Trace ID</th>
                    <th class="whitespace-nowrap p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">用户</th>
                    <th class="whitespace-nowrap p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">类型</th>
                    <th class="whitespace-nowrap p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">状态</th>
                    <th class="p-[10px_12px] font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">目标 / 摘要</th>
                    <th class="whitespace-nowrap p-[10px_12px] text-right font-label-caps text-label-caps uppercase text-on-surface-variant dark:text-zinc-500">操作</th>
                  </tr>
                </thead>
                <tbody class="divide-y divide-outline-variant text-body-sm text-on-surface dark:divide-zinc-800 dark:text-zinc-200">
                  <tr v-if="items.length === 0">
                    <td colspan="6" class="p-8 text-center text-on-surface-variant dark:text-zinc-500">暂无记录</td>
                  </tr>
                  <tr
                    v-for="item in items"
                    :key="`${activeSegment}-${item.id}`"
                    class="cursor-pointer transition-colors hover:bg-surface-container dark:hover:bg-zinc-800/60"
                    @click="selectItem(item)"
                  >
                    <td class="max-w-[220px] p-[10px_12px]">
                      <span class="block truncate font-code-inline text-code-inline text-primary dark:text-primary-dark">{{ item.trace_id || '-' }}</span>
                    </td>
                    <td class="whitespace-nowrap p-[10px_12px]">{{ item.user_id }}</td>
                    <td class="whitespace-nowrap p-[10px_12px]">{{ kindLabel(item.kind) }}</td>
                    <td class="whitespace-nowrap p-[10px_12px]"><StatusChip :status="item.status || ''" /></td>
                    <td class="max-w-[520px] p-[10px_12px]">
                      <span class="block truncate text-on-surface-variant dark:text-zinc-400">{{ item.goal || item.summary || '-' }}</span>
                    </td>
                    <td class="whitespace-nowrap p-[10px_12px] text-right">
                      <div class="flex items-center justify-end gap-1">
                        <button type="button" class="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container hover:text-primary dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-primary-dark" @click.stop="selectItem(item)">
                          <Eye :size="16" />
                        </button>
                        <button type="button" class="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-100" @click.stop="copyTraceId(item)">
                          <Copy :size="16" />
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="flex shrink-0 items-center justify-between border-t border-outline-variant px-4 py-2 text-body-sm text-on-surface-variant dark:border-zinc-800 dark:text-zinc-500">
              <span>共 {{ total }} 条，第 {{ page }}/{{ totalPages }} 页</span>
              <div class="flex gap-1">
                <button type="button" class="rounded-lg border border-outline-variant px-2 py-1 transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800" :disabled="page <= 1" @click="page--; fetchData()">上一页</button>
                <button type="button" class="rounded-lg border border-outline-variant px-2 py-1 transition-colors hover:bg-surface-container disabled:cursor-not-allowed disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800" :disabled="page >= totalPages" @click="page++; fetchData()">下一页</button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>

    <Teleport to="body">
      <div v-if="selectedItem" class="fixed inset-0 z-50">
        <div class="absolute inset-0 bg-black/10 dark:bg-black/45" @click="closeDetail" />
        <aside class="fixed bottom-0 right-0 top-topbar flex w-drawer-max max-w-[92vw] flex-col border-l border-outline-variant bg-surface-container-lowest shadow-xl dark:border-zinc-800 dark:bg-zinc-900">
          <div class="flex shrink-0 items-start justify-between gap-3 border-b border-outline-variant bg-surface-bright p-4 dark:border-zinc-800 dark:bg-zinc-900/60">
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <h2 class="font-h2 text-h2 text-on-surface dark:text-zinc-100">运行详情</h2>
                <StatusChip :status="selectedItem.status || ''" />
              </div>
              <p class="mt-1 truncate font-code-inline text-code-inline text-on-surface-variant dark:text-zinc-500">{{ selectedItem.trace_id }}</p>
            </div>
            <button type="button" class="rounded-lg p-1.5 text-on-surface-variant transition-colors hover:bg-surface-container dark:text-zinc-400 dark:hover:bg-zinc-800" @click="closeDetail">
              <X :size="18" />
            </button>
          </div>

          <div class="min-h-0 flex-1 overflow-y-auto p-4">
            <div v-if="detailLoading" class="py-8 text-center text-on-surface-variant dark:text-zinc-500">加载中...</div>
            <div v-else class="space-y-4">
              <DetailCard title="基础信息">
                <div class="grid gap-3 sm:grid-cols-2">
                  <InfoTile label="用户 ID" :value="String(selectedItem.user_id)" />
                  <InfoTile label="类型" :value="kindLabel(selectedItem.kind)" />
                  <InfoTile label="Playbook" :value="selectedItem.playbook_name || selectedItem.playbook_id || '-'" />
                  <InfoTile label="创建时间" :value="formatTime(selectedItem.created_at)" />
                </div>
                <div class="mt-4 rounded-lg bg-surface-container p-3 dark:bg-zinc-800">
                  <div class="text-[12px] font-medium text-on-surface-variant dark:text-zinc-500">目标 / 摘要</div>
                  <p class="mt-1 text-body-sm leading-6 text-on-surface dark:text-zinc-200">{{ selectedItem.goal || selectedItem.summary || '暂无说明' }}</p>
                </div>
              </DetailCard>

              <DetailCard title="工作流步骤">
                <div v-if="detailSteps.length" class="space-y-2">
                  <div
                    v-for="(step, index) in detailSteps"
                    :key="String(readField(step, 'step_id') || index)"
                    class="rounded-lg border border-outline-variant bg-surface-container-lowest p-3 dark:border-zinc-800 dark:bg-zinc-900/60"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <span class="font-body-sm text-body-sm font-semibold text-on-surface dark:text-zinc-100">
                        {{ readField(step, 'title') || `步骤 ${index + 1}` }}
                      </span>
                      <StatusChip :status="String(readField(step, 'status') || 'pending')" />
                    </div>
                    <p class="mt-1 font-code-inline text-code-inline text-primary dark:text-primary-dark">
                      {{ readField(step, 'command') || '-' }}
                    </p>
                    <p v-if="readField(step, 'description')" class="mt-1 text-[12px] leading-5 text-on-surface-variant dark:text-zinc-500">
                      {{ readField(step, 'description') }}
                    </p>
                  </div>
                </div>
                <p v-else class="text-body-sm text-on-surface-variant dark:text-zinc-500">该记录没有可执行步骤，可能是普通对话或直接回复。</p>
              </DetailCard>

              <DetailCard title="可观测指标">
                <div v-if="promptStages.length" class="grid gap-2">
                  <div
                    v-for="stage in promptStages"
                    :key="String(readField(stage, 'stage'))"
                    class="rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900/60"
                  >
                    <div class="flex items-center justify-between gap-2">
                      <span class="font-code-inline text-code-inline text-on-surface dark:text-zinc-100">{{ readField(stage, 'stage') }}</span>
                      <span class="text-[12px] text-on-surface-variant dark:text-zinc-500">
                        {{ readField(stage, 'prompt_char_length') || 0 }} chars
                      </span>
                    </div>
                    <div class="mt-1 text-[12px] text-on-surface-variant dark:text-zinc-500">
                      命令召回 {{ readField(stage, 'recalled_command_count') || 0 }} / Skill 召回 {{ readField(stage, 'recalled_skill_count') || 0 }}
                    </div>
                  </div>
                </div>
                <p v-else class="text-body-sm text-on-surface-variant dark:text-zinc-500">暂无可观测指标。</p>
              </DetailCard>

              <DetailCard title="事件轨迹">
                <div v-if="detailEvents.length" class="space-y-2">
                  <div v-for="(event, index) in detailEvents" :key="String(readField(event, 'event') || index)" class="rounded-lg bg-surface-container px-3 py-2 dark:bg-zinc-800">
                    <div class="flex items-center justify-between gap-2">
                      <span class="font-code-inline text-code-inline text-on-surface dark:text-zinc-100">{{ readField(event, 'event') || readField(event, 'type') || `event-${index + 1}` }}</span>
                      <span class="text-[11px] text-on-surface-variant dark:text-zinc-500">{{ formatTime(String(readField(event, 'created_at') || readField(event, 'timestamp') || '')) }}</span>
                    </div>
                    <p class="mt-1 text-[12px] leading-5 text-on-surface-variant dark:text-zinc-500">{{ readField(event, 'message') || readField(event, 'description') || '-' }}</p>
                  </div>
                </div>
                <p v-else class="text-body-sm text-on-surface-variant dark:text-zinc-500">暂无事件轨迹。</p>
              </DetailCard>
            </div>
          </div>
        </aside>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  Activity,
  AlertTriangle,
  BrainCircuit,
  Copy,
  Eye,
  GitBranch,
  Layers3,
  Link2,
  Network,
  PlayCircle,
  Puzzle,
  RefreshCw,
  Save,
  Search,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Trash2,
  X,
} from 'lucide-vue-next'
import {
  fetchAgentCheckpoints,
  fetchAgentCheckpoint,
  fetchAgentDesigner,
  fetchAgentLiveTrace,
  fetchAgentLiveTraces,
  fetchAgentLiveTraceStatus,
  fetchAgentOverview,
  fetchAgentRun,
  fetchAgentRuns,
  saveAgentDesigner,
} from '@/api/agents'
import type {
  AgentCheckpointDetail,
  AgentCheckpointSummary,
  AgentConfigField,
  AgentConfigItem,
  AgentDesignerEdge,
  AgentDesignerNode,
  AgentDesignerResponse,
  AgentLiveTraceDetail,
  AgentLiveTraceEvent,
  AgentLiveTraceStatus,
  AgentLiveTraceSummary,
  AgentModuleInfo,
  AgentOverviewResponse,
  AgentRunDetail,
  AgentRunSummary,
} from '@/types/api'
import AppSelect from '@/components/AppSelect.vue'
import ChartPanel from '@/components/ChartPanel.vue'
import StatusChip from '@/components/StatusChip.vue'
import { useTheme } from '@/composables/useTheme'
import { useAuthStore } from '@/composables/useAuth'

type MainTab = 'overview' | 'flow' | 'live' | 'config' | 'records'
type SegmentKey = 'runs' | 'checkpoints' | 'pending' | 'failed'
type RecordItem = AgentRunSummary | AgentCheckpointSummary
type LiveSocketState = 'idle' | 'connecting' | 'connected' | 'closed' | 'fallback'

interface LiveTraceSnapshotMessage {
  type: 'snapshot'
  status: AgentLiveTraceStatus
  traces: {
    items: AgentLiveTraceSummary[]
    total: number
  }
  selected_trace_id: string
  detail: AgentLiveTraceDetail | null
}

const StatCard = defineComponent({
  props: {
    title: { type: String, required: true },
    value: { type: [String, Number], required: true },
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

const InfoTile = defineComponent({
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true },
    code: { type: Boolean, default: false },
  },
  setup(props) {
    return () => h('div', { class: 'rounded-lg border border-outline-variant bg-surface-container-lowest px-3 py-2 dark:border-zinc-800 dark:bg-zinc-900/60' }, [
      h('div', { class: 'text-[12px] text-on-surface-variant dark:text-zinc-500' }, props.label),
      h('div', {
        class: [
          'mt-1 break-all text-body-sm text-on-surface dark:text-zinc-100',
          props.code ? 'font-code-inline text-code-inline' : '',
        ],
      }, props.value || '-'),
    ])
  },
})

const { isDark } = useTheme()
const authStore = useAuthStore()
const overview = ref<AgentOverviewResponse | null>(null)
const designer = ref<AgentDesignerResponse | null>(null)
const loading = ref(false)
const designerSaving = ref(false)
const designerApplying = ref(false)
const activeTab = ref<MainTab>('overview')
const moduleSearch = ref('')
const selectedModuleId = ref('')
const designerNodes = ref<AgentDesignerNode[]>([])
const designerEdges = ref<AgentDesignerEdge[]>([])
const designerNote = ref('')
const selectedDesignerNodeId = ref('')
const linkSourceNodeId = ref('')
const designerMessage = ref('')
const activeSegment = ref<SegmentKey>('runs')
const items = ref<RecordItem[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const search = ref('')
const kindFilter = ref('')
const pendingCount = ref(0)
const selectedItem = ref<RecordItem | null>(null)
const selectedItemIsCheckpoint = ref(false)
const detailData = ref<AgentRunDetail | AgentCheckpointDetail | null>(null)
const detailLoading = ref(false)
const liveStatus = ref<AgentLiveTraceStatus | null>(null)
const liveTraces = ref<AgentLiveTraceSummary[]>([])
const liveDetail = ref<AgentLiveTraceDetail | null>(null)
const selectedLiveTraceId = ref('')
const selectedLiveEvent = ref<AgentLiveTraceEvent | null>(null)
const liveSocket = ref<WebSocket | null>(null)
const liveSocketState = ref<LiveSocketState>('idle')
const liveReconnectTimer = ref<ReturnType<typeof setTimeout> | null>(null)

const mainTabs = [
  { key: 'overview' as const, label: '概览', icon: BrainCircuit },
  { key: 'flow' as const, label: '编排', icon: Network },
  { key: 'live' as const, label: '实时', icon: Activity },
  { key: 'config' as const, label: '配置', icon: Settings2 },
  { key: 'records' as const, label: '运行', icon: Activity },
]
const segments = [
  { key: 'runs' as const, label: '运行记录' },
  { key: 'checkpoints' as const, label: '检查点' },
  { key: 'pending' as const, label: '待确认' },
  { key: 'failed' as const, label: '失败记录' },
]
const kindOptions = [
  { label: '全部类型', value: '' },
  { label: '聊天', value: 'chat' },
  { label: '命令', value: 'command' },
  { label: '命令序列', value: 'command_sequence' },
  { label: '知识检索', value: 'knowledge' },
]

const activeSegmentClass = 'bg-surface-container-lowest text-primary shadow-sm dark:bg-zinc-900 dark:text-primary-dark'
const inactiveSegmentClass = 'text-on-surface-variant hover:text-on-surface dark:text-zinc-400 dark:hover:text-zinc-100'
const selectedModuleClass = 'border-primary/30 bg-primary/10 text-primary dark:border-primary-dark/30 dark:bg-primary-dark/12 dark:text-primary-dark'
const idleModuleClass = 'border-transparent text-on-surface hover:bg-surface-container dark:text-zinc-200 dark:hover:bg-zinc-800/70'
const chipBaseClass = 'inline-flex shrink-0 items-center rounded-full px-2.5 py-1 text-[11px] font-medium leading-none'
const okChipClass = 'bg-primary/10 text-primary dark:bg-primary-dark/15 dark:text-primary-dark'
const mutedChipClass = 'bg-surface-container text-on-surface-variant dark:bg-zinc-800 dark:text-zinc-400'
const dangerChipClass = 'bg-red-500/10 text-red-700 dark:bg-red-500/12 dark:text-red-300'
const infoChipClass = 'rounded-full bg-sky-500/10 px-2 py-0.5 text-[11px] text-sky-700 dark:bg-sky-400/10 dark:text-sky-300'

const modules = computed(() => overview.value?.modules || [])
const designerPalette = computed(() => designer.value?.palette || modules.value)
const sidebarModules = computed(() => activeTab.value === 'flow' ? designerPalette.value : modules.value)
const stats = computed(() => overview.value?.stats)
const selectedModule = computed<AgentModuleInfo | null>(() => {
  return sidebarModules.value.find((item) => item.id === selectedModuleId.value) || filteredModules.value[0] || null
})
const selectedDesignerNode = computed<AgentDesignerNode | null>(() => {
  return designerNodes.value.find((item) => item.id === selectedDesignerNodeId.value) || designerNodes.value[0] || null
})
const selectedDesignerModule = computed<AgentModuleInfo | null>(() => {
  if (!selectedDesignerNode.value) return null
  return designerPalette.value.find((item) => (
    item.node_type === selectedDesignerNode.value?.node_type ||
    item.id === selectedDesignerNode.value?.node_type ||
    item.id === selectedDesignerNode.value?.module_id
  )) || null
})
const designerConfigSchema = computed<AgentConfigField[]>(() => {
  return selectedDesignerModule.value?.config_schema || designer.value?.config_schema || []
})
const canvasSize = computed(() => {
  const maxX = Math.max(960, ...designerNodes.value.map((item) => item.x + 220))
  const maxY = Math.max(560, ...designerNodes.value.map((item) => item.y + 132))
  return { width: maxX + 80, height: maxY + 80 }
})
const filteredModules = computed(() => {
  const keyword = normalize(moduleSearch.value)
  if (!keyword) return sidebarModules.value
  return sidebarModules.value.filter((module) => [
    module.name,
    module.category,
    module.source,
    module.description,
    module.capabilities.join(' '),
  ].some((value) => normalize(value).includes(keyword)))
})
const statCards = computed(() => [
  {
    title: '模块',
    value: stats.value?.modules || 0,
    sub: `${stats.value?.enabled_modules || 0} 已接入`,
    icon: Layers3,
  },
  {
    title: 'Agent 命令',
    value: stats.value?.available_agent_commands || 0,
    sub: `${stats.value?.agent_callable_commands || 0} 已登记`,
    icon: ShieldCheck,
  },
  {
    title: 'Skill',
    value: stats.value?.skills || 0,
    sub: `${stats.value?.loaded_skills || 0} 运行时`,
    icon: Puzzle,
  },
  {
    title: '待确认',
    value: stats.value?.pending_checkpoints || 0,
    sub: '检查点等待用户确认',
    icon: PlayCircle,
  },
  {
    title: '失败',
    value: stats.value?.failed_runs || 0,
    sub: `${stats.value?.runs || 0} 次运行记录`,
    icon: AlertTriangle,
  },
])
const activeTabIcon = computed(() => mainTabs.find((tab) => tab.key === activeTab.value)?.icon || BrainCircuit)
const activeTitle = computed(() => {
  if (activeTab.value === 'flow') return 'Agent 编排设计器'
  if (activeTab.value === 'live') return 'Live Trace'
  if (activeTab.value === 'config') return 'Agent 配置'
  if (activeTab.value === 'records') return '运行数据'
  return selectedModule.value?.name || 'Agent 概览'
})
const activeSubtitle = computed(() => {
  if (activeTab.value === 'flow') return '拖动 Runtime 节点到画布，合法图可以保存并热更新到后续 Agent 轮次'
  if (activeTab.value === 'live') return '开发模式下实时查看消息、节点、工具调用、参数预览和 observation'
  if (activeTab.value === 'config') return '展示真实运行配置，并管理 Agent 节点参数预设'
  if (activeTab.value === 'records') return '运行记录、检查点、待确认和失败轨迹'
  return selectedModule.value?.description || '选择左侧模块查看职责和能力'
})
const runtimeStatusText = computed(() => {
  if (!designer.value) return '未读取'
  if (!designer.value.runtime.valid) return `配置无效：${designer.value.runtime.errors.join('；') || '未知错误'}`
  return designer.value.runtime.enabled
    ? `编排图，${designer.value.runtime.active_node_count} 个节点，${designer.value.runtime.active_edge_count} 条连线`
    : '编排图暂不可用'
})
const configGroups = computed(() => {
  const groups = new Map<string, AgentConfigItem[]>()
  for (const item of overview.value?.config || []) {
    if (!groups.has(item.group)) groups.set(item.group, [])
    groups.get(item.group)?.push(item)
  }
  return Array.from(groups.entries()).map(([name, groupItems]) => ({ name, items: groupItems }))
})
const isCheckpointSegment = computed(() => activeSegment.value === 'checkpoints' || activeSegment.value === 'pending')
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
const detailWorkflow = computed(() => asRecord(detailData.value?.workflow_data))
const detailSteps = computed(() => asRecordArray(detailWorkflow.value?.steps))
const detailEvents = computed(() => asRecordArray(detailWorkflow.value?.events))
const detailObservability = computed(() => asRecord(detailWorkflow.value?.observability))
const promptStages = computed(() => asRecordArray(detailObservability.value?.prompt_stages))

const statusChartOption = computed<Record<string, unknown>>(() => buildPieOption(overview.value?.metrics.runs_by_status || {}, statusLabel))
const kindChartOption = computed<Record<string, unknown>>(() => {
  const entries = Object.entries(overview.value?.metrics.runs_by_kind || {})
  return {
    color: [isDark.value ? '#4da394' : '#28645a'],
    tooltip: { trigger: 'axis' },
    grid: { left: 24, right: 12, top: 18, bottom: 28, containLabel: true },
    xAxis: {
      type: 'category',
      data: entries.map(([name]) => kindLabel(name)),
      axisLabel: { color: isDark.value ? '#a1a1aa' : '#475569', fontSize: 11 },
      axisLine: { lineStyle: { color: isDark.value ? '#3f3f46' : '#cbd5e1' } },
    },
    yAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { color: isDark.value ? '#a1a1aa' : '#475569', fontSize: 11 },
      splitLine: { lineStyle: { color: isDark.value ? '#27272a' : '#e2e8f0' } },
    },
    series: [{ type: 'bar', barWidth: 24, data: entries.map(([, value]) => value), itemStyle: { borderRadius: [6, 6, 0, 0] } }],
  }
})

let searchTimer: ReturnType<typeof setTimeout> | undefined

onMounted(() => {
  reload()
  if (activeTab.value === 'live') connectLiveSocket()
})

onBeforeUnmount(() => closeLiveSocket())

watch(activeTab, (tab) => {
  if (tab === 'live') connectLiveSocket()
  else closeLiveSocket()
})

watch(selectedLiveTraceId, () => {
  if (activeTab.value === 'live') sendLiveTraceSelection()
})

async function reload() {
  loading.value = true
  try {
    await Promise.all([loadOverview(), loadDesigner(), fetchData(), loadLiveTraceStatus()])
    if (activeTab.value === 'live' && liveSocketState.value !== 'connected') await loadLiveTraceSnapshotFallback()
  } finally {
    loading.value = false
  }
}

async function loadLiveTraceStatus() {
  try {
    liveStatus.value = await fetchAgentLiveTraceStatus()
  } catch {
    liveStatus.value = null
  }
}

async function loadLiveTraces() {
  try {
    const res = await fetchAgentLiveTraces()
    liveTraces.value = res.items
    if (!selectedLiveTraceId.value && liveTraces.value.length) {
      selectedLiveTraceId.value = liveTraces.value[0].trace_id
      await loadSelectedLiveTrace()
    }
  } catch {
    liveTraces.value = []
  }
}

async function loadLiveTraceSnapshotFallback() {
  await Promise.all([loadLiveTraceStatus(), loadLiveTraces()])
  if (selectedLiveTraceId.value) await loadSelectedLiveTrace()
}

async function loadSelectedLiveTrace() {
  if (!selectedLiveTraceId.value) {
    liveDetail.value = null
    selectedLiveEvent.value = null
    return
  }
  try {
    const detail = await fetchAgentLiveTrace(selectedLiveTraceId.value)
    liveDetail.value = detail
    if (!selectedLiveEvent.value && detail.events.length) {
      selectedLiveEvent.value = detail.events[detail.events.length - 1]
    } else if (selectedLiveEvent.value) {
      selectedLiveEvent.value = detail.events.find((event) => event.sequence === selectedLiveEvent.value?.sequence) || detail.events[detail.events.length - 1] || null
    }
  } catch {
    liveDetail.value = null
    selectedLiveEvent.value = null
  }
}

function selectLiveTrace(traceId: string) {
  selectedLiveTraceId.value = traceId
  selectedLiveEvent.value = null
  sendLiveTraceSelection()
  if (liveSocketState.value !== 'connected') loadSelectedLiveTrace()
}

function liveTraceWsUrl() {
  const token = authStore.sessionToken
  if (!token) return ''
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  const traceParam = selectedLiveTraceId.value ? `&trace_id=${encodeURIComponent(selectedLiveTraceId.value)}` : ''
  return `${protocol}//${window.location.host}/api/v1/manager/agents/live/ws?token=${encodeURIComponent(token)}${traceParam}`
}

function connectLiveSocket() {
  clearLiveReconnectTimer()
  closeLiveSocket({ keepState: true })
  if (activeTab.value !== 'live') return
  const url = liveTraceWsUrl()
  if (!url) {
    liveSocketState.value = 'fallback'
    loadLiveTraceSnapshotFallback()
    return
  }
  liveSocketState.value = 'connecting'
  const socket = new WebSocket(url)
  liveSocket.value = socket

  socket.onopen = () => {
    if (liveSocket.value !== socket) return
    liveSocketState.value = 'connected'
    sendLiveTraceSelection()
  }
  socket.onmessage = (event) => {
    try {
      const payload = JSON.parse(String(event.data)) as LiveTraceSnapshotMessage
      if (payload.type === 'snapshot') applyLiveTraceSnapshot(payload)
    } catch {
      // Ignore malformed dev-trace frames; the next valid snapshot will repair UI state.
    }
  }
  socket.onerror = () => {
    if (liveSocket.value === socket) liveSocketState.value = 'fallback'
  }
  socket.onclose = () => {
    if (liveSocket.value === socket) liveSocket.value = null
    if (activeTab.value === 'live') scheduleLiveReconnect()
    else liveSocketState.value = 'closed'
  }
}

function closeLiveSocket(options: { keepState?: boolean } = {}) {
  clearLiveReconnectTimer()
  const socket = liveSocket.value
  if (socket) {
    socket.onopen = null
    socket.onmessage = null
    socket.onerror = null
    socket.onclose = null
    if (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN) socket.close()
    liveSocket.value = null
  }
  if (!options.keepState) liveSocketState.value = 'idle'
}

function clearLiveReconnectTimer() {
  if (liveReconnectTimer.value) {
    clearTimeout(liveReconnectTimer.value)
    liveReconnectTimer.value = null
  }
}

function scheduleLiveReconnect() {
  clearLiveReconnectTimer()
  liveSocketState.value = 'closed'
  liveReconnectTimer.value = setTimeout(() => {
    if (activeTab.value === 'live') connectLiveSocket()
  }, 2500)
}

function sendLiveTraceSelection() {
  const socket = liveSocket.value
  if (!socket || socket.readyState !== WebSocket.OPEN) return
  socket.send(JSON.stringify({ type: 'select_trace', trace_id: selectedLiveTraceId.value }))
}

function refreshLiveTraceConnection() {
  if (activeTab.value !== 'live') return
  if (liveSocketState.value === 'connected') {
    sendLiveTraceSelection()
    return
  }
  connectLiveSocket()
  if (liveSocketState.value === 'fallback') loadLiveTraceSnapshotFallback()
}

function applyLiveTraceSnapshot(payload: LiveTraceSnapshotMessage) {
  liveStatus.value = payload.status
  liveTraces.value = payload.traces.items

  const currentTraceExists = selectedLiveTraceId.value
    ? liveTraces.value.some((trace) => trace.trace_id === selectedLiveTraceId.value)
    : false
  if (!selectedLiveTraceId.value && liveTraces.value.length) {
    selectedLiveTraceId.value = liveTraces.value[0].trace_id
  } else if (!currentTraceExists && payload.selected_trace_id) {
    selectedLiveTraceId.value = payload.selected_trace_id
  }

  if (payload.detail) {
    liveDetail.value = payload.detail
    selectedLiveTraceId.value = payload.detail.trace_id
    if (selectedLiveEvent.value) {
      selectedLiveEvent.value =
        payload.detail.events.find((event) => event.sequence === selectedLiveEvent.value?.sequence) ||
        payload.detail.events[payload.detail.events.length - 1] ||
        null
    } else {
      selectedLiveEvent.value = payload.detail.events[payload.detail.events.length - 1] || null
    }
  } else if (selectedLiveTraceId.value && selectedLiveTraceId.value === payload.selected_trace_id) {
    liveDetail.value = null
    selectedLiveEvent.value = null
  }
}

async function loadOverview() {
  overview.value = await fetchAgentOverview()
  pendingCount.value = overview.value.stats.pending_checkpoints
  if (!selectedModuleId.value || !modules.value.some((item) => item.id === selectedModuleId.value)) {
    selectedModuleId.value = modules.value[0]?.id || ''
  }
}

async function loadDesigner() {
  designer.value = await fetchAgentDesigner()
  designerNodes.value = designer.value.draft.nodes.map((node) => ({
    ...node,
    node_type: node.node_type || node.id,
    config: { ...(node.config || {}) },
  }))
  designerEdges.value = designer.value.draft.edges.map((edge) => ({ ...edge }))
  designerNote.value = designer.value.draft.note || ''
  if (!selectedDesignerNodeId.value || !designerNodes.value.some((item) => item.id === selectedDesignerNodeId.value)) {
    selectedDesignerNodeId.value = designerNodes.value[0]?.id || ''
  }
}

function getDesignerNode(id: string) {
  return designerNodes.value.find((item) => item.id === id) || null
}

function nodeCenter(id: string) {
  const node = getDesignerNode(id)
  if (!node) return { x: 0, y: 0 }
  return { x: node.x + 96, y: node.y + 42 }
}

function edgeLine(edge: AgentDesignerEdge) {
  const start = nodeCenter(edge.source)
  const end = nodeCenter(edge.target)
  return { x1: start.x, y1: start.y, x2: end.x, y2: end.y }
}

function handlePaletteDragStart(event: DragEvent, module: AgentModuleInfo) {
  event.dataTransfer?.setData('application/x-agent-module', module.id)
  event.dataTransfer?.setData('text/plain', module.name)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy'
}

function handleNodeDragStart(event: DragEvent, node: AgentDesignerNode) {
  event.dataTransfer?.setData('application/x-agent-node', node.id)
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'move'
}

function handleDesignerDrop(event: DragEvent) {
  event.preventDefault()
  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const x = Math.max(24, Math.round(event.clientX - rect.left - 96))
  const y = Math.max(24, Math.round(event.clientY - rect.top - 42))
  const movedNodeId = event.dataTransfer?.getData('application/x-agent-node')
  if (movedNodeId) {
    designerNodes.value = designerNodes.value.map((node) => (
      node.id === movedNodeId ? { ...node, x, y } : node
    ))
    selectedDesignerNodeId.value = movedNodeId
    return
  }

  const moduleId = event.dataTransfer?.getData('application/x-agent-module')
  const module = designerPalette.value.find((item) => item.id === moduleId)
  if (!module) return
  const nodeType = module.node_type || module.id
  const nodeId = `${nodeType}-${Date.now().toString(36)}`
  designerNodes.value.push({
    id: nodeId,
    node_type: nodeType,
    module_id: module.module_id || module.id,
    label: module.name,
    phase: module.category,
    x,
    y,
    enabled: true,
    config: {},
    runtime_applied: false,
  })
  selectedDesignerNodeId.value = nodeId
  designerMessage.value = '已加入画布，点击“连接下一步”后再选择目标节点即可建立链路。'
}

function handleDesignerNodeClick(node: AgentDesignerNode) {
  if (linkSourceNodeId.value && linkSourceNodeId.value !== node.id) {
    connectDesignerNodes(linkSourceNodeId.value, node.id)
    return
  }
  selectedDesignerNodeId.value = node.id
}

function connectDesignerNodes(source: string, target: string) {
  if (source === target) return
  const exists = designerEdges.value.some((edge) => edge.source === source && edge.target === target)
  if (!exists) {
    designerEdges.value.push({
      id: `${source}__${target}`,
      source,
      target,
      label: '',
      runtime_applied: false,
    })
  }
  linkSourceNodeId.value = ''
  selectedDesignerNodeId.value = target
  designerMessage.value = exists ? '这条链路已经存在。' : '已建立新的 Agent 链路。'
}

function startDesignerLink(node: AgentDesignerNode | null) {
  if (!node) return
  linkSourceNodeId.value = node.id
  selectedDesignerNodeId.value = node.id
  designerMessage.value = `请选择 ${node.label} 的下一个 Agent。`
}

function removeDesignerEdge(edgeId: string) {
  designerEdges.value = designerEdges.value.filter((edge) => edge.id !== edgeId)
}

function removeSelectedDesignerNode() {
  const node = selectedDesignerNode.value
  if (!node) return
  if (isDesignerNodeRequired(node)) {
    designerMessage.value = '这个节点是 Runtime 安全链路必需节点，不能从编排中删除。'
    return
  }
  designerNodes.value = designerNodes.value.filter((item) => item.id !== node.id)
  designerEdges.value = designerEdges.value.filter((edge) => edge.source !== node.id && edge.target !== node.id)
  selectedDesignerNodeId.value = designerNodes.value[0]?.id || ''
  linkSourceNodeId.value = linkSourceNodeId.value === node.id ? '' : linkSourceNodeId.value
}

function resetDesignerDraft() {
  if (!overview.value) return
  designerNodes.value = overview.value.orchestration.nodes.map((node, index) => ({
    id: node.id,
    node_type: node.node_type || node.id,
    module_id: node.module_id,
    label: node.label,
    phase: node.phase,
    x: 56 + (index % 4) * 220,
    y: 56 + Math.floor(index / 4) * 144,
    enabled: true,
    config: {},
    runtime_applied: false,
  }))
  designerEdges.value = overview.value.orchestration.edges.map((edge) => ({
    id: `${edge.from}__${edge.to}`,
    source: edge.from,
    target: edge.to,
    label: edge.label,
    runtime_applied: false,
  }))
  selectedDesignerNodeId.value = designerNodes.value[0]?.id || ''
  linkSourceNodeId.value = ''
  designerMessage.value = '已恢复为当前 AutoGPT 默认编排图，保存后会覆盖草稿。'
}

async function saveDesignerDraft(applyToRuntime = false) {
  designerSaving.value = true
  designerApplying.value = applyToRuntime
  designerMessage.value = ''
  try {
    const res = await saveAgentDesigner({
      nodes: designerNodes.value,
      edges: designerEdges.value,
      note: designerNote.value,
      apply_to_runtime: applyToRuntime,
    })
    designer.value = res.designer
    designerNodes.value = res.designer.draft.nodes.map((node) => ({
      ...node,
      node_type: node.node_type || node.id,
      config: { ...(node.config || {}) },
    }))
    designerEdges.value = res.designer.draft.edges.map((edge) => ({ ...edge }))
    designerNote.value = res.designer.draft.note || ''
    designerMessage.value = res.message
  } catch (error) {
    const err = error as { response?: { data?: { detail?: string } } }
    designerMessage.value = err.response?.data?.detail || '保存失败，请检查节点和连线是否合法。'
  } finally {
    designerSaving.value = false
    designerApplying.value = false
  }
}

function isDesignerNodeRequired(node: AgentDesignerNode | null) {
  if (!node) return false
  const paletteItem = designerPalette.value.find((item) => item.node_type === node.node_type || item.id === node.node_type)
  return Boolean(paletteItem?.required || paletteItem?.allow_disable === false)
}

function toggleSelectedDesignerNode() {
  const node = selectedDesignerNode.value
  if (!node || isDesignerNodeRequired(node)) return
  node.enabled = !node.enabled
  designerMessage.value = node.enabled ? `${node.label} 已启用。` : `${node.label} 已停用，热更新后不会进入运行时节点顺序。`
}

function fieldOptions(field: AgentConfigField) {
  return (field.options || []).map((option) => ({
    label: option.label,
    value: option.value,
  }))
}

function selectedConfigValue(key: string) {
  const value = selectedDesignerNode.value?.config?.[key]
  return typeof value === 'number' ? value : String(value ?? '')
}

function setSelectedNodeConfig(key: string, value: string | number) {
  const node = selectedDesignerNode.value
  if (!node) return
  if (value === '') {
    delete node.config[key]
    return
  }
  node.config[key] = value
}

function setSelectedNumberConfig(field: AgentConfigField, event: Event) {
  const raw = (event.target as HTMLInputElement).value
  if (raw === '') {
    setSelectedNodeConfig(field.key, '')
    return
  }
  const value = Number(raw)
  if (Number.isFinite(value)) {
    setSelectedNodeConfig(field.key, value)
  }
}

function setSelectedNodeLabel(event: Event) {
  const node = selectedDesignerNode.value
  if (!node) return
  node.label = (event.target as HTMLInputElement).value
}

function setSegment(segment: SegmentKey) {
  activeSegment.value = segment
  page.value = 1
  if (isCheckpointSegment.value) search.value = ''
  fetchData()
}

function onSearch() {
  if (isCheckpointSegment.value) return
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    page.value = 1
    fetchData()
  }, 300)
}

async function fetchData() {
  try {
    if (isCheckpointSegment.value) {
      const res = await fetchAgentCheckpoints({
        status: activeSegment.value === 'pending' ? 'needs_confirm' : undefined,
        page: page.value,
        page_size: pageSize,
      })
      items.value = res.items
      total.value = res.total
      if (activeSegment.value === 'pending') pendingCount.value = res.total
      return
    }

    const statusMap: Record<SegmentKey, string | undefined> = {
      runs: undefined,
      checkpoints: undefined,
      pending: 'needs_confirm',
      failed: 'failed',
    }
    const res = await fetchAgentRuns({
      status: statusMap[activeSegment.value],
      kind: activeSegment.value === 'runs' ? kindFilter.value || undefined : undefined,
      q: search.value || undefined,
      page: page.value,
      page_size: pageSize,
    })
    items.value = res.items
    total.value = res.total
  } catch {
    items.value = []
    total.value = 0
  }
}

async function selectItem(item: RecordItem) {
  selectedItem.value = item
  selectedItemIsCheckpoint.value = isCheckpointSegment.value
  detailData.value = null
  detailLoading.value = true
  try {
    detailData.value = selectedItemIsCheckpoint.value
      ? await fetchAgentCheckpoint(item.user_id)
      : await fetchAgentRun(item.trace_id)
  } catch {
    detailData.value = null
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  selectedItem.value = null
  detailData.value = null
}

function copyTraceId(item: RecordItem) {
  if (item.trace_id) navigator.clipboard?.writeText(item.trace_id)
}

function normalize(value: string | null | undefined) {
  return (value || '').trim().toLowerCase()
}

function kindLabel(value: string | null | undefined) {
  const labels: Record<string, string> = {
    chat: '聊天',
    command: '命令',
    command_sequence: '命令序列',
    knowledge: '知识检索',
    clarification: '待澄清',
    violation: '违规拦截',
  }
  return labels[value || ''] || value || '-'
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    planned: '已规划',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    needs_confirm: '待确认',
    cancelled: '已取消',
  }
  return labels[value] || value
}

function buildPieOption(data: Record<string, number>, labeler: (value: string) => string) {
  const entries = Object.entries(data)
  return {
    color: isDark.value ? ['#4da394', '#38bdf8', '#fbbf24', '#f87171', '#a78bfa'] : ['#28645a', '#0ea5e9', '#d97706', '#dc2626', '#7c3aed'],
    tooltip: { trigger: 'item' },
    legend: {
      bottom: 0,
      icon: 'circle',
      textStyle: { color: isDark.value ? '#a1a1aa' : '#475569', fontSize: 11 },
    },
    series: [
      {
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['50%', '42%'],
        avoidLabelOverlap: true,
        label: { show: false },
        data: entries.map(([name, value]) => ({ name: labeler(name), value })),
      },
    ],
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
    return value as Record<string, unknown>
  }
  return null
}

function asRecordArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.map((item) => asRecord(item)).filter((item): item is Record<string, unknown> => item !== null)
    : []
}

function readField(record: Record<string, unknown>, key: string) {
  const value = record[key]
  if (Array.isArray(value)) return value.map((item) => String(item)).join('、')
  if (typeof value === 'object' && value !== null) return ''
  return value === null || value === undefined ? '' : String(value)
}

function formatJson(value: unknown) {
  if (value === null || value === undefined || value === '') return '{}'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function formatTime(value: string | null | undefined) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString()
}
</script>

<style scoped>
.module-row {
  margin-bottom: 0.25rem;
  width: 100%;
  border-radius: 0.75rem;
  border-width: 1px;
  padding: 0.75rem;
  text-align: left;
  transition: background-color 160ms ease, border-color 160ms ease, color 160ms ease;
}

.designer-canvas {
  background-image:
    linear-gradient(rgba(40, 100, 90, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(40, 100, 90, 0.08) 1px, transparent 1px);
  background-size: 28px 28px;
}

.designer-node {
  cursor: grab;
  user-select: none;
}

.designer-node:active {
  cursor: grabbing;
}

:global(.dark) .designer-canvas {
  background-image:
    linear-gradient(rgba(77, 163, 148, 0.12) 1px, transparent 1px),
    linear-gradient(90deg, rgba(77, 163, 148, 0.12) 1px, transparent 1px);
}
</style>
