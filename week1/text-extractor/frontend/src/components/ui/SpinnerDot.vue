<script lang="ts">
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'SpinnerDot',
  props: {
    size: { type: Number, default: 16 },
  },
})
</script>

<template>
  <span
    class="spinner"
    :style="{ width: `${size}px`, height: `${size}px`, borderWidth: `${Math.max(1.5, size / 9)}px` }"
    role="status"
    aria-label="Loading"
  />
</template>

<style scoped>
.spinner {
  display: inline-block;
  border-style: solid;
  border-color: currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: spin 620ms linear infinite;
  opacity: 0.8;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
