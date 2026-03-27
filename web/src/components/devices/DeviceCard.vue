<template>
  <div
    class="rounded-lg border bg-white p-4 cursor-pointer transition hover:shadow-sm"
    :class="device.status === 'online' ? 'border-green-200' : 'border-gray-200'"
    @click="$emit('select', device)"
  >
    <div class="flex items-center gap-3">
      <span
        class="w-3 h-3 rounded-full shrink-0"
        :class="device.status === 'online' ? 'bg-green-500' : 'bg-gray-300'"
      />
      <div class="flex-1 min-w-0">
        <div class="font-medium text-sm text-gray-900 truncate">{{ device.name }}</div>
        <div class="text-xs text-gray-500">{{ device.device_type }}</div>
      </div>
      <div class="text-xs text-gray-400">
        {{ formatTime(device.last_heartbeat) }}
      </div>
    </div>
    <div v-if="expanded" class="mt-3 pt-3 border-t border-gray-100 text-xs space-y-1">
      <div class="text-gray-500">ID: <span class="text-gray-700 font-mono">{{ device.device_id }}</span></div>
      <div v-if="device.capabilities.length" class="flex flex-wrap gap-1 mt-1">
        <span
          v-for="cap in device.capabilities"
          :key="cap"
          class="px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full"
        >
          {{ cap }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Device } from '../../types'

defineProps<{ device: Device; expanded?: boolean }>()
defineEmits<{ select: [device: Device] }>()

function formatTime(iso: string): string {
  if (!iso) return ''
  try {
    return new Date(iso).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  } catch {
    return ''
  }
}
</script>
