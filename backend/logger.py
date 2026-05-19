
"""
统一日志系统

提供预配置的 logger 实例，所有模块统一使用此 logger。
日志会同时输出到控制台和（可选的）日志文件。
"""

import sys
import logging
from pathlib import Path


from backend.config import settings


def setup_logger(name: str = "RatingGuard") -> logging.Logger:
    """
    创建并返回一个配置好的 Logger 实例。

    参数：
        name: Logger 名称，建议按模块命名，如 "RatingGuard.scraper"

    返回：
        配置完成的 logging.Logger 对象
    """
    logger = logging.getLogger(name)

    # 防止重复添加 handler
    if logger.handlers:
        return logger

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(level)
    logger.propagate = False  # 避免根日志重复输出

    # --- 格式化器：时间 | 级别 | 模块 | 消息 ---
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # --- 控制台 Handler ---
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # --- 文件 Handler（可选） ---
    if settings.log_file:
        log_path = Path(settings.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


# 全局默认 Logger —— 大多数模块直接导入使用
logger = setup_logger()
