"""设备管理器"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import WebSocket
from loguru import logger
from pydantic import BaseModel


class MessageType:
    CHAT = "chat"
    HEARTBEAT = "heartbeat"
    DEVICE_COMMAND = "device_command"
    DEVICE_RESULT = "device_result"
    DEVICE_REGISTER = "device_register"
    DEVICE_REGISTERED = "device_registered"
    ERROR = "error"


class DeviceInfo(BaseModel):
    """设备信息"""
    device_id: str
    name: str = ""
    device_type: str = "unknown"
    connected_at: datetime = datetime.now()
    last_heartbeat: datetime = datetime.now()
    metadata: dict = {}


class DeviceManager:
    """管理所有已连接的设备"""

    def __init__(self, max_connections: int = 100, heartbeat_interval: int = 30):
        self._connections: dict[str, WebSocket] = {}
        self._devices: dict[str, DeviceInfo] = {}
        self._max_connections = max_connections
        self._heartbeat_interval = heartbeat_interval
        self._message_queue: dict[str, list] = {}

    @property
    def connected_count(self) -> int:
        return len(self._connections)

    def is_connected(self, device_id: str) -> bool:
        return device_id in self._connections

    async def register(self, device_id: str, websocket: WebSocket, info: dict | None = None) -> DeviceInfo:
        if self.connected_count >= self._max_connections:
            raise ConnectionError(f"Max connections ({self._max_connections}) reached")

        device_info = DeviceInfo(
            device_id=device_id,
            name=info.get("name", device_id) if info else device_id,
            device_type=info.get("device_type", "unknown") if info else "unknown",
            metadata=info.get("metadata", {}) if info else {},
        )

        self._connections[device_id] = websocket
        self._devices[device_id] = device_info
        logger.info(f"Device registered: {device_id} ({device_info.device_type})")

        if device_id in self._message_queue:
            for msg in self._message_queue.pop(device_id):
                await self.send_to_device(device_id, msg)

        return device_info

    async def unregister(self, device_id: str) -> None:
        self._connections.pop(device_id, None)
        self._devices.pop(device_id, None)
        logger.info(f"Device unregistered: {device_id}")

    async def send_to_device(self, device_id: str, message: Any) -> bool:
        ws = self._connections.get(device_id)
        if not ws:
            if device_id not in self._message_queue:
                self._message_queue[device_id] = []
            self._message_queue[device_id].append(message)
            return False

        try:
            if hasattr(message, "model_dump"):
                await ws.send_json(message.model_dump(mode="json"))
            else:
                await ws.send_json(message)
            return True
        except Exception as e:
            logger.warning(f"Failed to send to device {device_id}: {e}")
            await self.unregister(device_id)
            return False

    async def broadcast(self, message: Any, exclude: str | None = None) -> int:
        sent = 0
        for device_id in list(self._connections.keys()):
            if device_id != exclude:
                if await self.send_to_device(device_id, message):
                    sent += 1
        return sent

    def update_heartbeat(self, device_id: str) -> None:
        if device_id in self._devices:
            self._devices[device_id].last_heartbeat = datetime.now()

    def list_devices(self) -> list[DeviceInfo]:
        return list(self._devices.values())

    def get_device(self, device_id: str) -> DeviceInfo | None:
        return self._devices.get(device_id)
