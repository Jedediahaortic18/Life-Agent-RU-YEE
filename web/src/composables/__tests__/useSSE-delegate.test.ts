import { describe, it, expect } from 'vitest'

describe('SSE delegate event handling', () => {
  it('agent_delegate sets thinking on assistant message', () => {
    const msg = {
      id: 'test-1',
      role: 'assistant' as const,
      content: '',
      timestamp: Date.now(),
      thinking: undefined as string | undefined,
    }

    const data = { source: 'meal_agent', target: 'fitness_agent', message: '查询运动量' }
    msg.thinking = `正在咨询 ${data.target}...`

    expect(msg.thinking).toBe('正在咨询 fitness_agent...')
  })

  it('agent_delegate_done clears thinking', () => {
    const msg = {
      id: 'test-1',
      role: 'assistant' as const,
      content: '',
      timestamp: Date.now(),
      thinking: '正在咨询 fitness_agent...' as string | undefined,
    }

    msg.thinking = undefined

    expect(msg.thinking).toBeUndefined()
  })
})
