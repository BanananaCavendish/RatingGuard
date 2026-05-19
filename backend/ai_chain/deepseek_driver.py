"""
DeepSeek 驱动实现

使用 HTTPX 直接调用 DeepSeek Chat API（兼容 OpenAI 格式）。
需在 .env 中配置 DEEPSEEK_API_KEY。
"""

from typing import Any

import httpx

from backend.config import settings
from backend.logger import logger
from backend.ai_chain.base import LLMDriver


class DeepSeekDriver(LLMDriver):
    """
    DeepSeek 模型驱动。

    注意：DeepSeek 的 API 兼容 OpenAI 的消息格式，
    因此也可以直接用 OpenAIDriver + 修改 base_url 来实现。
    这里单独实现以展示「驱动可替换」的架构设计。
    """

    def __init__(self):
        if not settings.deepseek_api_key:
            raise ValueError(
                "DEEPSEEK_API_KEY 未配置。请在 .env 中设置 DEEPSEEK_API_KEY。"
            )
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_base_url.rstrip("/")
        self._model = settings.deepseek_model
        self.log = logger

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """同步调用 DeepSeek Chat API。"""
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": kwargs.pop("model", self._model),
            "messages": messages,
            "temperature": kwargs.pop("temperature", 0.7),
            **kwargs,
        }

        self.log.debug("DeepSeek chat 请求：model=%s", payload["model"])

        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        result = data["choices"][0]["message"]["content"]
        return result

    async def chat_async(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> str:
        """异步调用 DeepSeek Chat API。"""
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": kwargs.pop("model", self._model),
            "messages": messages,
            "temperature": kwargs.pop("temperature", 0.7),
            **kwargs,
        }

        self.log.debug("DeepSeek async chat 请求：model=%s", payload["model"])

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        result = data["choices"][0]["message"]["content"]
        return result

    @property
    def model_name(self) -> str:
        return self._model
