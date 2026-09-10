<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import type { FileType } from '@/types/api'

export default defineComponent({
  name: 'FileTypeBadge',
  props: {
    fileType: { type: String as PropType<FileType>, required: true },
  },
})
</script>

<template>
  <span class="type-badge" :class="fileType">{{ fileType.toUpperCase() }}</span>
</template>

<style scoped>
.type-badge {
  display: inline-flex;
  align-items: center;
  height: 19px;
  padding: 0 6px;
  border-radius: 4px;
  font-family: var(--font-mono);
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.04em;
  border: 1px solid;
}

.pdf {
  background: var(--red-50);
  border-color: var(--red-100);
  color: var(--red-700);
}

.docx {
  background: var(--blue-50);
  border-color: var(--blue-100);
  color: var(--blue-700);
}
</style>
