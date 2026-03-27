import { createI18n } from 'vue-i18n'
import zh from './locales/zh.json'
import en from './locales/en.json'

const LOCALE_KEY = 'lary_locale'

function getSavedLocale(): string {
  return localStorage.getItem(LOCALE_KEY) || 'zh'
}

export function saveLocale(locale: string): void {
  localStorage.setItem(LOCALE_KEY, locale)
}

export const i18n = createI18n({
  legacy: false,
  locale: getSavedLocale(),
  fallbackLocale: 'zh',
  messages: { zh, en },
})
