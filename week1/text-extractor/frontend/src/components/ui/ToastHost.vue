<script lang="ts">
import { defineComponent } from 'vue'
import { mapState } from 'pinia'

import { useToastStore } from '@/stores/toasts'

import AppIcon from './AppIcon.vue'

export default defineComponent({
  name: 'ToastHost',
  components: { AppIcon },
  computed: {
    ...mapState(useToastStore, ['items']),
  },
  methods: {
    iconFor(tone: string): string {
      if (tone === 'success') return 'check'
      if (tone === 'error') return 'alert'
      return 'info'
    },
    dismiss(id: number) {
      useToastStore().dismiss(id)
    },
  },
})
</script>

<template>
  <div class="toast-host" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="toast in items" :key="toast.id" class="toast" :class="`tone-${toast.tone}`">
        <AppIcon :name="iconFor(toast.tone)" :size="16" class="toast-icon" />
        <div class="toast-body">
          <p class="toast-title">{{ toast.title }}</p>
          <p v-if="toast.description" class="toast-description">{{ toast.description }}</p>
        </div>
        <button class="toast-close" type="button" aria-label="Dismiss" @click="dismiss(toast.id)">
          <AppIcon name="close" :size="14" />
        </button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.toast-host {
  position: fixed;
  right: 20px;
  bottom: 20px;
  z-index: 100;
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: min(380px, calc(100vw - 40px));
  pointer-events: none;
}

.toast {
  display: flex;
  gap: 11px;
  padding: 12px 14px;
  background: var(--bg-raised);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
  pointer-events: auto;
}

.toast-icon {
  margin-top: 2px;
}

.tone-success .toast-icon { color: var(--green-600); }
.tone-error .toast-icon { color: var(--red-600); }
.tone-info .toast-icon { color: var(--accent); }

.toast-body {
  flex: 1;
  min-width: 0;
}

.toast-title {
  font-size: 13.5px;
  font-weight: 500;
}

.toast-description {
  margin-top: 2px;
  font-size: 12.5px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.toast-close {
  color: var(--text-tertiary);
  padding: 2px;
  height: fit-content;
  border-radius: 4px;
}

.toast-close:hover {
  color: var(--text-primary);
  background: var(--bg-muted);
}

.toast-enter-active,
.toast-leave-active {
  transition: all 220ms cubic-bezier(0.4, 0, 0.2, 1);
}

.toast-enter-from {
  opacity: 0;
  transform: translateX(16px);
}

.toast-leave-to {
  opacity: 0;
  transform: scale(0.96);
}
</style>
