"""
工具函数集

包含爬虫通用辅助方法：UA 池、频率控制、重试装饰器等。
"""

import time
import random
import functools
from typing import Callable, Any

from backend.logger import logger

# ============================================================
# User-Agent 池 —— 定期更新以保持真实性
# ============================================================
USER_AGENTS = [
    # Chrome 120+ on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome 120+ on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Edge 120+ on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    # Firefox 121 on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari 17 on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]


def get_random_ua() -> str:
    """从内置池中随机返回一个 User-Agent 字符串。"""
    return random.choice(USER_AGENTS)


def random_delay(min_sec: float = 2.0, max_sec: float = 5.0) -> None:
    """
    随机休眠一段时间，用于请求间频率控制。

    参数：
        min_sec: 最小休眠秒数
        max_sec: 最大休眠秒数
    """
    delay = random.uniform(min_sec, max_sec)
    logger.debug(f"频率控制：休眠 {delay:.1f}s")
    time.sleep(delay)


def retry_on_failure(
    max_retries: int = 3,
    base_delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    重试装饰器 —— 请求失败时自动重试，指数退避。

    参数：
        max_retries: 最大重试次数（默认 3）
        base_delay:  首次重试前的基础等待秒数（默认 1s）
        backoff:     每次重试延迟的倍数（默认 2x）
        exceptions:  捕获的异常类型元组（默认所有 Exception）

    使用示例：
        @retry_on_failure(max_retries=3)
        def fetch_data(url):
            return requests.get(url, timeout=10)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt < max_retries:
                        wait = base_delay * (backoff ** (attempt - 1))
                        logger.warning(
                            "%s 第 %d/%d 次失败：%s，%0.1fs 后重试...",
                            func.__name__,
                            attempt,
                            max_retries,
                            e,
                            wait,
                        )
                        time.sleep(wait)
            logger.error(
                "%s 已重试 %d 次，全部失败：%s",
                func.__name__,
                max_retries,
                last_exc,
            )
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
