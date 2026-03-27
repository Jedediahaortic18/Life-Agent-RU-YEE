<template>
  <header class="flex items-center justify-between px-4 py-3 bg-white border-b border-gray-200">
    <h1 class="text-lg font-semibold text-gray-900">{{ title }}</h1>
    <div class="flex items-center gap-3">
      <button
        class="text-xs px-2 py-1 rounded border border-gray-200 text-gray-500 hover:text-blue-600 hover:border-blue-300 transition-colors"
        @click="toggleLocale"
      >
        {{ locale === 'zh' ? 'EN' : '中' }}
      </button>
      <span
        class="inline-flex items-center gap-1.5 text-xs"
        :class="online ? 'text-green-600' : 'text-gray-400'"
      >
        <span class="w-2 h-2 rounded-full" :class="online ? 'bg-green-500' : 'bg-gray-300'" />
        {{ online ? t('app.status.online') : t('app.status.offline') }}
      </span>
    </div>
  </header>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { saveLocale } from '../i18n'

defineProps<{ title: string; online: boolean }>()

const { t, locale } = useI18n()

function toggleLocale() {
  const next = locale.value === 'zh' ? 'en' : 'zh'
  locale.value = next
  saveLocale(next)
}
</script>
