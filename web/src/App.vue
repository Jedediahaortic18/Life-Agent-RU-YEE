<template>
  <div class="h-screen flex bg-gray-100">
    <!-- Desktop: centered card with shadow -->
    <div class="flex-1 flex flex-col w-full max-w-2xl mx-auto bg-gray-50 shadow-lg md:my-4 md:rounded-xl overflow-hidden">
      <AppHeader :title="pageTitle" :online="isOnline" />
      <router-view class="flex-1 overflow-hidden" />
      <BottomNav />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './components/AppHeader.vue'
import BottomNav from './components/BottomNav.vue'
import { checkHealth } from './api/health'

const route = useRoute()
const isOnline = ref(false)
let healthTimer: ReturnType<typeof setInterval> | null = null

const pageTitle = computed(() => {
  const titles: Record<string, string> = {
    '/': '如意助手',
    '/devices': '设备网关',
    '/skillhub': '扩展',
  }
  return titles[route.path] ?? 'Life-Agent-RU-YEE'
})

async function pollHealth() {
  isOnline.value = await checkHealth()
}

onMounted(() => {
  pollHealth()
  healthTimer = setInterval(pollHealth, 10_000)
})

onUnmounted(() => {
  if (healthTimer) clearInterval(healthTimer)
})
</script>
