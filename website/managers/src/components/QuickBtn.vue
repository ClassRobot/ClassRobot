<template>
  <router-link
    v-if="to"
    :to="to"
    class="flex items-center gap-2.5 rounded-lg px-4 py-2.5 border border-outline-variant dark:border-zinc-700 bg-surface-container dark:bg-zinc-800 text-on-surface dark:text-zinc-200 font-body-sm text-body-sm hover:bg-surface-container-high dark:hover:bg-zinc-700 transition-colors"
  >
    <component :is="iconComponent" :size="18" />
    <span>{{ label }}</span>
  </router-link>
  <button
    v-else
    @click="$emit('click')"
    class="flex items-center gap-2.5 rounded-lg px-4 py-2.5 border border-outline-variant dark:border-zinc-700 bg-surface-container dark:bg-zinc-800 text-on-surface dark:text-zinc-200 font-body-sm text-body-sm hover:bg-surface-container-high dark:hover:bg-zinc-700 transition-colors"
    :class="fullWidth ? 'justify-center' : ''"
  >
    <component :is="iconComponent" :size="fullWidth ? 16 : 18" />
    <span>{{ label }}</span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import * as icons from 'lucide-vue-next'

const props = defineProps<{
  icon: string
  label: string
  to?: string
  fullWidth?: boolean
}>()

defineEmits<{ click: [] }>()

const iconComponent = computed(() => {
  return (icons as Record<string, unknown>)[props.icon] || icons.Box
})
</script>
