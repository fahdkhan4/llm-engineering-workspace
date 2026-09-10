<script lang="ts">
import { defineComponent } from 'vue'

import AppIcon from './AppIcon.vue'

export default defineComponent({
  name: 'EmptyState',
  components: { AppIcon },
  props: {
    icon: { type: String, default: 'file-text' },
    title: { type: String, required: true },
    description: { type: String, default: '' },
    tone: { type: String, default: 'neutral' },
    compact: { type: Boolean, default: false },
  },
})
</script>

<template>
  <div class="empty" :class="[`tone-${tone}`, { compact }]">
    <div class="glyph">
      <AppIcon :name="icon" :size="compact ? 18 : 22" />
    </div>
    <h3 class="title">{{ title }}</h3>
    <p v-if="description || $slots.description" class="description">
      <slot name="description">{{ description }}</slot>
    </p>
    <div v-if="$slots.actions" class="actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style scoped>
.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 56px 32px;
}

.empty.compact {
  padding: 32px 24px;
}

.glyph {
  display: grid;
  place-items: center;
  width: 46px;
  height: 46px;
  margin-bottom: 16px;
  border-radius: 12px;
  background: var(--bg-muted);
  border: 1px solid var(--border);
  color: var(--text-tertiary);
}

.compact .glyph {
  width: 38px;
  height: 38px;
  margin-bottom: 12px;
}

.tone-accent .glyph {
  background: var(--accent-soft);
  border-color: var(--accent-soft-border);
  color: var(--accent);
}

.tone-danger .glyph {
  background: var(--red-50);
  border-color: var(--red-100);
  color: var(--red-700);
}

.tone-warning .glyph {
  background: var(--amber-50);
  border-color: var(--amber-100);
  color: var(--amber-700);
}

.title {
  font-size: 15px;
  font-weight: 600;
}

.description {
  margin-top: 6px;
  max-width: 46ch;
  color: var(--text-secondary);
  font-size: 13.5px;
  line-height: 1.6;
}

.actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  flex-wrap: wrap;
  justify-content: center;
}
</style>
