<script lang="ts">
import { defineComponent } from 'vue'

import AppIcon from './AppIcon.vue'

/** A single headline number. Used on the overview and above the library table. */
export default defineComponent({
  name: 'StatTile',
  components: { AppIcon },
  props: {
    label: { type: String, required: true },
    value: { type: String, required: true },
    caption: { type: String, default: '' },
    icon: { type: String, default: 'library' },
    /** brand · green · blue · violet · neutral */
    tone: { type: String, default: 'neutral' },
    compact: { type: Boolean, default: false },
    /** Shows a placeholder instead of a misleading zero while loading. */
    loading: { type: Boolean, default: false },
  },
})
</script>

<template>
  <div class="tile" :class="[`tone-${tone}`, { compact }]">
    <span class="tile-icon">
      <AppIcon :name="icon" :size="compact ? 14 : 15" />
    </span>
    <p class="tile-label">{{ label }}</p>
    <p class="tile-value" :class="{ pending: loading }">{{ loading ? '—' : value }}</p>
    <p v-if="caption && !compact" class="tile-caption">{{ caption }}</p>
  </div>
</template>

<style scoped>
.tile {
  padding: 16px 17px 17px;
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}

.tile.compact {
  padding: 13px 14px 14px;
  border-radius: var(--radius-md);
  box-shadow: none;
}

.tile-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--bg-muted);
  color: var(--text-tertiary);
}

.compact .tile-icon {
  width: 26px;
  height: 26px;
  border-radius: 7px;
}

.tone-brand .tile-icon { background: var(--accent-soft); color: var(--accent); }
.tone-green .tile-icon { background: var(--green-50); color: var(--green-700); }
.tone-blue .tile-icon { background: var(--blue-50); color: var(--blue-700); }
.tone-violet .tile-icon { background: var(--accent-soft); color: var(--violet-600); }

[data-theme='dark'] .tone-violet .tile-icon { color: var(--violet-400); }

.tile-label {
  margin-top: 13px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.compact .tile-label {
  margin-top: 10px;
  font-size: 11.5px;
}

.tile-value {
  margin-top: 3px;
  font-size: 26px;
  font-weight: 650;
  letter-spacing: -0.03em;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.compact .tile-value {
  font-size: 20px;
}

.tile-value.pending {
  color: var(--text-tertiary);
}

.tile-caption {
  margin-top: 3px;
  font-size: 11.5px;
  color: var(--text-tertiary);
}
</style>
