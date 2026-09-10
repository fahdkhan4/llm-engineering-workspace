<script lang="ts">
import { defineComponent } from 'vue'
import { mapState } from 'pinia'

import AlertPanel from '@/components/ui/AlertPanel.vue'
import { useHealthStore } from '@/stores/health'

import AppSidebar from './AppSidebar.vue'
import AppTopbar from './AppTopbar.vue'

export default defineComponent({
  name: 'AppShell',
  components: { AlertPanel, AppSidebar, AppTopbar },
  data() {
    return {
      sidebarOpen: false,
    }
  },
  computed: {
    ...mapState(useHealthStore, ['isOffline']),
  },
  watch: {
    $route() {
      this.sidebarOpen = false
    },
  },
  methods: {
    retryConnection() {
      void useHealthStore().refresh()
    },
  },
})
</script>

<template>
  <div class="shell">
    <div class="sidebar-slot" :class="{ open: sidebarOpen }">
      <AppSidebar @navigate="sidebarOpen = false" />
    </div>
    <div v-if="sidebarOpen" class="scrim" @click="sidebarOpen = false" />

    <div class="main">
      <AppTopbar @toggle-sidebar="sidebarOpen = !sidebarOpen" />

      <div v-if="isOffline" class="offline-banner">
        <AlertPanel tone="danger" title="Backend unavailable">
          Uploads, questions and your library stay unavailable until it is reachable.
          <template #actions>
            <button class="btn btn-sm btn-secondary" type="button" @click="retryConnection">
              Try again
            </button>
          </template>
        </AlertPanel>
      </div>

      <main class="content">
        <RouterView v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <component :is="Component" />
          </Transition>
        </RouterView>
      </main>
    </div>
  </div>
</template>

<style scoped>
.shell {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.sidebar-slot {
  flex-shrink: 0;
  height: 100%;
}

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.content {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  background: var(--bg-canvas);
  background-attachment: local;
}

.offline-banner {
  padding: 12px 20px 0;
}

.scrim {
  display: none;
}

.fade-enter-active {
  transition: opacity 200ms ease, transform 200ms cubic-bezier(0.22, 1, 0.36, 1);
}

.fade-leave-active {
  transition: opacity 110ms ease;
}

.fade-enter-from {
  opacity: 0;
  transform: translateY(6px);
}

.fade-leave-to {
  opacity: 0;
}

@media (max-width: 900px) {
  .sidebar-slot {
    position: fixed;
    inset: 0 auto 0 0;
    z-index: 60;
    transform: translateX(-100%);
    transition: transform 200ms cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: var(--shadow-xl);
  }

  .sidebar-slot.open {
    transform: translateX(0);
  }

  .scrim {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 50;
    background: rgba(12, 17, 27, 0.45);
  }
}
</style>
