"use client";

import { useState, useCallback } from "react";
import { fetchReviews, triggerScrape } from "@/lib/api";
import type { ProductReview } from "@/lib/api";

/* ═══════════════════════════════════════════════════════════════
   类型定义
   ═══════════════════════════════════════════════════════════════ */

interface UseReviewsReturn {
  /** 评论列表 */
  reviews: ProductReview[];
  /** 是否正在加载评论列表 */
  isLoading: boolean;
  /** 是否正在爬取 */
  isScraping: boolean;
  /** 错误消息 */
  error: string | null;
  /** 当前选中的评论 */
  selectedReview: ProductReview | null;
  /** 抓取指定商品 URL 的评论 */
  scrapeProduct: (url: string) => Promise<void>;
  /** 选中一条评论 */
  selectReview: (review: ProductReview | null) => void;
  /** 加载已有评论 */
  loadReviews: () => Promise<void>;
}

/* ═══════════════════════════════════════════════════════════════
   Hook
   ═══════════════════════════════════════════════════════════════ */

export function useReviews(): UseReviewsReturn {
  const [reviews, setReviews] = useState<ProductReview[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isScraping, setIsScraping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedReview, setSelectedReview] = useState<ProductReview | null>(null);

  /** 从后端加载评论列表 */
  const loadReviews = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await fetchReviews();
      setReviews(data.reviews);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setIsLoading(false);
    }
  }, []);

  /** 抓取指定商品 URL 的差评 */
  const scrapeProduct = useCallback(
    async (url: string) => {
      setIsScraping(true);
      setError(null);
      try {
        const result = await triggerScrape(url);
        if (result.reviews_count > 0) {
          // 抓取成功，重新加载评论列表
          await loadReviews();
        } else {
          setError(result.message || "未找到差评");
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : "抓取失败");
      } finally {
        setIsScraping(false);
      }
    },
    [loadReviews]
  );

  /** 选中一条评论 */
  const selectReview = useCallback((review: ProductReview | null) => {
    setSelectedReview(review);
  }, []);

  return {
    reviews,
    isLoading,
    isScraping,
    error,
    selectedReview,
    scrapeProduct,
    selectReview,
    loadReviews,
  };
}
