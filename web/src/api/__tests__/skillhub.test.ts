import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  fetchRegistry,
  fetchInstalled,
  searchPlugins,
  installPlugin,
  uninstallPlugin,
} from '../skillhub'

const mockFetch = vi.fn()
vi.stubGlobal('fetch', mockFetch)

beforeEach(() => {
  mockFetch.mockReset()
})

describe('skillhub API', () => {
  it('fetchRegistry returns index data', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: { version: 1, plugins: [{ name: 'test', version: '1.0.0' }] },
      }),
    })

    const result = await fetchRegistry()
    expect(result.version).toBe(1)
    expect(result.plugins).toHaveLength(1)
    expect(mockFetch).toHaveBeenCalledWith('/api/skillhub/registry')
  })

  it('fetchInstalled returns plugin list', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: [{ name: 'meal_agent', source: 'builtin' }],
      }),
    })

    const result = await fetchInstalled()
    expect(result).toHaveLength(1)
    expect(result[0].source).toBe('builtin')
  })

  it('searchPlugins passes query params', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: true, data: [] }),
    })

    await searchPlugins({ q: '健身', tags: '运动,健康', type: 'agent' })
    const url = mockFetch.mock.calls[0][0] as string
    expect(url).toContain('q=%E5%81%A5%E8%BA%AB')
    expect(url).toContain('tags=%E8%BF%90%E5%8A%A8')
    expect(url).toContain('type=agent')
  })

  it('installPlugin sends POST with name', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: { status: 'installed', version: '1.0.0' },
      }),
    })

    const result = await installPlugin('fitness_agent')
    expect(result.status).toBe('installed')
    expect(mockFetch).toHaveBeenCalledWith('/api/skillhub/install', expect.objectContaining({
      method: 'POST',
    }))
  })

  it('uninstallPlugin sends DELETE', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        success: true,
        data: { status: 'uninstalled' },
      }),
    })

    const result = await uninstallPlugin('fitness_agent')
    expect(result.status).toBe('uninstalled')
    expect(mockFetch).toHaveBeenCalledWith(
      '/api/skillhub/uninstall/fitness_agent',
      expect.objectContaining({ method: 'DELETE' }),
    )
  })

  it('throws on API error', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ success: false, error: 'not found' }),
    })

    await expect(fetchRegistry()).rejects.toThrow('not found')
  })
})
