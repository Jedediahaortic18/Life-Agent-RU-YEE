"""BaseStreamAgent - 流式 Agent 基类"""
from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator

from pydantic import BaseModel

from core.interfaces.tool import BaseTool


class SSEEvent(BaseModel):
    """SSE 事件"""
    event: str  # text_delta | tool_call | tool_output | done | error
    data: dict[str, Any]


class AgentResult(BaseModel):
    """Agent 执行结果（同步模式）"""
    session_id: str
    agent: str
    result: dict[str, Any]


class BaseStreamAgent(ABC):
    """流式 Agent 基类，支持 SSE 事件流和 Tool 调用"""

    def __init__(self, context_bus: Any, config: dict | None = None):
        self.context_bus = context_bus
        self.config = config or {}

    @abstractmethod
    def get_system_prompt(self, context: dict) -> str:
        ...

    @abstractmethod
    def get_tools(self) -> list[BaseTool]:
        ...

    @abstractmethod
    def get_model(self) -> str:
        ...

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        ...

    @property
    def agent_name(self) -> str:
        return self.__class__.__name__

    async def run(
        self,
        user_message: str,
        session_id: str | None = None,
        conversation_history: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[SSEEvent]:
        import litellm

        session_id = session_id or str(uuid.uuid4())
        history = conversation_history or []
        context = {
            "session_id": session_id,
            "user_message": user_message,
            "conversation_history": history,
        }
        system_prompt = self.get_system_prompt(context)
        tools = self.get_tools()

        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
        ]
        # 注入对话历史
        for turn in history:
            role = turn.get("role")
            content = turn.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_message})

        tool_schemas = [t.to_function_tool() for t in tools] or None

        try:
            max_tool_rounds = getattr(self, 'max_tool_rounds', 5)
            _round = 0

            while max_tool_rounds <= 0 or _round <= max_tool_rounds:
                _round += 1
                response = await litellm.acompletion(
                    model=self.get_model(),
                    messages=messages,
                    tools=tool_schemas,
                    stream=True,
                )

                round_content = ""
                tool_calls_buffer: dict[int, dict] = {}
                has_tool_calls = False

                async for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue

                    if delta.content:
                        round_content += delta.content
                        yield SSEEvent(
                            event="text_delta",
                            data={"content": delta.content},
                        )

                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_buffer:
                                tool_calls_buffer[idx] = {
                                    "id": tc.id or "",
                                    "name": "",
                                    "arguments": "",
                                }
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_buffer[idx]["name"] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls_buffer[idx]["arguments"] += tc.function.arguments

                    if chunk.choices[0].finish_reason == "tool_calls":
                        has_tool_calls = True

                # 没有工具调用 → 本轮结束
                if not has_tool_calls:
                    break

                # 执行工具调用
                assistant_tool_calls = []
                tool_results_for_messages = []

                for _idx, tc_data in sorted(tool_calls_buffer.items()):
                    tool_name = tc_data["name"]
                    _tc_id = tc_data["id"]
                    try:
                        params = json.loads(tc_data["arguments"]) if tc_data["arguments"] else {}
                    except json.JSONDecodeError:
                        params = {}

                    yield SSEEvent(
                        event="tool_call",
                        data={"tool": tool_name, "params": params, "tool_call_id": _tc_id},
                    )

                    assistant_tool_calls.append({
                        "id": _tc_id,
                        "type": "function",
                        "function": {"name": tool_name, "arguments": tc_data["arguments"]},
                    })

                    tool = next((t for t in tools if t.name == tool_name), None)
                    if tool:
                        # 注入进度回调 + SSE 队列：工具执行期间实时推送事件
                        import asyncio as _asyncio
                        _progress_q: _asyncio.Queue[SSEEvent] = _asyncio.Queue()

                        def _on_progress(t_name: str, step: str, *, _id: str = _tc_id) -> None:
                            _progress_q.put_nowait(SSEEvent(
                                event="tool_progress",
                                data={"tool": t_name, "step": step, "tool_call_id": _id},
                            ))

                        tool.set_progress_callback(_on_progress)
                        tool.set_sse_queue(_progress_q)
                        # 始终注入 session_id，工具可选择使用
                        params["session_id"] = session_id
                        # 后台执行工具，同时实时 yield 进度事件和 SSE 事件
                        _tool_task = _asyncio.create_task(tool.execute(**params))
                        while not _tool_task.done():
                            try:
                                _pe = await _asyncio.wait_for(_progress_q.get(), timeout=0.3)
                                yield _pe
                            except _asyncio.TimeoutError:
                                continue
                        tool_result = await _tool_task
                        tool.set_progress_callback(None)
                        tool.set_sse_queue(None)
                        # drain 剩余事件
                        while not _progress_q.empty():
                            yield _progress_q.get_nowait()
                        result_dump = tool_result.model_dump()
                        result_json = json.dumps(result_dump, ensure_ascii=False)
                        # 流式发送 tool_output
                        chunk_size = 80
                        for ci in range(0, len(result_json), chunk_size):
                            yield SSEEvent(
                                event="tool_output_delta",
                                data={"tool": tool_name, "chunk": result_json[ci:ci + chunk_size], "tool_call_id": _tc_id},
                            )
                        yield SSEEvent(
                            event="tool_output_done",
                            data={"tool": tool_name, "result": result_dump, "tool_call_id": _tc_id},
                        )
                        tool_results_for_messages.append({
                            "role": "tool",
                            "tool_call_id": tc_data["id"],
                            "content": result_json,
                        })

                        if self.context_bus and tool_result.success:
                            await self.context_bus.write(
                                self.agent_name, tool_name, tool_result.data
                            )
                    else:
                        error_result = {"success": False, "data": None, "error": f"Tool not found: {tool_name}"}
                        yield SSEEvent(
                            event="tool_output_done",
                            data={"tool": tool_name, "result": error_result},
                        )
                        tool_results_for_messages.append({
                            "role": "tool",
                            "tool_call_id": tc_data["id"],
                            "content": json.dumps({"error": f"Tool not found: {tool_name}"}),
                        })

                # 将工具结果追加到 messages，进入下一轮
                messages.append({
                    "role": "assistant",
                    "content": round_content or None,
                    "tool_calls": assistant_tool_calls,
                })
                messages.extend(tool_results_for_messages)

                yield SSEEvent(
                    event="thinking",
                    data={"status": "根据结果生成回复中..."},
                )

            yield SSEEvent(
                event="done",
                data={"session_id": session_id, "agent": self.agent_name},
            )

        except Exception as e:
            yield SSEEvent(
                event="error",
                data={"error": str(e), "suggestion": "请检查 LLM provider 配置"},
            )

    async def run_sync(self, user_message: str, session_id: str | None = None) -> AgentResult:
        session_id = session_id or str(uuid.uuid4())
        collected: dict[str, Any] = {"content": "", "tool_results": []}

        async for event in self.run(user_message, session_id):
            if event.event == "text_delta":
                collected["content"] += event.data.get("content", "")
            elif event.event == "tool_output_done":
                collected["tool_results"].append(event.data)
            elif event.event == "error":
                return AgentResult(
                    session_id=session_id,
                    agent=self.agent_name,
                    result={"error": event.data.get("error", "Unknown error")},
                )

        return AgentResult(
            session_id=session_id,
            agent=self.agent_name,
            result={
                "summary": collected["content"],
                "tool_results": collected["tool_results"],
            },
        )
