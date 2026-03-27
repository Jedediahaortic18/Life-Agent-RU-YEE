"""SSE 流式响应工具"""
from __future__ import annotations

import json
from typing import AsyncIterator

from starlette.responses import StreamingResponse

from core.interfaces.agent import SSEEvent


async def sse_generator(events: AsyncIterator[SSEEvent]) -> AsyncIterator[str]:
    """将 SSEEvent 转换为 SSE 文本流"""
    async for event in events:
        data = json.dumps(event.data, ensure_ascii=False)
        yield f"event: {event.event}\ndata: {data}\n\n"


def sse_response(events: AsyncIterator[SSEEvent]) -> StreamingResponse:
    """创建 SSE StreamingResponse"""
    return StreamingResponse(
        sse_generator(events),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
