"""BaseTool - Agent Tool 基类"""
from __future__ import annotations

import asyncio
import uuid
from abc import ABC, abstractmethod
from typing import Any, Callable

from pydantic import BaseModel


class ToolResult(BaseModel):
    """Tool 执行结果"""
    success: bool
    data: Any = None
    error: str | None = None


# 进度回调类型: (tool_name, step_description) -> None
ProgressCallback = Callable[[str, str], None]


# ── 用户内联输入：全局等待队列 ──────────────────────
# key = request_id, value = asyncio.Future[Any]
_pending_inputs: dict[str, asyncio.Future[Any]] = {}


def resolve_user_input(request_id: str, value: Any) -> bool:
    """外部（API 端点）调用：将用户的回复投递给等待中的工具。返回是否找到对应请求。"""
    future = _pending_inputs.pop(request_id, None)
    if future and not future.done():
        # API handler 和工具在同一个 asyncio 事件循环中
        future.set_result(value)
        return True
    return False


class BaseTool(ABC):
    """Agent Tool 基类，基于 Pydantic schema"""

    _progress_callback: ProgressCallback | None = None
    _sse_queue: Any = None  # asyncio.Queue[SSEEvent]，工具可推送任意 SSE 事件

    def set_progress_callback(self, callback: ProgressCallback | None) -> None:
        """设置进度回调，工具执行期间可通过 _report_progress 报告步骤"""
        self._progress_callback = callback

    def set_sse_queue(self, queue: Any) -> None:
        """注入 SSE 事件队列，工具可通过 _emit_sse 推送任意事件"""
        self._sse_queue = queue

    def _report_progress(self, step: str) -> None:
        """报告当前执行步骤（子类在关键操作处调用）"""
        if self._progress_callback:
            self._progress_callback(self.name, step)

    def _emit_sse(self, event: str, data: dict) -> None:
        """推送任意 SSE 事件（工具执行期间实时发送到前端）"""
        if self._sse_queue is not None:
            from core.interfaces.agent import SSEEvent
            self._sse_queue.put_nowait(SSEEvent(event=event, data=data))

    async def _request_user_input(
        self,
        prompt: str,
        options: list[dict[str, str]] | None = None,
        input_type: str = "select",
        timeout: float = 300.0,
    ) -> Any:
        """请求用户内联输入。暂停工具执行，等待前端回传。

        Args:
            prompt: 提示语，如「请选择要加购的商品」
            options: 选项列表 [{"label": "显示文字", "value": "回传值"}, ...]
            input_type: "select"（按钮选择）| "text"（文字输入）
            timeout: 超时时间（秒），默认 300s，超时后自动清理 Future
        Returns:
            用户提交的值（字符串）
        Raises:
            TimeoutError: 用户在超时时间内未响应
        """
        request_id = uuid.uuid4().hex[:10]
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        _pending_inputs[request_id] = future

        self._emit_sse("input_request", {
            "request_id": request_id,
            "tool": self.name,
            "prompt": prompt,
            "options": options or [],
            "input_type": input_type,
        })

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"用户输入超时（{int(timeout)}s），已自动跳过")
        finally:
            _pending_inputs.pop(request_id, None)

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool 名称"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool 描述，供 LLM 理解用途"""
        ...

    @property
    @abstractmethod
    def parameters_schema(self) -> dict:
        """JSON Schema 格式的参数定义"""
        ...

    @abstractmethod
    async def execute(self, **params: Any) -> ToolResult:
        """执行 Tool"""
        ...

    def to_function_tool(self) -> dict:
        """转换为 OpenAI function calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
