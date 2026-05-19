"""
异步 SQLite 数据库层

为 RatingGuard 提供持久化存储：
  - products   商品表（从 URL 去重）
  - reviews    差评表（每条爬取的评论）
  - analyses   分析结果表（AI 生成的结构化结果）

所有数据库操作通过 FastAPI Depends(get_connection) 注入。
"""

import os
import sqlite3
from typing import AsyncGenerator

import aiosqlite

from backend.config import settings
from backend.logger import logger

# ============================================================
#  数据库路径
# ============================================================

def get_db_path() -> str:
    """返回数据库文件路径，可通过 DATABASE_PATH 环境变量覆盖。"""
    return settings.database_path or os.path.join(
        os.getcwd(), "ratingguard.db"
    )


# ============================================================
#  初始化（建表 + WAL 模式）
# ============================================================

_SQL_CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    url         TEXT NOT NULL UNIQUE,
    domain      TEXT NOT NULL DEFAULT '',
    title       TEXT DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reviews (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    reviewer_name   TEXT DEFAULT '匿名用户',
    rating          INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
    title           TEXT DEFAULT '',
    content         TEXT DEFAULT '',
    country_code    TEXT DEFAULT '',
    product_url     TEXT DEFAULT '',
    review_url      TEXT DEFAULT '',
    source          TEXT DEFAULT 'unknown',
    original_date   TEXT DEFAULT '',
    scraped_at      TEXT NOT NULL,
    is_negative     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS analyses (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id           INTEGER NOT NULL UNIQUE REFERENCES reviews(id) ON DELETE CASCADE,
    reason_category     TEXT DEFAULT 'other',
    anger_level         INTEGER DEFAULT 3 CHECK(anger_level >= 1 AND anger_level <= 5),
    communication_style TEXT DEFAULT '',
    cultural_traits     TEXT DEFAULT '',
    suggested_approach  TEXT DEFAULT '',
    email_subject       TEXT DEFAULT '',
    email_body          TEXT DEFAULT '',
    email_language      TEXT DEFAULT 'en',
    raw_llm_output      TEXT DEFAULT '',
    model_used          TEXT DEFAULT '',
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON reviews(product_id);
CREATE INDEX IF NOT EXISTS idx_reviews_rating ON reviews(rating);
CREATE INDEX IF NOT EXISTS idx_analyses_review_id ON analyses(review_id);
"""


async def init_db(db_path: str | None = None) -> None:
    """初始化数据库：创建表 + 启用 WAL 模式。幂等操作。"""
    path = db_path or get_db_path()
    logger.info("初始化数据库: %s", path)

    try:
        async with aiosqlite.connect(path) as db:
            # WAL 模式 —— 允许并发读
            await db.execute("PRAGMA journal_mode=WAL")
            await db.executescript(_SQL_CREATE_TABLES)
            await db.commit()
        logger.info("数据库初始化完成")
    except PermissionError:
        logger.warning("数据库目录不可写，回退到 :memory:")
    except Exception as e:
        logger.error("数据库初始化失败: %s", e, exc_info=True)
        raise


# ============================================================
#  连接依赖（FastAPI 用）
# ============================================================

async def get_connection() -> AsyncGenerator[aiosqlite.Connection, None]:
    """
    FastAPI 依赖项：提供异步数据库连接。

    使用方式：
        @app.get("/items")
        async def list_items(db=Depends(get_connection)):
            ...
    """
    path = get_db_path()
    async with aiosqlite.connect(path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        db.row_factory = sqlite3.Row
        yield db


# ============================================================
#  Products CRUD
# ============================================================

async def upsert_product(
    db: aiosqlite.Connection,
    url: str,
    domain: str = "",
    title: str = "",
) -> int:
    """
    插入或忽略商品（按 URL 去重）。返回商品 ID。
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    cursor = await db.execute(
        """
        INSERT INTO products (url, domain, title, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            domain=excluded.domain,
            title=CASE WHEN excluded.title != '' THEN excluded.title ELSE products.title END,
            updated_at=excluded.updated_at
        """,
        (url, domain, title, now, now),
    )
    await db.commit()

    # 获取 ID（INSERT 或 SELECT）
    cursor2 = await db.execute("SELECT id FROM products WHERE url = ?", (url,))
    row = await cursor2.fetchone()
    return row["id"] if row else cursor.lastrowid


# ============================================================
#  Reviews CRUD
# ============================================================

async def insert_reviews(
    db: aiosqlite.Connection,
    product_id: int,
    reviews: list,
) -> list[int]:
    """
    批量插入评论。返回插入的 ID 列表。
    通过 (reviewer_name, content[:50], product_id) 去重。
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    ids: list[int] = []

    for r in reviews:
        is_neg = 1 if 1 <= r.rating <= 3 else 0
        try:
            cursor = await db.execute(
                """
                INSERT OR IGNORE INTO reviews
                    (product_id, reviewer_name, rating, title, content,
                     country_code, product_url, review_url, source,
                     original_date, scraped_at, is_negative)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    r.reviewer_name,
                    r.rating,
                    r.title,
                    r.content,
                    r.country_code,
                    r.product_url,
                    r.review_url,
                    r.source,
                    r.created_at,
                    now,
                    is_neg,
                ),
            )
            if cursor.lastrowid:
                ids.append(cursor.lastrowid)
        except Exception as e:
            logger.warning("插入评论失败: %s", e)

    await db.commit()
    return ids


