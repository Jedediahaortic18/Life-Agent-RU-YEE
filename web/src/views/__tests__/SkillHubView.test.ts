import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import SkillHubView from '../SkillHubView.vue'

// Mock API
vi.mock('../../api/skillhub', () => ({
  fetchInstalled: vi.fn().mockResolvedValue([
    { name: 'meal_agent', version: '0.1.0', type: 'agent', status: 'loaded', source: 'builtin' },
  ]),
  fetchRegistry: vi.fn().mockResolvedValue({
    version: 1,
    plugins: [
      { name: 'fitness_agent', version: '1.0.0', type: 'agent', description: 'AI 健身', author: 'test', tags: ['健身'], verified: true },
    ],
  }),
  searchPlugins: vi.fn().mockResolvedValue([]),
  installPlugin: vi.fn().mockResolvedValue({ status: 'installed', version: '1.0.0' }),
  uninstallPlugin: vi.fn().mockResolvedValue({ status: 'uninstalled' }),
}))

describe('SkillHubView', () => {
  it('renders installed tab', () => {
    const wrapper = mount(SkillHubView)
    const tabs = wrapper.findAll('[data-testid="tab"]')
    expect(tabs).toHaveLength(1)
    expect(tabs[0].text()).toContain('已加载')
  })

  it('shows installed tab by default', async () => {
    const wrapper = mount(SkillHubView)
    await flushPromises()
    expect(wrapper.find('[data-testid="installed-panel"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="market-panel"]').exists()).toBe(false)
  })

  it('loads installed plugins on mount', async () => {
    const { fetchInstalled } = await import('../../api/skillhub')
    mount(SkillHubView)
    await flushPromises()
    expect(fetchInstalled).toHaveBeenCalled()
  })
})
