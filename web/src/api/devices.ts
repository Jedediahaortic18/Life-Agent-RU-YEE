import type { MessageEnvelope } from '../types'

export function createDeviceSocket(
  onMessage: (envelope: MessageEnvelope) => void,
  onStateChange: (connected: boolean) => void
): { send: (msg: Partial<MessageEnvelope>) => void; close: () => void } {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  const url = `${protocol}//${location.host}/api/devices/ws`

  let ws: WebSocket | null = null
  let retries = 0
  const maxRetries = 5
  let closed = false

  function connect() {
    ws = new WebSocket(url)

    ws.onopen = () => {
      retries = 0
      onStateChange(true)
    }

    ws.onmessage = (e) => {
      try {
        const envelope = JSON.parse(e.data) as MessageEnvelope
        onMessage(envelope)
      } catch { /* ignore */ }
    }

    ws.onclose = () => {
      onStateChange(false)
      if (!closed && retries < maxRetries) {
        const delay = Math.min(1000 * Math.pow(2, retries), 30000)
        retries++
        setTimeout(connect, delay)
      }
    }

    ws.onerror = () => {
      ws?.close()
    }
  }

  connect()

  return {
    send(msg: Partial<MessageEnvelope>) {
      if (ws?.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(msg))
      }
    },
    close() {
      closed = true
      ws?.close()
    },
  }
}
