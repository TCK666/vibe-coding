"""mock 供应商客户端：即指向本地 mock_llm(9002) 的 OpenAI 兼容客户端。

开发期默认 llm_provider=mock → get_llm_client() 返回本类；
接真模型时把 system_configs 的 llm.base_url/key/model 换成 SiliconFlow 即可。
"""
from .openai_client import OpenAICompatClient


class MockClient(OpenAICompatClient):
    """行为与 OpenAICompatClient 完全一致（mock_llm 说的就是 OpenAI 协议）。"""


def get_mock_client() -> MockClient:
    return MockClient()
