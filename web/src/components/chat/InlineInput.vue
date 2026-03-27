<template>
  <div class="mt-1.5 mb-1 px-2 py-2 rounded-lg bg-amber-50 border border-amber-200">
    <div class="text-xs text-gray-700 mb-2">{{ request.prompt }}</div>

    <!-- 按钮选择模式 -->
    <div v-if="request.inputType === 'select' && request.options.length" class="flex flex-wrap gap-1.5">
      <button
        v-for="opt in request.options"
        :key="opt.value"
        class="px-3 py-1.5 text-xs rounded-full border transition-colors
               bg-white border-gray-200 text-gray-700
               hover:bg-blue-50 hover:border-blue-300 hover:text-blue-700
               active:bg-blue-100"
        @click="$emit('submit', request, opt.value)"
      >{{ opt.label }}</button>
    </div>

    <!-- 文字输入模式 -->
    <div v-else class="flex gap-1.5">
      <input
        v-model="textValue"
        type="text"
        class="flex-1 px-2.5 py-1.5 text-xs rounded-lg border border-gray-200
               focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-200"
        :placeholder="request.prompt"
        @keyup.enter="submitText"
      />
      <button
        class="px-3 py-1.5 text-xs rounded-lg bg-blue-600 text-white
               hover:bg-blue-700 active:bg-blue-800 transition-colors
               disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="!textValue.trim()"
        @click="submitText"
      >确定</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { InputRequest } from '../../types'

const props = defineProps<{ request: InputRequest }>()
const emit = defineEmits<{ submit: [request: InputRequest, value: string] }>()

const textValue = ref('')

function submitText() {
  const v = textValue.value.trim()
  if (!v) return
  emit('submit', props.request, v)
}
</script>