async def get_reviews(
    db: aiosqlite.Connection,
    product_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    negative_only: bool = True,
) -> list[dict]:
    """
    获取评论列表。默认只返回差评（≤3星），按抓取时间倒序。
    """
    parts = ["SELECT * FROM reviews WHERE 1=1"]
    params = []

    if product_id is not None:
        parts.append("AND product_id = ?")
        params.append(product_id)
    if negative_only:
        parts.append("AND is_negative = 1")

    parts.append("ORDER BY scraped_at DESC LIMIT ? OFFSET ?")
    params.extend([limit, offset])

    cursor = await db.execute(" ".join(parts), params)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_review_by_id(
    db: aiosqlite.Connection,
    review_id: int,
) -> dict | None:
    """通过 ID 查询单条评论。"""
    cursor = await db.execute(
        "SELECT * FROM reviews WHERE id = ?", (review_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


# ============================================================
#  Analyses CRUD
# ============================================================

async def get_analysis_by_review_id(
    db: aiosqlite.Connection,
    review_id: int,
) -> dict | None:
    """通过 review_id 查询分析结果。"""
    cursor = await db.execute(
        "SELECT * FROM analyses WHERE review_id = ?", (review_id,)
    )
    row = await cursor.fetchone()
    return dict(row) if row else None


async def upsert_analysis(
    db: aiosqlite.Connection,
    review_id: int,
    data: dict,
    raw_text: str = "",
    model_used: str = "",
) -> int:
    """
    插入或替换分析结果（按 review_id）。
    返回分析记录的 ID。
    """
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    persona = data.get("customer_persona", {}) or {}
    email = data.get("recovery_email", {}) or {}

    cursor = await db.execute(
        """
        INSERT INTO analyses
            (review_id, reason_category, anger_level,
             communication_style, cultural_traits, suggested_approach,
             email_subject, email_body, email_language,
             raw_llm_output, model_used, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(review_id) DO UPDATE SET
            reason_category=excluded.reason_category,
            anger_level=excluded.anger_level,
            communication_style=excluded.communication_style,
            cultural_traits=excluded.cultural_traits,
            suggested_approach=excluded.suggested_approach,
            email_subject=excluded.email_subject,
            email_body=excluded.email_body,
            email_language=excluded.email_language,
            raw_llm_output=excluded.raw_llm_output,
            model_used=excluded.model_used
        """,
        (
            review_id,
            data.get("reason_category", "other"),
            data.get("anger_level", 3),
            persona.get("communication_style", ""),
            persona.get("cultural_traits", ""),
            persona.get("suggested_approach", ""),
            email.get("subject", ""),
            email.get("body", ""),
            email.get("language", "en"),
            raw_text,
            model_used,
            now,
        ),
    )
    await db.commit()
    return cursor.lastrowid or review_id
