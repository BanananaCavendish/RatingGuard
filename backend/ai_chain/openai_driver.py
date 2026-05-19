"""
OpenAI / GPT-4o 驱动实现

使用 OpenAI Python SDK 调用 GPT-4o 等模型。
需在 .env 中配置 OPENAI_API_KEY。
"""

from typing import Any

from openai import OpenAI

from backend.config import settings
from backend.logger import logger
from backend.ai_chain.base import LLMDriver


class OpenAIDriver(LLMDriver):
    """OpenAI 兼容接口的模型驱动（适用于 GPT-4o / GPT-4-turbo 等）。"""

    def __init__(self):
        if not settings.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY 未配置。请在 .env 中设置 OPENAI_API_KEY。"
            )
        self._client = OpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
        self._model = settings.openai_model
        self.log = logger

    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """同步调用 OpenAI Chat Completion API。"""
        params = {
            "model": kwargs.pop("model", self._model),
            "messages": messages,
            "temperature": kwargs.pop("temperature", 0.7),
            **kwargs,
        }
        self.log.debug("OpenAI chat 请求：model=%s, messages=%d 条", params["model"], len(messages))

        response = self._client.chat.completions.create(**params)

        result = response.choices[0].message.content or ""
        self.log.debug("OpenAI 响应：%d tokens", response.usage.total_tokens if response.usage else 0)
        return result

    async def chat_async(
        self, messages: list[dict[str, str]], **kwargs: Any
    ) -> str:
        """异步调用 OpenAI Chat Completion API。"""
        params = {
            "model": kwargs.pop("model", self._model),
            "messages": messages,
            "temperature": kwargs.pop("temperature", 0.7),
            **kwargs,
        }
        self.log.debug("OpenAI async chat 请求：model=%s", params["model"])

        response = await self._client.chat.completions.create(**params)

        result = response.choices[0].message.content or ""
        return result

    @property
    def model_name(self) -> str:
        return self._model
