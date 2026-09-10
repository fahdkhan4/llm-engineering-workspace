<script lang="ts">
import { defineComponent } from 'vue'

import AppIcon from './AppIcon.vue'

const ICONS: Record<string, string> = {
  info: 'info',
  warning: 'alert',
  danger: 'alert',
  accent: 'sparkle',
}

export default defineComponent({
  name: 'AlertPanel',
  components: { AppIcon },
  props: {
    tone: { type: String, default: 'info' },
    title: { type: String, default: '' },
    icon: { type: String, default: '' },
  },
  computed: {
    iconName(): string {
      return this.icon || ICONS[this.tone] || 'info'
    },
  },
})
</script>

<template>
  <div class="alert" :class="`tone-${tone}`" role="status">
    <AppIcon :name="iconName" :size="17" class="alert-icon" />
    <div class="alert-body">
      <p v-if="title" class="alert-title">{{ title }}</p>
      <div class="alert-text"><slot /></div>
      <div v-if="$slots.actions" class="alert-actions"><slot name="actions" /></div>
    </div>
    <slot name="trailing" />
  </div>
</template>

<style scoped>
.alert {
  display: flex;
  gap: 11px;
  padding: 13px 15px;
  border-radius: var(--radius-md);
  border: 1px solid;
  font-size: 13px;
  line-height: 1.55;
}

.alert-icon {
  margin-top: 1px;
}

.alert-body {
  flex: 1;
  min-width: 0;
}

.alert-title {
  font-weight: 600;
  margin-bottom: 2px;
}

.alert-text {
  color: inherit;
  opacity: 0.92;
}

.alert-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.tone-info {
  background: var(--blue-50);
  border-color: var(--blue-100);
  color: var(--blue-700);
}

.tone-warning {
  background: var(--amber-50);
  border-color: var(--amber-100);
  color: var(--amber-700);
}

.tone-danger {
  background: var(--red-50);
  border-color: var(--red-100);
  color: var(--red-700);
}

.tone-accent {
  background: var(--accent-soft);
  border-color: var(--accent-soft-border);
  color: var(--accent);
}

.tone-neutral {
  background: var(--bg-subtle);
  border-color: var(--border);
  color: var(--text-secondary);
}
</style>
