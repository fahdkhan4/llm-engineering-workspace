<script lang="ts">
import { defineComponent, type PropType } from 'vue'

import AppIcon from '@/components/ui/AppIcon.vue'

import { PIPELINE_STEPS, type PipelineStepKey } from './pipeline'

/**
 * Compact four-stage strip. Everything before `active` reads as done, so the
 * page can show where a document currently is without a second explanation.
 */
export default defineComponent({
  name: 'WorkflowRail',
  components: { AppIcon },
  props: {
    /** Stage currently in progress; `null` leaves the rail purely explanatory. */
    active: { type: String as PropType<PipelineStepKey | null>, default: null },
    /** Marks every stage complete — used once a batch has finished. */
    complete: { type: Boolean, default: false },
  },
  data() {
    return {
      steps: PIPELINE_STEPS,
    }
  },
  computed: {
    activeIndex(): number {
      if (this.complete) return this.steps.length
      if (!this.active) return -1
      return this.steps.findIndex((step) => step.key === this.active)
    },
  },
  methods: {
    stateOf(index: number): 'done' | 'current' | 'todo' {
      if (this.activeIndex < 0) return 'todo'
      if (index < this.activeIndex) return 'done'
      return index === this.activeIndex ? 'current' : 'todo'
    },
  },
})
</script>

<template>
  <ol class="rail" :class="{ idle: activeIndex < 0 }" aria-label="Document pipeline">
    <li
      v-for="(step, index) in steps"
      :key="step.key"
      class="step"
      :class="stateOf(index)"
      :aria-current="stateOf(index) === 'current' ? 'step' : undefined"
    >
      <span class="node">
        <AppIcon
          :name="stateOf(index) === 'done' ? 'check' : step.icon"
          :size="14"
          :stroke-width="1.9"
        />
      </span>
      <span class="label">{{ step.label }}</span>
      <span v-if="index < steps.length - 1" class="connector" aria-hidden="true" />
    </li>
  </ol>
</template>

<style scoped>
.rail {
  display: flex;
  align-items: center;
  gap: 0;
  flex-wrap: wrap;
}

.step {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.node {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  flex-shrink: 0;
  border-radius: 50%;
  border: 1px solid var(--border);
  background: var(--bg-surface);
  color: var(--text-tertiary);
  transition: background var(--transition), border-color var(--transition),
    color var(--transition), box-shadow var(--transition);
}

.label {
  font-size: 12.5px;
  font-weight: 500;
  color: var(--text-tertiary);
  white-space: nowrap;
  transition: color var(--transition);
}

.connector {
  width: 34px;
  height: 1.5px;
  margin: 0 10px;
  border-radius: 999px;
  background: var(--border);
  transition: background var(--transition);
}

/* An idle rail is a description of the process, so nothing is dimmed. */
.rail.idle .label {
  color: var(--text-secondary);
}

.step.done .node {
  background: var(--green-50);
  border-color: var(--green-100);
  color: var(--green-700);
}

.step.done .label {
  color: var(--text-secondary);
}

.step.done .connector {
  background: var(--green-100);
}

.step.current .node {
  background: var(--brand-gradient);
  border-color: transparent;
  color: #fff;
  box-shadow: var(--brand-glow);
  animation: breathe 2s ease-in-out infinite;
}

.step.current .label {
  color: var(--text-primary);
  font-weight: 600;
}

@keyframes breathe {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.07); }
}

@media (max-width: 640px) {
  .connector {
    width: 16px;
    margin: 0 6px;
  }

  .label {
    font-size: 12px;
  }
}
</style>
