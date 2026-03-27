"""DeviceGateway - WebSocket 设备网关 Extension"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from loguru import logger

from core.interfaces.extension import BaseExtension

if TYPE_CHECKING:
    from fastapi import FastAPI
    from core.plugin_registry import PluginRegistry


class DeviceGateway(BaseExtension):
    """设备 WebSocket 网关，支持外部设备实时双向通信"""

    def __init__(self) -> None:
        self.device_manager = None
        self._registry = None

    async def on_load(self, app: "FastAPI", registry: "PluginRegistry") -> None:
        """注册路由和初始化设备管理器"""
        # 导入同目录模块
        gateway_dir = str(Path(__file__).parent)
        if gateway_dir not in sys.path:
            sys.path.insert(0, gateway_dir)

        from device_manager import DeviceManager, DeviceInfo  # noqa: E402
        from protocol import MessageEnvelope, MessageType  # noqa: E402

        self._registry = registry
        self.device_manager = DeviceManager(max_connections=100, heartbeat_interval=30)

        router = APIRouter(prefix="/api/devices", tags=["Devices"])
        device_mgr = self.device_manager

        @router.websocket("/ws")
        async def device_websocket(websocket: WebSocket):
            await websocket.accept()
            device_id = None

            try:
                raw = await websocket.receive_json()
                msg = MessageEnvelope(**raw)

                if msg.type != MessageType.DEVICE_REGISTER:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"error": "First message must be device_register"},
                    })
                    await websocket.close()
                    return

                device_id = msg.device_id or msg.payload.get("device_id", "")
                if not device_id:
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"error": "device_id is required"},
                    })
                    await websocket.close()
                    return

                device_info = await device_mgr.register(device_id, websocket, msg.payload)

                ack = MessageEnvelope(
                    type=MessageType.DEVICE_REGISTERED,
                    device_id=device_id,
                    payload={"device": device_info.model_dump(mode="json")},
                )
                await websocket.send_json(ack.model_dump(mode="json"))

                while True:
                    raw = await websocket.receive_json()
                    msg = MessageEnvelope(**raw)

                    if msg.type == MessageType.HEARTBEAT:
                        device_mgr.update_heartbeat(device_id)
                    elif msg.type == MessageType.DEVICE_RESULT:
                        logger.info(f"Device result from {device_id}: {msg.payload}")
                    elif msg.type == MessageType.CHAT:
                        logger.info(f"Chat from device {device_id}: {msg.payload}")

            except WebSocketDisconnect:
                logger.info(f"Device disconnected: {device_id}")
            except Exception as e:
                logger.error(f"WebSocket error for device {device_id}: {e}")
            finally:
                if device_id and device_mgr:
                    await device_mgr.unregister(device_id)

        @router.get("")
        async def list_devices():
            devices = device_mgr.list_devices()
            return {
                "success": True,
                "data": [d.model_dump(mode="json") for d in devices],
                "total": len(devices),
            }

        @router.get("/{device_id}/status")
        async def device_status(device_id: str):
            device = device_mgr.get_device(device_id)
            if not device:
                raise HTTPException(status_code=404, detail=f"Device '{device_id}' not found")
            return {"success": True, "data": device.model_dump(mode="json")}

        @router.post("/{device_id}/command")
        async def send_command(device_id: str, command: dict):
            if not device_mgr.is_connected(device_id):
                raise HTTPException(status_code=404, detail=f"Device '{device_id}' not connected")

            msg = MessageEnvelope(
                type=MessageType.DEVICE_COMMAND,
                device_id=device_id,
                payload=command,
                ack_required=True,
            )
            sent = await device_mgr.send_to_device(device_id, msg)
            return {"success": sent, "message_id": msg.id}

        app.include_router(router)
        logger.info("DeviceGateway: routes registered")

    async def on_unload(self) -> None:
        if self.device_manager:
            for device_id in list(self.device_manager._connections.keys()):
                await self.device_manager.unregister(device_id)
        logger.info("DeviceGateway: unloaded")
