"""
评论 + 分析结果 API 路由

GET /api/reviews         — 评论列表（分页，可按 product_id 过滤）
GET /api/reviews/{id}    — 单条评论详情（含关联分析结果）
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.database import (
    get_connection,
    get_reviews,
    get_review_by_id,
    get_analysis_by_review_id,
)
from backend.logger import logger

router = APIRouter(prefix="/api", tags=["reviews"])


@router.get("/reviews")
async def list_reviews(
    product_id: int | None = Query(None, description="按商品过滤"),
    limit: int = Query(50, ge=1, le=200, description="每页条数"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db=Depends(get_connection),
):
    """获取差评列表（默认只返回 ≤3 星的差评）。"""
    reviews = await get_reviews(
        db,
        product_id=product_id,
        limit=limit,
        offset=offset,
        negative_only=True,
    )
    return {
        "reviews": reviews,
        "total": len(reviews),
        "limit": limit,
        "offset": offset,
    }


@router.get("/reviews/{review_id}")
async def get_review_detail(
    review_id: int,
    db=Depends(get_connection),
):
    """获取单条评论详情 + 关联的 AI 分析结果。"""
    review = await get_review_by_id(db, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="评论不存在")

    analysis = await get_analysis_by_review_id(db, review_id)

    return {
        "review": review,
        "analysis": analysis,
    }
