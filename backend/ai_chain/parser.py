"""
AI 输出解析层

【职责】
  将 LLM 返回的原始文本解析为结构化数据。
  隔离 LLM 输出格式变化对业务代码的影响。

【场景】
  - JSON 字符串 → Python 字典
  - 自由文本提取关键字段
  - 数据校验与默认值填充
"""

import json
import re
from typing import Any, Optional


def parse_json_response(raw: str) -> dict[str, Any]:
    """
    从 LLM 输出中提取并解析 JSON。

    LLM 有时会在 JSON 前后添加说明文字、markdown 代码块标记等，
    此方法会智能提取 JSON 部分。

    参数：
        raw: LLM 返回的原始文本

    返回：
        解析后的字典；如果完全无法解析则返回空字典
    """
    if not raw:
        return {}

    # 1) 尝试直接解析
    text = raw.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2) 匹配 ```json ... ``` 代码块
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3) 匹配最外层的 { ... }
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    return {}


def extract_tone(raw: str) -> str:
    """
    从语气分类器输出中提取标准分类结果。

    参数：
        raw: LLM 返回的分类结果

    返回：
        标准化语气：frustrated / disappointed / neutral / constructive
    """
    valid = {"frustrated", "disappointed", "neutral", "constructive"}
    word = raw.strip().lower().strip(".")

    # 如果直接匹配成功，立即返回
    if word in valid:
        return word

    # 尝试从段落中提取关键词
    for v in valid:
        if v in word:
            return v

    return "neutral"


def validate_analysis(data: dict[str, Any]) -> dict[str, Any]:
    """
    校验并规范化差评分析结果，填入安全的默认值。

    参数：
        data: parse_json_response 的输出

    返回：
        包含所有必需字段的规范化字典
    """
    valid_sentiments = {"愤怒", "失望", "中性", "建设性", "frustrated", "disappointed", "neutral", "constructive"}
    sentiment = data.get("sentiment", "中性")
    if sentiment not in valid_sentiments:
        sentiment = "中性"

    urgency = str(data.get("urgency", "medium")).lower()
    if urgency not in ("high", "medium", "low"):
        urgency = "medium"

    return {
        "sentiment": sentiment,
        "key_issues": data.get("key_issues", []),
        "urgency": urgency,
        "customer_expectation": data.get("customer_expectation", ""),
        "is_actionable": bool(data.get("is_actionable", True)),
    }


def parse_review_analysis(raw: str) -> dict[str, Any]:
    """一站式：解析 JSON → 校验 → 返回规范化分析结果。"""
    data = parse_json_response(raw)
    return validate_analysis(data)
