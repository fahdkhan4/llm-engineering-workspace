<script lang="ts">
import { defineComponent } from 'vue'

import AppShell from '@/components/layout/AppShell.vue'
import ToastHost from '@/components/ui/ToastHost.vue'
import { useChatStore } from '@/stores/chat'
import { useHealthStore } from '@/stores/health'

export default defineComponent({
  name: 'App',
  components: { AppShell, ToastHost },
  created() {
    useHealthStore().startPolling()
    useChatStore().restore()
  },
  beforeUnmount() {
    useHealthStore().stopPolling()
  },
})
</script>

<template>
  <AppShell />
  <ToastHost />
</template>
