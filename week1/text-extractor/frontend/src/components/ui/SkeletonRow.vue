<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'SkeletonRow',
  props: {
    width: { type: String, default: '100%' },
    height: { type: Number, default: 12 },
  },
})
</script>

<template>
  <span class="skeleton" :style="{ width, height: `${height}px` }" />
</template>

<style scoped>
.skeleton {
  display: block;
  border-radius: 4px;
  background: linear-gradient(
    90deg,
    var(--bg-muted) 25%,
    var(--bg-hover) 37%,
    var(--bg-muted) 63%
  );
  background-size: 400% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

@keyframes shimmer {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}
</style>
