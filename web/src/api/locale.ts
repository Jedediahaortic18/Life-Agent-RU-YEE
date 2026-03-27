import { i18n } from '../i18n'

/** 返回当前 locale 对应的 Accept-Language header */
export function localeHeaders(): Record<string, string> {
  return { 'Accept-Language': i18n.global.locale.value }
}
