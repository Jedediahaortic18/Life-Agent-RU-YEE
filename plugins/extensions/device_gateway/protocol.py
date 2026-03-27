"""消息协议定义"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MessageType:
    CHAT = "chat"
    HEARTBEAT = "heartbeat"
    DEVICE_COMMAND = "device_command"
    DEVICE_RESULT = "device_result"
    DEVICE_REGISTER = "device_register"
    DEVICE_REGISTERED = "device_registered"
    ERROR = "error"


class MessageEnvelope(BaseModel):
    """消息信封"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = "chat"
    payload: dict = {}
    timestamp: datetime = Field(default_factory=datetime.now)
    device_id: str | None = None
    ack_required: bool = False
