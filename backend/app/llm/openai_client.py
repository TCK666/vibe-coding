"""OpenAI 兼容流式客户端：mock_llm 与 SiliconFlow 等真模型共用同一协议。

切换供应商只改 base_url / api_key / model（后续进 system_configs 热更新）。
"""
import json
from typing import AsyncIterator

import httpx

from ..core.config import get_settings
from .base import DeltaText, Finish, ToolCall


class OpenAICompatClient:
    def __init__(
        self, base_url: str | None = None, api_key: str | None = None, model: str | None = None
    ):
        s = get_settings()
        self.base_url = (base_url or s.llm_base_url).rstrip("/")
        self.api_key = api_key or s.llm_api_key
        self.model = model or s.llm_model

    async def stream_chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> AsyncIterator[DeltaText | ToolCall | Finish]:
        body: dict = {"model": self.model, "messages": messages, "stream": True}
        if tools:
            body["tools"] = tools
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=body,
                headers={"Authorization": f"Bearer {self.api_key}"},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    if payload == "[DONE]":
                        break
                    chunk = json.loads(payload)
                    choices = chunk.get("choices") or [{}]
                    choice = choices[0] if choices else {}
                    delta = choice.get("delta") or {}
                    if delta.get("content"):
                        yield DeltaText(delta["content"])
                    for tc in delta.get("tool_calls") or []:
                        fn = tc.get("function") or {}
                        yield ToolCall(
                            call_id=tc.get("id") or "",
                            name=fn.get("name") or "",
                            arguments=fn.get("arguments") or "",
                        )
                    if choice.get("finish_reason"):
                        yield Finish(choice["finish_reason"])


def get_llm_client() -> OpenAICompatClient:
    """mock 与 openai 供应商都走 OpenAI 兼容协议，差别仅在与配置。"""
    return OpenAICompatClient()
