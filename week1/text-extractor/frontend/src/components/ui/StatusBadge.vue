<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import type { DocumentStatus } from '@/types/api'

const TONES: Record<DocumentStatus, string> = {
  pending: 'badge-neutral',
  processing: 'badge-info',
  completed: 'badge-success',
  failed: 'badge-danger',
}

const LABELS: Record<DocumentStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  completed: 'Completed',
  failed: 'Failed',
}

export default defineComponent({
  name: 'StatusBadge',
  props: {
    status: { type: String as PropType<DocumentStatus>, required: true },
  },
  computed: {
    toneClass(): string {
      return TONES[this.status] ?? 'badge-neutral'
    },
    label(): string {
      return LABELS[this.status] ?? this.status
    },
    isActive(): boolean {
      return this.status === 'processing' || this.status === 'pending'
    },
  },
})
</script>

<template>
  <span class="badge" :class="toneClass">
    <span class="dot" :class="{ pulse: isActive }" />
    {{ label }}
  </span>
</template>

<style scoped>
.dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: currentColor;
}

.dot.pulse {
  animation: pulse 1.4s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
</style>
