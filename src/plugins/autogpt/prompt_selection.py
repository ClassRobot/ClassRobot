from __future__ import annotations

import re
from collections.abc import Iterable

PROMPT_QUERY_STOP_TERMS = {
    "帮我",
    "请",
    "一下",
    "查一下",
    "查",
    "查询",
    "检索",
    "搜索",
    "找一下",
    "看看",
    "刚才",
    "之前",
    "最近",
    "聊天记录",
    "聊天",
    "群聊记录",
    "群聊",
    "记录",
    "文件夹",
    "文件",
    "文档",
    "目录",
    "资料",
    "里面",
    "里",
    "内容",
    "关于",
    "有关",
    "的",
    "什么",
    "哪些",
    "谁说过",
    "说过",
    "回顾",
    "总结",
    "现在",
    "可以",
    "有没有",
    "是否",
    "是什么",
    "怎么",
    "如何",
    "是否能",
    "能否",
    "告诉我",
    "帮忙",
    "一个",
}

_PUNCT_RE = re.compile(r"[，。！？!?；;：:、,.()\[\]{}<>《》\"'“”‘’`~～|/\\]+")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]{2,}")
_ALNUM_RE = re.compile(r"[a-z0-9][a-z0-9_-]+")


def normalize_prompt_query(text: str | None) -> str:
    """清理提示词检索时使用的自然语言查询。"""

    text = str(text or "").strip().lower()
    if not text:
        return ""
    text = _PUNCT_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def strip_prompt_stop_terms(text: str | None) -> str:
    """移除会干扰命令召回的高频虚词和提问套话。"""

    normalized = normalize_prompt_query(text)
    if not normalized:
        return ""
    compact = normalized
    for term in sorted(PROMPT_QUERY_STOP_TERMS, key=len, reverse=True):
        compact = compact.replace(term, " ")
    return re.sub(r"\s+", " ", compact).strip()


def extract_prompt_terms(text: str | None, *, max_terms: int = 24) -> list[str]:
    """从自然语言查询中提取适合做字符串匹配的短词。"""

    normalized = strip_prompt_stop_terms(text) or normalize_prompt_query(text)
    if not normalized:
        return []

    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        if not term or term in seen:
            return
        if term in PROMPT_QUERY_STOP_TERMS:
            return
        seen.add(term)
        terms.append(term)

    for part in normalized.split():
        if len(part) >= 2:
            add(part)

    compact = normalized.replace(" ", "")
    if compact:
        add(compact)

    for match in _ALNUM_RE.findall(normalized):
        add(match)

    for chunk in _CJK_RE.findall(compact):
        add(chunk)
        if len(terms) >= max_terms:
            break
        upper = min(len(chunk), 4)
        for width in range(2, upper + 1):
            if len(terms) >= max_terms:
                break
            for start in range(0, len(chunk) - width + 1):
                add(chunk[start : start + width])
                if len(terms) >= max_terms:
                    break
            if len(terms) >= max_terms:
                break
        if len(terms) >= max_terms:
            break

    return terms[:max_terms]


def score_prompt_relevance(
    query: str | None,
    *,
    names: Iterable[str] = (),
    texts: Iterable[str] = (),
) -> int:
    """计算某个提示词候选项与查询的相关性分数。"""

    normalized_query = normalize_prompt_query(query)
    if not normalized_query:
        return 0

    active_query = strip_prompt_stop_terms(normalized_query) or normalized_query
    compact_query = active_query.replace(" ", "")
    query_terms = extract_prompt_terms(active_query)
    score = 0

    name_texts = [normalize_prompt_query(name).replace(" ", "") for name in names if name]
    body_text = " ".join(normalize_prompt_query(text) for text in texts if text)
    compact_body = body_text.replace(" ", "")

    for name in name_texts:
        if not name:
            continue
        if name in compact_query:
            score += 160
        elif compact_query in name:
            score += 120

    for term in query_terms:
        if not term:
            continue
        if any(term in name for name in name_texts):
            score += 32 + min(len(term), 6) * 2
        if term in compact_body:
            score += 12 + min(len(term), 4)

    if compact_query and compact_query in compact_body:
        score += 80

    return score
