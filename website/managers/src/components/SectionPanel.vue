<template>
  <section class="rounded-[28px] border border-white/70 bg-white/90 p-5 shadow-panel backdrop-blur">
    <div v-if="title || description" class="mb-4">
      <h2 v-if="title" class="text-lg font-semibold text-brand-ink">{{ title }}</h2>
      <p v-if="description" class="mt-1 text-sm text-slate-500">{{ description }}</p>
    </div>
    <slot />
  </section>
</template>

<script setup lang="ts">
defineProps<{
  title?: string;
  description?: string;
}>();
</script>
