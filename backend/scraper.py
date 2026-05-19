"""
Shopify 商品评论爬虫

【功能】
  采集 Shopify 店铺的商品评论，自动过滤出 ≤3 星的差评，输出结构化数据。

【抓取策略（按优先级）】
  1. JSON-LD 结构化数据  —— 最可靠，解析 <script type="application/ld+json"> 中的 Review 对象
  2. Judge.me 嵌入数据   —— 流行评论 App，解析其注入的 JSON 数据块
  3. 通用 HTML 容器解析  —— 兜底方案，扫描常见评论 CSS 类名

【使用示例】
  >>> from backend.scraper import ShopifyReviewScraper
  >>> scraper = ShopifyReviewScraper()
  >>> reviews = scraper.scrape_product(
  ...     "https://example.myshopify.com/products/some-product"
  ... )
  >>> len(reviews)  # 仅含 ≤3 星的评论
  7

【架构说明】
  - 全流程日志覆盖，每条评论的抽取路径均可追溯
  - 单条评论解析失败不影响整体采集
  - 所有可调参数（延迟、超时、UA）均通过 config 模块注入
"""

import json
import re
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, Field

from backend.config import settings
from backend.logger import logger
from backend.utils.helpers import get_random_ua, random_delay, retry_on_failure

# ============================================================
# 数据模型
# ============================================================

class Review(BaseModel):
    """统一评论数据模型 —— 所有解析策略最终都归约为此结构。"""

    reviewer_name: str = "匿名用户"
    rating: int = Field(..., ge=1, le=5)          # 1-5 星
    title: str = ""                                 # 评论标题（可能为空）
    content: str = ""                               # 评论文本正文
    country_code: str = ""                          # 国家码，如 US / CN
    product_url: str = ""                           # 所属商品页 URL
    review_url: str = ""                            # 该评论的独立 URL（如有）
    source: str = "unknown"                         # 解析来源标识
    created_at: str = ""                            # 评论时间（原始字符串）


# ============================================================
# 爬虫主类
# ============================================================

