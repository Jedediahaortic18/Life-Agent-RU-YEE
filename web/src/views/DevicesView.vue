<template>
  <div class="flex flex-col h-full">
    <!-- Banner -->
    <div
      v-if="!connected"
      class="mx-4 mt-2 px-4 py-2 bg-yellow-50 border border-yellow-200 rounded-lg text-sm text-yellow-700 flex items-center gap-2"
    >
      连接中断，正在重连...
    </div>

    <!-- Info -->
    <div class="px-4 pt-4 pb-2">
      <p class="text-xs text-gray-500">
        设备网关 Demo — 展示框架的 WebSocket 实时双向通信能力
      </p>
      <div class="mt-2 text-sm text-gray-700">
        已连接: <span class="font-semibold">{{ devices.filter(d => d.status === 'online').length }}</span>
        / {{ devices.length }} 台设备
      </div>
    </div>

    <!-- Device list -->
    <div class="flex-1 overflow-y-auto px-4 pb-2 space-y-2">
      <div v-if="devices.length === 0" class="flex flex-col items-center justify-center h-40 text-gray-400 text-sm">
        <p class="mb-2">暂无设备连接</p>
      </div>
      <DeviceCard
        v-for="d in devices"
        :key="d.device_id"
        :device="d"
        :expanded="selectedId === d.device_id"
        @select="selectedId = selectedId === d.device_id ? null : d.device_id"
      />
    </div>

    <!-- Send panel -->
    <div class="border-t border-gray-200 bg-white px-4 py-3 space-y-2">
      <select
        v-model="targetDevice"
        class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
      >
        <option value="">选择目标设备</option>
        <option
          v-for="d in devices.filter(d => d.status === 'online')"
          :key="d.device_id"
          :value="d.device_id"
        >
          {{ d.name }}
        </option>
      </select>
      <form class="flex gap-2" @submit.prevent="handleSend">
        <input
          v-model="commandInput"
          type="text"
          placeholder="输入命令..."
          class="flex-1 rounded-full border border-gray-300 px-4 py-2.5 text-sm focus:outline-none focus:border-blue-500"
          :disabled="!targetDevice"
        />
        <button
          type="submit"
          class="shrink-0 w-10 h-10 rounded-full bg-blue-600 text-white flex items-center justify-center disabled:opacity-40"
          :disabled="!targetDevice || !commandInput.trim()"
        >
          <span class="text-lg">&#x2191;</span>
        </button>
      </form>
    </div>

    <!-- Messages -->
    <div v-if="deviceMessages.length" class="border-t border-gray-100 px-4 py-2 max-h-32 overflow-y-auto">
      <div class="text-xs text-gray-500 mb-1">消息记录</div>
      <div
        v-for="(m, i) in deviceMessages.slice(-10)"
        :key="i"
        class="text-xs text-gray-600 py-0.5"
      >
        [{{ m.type }}] {{ JSON.stringify(m.payload).slice(0, 80) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useWebSocket } from '../composables/useWebSocket'
import DeviceCard from '../components/devices/DeviceCard.vue'

const { devices, connected, deviceMessages, sendCommand } = useWebSocket()

const selectedId = ref<string | null>(null)
const targetDevice = ref('')
const commandInput = ref('')

function handleSend() {
  if (!targetDevice.value || !commandInput.value.trim()) return
  sendCommand(targetDevice.value, 'query', commandInput.value)
  commandInput.value = ''
}
</script>
