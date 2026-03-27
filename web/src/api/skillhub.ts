import type {
  RegistryIndex,
  RegistryPlugin,
  InstalledPlugin,
  InstallResult,
  UninstallResult,
} from '../types'

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  const json = await res.json()
  if (!json.success) throw new Error(json.error ?? 'Request failed')
  return json.data as T
}

export async function fetchRegistry(): Promise<RegistryIndex> {
  return request<RegistryIndex>('/api/skillhub/registry')
}

export async function fetchInstalled(): Promise<InstalledPlugin[]> {
  return request<InstalledPlugin[]>('/api/skillhub/installed')
}

export async function searchPlugins(params: {
  q?: string
  tags?: string
  type?: string
}): Promise<RegistryPlugin[]> {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.tags) qs.set('tags', params.tags)
  if (params.type) qs.set('type', params.type)
  return request<RegistryPlugin[]>(`/api/skillhub/search?${qs.toString()}`)
}

export async function installPlugin(name: string, version?: string): Promise<InstallResult> {
  return request<InstallResult>('/api/skillhub/install', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, version }),
  })
}

export async function uninstallPlugin(name: string): Promise<UninstallResult> {
  return request<UninstallResult>(`/api/skillhub/uninstall/${name}`, {
    method: 'DELETE',
  })
}
