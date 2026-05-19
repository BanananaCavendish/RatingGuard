"""
Prompt 模板管理

【设计原则】
  - 所有 Prompt 集中在此文件，不散落在业务代码中
  - 社区贡献者可在此直接修改提示词策略，无需了解爬虫 / 前端逻辑
  - 支持模板变量注入（Python str.format）

【策略分类】
  - REVIEW_ANALYSIS:   差评原因分析（语气、关键问题识别）
  - REPLY_GENERATION:  个性化挽回回复生成
  - TONE_CLASSIFIER:   评论语气分类（愤怒/失望/中性/建设性）
"""

# ============================================================
# 差评分析
# ============================================================

REVIEW_ANALYSIS_SYSTEM = """你是一位资深的跨境电商客户体验分析师。
你的任务是从商品评论中提取关键信息，帮助卖家理解客户的真实反馈。

请分析以下差评（评分 ≤3），输出 JSON 格式的分析结果：

{{
    "sentiment": "愤怒 / 失望 / 中性 / 建设性",
    "key_issues": ["问题1", "问题2", ...],
    "urgency": "high / medium / low",
    "customer_expectation": "客户期望的解决方案",
    "is_actionable": true/false
}}

注意：
  - 保持客观，不要过度推断
  - 如果评论是非英文，先翻译为英文再分析
  - 只输出 JSON，不要其他文字"""

REVIEW_ANALYSIS_USER = """请分析以下商品评论：

评分：{rating}/5
标题：{title}
内容：{content}
国家/地区：{country_code}"""

# ============================================================
# 挽回回复生成
# ============================================================

REPLY_GENERATION_SYSTEM = """你是一位跨境电商客服专家，擅长撰写个性化的差评挽回回复。

回复要求：
  1. 语气：诚恳、共情、专业，绝不模板化
  2. 结构：感谢反馈 → 共情理解 → 解释/道歉 → 解决方案 → 邀请沟通
  3. 根据客户的国家码调整文化表达（如 US 倾向简洁直接，JP 倾向委婉礼貌）
  4. 长度控制在 80-150 词之间
  5. 不得承诺无法兑现的补偿

请直接输出回复文本，不要加前缀。"""

REPLY_GENERATION_USER = """请为以下差评撰写挽回回复：

评论标题：{title}
评论内容：{content}
客户评分：{rating}/5
客户国家：{country_code}
分析结果：{analysis_summary}"""

# ============================================================
# 语气分类
# ============================================================

TONE_CLASSIFIER_SYSTEM = """你是一个评论语气分类器。
请将以下评论分类为以下四类之一：

  frustrated      — 愤怒、挫折感强，需要紧急处理
  disappointed    — 失望但理性，适合用解释和补偿挽回
  neutral         — 客观陈述问题，关注解决方案
  constructive    — 给出具体改进建议，是忠实客户

只输出一个单词（小写）。"""

TONE_CLASSIFIER_USER = """评分：{rating}/5
评论：{content}"""

# ============================================================
# 工具函数
# ============================================================

def build_analysis_messages(rating: int, title: str, content: str, country_code: str) -> list[dict]:
    """构造差评分析所需的 messages 列表。"""
    user_prompt = REVIEW_ANALYSIS_USER.format(
        rating=rating,
        title=title or "(无标题)",
        content=content,
        country_code=country_code or "unknown",
    )
    return [
        {"role": "system", "content": REVIEW_ANALYSIS_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]


def build_reply_messages(
    rating: int,
    title: str,
    content: str,
    country_code: str,
    analysis_summary: str,
) -> list[dict]:
    """构造回复生成所需的 messages 列表。"""
    user_prompt = REPLY_GENERATION_USER.format(
        title=title or "(无标题)",
        content=content,
        rating=rating,
        country_code=country_code or "unknown",
        analysis_summary=analysis_summary,
    )
    return [
        {"role": "system", "content": REPLY_GENERATION_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]


def build_tone_classifier_messages(rating: int, content: str) -> list[dict]:
    """构造语气分类所需的 messages 列表。"""
    user_prompt = TONE_CLASSIFIER_USER.format(rating=rating, content=content)
    return [
        {"role": "system", "content": TONE_CLASSIFIER_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]