class ShopifyReviewScraper:
    """
    Shopify 商品评论爬虫。

    参数：
        session: 可选的 requests.Session，用于连接复用
    """

    def __init__(self, session: Optional[requests.Session] = None):
        self._session = session or requests.Session()
        # 如用户在 .env 中指定了 UA，则固定使用；否则从池中随机选取
        self._fixed_ua = settings.scraper_user_agent
        self._delay_min = settings.scraper_delay_min
        self._delay_max = settings.scraper_delay_max
        self._timeout = settings.scraper_timeout

        self.log = logger  # 各方法可直接用 self.log

    # ----------------------------------------------------------
    # 公共入口
    # ----------------------------------------------------------

    def scrape_product(self, product_url: str) -> list[Review]:
        """
        抓取指定商品页的全部评论，返回 ≤3 星的差评列表。

        参数：
            product_url: 商品页完整 URL（或其路径 `/products/handle`）

        返回：
            过滤后的 Review 列表，按评分升序排列（差评在前）
        """
        # 补全相对路径
        if product_url.startswith("/"):
            product_url = f"https://{settings.shopify_domain}{product_url}"

        self.log.info("开始抓取商品评论：%s", product_url)

        html = self._fetch_page(product_url)
        if not html:
            self.log.warning("页面抓取为空，跳过：%s", product_url)
            return []

        reviews = self._parse_reviews(html, product_url)

        # 过滤并排序
        negative = self._filter_negative(reviews)
        negative.sort(key=lambda r: r.rating)

        self.log.info(
            "抓取完成：共提取 %d 条评论，其中差评 %d 条",
            len(reviews),
            len(negative),
        )
        return negative

    # ----------------------------------------------------------
    # 页面抓取（含反爬策略）
    # ----------------------------------------------------------

    @retry_on_failure(max_retries=3, exceptions=(requests.RequestException,))
    def _fetch_page(self, url: str) -> str:
        """
        执行 HTTP GET 请求，带反爬保护。

        反爬策略：
          - 每次请求使用不同的 User-Agent
          - 请求间隔随机延时
          - 设置合理的超时时间
        """
        ua = self._fixed_ua or get_random_ua()
        headers = {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        }

        random_delay(self._delay_min, self._delay_max)
        self.log.debug("请求页面：%s (UA: %s…)", url, ua[:40])

        resp = self._session.get(
            url,
            headers=headers,
            timeout=self._timeout,
        )
        resp.raise_for_status()
        return resp.text

    # ----------------------------------------------------------
    # 多策略解析引擎
    # ----------------------------------------------------------

    def _parse_reviews(self, html: str, product_url: str) -> list[Review]:
        """
        多策略解析 HTML，提取评论列表。

        策略优先级：JSON-LD → Judge.me → 通用 HTML
        如某策略成功返回数据，则跳过后续策略。
        """
        soup = BeautifulSoup(html, "lxml")

        strategies = [
            ("jsonld", self._parse_json_ld),
            ("judgeme", self._parse_judgeme),
            ("html", self._parse_html_generic),
        ]

        for name, method in strategies:
            try:
                reviews = method(soup, product_url)
                if reviews:
                    self.log.info("策略 [%s] 成功提取 %d 条评论", name, len(reviews))
                    return reviews
            except Exception as exc:
                self.log.warning("策略 [%s] 解析异常：%s", name, exc, exc_info=True)

        self.log.warning("所有解析策略均未提取到评论：%s", product_url)
        return []

    # ----------------------------------------------------------
    # 策略 1：JSON-LD 结构化数据
    # ----------------------------------------------------------

    def _parse_json_ld(self, soup: BeautifulSoup, product_url: str) -> list[Review]:
        """
        解析 <script type="application/ld+json"> 中的 Product + Review 数据。

        这是最可靠的策略 —— 数据由 Shopify SEO 模块直接输出到静态 HTML 中，
        不需要执行 JavaScript。
        """
        reviews: list[Review] = []
        scripts = soup.find_all("script", type="application/ld+json")

        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue

            # 处理单个对象或数组
            items = data if isinstance(data, list) else [data]

            for item in items:
                if not isinstance(item, dict):
                    continue
                # 查找 @type 为 Product 的节点
                if item.get("@type") != "Product":
                    continue
                raw_reviews = item.get("review", [])
                if isinstance(raw_reviews, dict):
                    raw_reviews = [raw_reviews]

                for r in raw_reviews:
                    try:
                        review = self._parse_single_jsonld_review(r, product_url, script)
                        reviews.append(review)
                    except Exception as exc:
                        self.log.debug("跳过一条 JSON-LD 评论：%s", exc)
        return reviews

    def _parse_single_jsonld_review(
        self, raw: dict, product_url: str, script: Tag
    ) -> Review:
        """将单条 JSON-LD Review 对象转为统一模型。"""
        author = raw.get("author") or {}
        return Review(
            reviewer_name=author.get("name", "匿名用户"),
            rating=int(raw.get("reviewRating", {}).get("ratingValue", 0)),
            title="",
            content=raw.get("description", ""),
            country_code=self._extract_country_from_page(script),
            product_url=product_url,
            review_url=raw.get("url", ""),
            source="jsonld",
            created_at=raw.get("datePublished", ""),
        )

    # ----------------------------------------------------------
    # 策略 2：Judge.me 嵌入数据
    # ----------------------------------------------------------

    def _parse_judgeme(self, soup: BeautifulSoup, product_url: str) -> list[Review]:
        """
        解析 Judge.me 评论 App 注入的 JSON 数据。

        Judge.me 会在页面中嵌入两种格式之一：
          - <script class="judgeme-reviews-json" type="application/json">
          - 自定义 data-* 属性中的 JSON
        """
        reviews: list[Review] = []

        # 方式 A：查找 <script class="judgeme-reviews-json">
        scripts = soup.find_all(
            "script",
            class_="judgeme-reviews-json",
            type="application/json",
        )
        for script in scripts:
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
                raw_list = data if isinstance(data, list) else data.get("reviews", [])
                for r in raw_list:
                    try:
                        review = Review(
                            reviewer_name=r.get("reviewer", {}).get("name", "匿名用户"),
                            rating=int(r.get("rating", 0)),
                            title=r.get("title", ""),
                            content=r.get("body", ""),
                            country_code=r.get("reviewer", {}).get("country", ""),
                            product_url=product_url,
                            source="judgeme",
                            created_at=r.get("created_at", ""),
                        )
                        reviews.append(review)
                    except Exception as exc:
                        self.log.debug("跳过一条 Judge.me 评论：%s", exc)
            except json.JSONDecodeError:
                continue

        return reviews

    # ----------------------------------------------------------
    # 策略 3：通用 HTML 容器解析（兜底）
    # ----------------------------------------------------------

    def _parse_html_generic(self, soup: BeautifulSoup, product_url: str) -> list[Review]:
        """
        在页面上搜索常见的评论 HTML 容器，提取评论数据。

        支持的 CSS 选择器集合（覆盖 Yotpo / Stamped / 原生评论等）：
          - [data-review]           —— 自定义 data 属性
          - .review, .product-review —— 通用类名
          - .yotpo-review           —— Yotpo
          - .stamped-review         —— Stamped.io
        """
        selectors = [
            "[data-review]",
            ".review",
            ".product-review",
            ".yotpo-review",
            ".stamped-review",
        ]

        reviews: list[Review] = []
        seen = set()  # 短文本去重，避免相邻策略重复采集

        for selector in selectors:
            containers = soup.select(selector)
            for container in containers:
                try:
                    review = self._parse_single_html_review(container, product_url)
                    # 简单去重
                    dedup_key = f"{review.reviewer_name}|{review.content[:30]}"
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)
                    reviews.append(review)
                except Exception as exc:
                    self.log.debug("跳过一条 HTML 评论：%s", exc)

        return reviews

    def _parse_single_html_review(
        self, container: Tag, product_url: str
    ) -> Review:
        """从单个 HTML 评论容器中提取数据。"""
        # 评分：尝试多种常见模式
        rating = 0

        # 1) 查找 data-rating 属性
        rating_el = container.find("[data-rating]")
        if rating_el:
            rating = int(float(rating_el.get("data-rating", 0)))

        # 2) 查找包含 rating 或 star 类名的元素
        if not rating:
            star_el = container.find(class_=re.compile(r"(rating|star)", re.I))
            if star_el:
                text = re.search(r"(\d+)", star_el.get_text(strip=True))
                if text:
                    rating = int(text.group(1))

        # 3) 查找 aria-label 属性（无障碍标准）
        if not rating:
            aria_el = container.find("[aria-label*=star i]")
            if aria_el:
                text = re.search(r"(\d+)", aria_el.get("aria-label", ""))
                if text:
                    rating = int(text.group(1))

        # 用户名
        name_el = (
            container.find(class_=re.compile(r"(author|name|user)", re.I))
            or container.find("[data-reviewer-name]")
        )
        reviewer_name = name_el.get_text(strip=True) if name_el else "匿名用户"

        # 评论文本
        content_el = (
            container.find(class_=re.compile(r"(content|text|body|comment)", re.I))
            or container.find("p")
        )
        content = content_el.get_text(strip=True) if content_el else ""

        # 标题
        title_el = container.find(class_=re.compile(r"(title|subject)", re.I))
        title = title_el.get_text(strip=True) if title_el else ""

        return Review(
            reviewer_name=reviewer_name[:80],
            rating=min(rating, 5),
            title=title[:200],
            content=content[:5000],
            country_code="",
            product_url=product_url,
            source="html",
        )

    # ----------------------------------------------------------
    # 辅助方法
    # ----------------------------------------------------------

    def _filter_negative(self, reviews: list[Review]) -> list[Review]:
        """只保留评分 ≤3 的差评。"""
        return [r for r in reviews if 1 <= r.rating <= 3]

    @staticmethod
    def _extract_country_from_page(soup: Tag) -> str:
        """
        尝试从页面级信息中推断国家码。
        此为尽力而为的辅助方法，当前返回空字符串。
        后续可通过 IP 归属地或用户收货地址等数据源增强。
        """
        return ""

    def close(self) -> None:
        """释放 HTTP 会话资源。"""
        self._session.close()
