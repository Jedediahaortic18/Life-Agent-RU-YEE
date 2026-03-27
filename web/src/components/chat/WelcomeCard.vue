<template>
  <div class="flex flex-col items-center justify-center py-8 px-4">
    <!-- 头像 + 问候 -->
    <div class="text-4xl mb-3">{{ config.agent_avatar }}</div>
    <div class="text-lg font-medium text-gray-800 mb-1">{{ greeting }}{{ t('welcome.serviceFor', { name: config.agent_name }) }}</div>
    <div class="text-sm text-gray-500 mb-6 text-center max-w-xs">{{ config.agent_intro }}</div>

    <!-- 推荐问题 -->
    <div class="w-full max-w-sm space-y-2">
      <div class="text-xs text-gray-400 mb-1.5">{{ t('welcome.trySaying') }}</div>
      <button
        v-for="q in config.suggested_questions"
        :key="q"
        class="w-full text-left px-4 py-2.5 rounded-xl border border-gray-200 bg-white text-sm text-gray-700 hover:border-blue-300 hover:bg-blue-50 transition-colors"
        @click="$emit('ask', q)"
      >
        {{ q }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import type { OpeningConfig } from '../../api/chat'

defineProps<{ config: OpeningConfig }>()
defineEmits<{ ask: [question: string] }>()

const { t } = useI18n()

const greeting = computed(() => {
  const h = new Date().getHours()
  if (h >= 5 && h < 11) return t('welcome.greeting.morning')
  if (h >= 11 && h < 14) return t('welcome.greeting.noon')
  if (h >= 14 && h < 18) return t('welcome.greeting.afternoon')
  return t('welcome.greeting.evening')
})
</script>
