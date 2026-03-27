import { ref, onUnmounted } from 'vue'
import { createDeviceSocket } from '../api/devices'
import type { Device, MessageEnvelope } from '../types'

export function useWebSocket() {
  const devices = ref<Device[]>([])
  const connected = ref(false)
  const deviceMessages = ref<MessageEnvelope[]>([])

  const socket = createDeviceSocket(
    (envelope) => {
      switch (envelope.type) {
        case 'device_registered': {
          const existing = devices.value.find((d) => d.device_id === envelope.device_id)
          if (!existing) {
            devices.value = [
              ...devices.value,
              {
                device_id: envelope.device_id ?? '',
                name: envelope.payload.name ?? 'Unknown',
                device_type: envelope.payload.device_type ?? 'unknown',
                status: 'online',
                last_heartbeat: envelope.timestamp,
                capabilities: envelope.payload.capabilities ?? [],
              },
            ]
          }
          break
        }
        case 'heartbeat': {
          devices.value = devices.value.map((d) =>
            d.device_id === envelope.device_id
              ? { ...d, status: envelope.payload.status ?? 'online', last_heartbeat: envelope.timestamp }
              : d
          )
          break
        }
        case 'device_result':
        case 'chat':
        case 'error':
          deviceMessages.value = [...deviceMessages.value, envelope]
          break
      }
    },
    (state) => {
      connected.value = state
    }
  )

  function sendCommand(deviceId: string, action: string, data: string) {
    socket.send({
      type: 'device_command',
      device_id: deviceId,
      payload: { action, data },
    })
  }

  onUnmounted(() => {
    socket.close()
  })

  return { devices, connected, deviceMessages, sendCommand }
}
