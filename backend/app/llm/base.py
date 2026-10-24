"""LLM 适配层协议：mock 与真实模型(OpenAI 兼容)共用同一事件流形状。

任务引擎（里程碑5/6）只依赖这三个事件，切换模型供应商无需改动编排逻辑。
"""
from dataclasses import dataclass
from typing import AsyncIterator, Protocol


@dataclass
class DeltaText:
    """增量文本。"""
    text: str


@dataclass
class ToolCall:
    """工具调用请求（arguments 为 JSON 分片，由调用方按 call_id 累积）。"""
    call_id: str
    name: str
    arguments: str


@dataclass
class Finish:
    """本轮回合结束。finish_reason: stop=产出最终文本 | tool_calls=等待工具结果。"""
    finish_reason: str


LLMEvent = DeltaText | ToolCall | Finish


class LLMClient(Protocol):
    async def stream_chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[LLMEvent]: ...
