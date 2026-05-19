/* ═══════════════════════════════════════════════════════════════
   API 客户端 —— 所有后端通信的统一入口
   ═══════════════════════════════════════════════════════════════ */

const BASE_URL = "/api";

// ================================================================
//  类型定义
// ================================================================

export interface ProductReview {
  id: number;
  product_id: number;
  reviewer_name: string;
  rating: number;
  title: string;
  content: string;
  country_code: string;
  product_url: string;
  source: string;
  original_date: string;
  scraped_at: string;
  is_negative: boolean;
}

export interface ReviewAnalysis {
  id: number;
  review_id: number;
  reason_category: string;
  anger_level: number;
  communication_style: string;
  cultural_traits: string;
  suggested_approach: string;
  email_subject: string;
  email_body: string;
  email_language: string;
  raw_llm_output: string;
  model_used: string;
  created_at: string;
}

export interface ScrapeResult {
  status: string;
  product_id: number | null;
  reviews_count: number;
  message: string;
}

export interface ReviewsResponse {
  reviews: ProductReview[];
  total: number;
  limit: number;
  offset: number;
}

export interface ReviewDetailResponse {
  review: ProductReview;
  analysis: ReviewAnalysis | null;
}

// ================================================================
//  API 方法
// ================================================================

export async function triggerScrape(productUrl: string): Promise<ScrapeResult> {
  const res = await fetch(`${BASE_URL}/scrape`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ product_url: productUrl }),
  });
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText);
    throw new Error(`抓取失败 (${res.status}): ${err}`);
  }
  return res.json();
}

export async function fetchReviews(productId?: number): Promise<ReviewsResponse> {
  const params = new URLSearchParams();
  if (productId != null) params.set("product_id", String(productId));
  params.set("limit", "100");
  const res = await fetch(`${BASE_URL}/reviews?${params}`);
  if (!res.ok) throw new Error(`获取评论失败: ${res.statusText}`);
  return res.json();
}

export async function fetchReviewDetail(reviewId: number): Promise<ReviewDetailResponse> {
  const res = await fetch(`${BASE_URL}/reviews/${reviewId}`);
  if (!res.ok) throw new Error(`获取评论详情失败: ${res.statusText}`);
  return res.json();
}
