<template>
  <article
    class="rounded-[24px] border border-white/70 bg-gradient-to-br p-5 text-white shadow-panel"
    :class="toneClass"
  >
    <p class="text-sm uppercase tracking-[0.22em] text-white/70">{{ label }}</p>
    <p class="mt-3 font-mono text-4xl font-semibold">{{ value }}</p>
    <p class="mt-4 text-sm leading-6 text-white/80">{{ description }}</p>
  </article>
</template>

<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    label: string;
    value: number | string;
    description: string;
    tone?: "ink" | "mint" | "amber" | "sea";
  }>(),
  {
    tone: "ink",
  },
);

const toneClass = computed(() => {
  return {
    ink: "from-brand-ink to-slate-900",
    mint: "from-brand-mint to-emerald-700",
    amber: "from-brand-amber to-orange-600",
    sea: "from-brand-sea to-cyan-800",
  }[props.tone];
});
</script>
