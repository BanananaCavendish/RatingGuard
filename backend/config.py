"""
全局配置模块

【设计原则】
  所有环境变量 统一 在此模块读取、校验、缓存。
  业务代码不得直接引用 os.environ，只能通过此模块获取配置。

【使用方式】
  from backend.config import settings
  print(settings.shopify_domain)
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# === 自动加载 .env 文件（仅第一次导入时执行） ===
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """不可变配置对象，所有属性在初始化时从环境变量读取。"""

    # ---------- Shopify ----------
    shopify_domain: str = field(
        default_factory=lambda: os.getenv("SHOPIFY_STORE_DOMAIN", "")
    )
    shopify_api_version: str = field(
        default_factory=lambda: os.getenv("SHOPIFY_API_VERSION", "2024-01")
    )

    # ---------- 爬虫 ----------
    scraper_delay_min: float = field(
        default_factory=lambda: float(os.getenv("SCRAPER_REQUEST_DELAY_MIN", "2.0"))
    )
    scraper_delay_max: float = field(
        default_factory=lambda: float(os.getenv("SCRAPER_REQUEST_DELAY_MAX", "5.0"))
    )
    scraper_timeout: int = field(
        default_factory=lambda: int(os.getenv("SCRAPER_REQUEST_TIMEOUT", "30"))
    )
    scraper_user_agent: Optional[str] = field(
        default_factory=lambda: os.getenv("SCRAPER_USER_AGENT") or None
    )

    # ---------- LLM：OpenAI ----------
    openai_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY") or None
    )
    openai_model: str = field(
        default_factory=lambda: os.getenv("OPENAI_MODEL_NAME", "gpt-4o")
    )
    openai_base_url: str = field(
        default_factory=lambda: os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        )
    )

    # ---------- LLM：DeepSeek ----------
    deepseek_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY") or None
    )
    deepseek_model: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_MODEL_NAME", "deepseek-chat")
    )
    deepseek_base_url: str = field(
        default_factory=lambda: os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
        )
    )

    # ---------- 调度 ----------
    cron_schedule: str = field(
        default_factory=lambda: os.getenv("CRON_SCHEDULE", "0 9 * * 1-5")
    )
    timezone: str = field(
        default_factory=lambda: os.getenv("TIMEZONE", "Asia/Shanghai")
    )

    # ---------- 数据库 ----------
    database_path: str = field(
        default_factory=lambda: os.getenv("DATABASE_PATH", "ratingguard.db")
    )

    # ---------- CORS ----------
    cors_origins: str = field(
        default_factory=lambda: os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        )
    )

    # ---------- 日志 ----------
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )
    log_file: Optional[str] = field(
        default_factory=lambda: os.getenv("LOG_FILE") or None
    )

    # ---------- 校验（运行时不再崩溃，健康检查会报告未配置状态） ----------
    def __post_init__(self):
        """基础校验：仅日志警告，不再抛出异常。"""
        if not self.shopify_domain:
            import warnings
            warnings.warn(
                "SHOPIFY_STORE_DOMAIN 未配置 — 需通过 .env 设置或在请求中直接传入完整 URL"
            )


# === 全局单例 ===
settings = Settings()
