"""
LLM 驱动抽象接口层

【设计初衷】
  开源社区可能希望接入不同的 AI 模型（GPT-4o、DeepSeek、Claude 等），
  本模块定义统一的抽象基类，所有模型驱动都必须实现 LLMDriver 接口。

【接入新模型】
  只要实现 LLMDriver 的三个方法，即可无缝接入现有 Prompt 和解析逻辑：

      class MyModelDriver(LLMDriver):
          def chat(self, messages, **kwargs) -> str: ...
          def chat_async(self, messages, **kwargs) -> Awaitable[str]: ...
          @property
          def model_name(self) -> str: ...
"""

from abc import ABC, abstractmethod
from typing import Any


class LLMDriver(ABC):
    """大语言模型驱动抽象基类。"""

    @abstractmethod
    def chat(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """
        同步对话接口。

        参数：
            messages: OpenAI 格式的消息列表，如 [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."},
            ]
            **kwargs: 额外参数（temperature、max_tokens 等）

        返回：
            模型输出的文本字符串
        """

    @abstractmethod
    async def chat_async(self, messages: list[dict[str, str]], **kwargs: Any) -> str:
        """
        异步对话接口（用于高并发场景）。
        """

    @property
    @abstractmethod
    def model_name(self) -> str:
        """返回当前使用的模型名称，用于日志和溯源。"""
